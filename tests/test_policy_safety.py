"""Deterministic orchestration safeguards; live answer quality has a separate eval."""

from dataclasses import replace

import pytest
from sqlalchemy import select

from app.models import Message
from app.providers.llm import InvalidModelResponseError, ModelAnswer
from app.services.chat import (
    build_retrieval_question,
    is_policy_comparison,
    needs_expanded_context,
)
from app.services.prompt_builder import HistoryMessage
from app.services.retrieval import RetrievalService
from tests.conftest import FakeEmbeddingProvider, FakeVectorStore
from tests.test_chat import evidence, request_with_setup, seed_conversation


def test_empty_evidence_abstains_without_calling_provider(application):
    response = request_with_setup(application, lambda: seed_conversation(application))

    assert response.status_code == 200
    assert response.json()["status"] == "insufficient_context"
    assert response.json()["citations"] == []
    assert application.state.fake_chat_provider.calls == []
    with application.state.database.session_factory() as session:
        assert len(list(session.scalars(select(Message)))) == 2


def test_complete_new_topic_does_not_inherit_previous_question():
    history = [
        HistoryMessage(role="user", content="What is the Europe lodging limit?"),
        HistoryMessage(role="assistant", content="A fabricated amount of EUR 9999."),
    ]
    query = build_retrieval_question(
        question="Can I keep Restricted data on a local hard drive?", history=history,
    )
    assert "Europe" not in query
    assert "9999" not in query
    assert "Restricted" in query


def test_correction_reuses_question_but_never_assistant_facts():
    query = build_retrieval_question(
        question="Are you sure? Zurich is in Europe.",
        history=[
            HistoryMessage(role="user", content="What is the Zurich lodging limit?"),
            HistoryMessage(role="assistant", content="Zurich is in Asia and the cap is 9999."),
        ],
    )
    assert "Zurich lodging" in query
    assert "9999" not in query
    assert "Zurich is in Asia" not in query


@pytest.mark.parametrize("question", [
    "Review inconsistencies across all uploaded policies.",
    "Do any documents contradict each other?",
    "Compare the workplace and temporary home office policies.",
    "Compare temporary home office guidelines and the current workplace policy.",
])
def test_comparisons_receive_wider_evidence(question):
    assert is_policy_comparison(question)


def test_ordinary_question_keeps_normal_evidence_budget():
    assert not is_policy_comparison("How much can I spend in Zurich?")


@pytest.mark.parametrize("question", [
    "List every expense explicitly identified as non-reimbursable.",
    "Is encrypted USB definitely approved under the current security policy?",
    "Does the old memo still remain valid under this policy?",
])
def test_exhaustive_and_authority_questions_receive_expanded_context(question):
    assert needs_expanded_context(question)


def test_broad_comparison_reaches_evidence_beyond_first_five(application):
    def setup():
        seed_conversation(application)
        application.state.fake_vector_store.search_results = [
            replace(evidence(index), text=f"Distinct policy evidence {index}")
            for index in range(1, 9)
        ]

    response = request_with_setup(
        application, setup, "Review conflicts across all uploaded policies.",
    )
    assert response.status_code == 200
    sent_context = application.state.fake_chat_provider.calls[0][-1].content
    assert "Distinct policy evidence 8" in sent_context


def test_comparison_page_enrichment_recovers_lower_ranked_document_evidence():
    vectors = FakeVectorStore()
    vectors.search_results = [evidence(index) for index in range(1, 7)]
    vectors.page_chunk_results = [
        replace(evidence(6), id="stipend-chunk", chunk_index=1, text="Monthly stipend USD 50"),
    ]
    service = RetrievalService(
        embedding_provider=FakeEmbeddingProvider(), vector_store=vectors,
    )
    results = service.retrieve(
        conversation_id="conversation-a", question="Compare all policies",
        top_k=20, include_document_context=True, expand_selected_pages=True,
    )
    assert any(chunk.id == "stipend-chunk" for chunk in results)
    assert len({chunk.id for chunk in results}) == len(results)


def test_valid_citations_are_numbered_by_first_use_without_another_model_call(application):
    def setup():
        seed_conversation(application)
        application.state.fake_vector_store.search_results = [
            evidence(1, filename="old.pdf"), evidence(2, filename="current.pdf"),
        ]
        application.state.fake_chat_provider.answer = ModelAnswer(
            status="answered", answer="Current rule [S2]; historical rule [S1].",
            source_ids=["S1", "S2"],
        )
    response = request_with_setup(application, setup)
    assert response.status_code == 200
    assert response.json()["answer"] == "Current rule [1]; historical rule [2]."
    assert [item["filename"] for item in response.json()["citations"]] == ["current.pdf", "old.pdf"]
    assert len(application.state.fake_chat_provider.calls) == 1


@pytest.mark.parametrize("answer,ids", [
    ("Unknown [S999].", ["S999"]),
    ("Public numeric marker [1].", ["S1"]),
    ("Grouped unknown [S1, S999].", ["S1"]),
    ("Malformed group [S1, nonsense].", ["S1"]),
    ("Public numeric group [1, 2].", ["S1"]),
])
def test_citation_normalization_never_accepts_invalid_mappings(application, answer, ids):
    def setup():
        seed_conversation(application)
        application.state.fake_vector_store.search_results = [evidence(1), evidence(2)]
        application.state.fake_chat_provider.answer = ModelAnswer(
            status="answered", answer=answer, source_ids=ids,
        )
    response = request_with_setup(application, setup)
    assert response.status_code == 502
    with application.state.database.session_factory() as session:
        assert list(session.scalars(select(Message))) == []


@pytest.mark.parametrize("ids", [["S2"], [], ["S1", "S1"]])
def test_inline_markers_canonicalize_redundant_source_id_metadata(application, ids):
    def setup():
        seed_conversation(application)
        application.state.fake_vector_store.search_results = [evidence(1)]
        application.state.fake_chat_provider.answer = ModelAnswer(
            status="answered", answer="Supported answer [S1].", source_ids=ids,
        )

    response = request_with_setup(application, setup)

    assert response.status_code == 200
    assert response.json()["answer"] == "Supported answer [1]."
    assert len(application.state.fake_chat_provider.calls) == 1


def test_grouped_citations_are_validated_and_mapped(application):
    def setup():
        seed_conversation(application)
        application.state.fake_vector_store.search_results = [evidence(1), evidence(2)]
        application.state.fake_chat_provider.answer = ModelAnswer(
            status="conflicting_sources", answer="Ambiguous wording [S2, S1].",
            source_ids=["S1", "S2"],
        )
    response = request_with_setup(application, setup)
    assert response.status_code == 200
    assert response.json()["answer"] == "Ambiguous wording [1] [2]."
    assert len(response.json()["citations"]) == 2


def test_invalid_json_refusal_gets_one_structured_retry(application):
    calls = []

    def generate(messages):
        calls.append(messages)
        if len(calls) == 1:
            raise InvalidModelResponseError("Gemini returned an invalid answer structure.")
        return ModelAnswer(
            status="insufficient_context", answer="This policy is not in the sources.",
            source_ids=[],
        )

    def setup():
        seed_conversation(application)
        application.state.fake_vector_store.search_results = [evidence(1)]
        application.state.fake_chat_provider.generate = generate

    response = request_with_setup(application, setup, "Invent a holiday allowance.")
    assert response.status_code == 200
    assert response.json()["status"] == "insufficient_context"
    assert len(calls) == 2


def test_second_bounded_correction_can_recover(application):
    def setup():
        seed_conversation(application)
        application.state.fake_vector_store.search_results = [evidence(1)]
        application.state.fake_chat_provider.answers = [
            ModelAnswer(
                status="answered", answer="Unknown [S999].", source_ids=["S999"],
            ),
            ModelAnswer(
                status="answered", answer="Still unknown [S998].", source_ids=["S998"],
            ),
            ModelAnswer(
                status="answered", answer="Verified answer [S1].", source_ids=["S1"],
            ),
        ]

    response = request_with_setup(application, setup)

    assert response.status_code == 200
    assert response.json()["answer"] == "Verified answer [1]."
    assert len(application.state.fake_chat_provider.calls) == 3


def test_irrelevant_zurich_conflict_gets_one_scope_correction(application):
    def setup():
        seed_conversation(application)
        application.state.fake_vector_store.search_results = [evidence(1)]
        application.state.fake_chat_provider.answers = [
            ModelAnswer(
                status="conflicting_sources",
                answer=(
                    "Tokyo is ambiguous because unrelated Zurich appears in the list "
                    "[S1]."
                ),
                source_ids=["S1"],
            ),
            ModelAnswer(
                status="answered",
                answer="Tokyo has a supported conditional rule [S1].",
                source_ids=["S1"],
            ),
        ]

    response = request_with_setup(
        application,
        setup,
        "What is the conditional lodging rule for Tokyo?",
    )

    assert response.status_code == 200
    assert response.json()["status"] == "answered"
    assert "Zurich" not in response.json()["answer"]
    assert len(application.state.fake_chat_provider.calls) == 2


@pytest.mark.parametrize(
    "question",
    [
        "What is the current Latin America limit and was there a 2022 value?",
        "What is one total for a five-day Asia-Pacific trip?",
        "What is the standard European lodging limit?",
    ],
)
def test_unasked_zurich_cannot_change_other_questions_to_conflict(application, question):
    def setup():
        seed_conversation(application)
        application.state.fake_vector_store.search_results = [evidence(1)]
        application.state.fake_chat_provider.answers = [
            ModelAnswer(
                status="conflicting_sources",
                answer="The requested rule is unclear because Zurich is ambiguous [S1].",
                source_ids=["S1"],
            ),
            ModelAnswer(
                status="answered",
                answer="The requested claim is answered without unrelated details [S1].",
                source_ids=["S1"],
            ),
        ]

    response = request_with_setup(application, setup, question)

    assert response.status_code == 200
    assert response.json()["status"] == "answered"
    assert "Zurich" not in response.json()["answer"]
    assert len(application.state.fake_chat_provider.calls) == 2


def test_broad_conflict_review_must_classify_relationship_types(application):
    def setup():
        seed_conversation(application)
        application.state.fake_vector_store.search_results = [evidence(1)]
        application.state.fake_chat_provider.answers = [
            ModelAnswer(
                status="conflicting_sources",
                answer=(
                    "Conflicts include a rule that supersedes an older rule, plus "
                    "Confidential and Restricted requirements [S1]."
                ),
                source_ids=["S1"],
            ),
            ModelAnswer(
                status="conflicting_sources",
                answer=(
                    "Resolved historical differences: the newer rule supersedes the "
                    "older one. Compatible different classifications: Confidential and "
                    "Restricted have distinct scopes. Unresolved ambiguity remains in "
                    "another requested rule [S1]."
                ),
                source_ids=["S1"],
            ),
        ]

    response = request_with_setup(
        application,
        setup,
        "Review conflicts across all uploaded policies.",
    )

    assert response.status_code == 200
    assert "Resolved historical" in response.json()["answer"]
    assert "Compatible different classifications" in response.json()["answer"]
    assert len(application.state.fake_chat_provider.calls) == 2


def test_broad_review_preserves_unresolved_usb_authority(application):
    def setup():
        seed_conversation(application)
        application.state.fake_vector_store.search_results = [
            replace(
                evidence(1),
                filename="data_guidelines.pdf",
                text="Interim guidance: hardware-encrypted USB drives are permitted.",
            ),
            replace(
                evidence(2),
                filename="information_security_data.pdf",
                text="Comprehensive security policy. Handling requirements.",
            ),
        ]
        application.state.fake_chat_provider.answers = [
            ModelAnswer(
                status="conflicting_sources",
                answer="USB is permitted by the old guidance; use current standards [S1].",
                source_ids=["S1"],
            ),
            ModelAnswer(
                status="conflicting_sources",
                answer=(
                    "Unresolved applicability: interim guidance permits USB, but the "
                    "comprehensive policy does not explicitly confirm or revoke it; "
                    "ask Information Security for clarification [S1] [S2]."
                ),
                source_ids=["S1", "S2"],
            ),
        ]

    response = request_with_setup(
        application,
        setup,
        "Review conflicts across all uploaded data policies.",
    )

    assert response.status_code == 200
    assert "does not explicitly confirm or revoke" in response.json()["answer"]
    assert len(application.state.fake_chat_provider.calls) == 2


def test_broad_data_review_covers_both_retrieved_classifications(application):
    def setup():
        seed_conversation(application)
        application.state.fake_vector_store.search_results = [
            replace(
                evidence(1),
                filename="data_guidelines.pdf",
                text="Confidential data may be stored on encrypted laptops.",
            ),
            replace(
                evidence(2),
                filename="information_security_data.pdf",
                text="Restricted data may not be stored on local hard drives.",
            ),
        ]
        application.state.fake_chat_provider.answers = [
            ModelAnswer(
                status="conflicting_sources",
                answer="Restricted data has a local-storage rule [S2].",
                source_ids=["S2"],
            ),
            ModelAnswer(
                status="conflicting_sources",
                answer=(
                    "Compatible different classifications: Confidential and Restricted "
                    "have distinct storage scopes [S1] [S2]."
                ),
                source_ids=["S1", "S2"],
            ),
        ]

    response = request_with_setup(
        application,
        setup,
        "Review conflicts across all uploaded data policies.",
    )

    assert response.status_code == 200
    assert "Confidential and Restricted" in response.json()["answer"]
    assert len(application.state.fake_chat_provider.calls) == 2


def test_historical_latin_value_cannot_borrow_asia_pacific_row(application):
    def setup():
        seed_conversation(application)
        application.state.fake_vector_store.search_results = [
            replace(
                evidence(1),
                filename="reimbursement_2025.pdf",
                text="Latin America USD 160.",
            ),
            replace(
                evidence(2),
                filename="travel_expenses_2022.pdf",
                text="Asia-Pacific USD 200.",
            ),
        ]
        application.state.fake_chat_provider.answers = [
            ModelAnswer(
                status="answered",
                answer="The 2025 value is USD 160; the 2022 value was USD 200 [S1] [S2].",
                source_ids=["S1", "S2"],
            ),
            ModelAnswer(
                status="answered",
                answer=(
                    "The 2025 Latin America value is USD 160 [S1]. The 2022 table "
                    "does not list Latin America [S2]."
                ),
                source_ids=["S1", "S2"],
            ),
        ]

    response = request_with_setup(
        application,
        setup,
        "What is the Latin America limit now and in the 2022 policy?",
    )

    assert response.status_code == 200
    assert "does not list Latin America" in response.json()["answer"]
    assert len(application.state.fake_chat_provider.calls) == 2


def test_partial_supported_answer_cannot_hide_under_insufficient_status(application):
    def setup():
        seed_conversation(application)
        application.state.fake_vector_store.search_results = [
            replace(evidence(1), text="The Europe lodging limit is EUR 220."),
        ]
        application.state.fake_chat_provider.answers = [
            ModelAnswer(
                status="insufficient_context",
                answer=(
                    "The policy provides a Europe limit of EUR 220, but parental "
                    "leave is missing."
                ),
                source_ids=[],
            ),
            ModelAnswer(
                status="answered",
                answer=(
                    "The Europe limit is EUR 220 [S1]. Paid parental leave is not "
                    "covered by the retrieved context."
                ),
                source_ids=["S1"],
            ),
        ]

    response = request_with_setup(
        application,
        setup,
        "What is the Europe lodging limit, and how much parental leave is provided?",
    )

    assert response.status_code == 200
    assert response.json()["status"] == "answered"
    assert response.json()["citations"]
    assert len(application.state.fake_chat_provider.calls) == 2


def test_procurement_portal_is_not_confused_with_travel_portal(application):
    def setup():
        seed_conversation(application)
        application.state.fake_vector_store.search_results = [evidence(1)]
        application.state.fake_chat_provider.answers = [
            ModelAnswer(
                status="conflicting_sources",
                answer=(
                    "The Procurement Portal rule conflicts with the Travel Portal "
                    "booking rule [S1]."
                ),
                source_ids=["S1"],
            ),
            ModelAnswer(
                status="answered",
                answer=(
                    "Purchases must use an approved vendor in the Procurement Portal; "
                    "an exception needs the documented approval [S1]."
                ),
                source_ids=["S1"],
            ),
        ]

    response = request_with_setup(
        application,
        setup,
        "May I use a vendor outside the Procurement Portal?",
    )

    assert response.status_code == 200
    assert response.json()["status"] == "answered"
    assert "Travel Portal" not in response.json()["answer"]
    assert len(application.state.fake_chat_provider.calls) == 2


def test_vendor_sponsored_meal_distinguishes_payment_from_reimbursement(application):
    def setup():
        seed_conversation(application)
        application.state.fake_vector_store.search_results = [evidence(1)]
        application.state.fake_chat_provider.answers = [
            ModelAnswer(
                status="answered",
                answer="A vendor-sponsored dinner must be disclosed [S1].",
                source_ids=["S1"],
            ),
            ModelAnswer(
                status="answered",
                answer=(
                    "If the vendor paid for the dinner, there is no expense to claim "
                    "for reimbursement; acceptance and disclosure rules still apply [S1]."
                ),
                source_ids=["S1"],
            ),
        ]

    response = request_with_setup(
        application,
        setup,
        "Which rules apply to a vendor-sponsored dinner?",
    )

    assert response.status_code == 200
    assert "no expense to claim" in response.json()["answer"]
    assert len(application.state.fake_chat_provider.calls) == 2


def test_vendor_meal_cannot_inherit_gift_threshold(application):
    def setup():
        seed_conversation(application)
        application.state.fake_vector_store.search_results = [evidence(1)]
        application.state.fake_chat_provider.answers = [
            ModelAnswer(
                status="answered",
                answer=(
                    "If the vendor paid, there is no expense to claim. Dinners over "
                    "USD 100 must be disclosed [S1]."
                ),
                source_ids=["S1"],
            ),
            ModelAnswer(
                status="answered",
                answer=(
                    "If the vendor paid, there is no expense to claim. A client-paid "
                    "dinner above the standard USD 45 limit must be recorded and "
                    "disclosed [S1]."
                ),
                source_ids=["S1"],
            ),
        ]

    response = request_with_setup(
        application,
        setup,
        "Which rules apply to a vendor-sponsored dinner?",
    )

    assert response.status_code == 200
    assert "USD 45" in response.json()["answer"]
    assert "USD 100" not in response.json()["answer"]
    assert len(application.state.fake_chat_provider.calls) == 2


def test_vendor_meal_cannot_inherit_procurement_spend_bands(application):
    def setup():
        seed_conversation(application)
        application.state.fake_vector_store.search_results = [evidence(1)]
        application.state.fake_chat_provider.answers = [
            ModelAnswer(
                status="answered",
                answer=(
                    "If the vendor paid, there is no expense to claim. The dinner may "
                    "require Executive Committee approval above USD 100,000 [S1]."
                ),
                source_ids=["S1"],
            ),
            ModelAnswer(
                status="answered",
                answer=(
                    "If the vendor paid, there is no expense to claim. A high-value "
                    "dinner may require Finance, Compliance, and Procurement sign-offs "
                    "[S1]."
                ),
                source_ids=["S1"],
            ),
        ]

    response = request_with_setup(
        application,
        setup,
        "Which rules apply to a vendor-sponsored dinner?",
    )

    assert response.status_code == 200
    assert "Finance, Compliance, and Procurement" in response.json()["answer"]
    assert "100,000" not in response.json()["answer"]
    assert len(application.state.fake_chat_provider.calls) == 2


def test_current_zurich_answer_retries_when_standard_is_omitted(application):
    def setup():
        seed_conversation(application)
        application.state.fake_vector_store.search_results = [evidence(1)]
        application.state.fake_chat_provider.answers = [
            ModelAnswer(
                status="conflicting_sources",
                answer=(
                    "Zurich is European but the exception is ambiguous; ask Finance "
                    "for clarification [S1]."
                ),
                source_ids=["S1"],
            ),
            ModelAnswer(
                status="conflicting_sources",
                answer=(
                    "Zurich is European, so the current standard is EUR 220; the "
                    "exception is ambiguous and requires Finance clarification [S1]."
                ),
                source_ids=["S1"],
            ),
        ]

    response = request_with_setup(
        application,
        setup,
        "What is the current lodging rule for Zurich?",
    )

    assert response.status_code == 200
    assert response.json()["status"] == "conflicting_sources"
    assert "220" in response.json()["answer"]
    assert len(application.state.fake_chat_provider.calls) == 2


def test_current_zurich_answer_labels_old_240_value_historical(application):
    def setup():
        seed_conversation(application)
        application.state.fake_vector_store.search_results = [evidence(1)]
        application.state.fake_chat_provider.answers = [
            ModelAnswer(
                status="conflicting_sources",
                answer=(
                    "Zurich is European. The standard is EUR 240 or current EUR 220; "
                    "the exception is ambiguous, so ask Finance for clarification [S1]."
                ),
                source_ids=["S1"],
            ),
            ModelAnswer(
                status="conflicting_sources",
                answer=(
                    "Zurich is European and the current standard is EUR 220. The older "
                    "2022 value was EUR 240. The exception is ambiguous, so ask Finance "
                    "for clarification [S1]."
                ),
                source_ids=["S1"],
            ),
        ]

    response = request_with_setup(
        application,
        setup,
        "Are you sure? Zurich is in Europe.",
    )

    assert response.status_code == 200
    assert "older 2022 value was EUR 240" in response.json()["answer"]
    assert len(application.state.fake_chat_provider.calls) == 2
