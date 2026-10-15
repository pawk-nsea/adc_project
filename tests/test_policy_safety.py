"""General policy-safety checks; live model quality is evaluated separately."""

from dataclasses import replace
from pathlib import Path

import pytest
from sqlalchemy import select

from app.models import Message
from app.providers.llm import ModelAnswer
from app.services.conversation_context import build_retrieval_question, needs_expanded_context
from app.services.prompt_builder import HistoryMessage
from tests.test_chat import evidence, request_with_setup, seed_conversation


def test_production_chat_path_contains_no_supplied_policy_facts() -> None:
    production_text = "\n".join(
        Path(path).read_text(encoding="utf-8")
        for path in (
            "app/services/chat.py",
            "app/services/conversation_context.py",
            "app/services/answer_validation.py",
            "app/services/claim_verification.py",
            "app/services/prompt_builder.py",
            "app/prompts/system.txt",
            "app/prompts/verification.txt",
        )
    ).casefold()
    forbidden = (
        "zurich",
        "tokyo",
        "singapore",
        "usd 250",
        "usd 25",
        "usb",
        "reimbursement_2025.pdf",
        "data_guidelines.pdf",
        "information_security_data.pdf",
    )

    assert all(item not in production_text for item in forbidden)


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
        HistoryMessage(role="user", content="What is the orbital-lab access rule?"),
        HistoryMessage(role="assistant", content="A fabricated limit of 9999 units."),
    ]
    query = build_retrieval_question(
        question="May interns operate the coastal sensor array?",
        history=history,
    )

    assert "orbital-lab" not in query
    assert "9999" not in query
    assert "coastal sensor array" in query


def test_confirmation_reuses_user_question_but_never_assistant_facts():
    query = build_retrieval_question(
        question="Are you sure?",
        history=[
            HistoryMessage(role="user", content="Which field manual is current?"),
            HistoryMessage(role="assistant", content="Manual Z has a limit of 9999."),
        ],
    )

    assert "Which field manual is current?" in query
    assert "Are you sure?" in query
    assert "9999" not in query
    assert "effective date" in query


@pytest.mark.parametrize(
    "question",
    [
        "Compare all uploaded policies.",
        "Which version supersedes the older manual?",
        "Do the documents contain conflicting rules?",
        "List every restriction in the temporary guidance.",
    ],
)
def test_broad_and_authority_questions_receive_expanded_context(question):
    assert needs_expanded_context(question)


def test_ordinary_fact_question_keeps_normal_context_budget():
    assert not needs_expanded_context("What is the bicycle parking allowance?")


@pytest.mark.parametrize(
    ("filename", "question", "source_text", "answer"),
    [
        (
            "renamed-orbit-rules.pdf",
            "May a research fellow book the observatory in Nuuk for 375 DKK?",
            "Research fellows may book the Nuuk observatory up to DKK 375 per visit.",
            "Yes. A research fellow may book the Nuuk observatory up to DKK 375 per visit [S1].",
        ),
        (
            "aquatic-fieldwork-v7.pdf",
            "Can a visiting engineer use a submersible after six months?",
            "Visiting engineers may use a submersible after at least 6 months of service.",
            "Yes, after at least 6 months of service [S1].",
        ),
        (
            "studio-materials.pdf",
            "What approval is needed for ceramic glaze?",
            "Ceramic glaze purchases require written approval from the studio custodian.",
            "Ceramic glaze purchases require written approval from the studio custodian [S1].",
        ),
    ],
)
def test_unfamiliar_policy_names_values_scopes_and_categories_flow_through_api(
    application,
    filename,
    question,
    source_text,
    answer,
):
    def setup() -> None:
        seed_conversation(application)
        application.state.fake_vector_store.search_results = [
            replace(evidence(1, filename=filename), text=source_text)
        ]
        application.state.fake_chat_provider.answer = ModelAnswer(
            status="answered",
            answer=answer,
        )

    response = request_with_setup(application, setup, message=question)

    assert response.status_code == 200
    assert response.json()["status"] == "answered"
    assert response.json()["answer"] == answer.replace("[S1]", "[1]")
    assert response.json()["citations"][0]["filename"] == filename


def test_partially_supported_question_answers_supported_part_and_names_gap(application):
    def setup() -> None:
        seed_conversation(application)
        application.state.fake_vector_store.search_results = [
            replace(
                evidence(1, filename="polar-station.pdf"),
                text="Winter researchers receive 12 battery packs per month.",
            )
        ]
        application.state.fake_chat_provider.answer = ModelAnswer(
            status="answered",
            answer=(
                "Winter researchers receive 12 battery packs per month [S1]. "
                "The uploaded policy does not specify a summer allowance."
            ),
        )

    response = request_with_setup(
        application,
        setup,
        message="What are the winter and summer battery allowances?",
    )

    assert response.status_code == 200
    assert response.json()["status"] == "answered"
    assert "does not specify a summer allowance" in response.json()["answer"]


def test_genuine_unseen_conflict_is_preserved(application):
    first = replace(
        evidence(1, filename="lab-access-a.pdf"),
        text="Contractors may enter Lab K after 07:00.",
    )
    second = replace(
        evidence(2, filename="lab-access-b.pdf"),
        text="Contractors may not enter Lab K before 09:00.",
    )

    def setup() -> None:
        seed_conversation(application)
        application.state.fake_vector_store.search_results = [first, second]
        application.state.fake_chat_provider.answer = ModelAnswer(
            status="conflicting_sources",
            answer=(
                "The contractor access time is conflicting: one rule permits entry "
                "after 07:00 [S1], while another prohibits entry before 09:00 [S2]."
            ),
        )

    response = request_with_setup(
        application,
        setup,
        message="When may a contractor enter Lab K?",
    )

    assert response.status_code == 200
    assert response.json()["status"] == "conflicting_sources"
    assert {item["filename"] for item in response.json()["citations"]} == {
        "lab-access-a.pdf",
        "lab-access-b.pdf",
    }


def test_compatible_unseen_rules_are_not_forced_into_conflict(application):
    first = replace(
        evidence(1, filename="archive-access.pdf"),
        text="Researchers must obtain archive-owner approval before entry.",
    )
    second = replace(
        evidence(2, filename="night-safety.pdf"),
        text="Anyone entering facilities after 20:00 must sign the night register.",
    )

    def setup() -> None:
        seed_conversation(application)
        application.state.fake_vector_store.search_results = [first, second]
        application.state.fake_chat_provider.answer = ModelAnswer(
            status="answered",
            answer=(
                "Both requirements apply: obtain archive-owner approval [S1] and, "
                "for entry after 20:00, sign the night register [S2]."
            ),
        )

    response = request_with_setup(
        application,
        setup,
        message="What requirements apply when a researcher enters the archive at 21:00?",
    )

    assert response.status_code == 200
    assert response.json()["status"] == "answered"
