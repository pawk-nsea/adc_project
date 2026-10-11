import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import httpx
from fastapi import FastAPI
from sqlalchemy import select

from app.models import Conversation, Message, MessageRole
from app.providers.llm import (
    ChatConfigurationError,
    ChatMessage,
    ChatProviderError,
    ChatProviderRateLimitError,
    ChatProviderTimeoutError,
    GeminiChatProvider,
    ModelAnswer,
)
from app.providers.vector_store import RetrievedChunk


def evidence(
    source_number: int,
    *,
    filename: str = "policy.pdf",
    page: int = 1,
) -> RetrievedChunk:
    return RetrievedChunk(
        id=f"chunk-{source_number}",
        text=f"Policy evidence {source_number}",
        conversation_id="conversation-a",
        document_id=f"document-{source_number}",
        filename=filename,
        page_number=page,
        chunk_index=0,
        distance=0.1,
        similarity=0.9,
    )


def request_with_setup(
    application: FastAPI,
    setup: Callable[[], None],
    message: str = "What is the policy?",
) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=application)
        async with application.router.lifespan_context(application):
            setup()
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://test",
            ) as client:
                return await client.post(
                    "/chat",
                    json={
                        "conversation_id": "conversation-a",
                        "message": message,
                    },
                )

    return asyncio.run(send())


def seed_conversation(application: FastAPI, message_count: int = 0) -> None:
    base_time = datetime(2026, 1, 1, tzinfo=UTC)
    with application.state.database.session_factory() as session:
        session.add(Conversation(id="conversation-a"))
        session.add_all(
            [
                Message(
                    conversation_id="conversation-a",
                    role=(
                        MessageRole.USER
                        if index % 2 == 0
                        else MessageRole.ASSISTANT
                    ),
                    content=f"history-{index}",
                    citations_json=[],
                    created_at=base_time + timedelta(seconds=index),
                )
                for index in range(message_count)
            ]
        )
        session.commit()


def test_chat_returns_verified_citation_and_persists_turn(
    application: FastAPI,
) -> None:
    def setup() -> None:
        seed_conversation(application)
        application.state.fake_vector_store.search_results = [
            evidence(1, filename="travel.pdf", page=2)
        ]

    response = request_with_setup(application, setup)

    assert response.status_code == 200
    assert response.json() == {
        "conversation_id": "conversation-a",
        "status": "answered",
        "answer": "The policy answer is supported. [1]",
        "citations": [{"id": 1, "filename": "travel.pdf", "page": 2}],
    }
    with application.state.database.session_factory() as session:
        messages = list(
            session.scalars(
                select(Message).order_by(Message.created_at, Message.id)
            ).all()
        )
    assert [message.role for message in messages] == ["user", "assistant"]
    assert messages[1].citations_json == [
        {"id": 1, "filename": "travel.pdf", "page": 2}
    ]


def test_chat_uses_only_last_five_messages_in_chronological_order(
    application: FastAPI,
) -> None:
    def setup() -> None:
        seed_conversation(application, message_count=7)
        application.state.fake_vector_store.search_results = [evidence(1)]

    response = request_with_setup(application, setup)

    assert response.status_code == 200
    provider_messages = application.state.fake_chat_provider.calls[0]
    assert provider_messages[0].role == "system"
    assert [message.content for message in provider_messages[1:6]] == [
        "history-2",
        "history-3",
        "history-4",
        "history-5",
        "history-6",
    ]
    assert "RETRIEVED CONTEXT" in provider_messages[-1].content
    assert "CURRENT USER QUESTION" in provider_messages[-1].content
    assert "What is the policy?" in provider_messages[-1].content
    assert "Answer the CURRENT USER QUESTION directly" in provider_messages[0].content


def test_invented_citation_is_rejected_without_partial_history(
    application: FastAPI,
) -> None:
    def setup() -> None:
        seed_conversation(application)
        application.state.fake_vector_store.search_results = [evidence(1)]
        application.state.fake_chat_provider.answer = ModelAnswer(
            status="answered",
            answer="Invented source. [S9]",
            source_ids=["S9"],
        )

    response = request_with_setup(application, setup)

    assert response.status_code == 502
    assert response.json() == {
        "detail": (
            "The assistant could not produce a verifiable cited answer. "
            "Please try again."
        )
    }
    with application.state.database.session_factory() as session:
        assert list(session.scalars(select(Message)).all()) == []


def test_unverified_numeric_citation_is_rejected(application: FastAPI) -> None:
    def setup() -> None:
        seed_conversation(application)
        application.state.fake_vector_store.search_results = [evidence(1)]
        application.state.fake_chat_provider.answer = ModelAnswer(
            status="answered",
            answer="This marker was not mapped by the application [1]. [S1]",
            source_ids=["S1"],
        )

    response = request_with_setup(application, setup)

    assert response.status_code == 502
    assert response.json() == {
        "detail": (
            "The assistant could not produce a verifiable cited answer. "
            "Please try again."
        )
    }


def test_chat_retries_one_invalid_citation_response(application: FastAPI) -> None:
    def setup() -> None:
        seed_conversation(application)
        application.state.fake_vector_store.search_results = [evidence(1)]
        application.state.fake_chat_provider.answers = [
            ModelAnswer(
                status="answered",
                answer="Unknown marker [S999].",
                source_ids=["S999"],
            ),
            ModelAnswer(
                status="answered",
                answer="Corrected answer [S1].",
                source_ids=["S1"],
            ),
        ]

    response = request_with_setup(application, setup)

    assert response.status_code == 200
    assert response.json()["answer"] == "Corrected answer [1]."
    assert len(application.state.fake_chat_provider.calls) == 2
    retry_messages = application.state.fake_chat_provider.calls[1]
    assert "failed answer validation" in retry_messages[-1].content


def test_follow_up_question_uses_recent_user_topic_for_retrieval(
    application: FastAPI,
) -> None:
    def setup() -> None:
        base_time = datetime(2026, 1, 1, tzinfo=UTC)
        with application.state.database.session_factory() as session:
            session.add(Conversation(id="conversation-a"))
            session.add_all(
                [
                    Message(
                        conversation_id="conversation-a",
                        role=MessageRole.USER,
                        content="What is the standard Asia-Pacific lodging limit?",
                        citations_json=[],
                        created_at=base_time,
                    ),
                    Message(
                        conversation_id="conversation-a",
                        role=MessageRole.ASSISTANT,
                        content="The policies contain different amounts.",
                        citations_json=[],
                        created_at=base_time + timedelta(seconds=1),
                    ),
                ]
            )
            session.commit()
        application.state.fake_vector_store.search_results = [evidence(1)]

    response = request_with_setup(
        application,
        setup,
        message="Which one is newest and should I use?",
    )

    assert response.status_code == 200
    retrieval_question = application.state.retrieval_service._embeddings.query_texts[0]
    assert "What is the standard Asia-Pacific lodging limit?" in retrieval_question
    assert "Which one is newest and should I use?" in retrieval_question
    assert "effective date" in retrieval_question
    assert "supersedes" in retrieval_question


def test_ordinary_question_does_not_receive_version_search_noise(
    application: FastAPI,
) -> None:
    def setup() -> None:
        seed_conversation(application)
        application.state.fake_vector_store.search_results = [evidence(1)]

    response = request_with_setup(
        application,
        setup,
        message="Which expenses are not reimbursable?",
    )

    assert response.status_code == 200
    retrieval_question = application.state.retrieval_service._embeddings.query_texts[0]
    assert "Which expenses are not reimbursable?" in retrieval_question
    assert "Policy applicability details" not in retrieval_question


def test_confirmation_question_reuses_previous_user_topic(
    application: FastAPI,
) -> None:
    def setup() -> None:
        base_time = datetime(2026, 1, 1, tzinfo=UTC)
        with application.state.database.session_factory() as session:
            session.add(Conversation(id="conversation-a"))
            session.add_all(
                [
                    Message(
                        conversation_id="conversation-a",
                        role=MessageRole.USER,
                        content="Which expenses are not reimbursable?",
                        citations_json=[],
                        created_at=base_time,
                    ),
                    Message(
                        conversation_id="conversation-a",
                        role=MessageRole.ASSISTANT,
                        content="Earlier answer",
                        citations_json=[],
                        created_at=base_time + timedelta(seconds=1),
                    ),
                ]
            )
            session.commit()
        application.state.fake_vector_store.search_results = [evidence(1)]

    response = request_with_setup(
        application,
        setup,
        message="Are you sure?",
    )

    assert response.status_code == 200
    retrieval_question = application.state.retrieval_service._embeddings.query_texts[0]
    assert "Which expenses are not reimbursable?" in retrieval_question
    assert "Are you sure?" in retrieval_question
    assert "Policy applicability details" not in retrieval_question


def test_short_location_fragment_reuses_previous_user_topic(
    application: FastAPI,
) -> None:
    def setup() -> None:
        base_time = datetime(2026, 1, 1, tzinfo=UTC)
        with application.state.database.session_factory() as session:
            session.add(Conversation(id="conversation-a"))
            session.add_all(
                [
                    Message(
                        conversation_id="conversation-a",
                        role=MessageRole.USER,
                        content="How much can I spend on lodging in Europe?",
                        citations_json=[],
                        created_at=base_time,
                    ),
                    Message(
                        conversation_id="conversation-a",
                        role=MessageRole.ASSISTANT,
                        content="Earlier answer",
                        citations_json=[],
                        created_at=base_time + timedelta(seconds=1),
                    ),
                ]
            )
            session.commit()
        application.state.fake_vector_store.search_results = [evidence(1)]

    response = request_with_setup(application, setup, message="To Asia?")

    assert response.status_code == 200
    retrieval_question = application.state.retrieval_service._embeddings.query_texts[0]
    assert "How much can I spend on lodging in Europe?" in retrieval_question
    assert "To Asia?" in retrieval_question


def test_document_conflict_follow_up_reuses_topic_and_authority_terms(
    application: FastAPI,
) -> None:
    def setup() -> None:
        base_time = datetime(2026, 1, 1, tzinfo=UTC)
        with application.state.database.session_factory() as session:
            session.add(Conversation(id="conversation-a"))
            session.add_all(
                [
                    Message(
                        conversation_id="conversation-a",
                        role=MessageRole.USER,
                        content="To Asia?",
                        citations_json=[],
                        created_at=base_time,
                    ),
                    Message(
                        conversation_id="conversation-a",
                        role=MessageRole.ASSISTANT,
                        content="Earlier answer",
                        citations_json=[],
                        created_at=base_time + timedelta(seconds=1),
                    ),
                ]
            )
            session.commit()
        application.state.fake_vector_store.search_results = [evidence(1)]

    response = request_with_setup(
        application,
        setup,
        message="Which documents are conflicting?",
    )

    assert response.status_code == 200
    retrieval_question = application.state.retrieval_service._embeddings.query_texts[0]
    assert "To Asia?" in retrieval_question
    assert "Which documents are conflicting?" in retrieval_question
    assert "supersedes" in retrieval_question


def test_chat_adds_document_start_context_for_strongest_sources(
    application: FastAPI,
) -> None:
    def setup() -> None:
        seed_conversation(application)
        current_rule = evidence(1, filename="current.pdf", page=2)
        old_rule = evidence(2, filename="old.pdf", page=2)
        current_header = RetrievedChunk(
            id="current-header",
            text="Version 3.2. This policy supersedes prior versions.",
            conversation_id="conversation-a",
            document_id=current_rule.document_id,
            filename="current.pdf",
            page_number=1,
            chunk_index=0,
            distance=1.0,
            similarity=0.0,
        )
        application.state.fake_vector_store.search_results = [
            current_rule,
            old_rule,
        ]
        application.state.fake_vector_store.document_start_results = [current_header]

    response = request_with_setup(application, setup)

    assert response.status_code == 200
    prompt = application.state.fake_chat_provider.calls[0][-1].content
    assert "This policy supersedes prior versions" in prompt


def test_provider_failure_leaves_no_partial_history(application: FastAPI) -> None:
    def setup() -> None:
        seed_conversation(application)
        application.state.fake_vector_store.search_results = [evidence(1)]
        application.state.fake_chat_provider.error = ChatProviderError(
            "simulated provider failure"
        )

    response = request_with_setup(application, setup)

    assert response.status_code == 502
    with application.state.database.session_factory() as session:
        assert list(session.scalars(select(Message)).all()) == []


def test_missing_provider_configuration_returns_service_unavailable(
    application: FastAPI,
) -> None:
    def setup() -> None:
        seed_conversation(application)
        application.state.fake_vector_store.search_results = [evidence(1)]
        application.state.fake_chat_provider.error = ChatConfigurationError(
            "Gemini is not configured. Set ADC_GEMINI_API_KEY."
        )

    response = request_with_setup(application, setup)

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Gemini is not configured. Set ADC_GEMINI_API_KEY."
    }
    with application.state.database.session_factory() as session:
        assert list(session.scalars(select(Message)).all()) == []


def test_provider_timeout_returns_gateway_timeout_without_partial_history(
    application: FastAPI,
) -> None:
    def setup() -> None:
        seed_conversation(application)
        application.state.fake_vector_store.search_results = [evidence(1)]
        application.state.fake_chat_provider.error = ChatProviderTimeoutError(
            "Gemini did not respond before the provider deadline. Try again."
        )

    response = request_with_setup(application, setup)

    assert response.status_code == 504
    assert response.json() == {
        "detail": "Gemini did not respond before the provider deadline. Try again."
    }
    with application.state.database.session_factory() as session:
        assert list(session.scalars(select(Message)).all()) == []


def test_insufficient_context_response_has_no_citations(application: FastAPI) -> None:
    def setup() -> None:
        seed_conversation(application)
        application.state.fake_vector_store.search_results = [evidence(1)]
        application.state.fake_chat_provider.answer = ModelAnswer(
            status="insufficient_context",
            answer="The provided policies do not contain this information.",
            source_ids=[],
        )

    response = request_with_setup(application, setup)

    assert response.status_code == 200
    assert response.json()["status"] == "insufficient_context"
    assert response.json()["citations"] == []


def test_conflict_response_maps_both_sources(application: FastAPI) -> None:
    def setup() -> None:
        seed_conversation(application)
        application.state.fake_vector_store.search_results = [
            evidence(1, filename="old.pdf", page=1),
            evidence(2, filename="current.pdf", page=2),
        ]
        application.state.fake_chat_provider.answer = ModelAnswer(
            status="conflicting_sources",
            answer="The older rule differs [S1] from the current rule [S2].",
            source_ids=["S1", "S2"],
        )

    response = request_with_setup(application, setup)

    assert response.status_code == 200
    assert response.json()["answer"] == (
        "The older rule differs [1] from the current rule [2]."
    )
    assert response.json()["citations"] == [
        {"id": 1, "filename": "old.pdf", "page": 1},
        {"id": 2, "filename": "current.pdf", "page": 2},
    ]


def test_gemini_provider_requires_api_key() -> None:
    provider = GeminiChatProvider(
        api_key=None,
        model="gemini-3.5-flash-lite",
        temperature=0.1,
        max_tokens=600,
        timeout_seconds=60,
    )

    try:
        provider.generate([])
    except ChatConfigurationError as exc:
        assert "ADC_GEMINI_API_KEY" in str(exc)
    else:
        raise AssertionError("Expected a missing-key configuration error")


def test_gemini_provider_maps_roles_and_requests_structured_output(
    monkeypatch,
) -> None:
    from google import genai

    captured: dict[str, object] = {}

    class FakeModels:
        def generate_content(self, **kwargs):
            captured.update(kwargs)
            return type(
                "Response",
                (),
                {
                    "text": (
                        '{"status":"answered","answer":"Supported. [S1]",'
                        '"source_ids":["S1"]}'
                    )
                },
            )()

    class FakeClient:
        def __init__(self, **kwargs) -> None:
            captured["client"] = kwargs
            self.models = FakeModels()

    monkeypatch.setattr(genai, "Client", FakeClient)
    provider = GeminiChatProvider(
        api_key="test-key",
        model="gemini-3.5-flash-lite",
        temperature=0.1,
        max_tokens=600,
        timeout_seconds=60,
    )

    result = provider.generate(
        [
            ChatMessage(role="system", content="Ground answers."),
            ChatMessage(role="user", content="Earlier question"),
            ChatMessage(role="assistant", content="Earlier answer"),
            ChatMessage(role="user", content="Current question and context"),
        ]
    )

    assert result.source_ids == ["S1"]
    assert captured["model"] == "gemini-3.5-flash-lite"
    contents = captured["contents"]
    assert [content.role for content in contents] == ["user", "model", "user"]
    config = captured["config"]
    assert config.system_instruction == "Ground answers."
    assert config.temperature == 0.1
    assert config.max_output_tokens == 600
    assert config.response_mime_type == "application/json"
    assert config.response_schema is None
    assert config.response_json_schema["required"] == [
        "status",
        "answer",
        "source_ids",
    ]
    assert "additionalProperties" not in config.response_json_schema
    assert captured["client"]["http_options"].timeout == 60_000


def test_gemini_provider_maps_response_status_code_to_rate_limit(
    monkeypatch,
) -> None:
    from google import genai

    class ProviderFailure(Exception):
        status_code = "429"

    class FakeModels:
        def generate_content(self, **kwargs):
            raise ProviderFailure

    class FakeClient:
        def __init__(self, **kwargs) -> None:
            self.models = FakeModels()

    monkeypatch.setattr(genai, "Client", FakeClient)
    provider = GeminiChatProvider(
        api_key="test-key",
        model="gemini-3.5-flash-lite",
        temperature=0.1,
        max_tokens=600,
        timeout_seconds=60,
    )

    try:
        provider.generate([ChatMessage(role="user", content="Question")])
    except ChatProviderRateLimitError:
        pass
    else:
        raise AssertionError("Expected a rate-limit provider error")
