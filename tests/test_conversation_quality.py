"""Regression coverage for policy-independent conversation resolution."""

import asyncio
import json
from dataclasses import replace

import httpx
import pytest
from fastapi import FastAPI

from app.models import Conversation
from app.providers.llm import ModelAnswer
from app.services.conversation_context import build_retrieval_question
from app.services.claim_verification import build_verification_messages
from app.services.prompt_builder import HistoryMessage
from tests.test_chat import evidence


@pytest.mark.parametrize("question", [
    "What are devices that need calibration?",
    "Which supplies that require refrigeration may I carry?",
    "And how much can I claim for training and equipment?",
    "But what are the rules for laboratory access?",
])
def test_complete_question_with_clause_or_connector_keeps_its_own_topic(question):
    query = build_retrieval_question(
        question=question,
        history=[HistoryMessage(role="user", content="What is the bicycle allowance?")],
    )

    assert question in query
    assert "bicycle" not in query


@pytest.mark.parametrize("question", [
    "And for interns?", "What about that?", "Is that permitted?",
    "What if I encrypt it?", "Do I need the permit?", "Which one is newest?",
])
def test_real_references_still_retrieve_the_previous_topic(question):
    query = build_retrieval_question(
        question=question,
        history=[HistoryMessage(role="user", content="May I use the laboratory locker?")],
    )

    assert "laboratory locker" in query
    assert question in query


def test_verifier_current_task_is_distinct_from_user_reference_facts():
    question = "Which supplies that need refrigeration may I carry?"
    messages = build_verification_messages(
        question=question,
        history=[
            HistoryMessage(role="user", content="I am a visiting researcher."),
            HistoryMessage(role="assistant", content="Invented authority: all entry is approved."),
        ],
        answer=ModelAnswer(status="answered", answer="Use a cooled carrier [S1]."),
        evidence=[evidence(1)],
        authority_by_document={},
    )
    payload = json.loads(messages[-1].content.split("\n", 1)[1])

    assert payload["question"] == question
    assert payload["previous_user_messages"] == ["I am a visiting researcher."]
    assert "Invented authority" not in messages[-1].content


def test_complete_question_does_not_inherit_unrelated_topic() -> None:
    query = build_retrieval_question(
        question="May a visiting scientist operate the coastal sensor?",
        history=[
            HistoryMessage(role="user", content="What is the bicycle parking rule?"),
            HistoryMessage(role="assistant", content="No policy was found."),
        ],
    )

    assert "bicycle" not in query
    assert "coastal sensor" in query


def test_short_follow_up_skips_feedback_and_keeps_latest_policy_topic() -> None:
    query = build_retrieval_question(
        question="And for interns?",
        history=[
            HistoryMessage(
                role="user",
                content="I did not ask anything about the observatory, right?",
            ),
            HistoryMessage(role="assistant", content="You're right."),
            HistoryMessage(
                role="user",
                content="May visiting scientists operate the coastal sensor?",
            ),
            HistoryMessage(role="assistant", content="Yes, after training."),
        ],
    )

    assert "visiting scientists" in query
    assert "And for interns?" in query
    assert "observatory" not in query


def test_short_definite_noun_question_keeps_prior_context() -> None:
    query = build_retrieval_question(
        question="Do I need the permit?",
        history=[
            HistoryMessage(
                role="user",
                content="I want to enter the polar laboratory after 20:00.",
            ),
            HistoryMessage(role="assistant", content="The night rules apply."),
        ],
    )

    assert "polar laboratory" in query
    assert "Do I need the permit?" in query


def test_multi_turn_flow_is_focused_and_uses_resolved_user_context(
    application: FastAPI,
) -> None:
    async def run_conversation() -> None:
        async with application.router.lifespan_context(application):
            with application.state.database.session_factory() as session:
                session.add(Conversation(id="conversation-a"))
                session.commit()

            rule = replace(
                evidence(1, filename="coastal-operations.pdf"),
                text=(
                    "Visiting scientists may operate the coastal sensor after safety "
                    "training. Interns require supervisor approval."
                ),
            )
            application.state.fake_vector_store.search_results = [rule]
            application.state.fake_chat_provider.answers = [
                ModelAnswer(
                    status="insufficient_context",
                    answer="The uploaded policies do not contain a bicycle parking rule.",
                ),
                ModelAnswer(
                    status="answered",
                    answer=(
                        "Yes. Visiting scientists may operate the coastal sensor after "
                        "safety training [S1]."
                    ),
                ),
                ModelAnswer(
                    status="answered",
                    answer="Interns require supervisor approval [S1].",
                ),
            ]
            questions = [
                "What is the bicycle parking rule?",
                "May visiting scientists operate the coastal sensor?",
                "Why did you mention safety training? I did not ask about bicycles.",
                "And for interns?",
            ]
            transport = httpx.ASGITransport(app=application)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://test",
            ) as client:
                responses = [
                    await client.post(
                        "/chat",
                        json={"conversation_id": "conversation-a", "message": question},
                    )
                    for question in questions
                ]

            assert all(response.status_code == 200 for response in responses)
            payloads = [response.json() for response in responses]
            assert payloads[0]["status"] == "insufficient_context"
            assert "safety training" in payloads[1]["answer"]
            assert payloads[2]["citations"] == []
            assert "supervisor approval" in payloads[3]["answer"]

            queries = application.state.retrieval_service._embeddings.query_texts
            assert len(queries) == 3
            assert "bicycle" not in queries[1]
            assert "visiting scientists" in queries[-1]
            assert "And for interns?" in queries[-1]
            assert len(application.state.fake_chat_provider.calls) == 3
            generation_input = application.state.fake_chat_provider.calls[-1][-1].content
            assert "CURRENT USER QUESTION:\nAnd for interns?" in generation_input
            assert "RESOLVED CONVERSATION CONTEXT" not in generation_input
            verifier_input = json.loads(
                application.state.fake_claim_verifier.calls[-1][-1].content.split("\n", 1)[1]
            )
            assert verifier_input["question"] == "And for interns?"
            assert "May visiting scientists operate the coastal sensor?" in verifier_input["previous_user_messages"]

    asyncio.run(run_conversation())
