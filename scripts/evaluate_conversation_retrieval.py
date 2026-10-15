"""Evaluate follow-up retrieval with synthetic history and real local policy embeddings."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from app.config import Settings
from app.database import Database
from app.providers.embeddings import OnnxMiniLmEmbeddingProvider
from app.providers.vector_store import ChromaVectorStore
from app.services.conversation_context import (
    EXPANDED_CONTEXT_TOP_K,
    build_retrieval_question,
    needs_expanded_context,
    resolve_question_context,
)
from app.services.ingestion import IngestionService
from app.services.prompt_builder import HistoryMessage
from app.services.retrieval import RetrievalService


POLICY_DIRECTORY = Path("data/sampleset_policies/sampleset_policies")
CASE_PATH = Path("evaluation/conversation_retrieval_cases.json")
CONVERSATION_ID = "conversation-retrieval-evaluation"


def main() -> None:
    """Check expected PDF/pages per turn in temporary storage, without hosted model calls.

    Synthetic assistant replies test context resolution, not generated answer quality.
    """

    cases = json.loads(CASE_PATH.read_text(encoding="utf-8"))
    policy_paths = sorted(POLICY_DIRECTORY.glob("*.pdf"))
    if len(policy_paths) != 8:
        raise RuntimeError(f"Expected 8 policy PDFs, found {len(policy_paths)}.")

    with TemporaryDirectory(prefix="adc-conversation-evaluation-") as temp_directory:
        temp_path = Path(temp_directory)
        settings = Settings(
            database_url=f"sqlite:///{temp_path / 'evaluation.db'}",
            vector_store_path=str(temp_path / "chroma"),
        )
        database = Database(settings.database_url)
        database.create_tables()
        embeddings = OnnxMiniLmEmbeddingProvider(
            cache_path=settings.model_cache_path,
            model_name=settings.embedding_model_name,
            dimension=settings.embedding_dimension,
        )
        vectors = ChromaVectorStore(
            path=settings.vector_store_path,
            collection_name=settings.vector_collection_name,
        )
        ingestion = IngestionService(
            database=database,
            embedding_provider=embeddings,
            vector_store=vectors,
            settings=settings,
        )
        retrieval = RetrievalService(
            embedding_provider=embeddings,
            vector_store=vectors,
            default_top_k=settings.retrieval_top_k,
        )

        for policy_path in policy_paths:
            ingestion.ingest(
                conversation_id=CONVERSATION_ID,
                filename=policy_path.name,
                content=policy_path.read_bytes(),
            )

        passed = 0
        total = 0
        for case in cases:
            history: list[HistoryMessage] = []
            print(f"\nConversation: {case['id']}")
            for turn_number, turn in enumerate(case["turns"], start=1):
                retrieval_question = build_retrieval_question(
                    question=turn["question"],
                    history=history,
                )
                resolved_question = resolve_question_context(
                    question=turn["question"],
                    history=history,
                )
                expanded_context = needs_expanded_context(resolved_question)
                results = retrieval.retrieve(
                    conversation_id=CONVERSATION_ID,
                    question=retrieval_question,
                    top_k=EXPANDED_CONTEXT_TOP_K if expanded_context else None,
                    include_document_context=True,
                    expand_selected_pages=expanded_context,
                )
                expected = {
                    (item["filename"], item["page"])
                    for item in turn["expected_evidence"]
                }
                actual = {
                    (result.filename, result.page_number) for result in results
                }
                turn_passed = expected <= actual
                passed += int(turn_passed)
                total += 1
                status = "PASS" if turn_passed else "MISS"
                print(f"  [{status}] turn {turn_number}: {turn['question']}")
                if not turn_passed:
                    print(f"    missing: {sorted(expected - actual)}")
                for rank, result in enumerate(results, start=1):
                    print(
                        f"    {rank}. {result.filename} p.{result.page_number} "
                        f"chunk={result.chunk_index} similarity={result.similarity:.3f}"
                    )

                history.extend(
                    [
                        HistoryMessage(role="user", content=turn["question"]),
                        HistoryMessage(
                            role="assistant",
                            content="The preceding turn was answered from retrieved context.",
                        ),
                    ]
                )
                history = history[-5:]

        database.close()
        print(f"\nConversation retrieval summary: {passed}/{total} turns passed")
        if passed != total:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
