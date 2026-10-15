"""Check served browser assets and saved-workspace listing, restoration and deletion APIs."""

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

import httpx
from fastapi import FastAPI
from sqlalchemy import select

from app.models import Conversation, Document, DocumentStatus, Message, MessageRole


def request_with_setup(
    application: FastAPI,
    method: str,
    path: str,
    setup: Callable[[], None] | None = None,
) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=application)
        async with application.router.lifespan_context(application):
            if setup:
                setup()
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://test",
            ) as client:
                return await client.request(method, path)

    return asyncio.run(send())


def test_employee_web_app_and_assets_are_served(application: FastAPI) -> None:
    page = request_with_setup(application, "GET", "/")
    stylesheet = request_with_setup(application, "GET", "/static/styles.css")
    script = request_with_setup(application, "GET", "/static/app.js")

    assert page.status_code == 200
    assert "Apex Global Policy Assistant" in page.text
    assert 'id="chat-form"' in page.text
    assert stylesheet.status_code == 200
    assert "text/css" in stylesheet.headers["content-type"]
    assert script.status_code == 200
    assert "javascript" in script.headers["content-type"]
    assert "#page=${page}" in script.text
    assert 'target = "_blank"' in script.text
    assert "explainChatFailure" in script.text
    assert "pendingQuestion.failed = true" in script.text


def test_unknown_conversation_summary_returns_not_found(application: FastAPI) -> None:
    response = request_with_setup(application, "GET", "/conversations/missing")

    assert response.status_code == 404
    assert response.json() == {"detail": "Conversation not found."}


def test_conversation_summary_restores_only_its_indexed_state(
    application: FastAPI,
) -> None:
    started_at = datetime(2026, 10, 10, 10, 0, tzinfo=UTC)

    def seed() -> None:
        with application.state.database.session_factory() as session:
            session.add_all(
                [
                    Conversation(id="workspace-a", created_at=started_at),
                    Conversation(id="workspace-b", created_at=started_at),
                    Document(
                        id="document-a",
                        conversation_id="workspace-a",
                        filename="travel.pdf",
                        uploaded_at=started_at,
                        chunk_count=3,
                        status=DocumentStatus.INDEXED,
                    ),
                    Document(
                        id="failed-a",
                        conversation_id="workspace-a",
                        filename="broken.pdf",
                        uploaded_at=started_at + timedelta(seconds=1),
                        chunk_count=None,
                        status=DocumentStatus.FAILED,
                    ),
                    Document(
                        id="document-b",
                        conversation_id="workspace-b",
                        filename="private.pdf",
                        uploaded_at=started_at,
                        chunk_count=2,
                        status=DocumentStatus.INDEXED,
                    ),
                    Message(
                        id="message-user",
                        conversation_id="workspace-a",
                        role=MessageRole.USER,
                        content="What is the limit?",
                        citations_json=[],
                        created_at=started_at + timedelta(seconds=2),
                    ),
                    Message(
                        id="message-assistant",
                        conversation_id="workspace-a",
                        role=MessageRole.ASSISTANT,
                        content="The limit is USD 180. [1]",
                        citations_json=[
                            {"id": 1, "filename": "travel.pdf", "page": 2}
                        ],
                        created_at=started_at + timedelta(seconds=3),
                    ),
                    Message(
                        id="message-private",
                        conversation_id="workspace-b",
                        role=MessageRole.USER,
                        content="Do not leak this",
                        citations_json=[],
                        created_at=started_at + timedelta(seconds=4),
                    ),
                ]
            )
            session.commit()

    response = request_with_setup(
        application,
        "GET",
        "/conversations/workspace-a",
        seed,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["conversation_id"] == "workspace-a"
    assert [document["filename"] for document in body["documents"]] == [
        "travel.pdf"
    ]
    assert [message["role"] for message in body["messages"]] == [
        "user",
        "assistant",
    ]
    assert body["messages"][1]["citations"] == [
        {"id": 1, "filename": "travel.pdf", "page": 2}
    ]
    assert "private.pdf" not in response.text
    assert "Do not leak this" not in response.text


def test_saved_conversations_use_first_prompt_titles_and_latest_activity_order(
    application: FastAPI,
) -> None:
    started_at = datetime(2026, 10, 10, 10, 0, tzinfo=UTC)

    def seed() -> None:
        with application.state.database.session_factory() as session:
            session.add_all(
                [
                    Conversation(id="older-chat", created_at=started_at),
                    Conversation(id="newer-chat", created_at=started_at),
                    Conversation(id="failed-empty", created_at=started_at),
                    Document(
                        id="older-document",
                        conversation_id="older-chat",
                        filename="travel.pdf",
                        uploaded_at=started_at,
                        chunk_count=2,
                        status=DocumentStatus.INDEXED,
                    ),
                    Document(
                        id="newer-document",
                        conversation_id="newer-chat",
                        filename="security.pdf",
                        uploaded_at=started_at,
                        chunk_count=2,
                        status=DocumentStatus.INDEXED,
                    ),
                    Document(
                        id="failed-document",
                        conversation_id="failed-empty",
                        filename="broken.pdf",
                        uploaded_at=started_at,
                        status=DocumentStatus.FAILED,
                    ),
                    Message(
                        id="older-question",
                        conversation_id="older-chat",
                        role=MessageRole.USER,
                        content="  What   is the travel limit?  ",
                        citations_json=[],
                        created_at=started_at + timedelta(minutes=1),
                    ),
                    Message(
                        id="newer-question",
                        conversation_id="newer-chat",
                        role=MessageRole.USER,
                        content="How should confidential data be handled?",
                        citations_json=[],
                        created_at=started_at + timedelta(minutes=2),
                    ),
                ]
            )
            session.commit()

    response = request_with_setup(application, "GET", "/conversations", seed)

    assert response.status_code == 200
    assert [item["conversation_id"] for item in response.json()["conversations"]] == [
        "newer-chat",
        "older-chat",
    ]
    assert response.json()["conversations"][0]["title"] == (
        "How should confidential data be handled?"
    )
    assert response.json()["conversations"][1]["title"] == (
        "What is the travel limit?"
    )


def test_delete_conversation_removes_messages_documents_and_vectors(
    application: FastAPI,
) -> None:
    started_at = datetime(2026, 10, 10, 10, 0, tzinfo=UTC)

    def seed() -> None:
        with application.state.database.session_factory() as session:
            session.add(Conversation(id="delete-me", created_at=started_at))
            session.add(
                Document(
                    id="delete-document",
                    conversation_id="delete-me",
                    filename="travel.pdf",
                    uploaded_at=started_at,
                    chunk_count=2,
                    status=DocumentStatus.INDEXED,
                )
            )
            session.add(
                Message(
                    id="delete-message",
                    conversation_id="delete-me",
                    role=MessageRole.USER,
                    content="Delete this chat",
                    citations_json=[],
                    created_at=started_at,
                )
            )
            session.commit()

    response = request_with_setup(
        application,
        "DELETE",
        "/conversations/delete-me",
        seed,
    )

    assert response.status_code == 204
    assert application.state.fake_vector_store.deleted_document_ids == [
        "delete-document"
    ]
    with application.state.database.session_factory() as session:
        assert session.get(Conversation, "delete-me") is None
        assert list(
            session.scalars(
                select(Document).where(Document.conversation_id == "delete-me")
            )
        ) == []
        assert list(
            session.scalars(
                select(Message).where(Message.conversation_id == "delete-me")
            )
        ) == []


def test_delete_unknown_conversation_returns_not_found(application: FastAPI) -> None:
    response = request_with_setup(
        application,
        "DELETE",
        "/conversations/missing",
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Conversation not found."}


def test_legacy_conversation_id_with_url_symbols_can_be_loaded_and_deleted(
    application: FastAPI,
) -> None:
    started_at = datetime(2026, 10, 10, 10, 0, tzinfo=UTC)
    conversation_id = "legacy/id#with?symbols"

    def seed() -> None:
        with application.state.database.session_factory() as session:
            session.add(Conversation(id=conversation_id, created_at=started_at))
            session.add(
                Document(
                    id="legacy-document",
                    conversation_id=conversation_id,
                    filename="reimbursement_2025.pdf",
                    uploaded_at=started_at,
                    chunk_count=2,
                    status=DocumentStatus.INDEXED,
                )
            )
            session.commit()

    encoded_id = quote(conversation_id, safe="")
    loaded = request_with_setup(
        application,
        "GET",
        f"/conversations/{encoded_id}",
        seed,
    )
    deleted = request_with_setup(
        application,
        "DELETE",
        f"/conversations/{encoded_id}",
    )

    assert loaded.status_code == 200
    assert loaded.json()["conversation_id"] == conversation_id
    assert deleted.status_code == 204
    assert application.state.fake_vector_store.deleted_document_ids == [
        "legacy-document"
    ]
