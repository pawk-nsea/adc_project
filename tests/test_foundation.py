import asyncio

import httpx
from fastapi import FastAPI
from sqlalchemy import inspect


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
