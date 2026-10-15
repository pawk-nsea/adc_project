"""Check application startup, relational schema and basic HTTP input validation."""

import asyncio

import httpx
from fastapi import FastAPI
from sqlalchemy import inspect, text

from app.database import Database


def request(
    application: FastAPI,
    method: str,
    path: str,
    **kwargs: object,
) -> httpx.Response:
    """Send an in-process request while running application startup/shutdown."""

    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=application)
        async with application.router.lifespan_context(application):
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://test",
            ) as client:
                return await client.request(method, path, **kwargs)

    return asyncio.run(send())


def test_health_reports_api_availability(application: FastAPI) -> None:
    response = request(application, "GET", "/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_lists_foundation_routes(application: FastAPI) -> None:
    response = request(application, "GET", "/openapi.json")

    assert response.status_code == 200
    assert {"/health", "/upload", "/chat"} <= set(response.json()["paths"])


def test_upload_requires_conversation_and_file(application: FastAPI) -> None:
    response = request(application, "POST", "/upload")

    assert response.status_code == 422


def test_upload_rejects_blank_conversation_id(application: FastAPI) -> None:
    response = request(
        application,
        "POST",
        "/upload",
        data={"conversation_id": "   "},
        files={"file": ("policy.pdf", b"not parsed in Stage 1", "application/pdf")},
    )

    assert response.status_code == 422


def test_non_pdf_upload_is_rejected(
    application: FastAPI,
) -> None:
    response = request(
        application,
        "POST",
        "/upload",
        data={"conversation_id": "demo"},
        files={"file": ("policy.pdf", b"not parsed in Stage 1", "application/pdf")},
    )

    assert response.status_code == 415
    assert response.json() == {
        "detail": "The uploaded file does not have a valid PDF signature."
    }


def test_chat_rejects_blank_fields(application: FastAPI) -> None:
    response = request(
        application,
        "POST",
        "/chat",
        json={"conversation_id": "   ", "message": "   "},
    )

    assert response.status_code == 422


def test_chat_rejects_unknown_conversation(
    application: FastAPI,
) -> None:
    response = request(
        application,
        "POST",
        "/chat",
        json={"conversation_id": "demo", "message": "What is the limit?"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Conversation not found."}


def test_database_schema_is_created(application: FastAPI) -> None:
    async def create_schema() -> set[str]:
        async with application.router.lifespan_context(application):
            return set(
                inspect(application.state.database.engine).get_table_names()
            )

    table_names = asyncio.run(create_schema())

    assert table_names == {"conversations", "documents", "messages"}


def test_existing_sqlite_documents_table_gets_additive_document_columns(tmp_path) -> None:
    database = Database(f"sqlite:///{tmp_path / 'legacy.db'}")
    with database.engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE documents ("
                "id VARCHAR(36) PRIMARY KEY, conversation_id VARCHAR(128), "
                "filename VARCHAR(255), uploaded_at DATETIME, "
                "content_sha256 VARCHAR(64), page_count INTEGER, "
                "chunk_count INTEGER, status VARCHAR(32))"
            )
        )

    database.create_tables()

    columns = {
        column["name"] for column in inspect(database.engine).get_columns("documents")
    }
    assert {"content_bytes", "authority_metadata_json"} <= columns
    database.close()
