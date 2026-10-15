"""Check hybrid ranking, scoped Chroma reads and bounded page-context enrichment."""

import json
import re
from dataclasses import replace
from pathlib import Path

import pytest

from app.providers.vector_store import ChromaVectorStore, RetrievedChunk
from app.services.chunker import TextChunk
from app.services.retrieval import RetrievalService, _exact_query_terms
from tests.conftest import FakeEmbeddingProvider, FakeVectorStore


def test_selected_lower_ranked_page_is_completed_before_header_expansion():
    """A third selected rule must not lose its condition to unrelated header chunks."""

    vectors = FakeVectorStore()
    hits = [
        RetrievedChunk(
            id=f"hit-{index}", text=f"Selected rule {index}.",
            conversation_id="conversation-a", document_id=f"document-{index}",
            filename=f"manual-{index}.pdf", page_number=2, chunk_index=0,
            distance=index / 10, similarity=1 - index / 10,
        )
        for index in range(3)
    ]
    vectors.search_results = hits
    companions = [
        replace(hit, id=f"mate-{index}", text=f"Companion condition {index}.", chunk_index=1)
        for index, hit in enumerate(hits)
    ]
    headers = [
        replace(hit, id=f"header-{index}-{part}", page_number=1,
                chunk_index=part, text=f"Header content {index}-{part}.")
        for index, hit in enumerate(hits) for part in range(6)
    ]
    vectors.document_start_results = [chunk for chunk in headers if chunk.chunk_index == 0]
    vectors.page_chunk_results = hits + companions + headers
    retrieval = RetrievalService(
        embedding_provider=FakeEmbeddingProvider(), vector_store=vectors, default_top_k=3,
    )

    results = retrieval.retrieve(
        conversation_id="conversation-a", question="Which conditions apply?",
        include_document_context=True,
    )

    for index, hit in enumerate(hits):
        page = next(c for c in results if c.document_id == hit.document_id and c.page_number == 2)
        assert f"Selected rule {index}." in page.text
        assert f"Companion condition {index}." in page.text
    # Header starts may be appended separately; page companions still share the
    # original twelve-addition budget, not a larger context window.
    assert sum(c.text.count("Header content") for c in results) <= 12


def test_retrieval_service_embeds_question_and_applies_limit() -> None:
    embeddings = FakeEmbeddingProvider()
    vectors = FakeVectorStore()
    vectors.search_results = [
        RetrievedChunk(
            id=f"chunk-{index}",
            text="evidence",
            conversation_id="conversation-a",
            document_id="document-a",
            filename="policy.pdf",
            page_number=1,
            chunk_index=index,
            distance=0.1,
            similarity=0.9,
        )
        for index in range(3)
    ]
    service = RetrievalService(
        embedding_provider=embeddings,
        vector_store=vectors,
        default_top_k=2,
    )

    results = service.retrieve(
        conversation_id=" conversation-a ",
        question=" What is the policy? ",
    )

    assert [result.id for result in results] == ["chunk-0", "chunk-1"]


def test_hybrid_reranking_promotes_exact_keyword_evidence() -> None:
    embeddings = FakeEmbeddingProvider()
    vectors = FakeVectorStore()
    semantic = RetrievedChunk(
        id="semantic-only",
        text="General security guidance",
        conversation_id="conversation-a",
        document_id="document-a",
        filename="general.pdf",
        page_number=1,
        chunk_index=0,
        distance=0.05,
        similarity=0.95,
    )
    exact = RetrievedChunk(
        id="exact-policy-id",
        text="Policy ID IT-SEC-004",
        conversation_id="conversation-a",
        document_id="document-b",
        filename="security.pdf",
        page_number=1,
        chunk_index=0,
        distance=0.2,
        similarity=0.8,
    )
    vectors.search_results = [semantic, exact]
    vectors.keyword_search_results = [replace(exact, keyword_score=0.9)]
    service = RetrievalService(
        embedding_provider=embeddings,
        vector_store=vectors,
        default_top_k=1,
    )

    results = service.retrieve(
        conversation_id="conversation-a",
        question="What does IT-SEC-004 require?",
    )

    assert [result.id for result in results] == ["exact-policy-id"]
    assert results[0].rerank_score > 0


def test_exact_term_detection_supports_unfamiliar_currencies() -> None:
    terms = _exact_query_terms(
        "Compare DKK 375, EUR 410.50, £200 and policy OBS-SAFE-1."
    )

    assert {"dkk 375", "eur 410.50", "£200", "obs-safe-1"} <= terms


def test_retrieval_includes_start_context_for_selected_documents() -> None:
    embeddings = FakeEmbeddingProvider()
    vectors = FakeVectorStore()
    vectors.search_results = [
        RetrievedChunk(
            id=f"rule-{index}",
            text="Relevant rule",
            conversation_id="conversation-a",
            document_id=f"document-{index}",
            filename=f"policy-{index}.pdf",
            page_number=2,
            chunk_index=1,
            distance=0.1 + index / 10,
            similarity=0.9 - index / 10,
        )
        for index in range(3)
    ]
    vectors.document_start_results = [
        RetrievedChunk(
            id=f"header-{index}",
            text=f"Policy {index} version and effective date",
            conversation_id="conversation-a",
            document_id=f"document-{index}",
            filename=f"policy-{index}.pdf",
            page_number=1,
            chunk_index=0,
            distance=1.0,
            similarity=0.0,
        )
        for index in range(3)
    ]
    service = RetrievalService(
        embedding_provider=embeddings,
        vector_store=vectors,
        default_top_k=3,
    )

    results = service.retrieve(
        conversation_id="conversation-a",
        question="Which policy applies?",
        include_document_context=True,
    )

    assert [result.id for result in results] == [
        "rule-0",
        "rule-1",
        "rule-2",
        "header-0",
        "header-1",
        "header-2",
    ]


def test_retrieval_adds_missing_chunks_from_strongest_pages() -> None:
    embeddings = FakeEmbeddingProvider()
    vectors = FakeVectorStore()
    current_exception = RetrievedChunk(
        id="current-exception",
        text="Conditional high-cost exception",
        conversation_id="conversation-a",
        document_id="current-policy",
        filename="reimbursement_2025.pdf",
        page_number=2,
        chunk_index=1,
        distance=0.1,
        similarity=0.9,
    )
    old_standard = RetrievedChunk(
        id="old-standard",
        text="Historical standard limit",
        conversation_id="conversation-a",
        document_id="old-policy",
        filename="travel_expenses_2022.pdf",
        page_number=2,
        chunk_index=0,
        distance=0.2,
        similarity=0.8,
    )
    current_standard = RetrievedChunk(
        id="current-standard",
        text="Current standard limit",
        conversation_id="conversation-a",
        document_id="current-policy",
        filename="reimbursement_2025.pdf",
        page_number=2,
        chunk_index=0,
        distance=1.0,
        similarity=0.0,
    )
    old_exception = RetrievedChunk(
        id="old-exception",
        text="Historical exception",
        conversation_id="conversation-a",
        document_id="old-policy",
        filename="travel_expenses_2022.pdf",
        page_number=2,
        chunk_index=1,
        distance=1.0,
        similarity=0.0,
    )
    vectors.search_results = [current_exception, old_standard]
    vectors.page_chunk_results = [current_standard, current_exception, old_standard, old_exception]
    service = RetrievalService(
        embedding_provider=embeddings,
        vector_store=vectors,
        default_top_k=2,
    )

    results = service.retrieve(
        conversation_id="conversation-a",
        question="To Asia?",
        include_document_context=True,
    )

    assert [result.id for result in results] == [
        "current-exception",
        "old-standard",
    ]
    assert "Current standard limit" in results[0].text
    assert "Conditional high-cost exception" in results[0].text
    assert "Historical exception" in results[1].text


@pytest.mark.parametrize(
    ("conversation_id", "question", "top_k"),
    [
        ("", "question", None),
        ("conversation", " ", None),
        ("conversation", "question", 0),
        ("conversation", "question", 21),
    ],
)
def test_retrieval_rejects_invalid_inputs(
    conversation_id: str,
    question: str,
    top_k: int | None,
) -> None:
    service = RetrievalService(
        embedding_provider=FakeEmbeddingProvider(),
        vector_store=FakeVectorStore(),
    )

    with pytest.raises(ValueError):
        service.retrieve(
            conversation_id=conversation_id,
            question=question,
            top_k=top_k,
        )


def _chunk(chunk_id: str, conversation_id: str, text: str) -> TextChunk:
    return TextChunk(
        id=chunk_id,
        document_id=f"document-{chunk_id}",
        conversation_id=conversation_id,
        filename=f"{chunk_id}.pdf",
        page_number=1,
        chunk_index=0,
        text=text,
    )


def test_chroma_search_ranks_by_cosine_and_isolates_conversations(
    tmp_path: Path,
) -> None:
    vectors = ChromaVectorStore(
        path=str(tmp_path / "chroma"),
        collection_name="retrieval_test",
    )
    chunks = [
        _chunk("best", "conversation-a", "best evidence"),
        _chunk("other", "conversation-a", "other evidence"),
        _chunk("leak", "conversation-b", "must not be returned"),
    ]
    vectors.add_chunks(
        chunks,
        [[1.0, 0.0], [0.0, 1.0], [1.0, 0.0]],
        embedding_model="test/model",
        chunking_version="test-v1",
    )

    results = vectors.search(
        [1.0, 0.0],
        conversation_id="conversation-a",
        embedding_model="test/model",
        top_k=5,
    )

    assert [result.id for result in results] == ["best", "other"]
    assert all(result.conversation_id == "conversation-a" for result in results)
    assert results[0].distance == pytest.approx(0.0)
    assert results[0].similarity == pytest.approx(1.0)


def test_chroma_keyword_search_finds_exact_policy_terms_and_isolates_chat(
    tmp_path: Path,
) -> None:
    vectors = ChromaVectorStore(
        path=str(tmp_path / "chroma"),
        collection_name="keyword_test",
    )
    chunks = [
        _chunk("exact", "conversation-a", "Policy ID IT-SEC-004 covers Restricted data."),
        _chunk("generic", "conversation-a", "General information handling guidance."),
        _chunk("leak", "conversation-b", "IT-SEC-004 must not leak."),
    ]
    vectors.add_chunks(
        chunks,
        [[1.0, 0.0], [0.0, 1.0], [1.0, 0.0]],
        embedding_model="test/model",
        chunking_version="test-v1",
    )

    results = vectors.keyword_search(
        "IT-SEC-004 Restricted",
        conversation_id="conversation-a",
        embedding_model="test/model",
        top_k=3,
    )

    assert [result.id for result in results] == ["exact"]
    assert results[0].keyword_score > 0


def test_chroma_search_filters_embedding_model(tmp_path: Path) -> None:
    vectors = ChromaVectorStore(
        path=str(tmp_path / "chroma"),
        collection_name="model_filter_test",
    )
    vectors.add_chunks(
        [_chunk("old", "conversation-a", "old model")],
        [[1.0, 0.0]],
        embedding_model="old/model",
        chunking_version="test-v1",
    )

    results = vectors.search(
        [1.0, 0.0],
        conversation_id="conversation-a",
        embedding_model="new/model",
        top_k=5,
    )

    assert results == []


def test_chroma_search_returns_only_best_chunk_per_document_page(
    tmp_path: Path,
) -> None:
    vectors = ChromaVectorStore(
        path=str(tmp_path / "chroma"),
        collection_name="page_diversity_test",
    )
    chunks = [
        TextChunk(
            id="page-1-best",
            document_id="document-a",
            conversation_id="conversation-a",
            filename="policy.pdf",
            page_number=1,
            chunk_index=0,
            text="best page one chunk",
        ),
        TextChunk(
            id="page-1-duplicate",
            document_id="document-a",
            conversation_id="conversation-a",
            filename="policy.pdf",
            page_number=1,
            chunk_index=1,
            text="another page one chunk",
        ),
        TextChunk(
            id="page-2",
            document_id="document-a",
            conversation_id="conversation-a",
            filename="policy.pdf",
            page_number=2,
            chunk_index=0,
            text="page two chunk",
        ),
    ]
    vectors.add_chunks(
        chunks,
        [[1.0, 0.0], [0.9, 0.1], [0.8, 0.2]],
        embedding_model="test/model",
        chunking_version="test-v1",
    )

    results = vectors.search(
        [1.0, 0.0],
        conversation_id="conversation-a",
        embedding_model="test/model",
        top_k=2,
    )

    assert [result.id for result in results] == ["page-1-best", "page-2"]


def test_chroma_search_uses_remaining_budget_for_same_page_evidence(
    tmp_path: Path,
) -> None:
    vectors = ChromaVectorStore(
        path=str(tmp_path / "chroma"),
        collection_name="page_fill_test",
    )
    chunks = [
        TextChunk(
            id="exception",
            document_id="document-a",
            conversation_id="conversation-a",
            filename="policy.pdf",
            page_number=2,
            chunk_index=1,
            text="Asia-Pacific high-cost city exception",
        ),
        TextChunk(
            id="standard-limit",
            document_id="document-a",
            conversation_id="conversation-a",
            filename="policy.pdf",
            page_number=2,
            chunk_index=0,
            text="Asia-Pacific standard lodging limit",
        ),
        TextChunk(
            id="overview",
            document_id="document-a",
            conversation_id="conversation-a",
            filename="policy.pdf",
            page_number=1,
            chunk_index=0,
            text="Policy overview",
        ),
    ]
    vectors.add_chunks(
        chunks,
        [[1.0, 0.0], [0.9, 0.1], [0.8, 0.2]],
        embedding_model="test/model",
        chunking_version="test-v1",
    )

    results = vectors.search(
        [1.0, 0.0],
        conversation_id="conversation-a",
        embedding_model="test/model",
        top_k=5,
    )

    assert [result.id for result in results] == [
        "exception",
        "standard-limit",
        "overview",
    ]


def test_chroma_returns_all_chunks_for_requested_page(tmp_path: Path) -> None:
    vectors = ChromaVectorStore(
        path=str(tmp_path / "chroma"),
        collection_name="page_context_test",
    )
    chunks = [
        TextChunk(
            id="page-2-chunk-1",
            document_id="document-a",
            conversation_id="conversation-a",
            filename="policy.pdf",
            page_number=2,
            chunk_index=1,
            text="Exception",
        ),
        TextChunk(
            id="page-2-chunk-0",
            document_id="document-a",
            conversation_id="conversation-a",
            filename="policy.pdf",
            page_number=2,
            chunk_index=0,
            text="Standard rule",
        ),
        TextChunk(
            id="page-1-chunk-0",
            document_id="document-a",
            conversation_id="conversation-a",
            filename="policy.pdf",
            page_number=1,
            chunk_index=0,
            text="Header",
        ),
    ]
    vectors.add_chunks(
        chunks,
        [[1.0, 0.0], [0.9, 0.1], [0.8, 0.2]],
        embedding_model="test/model",
        chunking_version="test-v1",
    )

    results = vectors.get_page_chunks(
        conversation_id="conversation-a",
        embedding_model="test/model",
        page_keys=[("document-a", 2)],
    )

    assert [result.id for result in results] == [
        "page-2-chunk-0",
        "page-2-chunk-1",
    ]


def test_retrieval_evaluation_set_is_well_formed() -> None:
    cases = json.loads(
        Path("evaluation/retrieval_cases.json").read_text(encoding="utf-8")
    )

    assert len(cases) >= 10
    assert len({case["id"] for case in cases}) == len(cases)
    assert {"direct_fact", "table", "cross_page", "conflict", "missing_answer"} <= {
        case["category"] for case in cases
    }
    assert all(case["question"].strip() for case in cases)
    assert all(
        evidence["filename"].endswith(".pdf") and evidence["page"] >= 1
        for case in cases
        for evidence in case["expected_evidence"]
    )


def test_natural_answer_evaluation_set_is_well_formed() -> None:
    cases = json.loads(
        Path("evaluation/natural_answer_cases.json").read_text(encoding="utf-8")
    )

    assert len(cases) >= 20
    assert len({case["id"] for case in cases}) == len(cases)
    assert all(case["question"].strip().endswith("?") for case in cases)
    assert all(len(case["question"].split()) <= 12 for case in cases)
    assert all(case["rubric"].strip() for case in cases)
    assert all(case["statuses"] for case in cases)
    assert all(
        status in {"answered", "insufficient_context", "conflicting_sources"}
        for case in cases
        for status in case["statuses"]
    )
    assert all(
        filename.endswith(".pdf")
        and all(phrase.strip() for phrase in phrases)
        for case in cases
        for filename, phrases in case["evidence"].items()
    )
    for case in cases:
        for pattern in case["answer_patterns"] + case.get("forbidden_patterns", []):
            re.compile(pattern)
