import asyncio
from pathlib import Path

import httpx
from fastapi import FastAPI
from sqlalchemy import select

from app.models import Conversation, Document, DocumentStatus


POLICY_PATH = Path(
    "data/sampleset_policies/sampleset_policies/travel_expenses_2022.pdf"
)


def request(
    application: FastAPI,
    method: str,
    path: str,
    **kwargs: object,
) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=application)
        async with application.router.lifespan_context(application):
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://test",
            ) as client:
                return await client.request(method, path, **kwargs)

    return asyncio.run(send())


def upload(application: FastAPI, conversation_id: str) -> httpx.Response:
    return request(
        application,
        "POST",
        "/upload",
        data={"conversation_id": conversation_id},
        files={
            "file": (
                "../travel_expenses_2022.pdf",
                POLICY_PATH.read_bytes(),
                "application/pdf",
            )
        },
    )


def test_upload_indexes_pdf_and_persists_provenance(application: FastAPI) -> None:
    response = upload(application, "conversation-a")

    assert response.status_code == 201
    body = response.json()
    assert body["conversation_id"] == "conversation-a"
    assert body["filename"] == "travel_expenses_2022.pdf"
    assert body["status"] == "indexed"
    assert body["chunks_indexed"] > 0

    with application.state.database.session_factory() as session:
        assert session.get(Conversation, "conversation-a") is not None
        document = session.scalar(select(Document))
        assert document is not None
        assert document.status == DocumentStatus.INDEXED
        assert document.page_count >= 1
        assert document.chunk_count == body["chunks_indexed"]

    records = application.state.fake_vector_store.records.values()
    assert len(list(records)) == body["chunks_indexed"]
    assert all(
        record["chunk"].conversation_id == "conversation-a"
        and record["chunk"].filename == "travel_expenses_2022.pdf"
        and record["chunk"].page_number >= 1
        and record["embedding_model"] == "test/fake-embedding"
        for record in application.state.fake_vector_store.records.values()
    )


def test_duplicate_is_scoped_to_conversation(application: FastAPI) -> None:
    assert upload(application, "conversation-a").status_code == 201
    duplicate = upload(application, "conversation-a")
    other_conversation = upload(application, "conversation-b")

    assert duplicate.status_code == 409
    assert "already indexed as document" in duplicate.json()["detail"]
    assert other_conversation.status_code == 201


def test_partial_vector_failure_is_cleaned_up_and_recorded(application: FastAPI) -> None:
    application.state.fake_vector_store.fail_on_add = True

    response = upload(application, "failure-conversation")

    assert response.status_code == 500
    assert response.json() == {"detail": "PDF indexing failed."}
    assert application.state.fake_vector_store.records == {}
    with application.state.database.session_factory() as session:
        document = session.scalar(select(Document))
        assert document is not None
        assert document.status == DocumentStatus.FAILED


def test_malformed_pdf_is_422(application: FastAPI) -> None:
    malformed = request(
        application,
        "POST",
        "/upload",
        data={"conversation_id": "demo"},
        files={"file": ("broken.pdf", b"%PDF-broken", "application/pdf")},
    )
    assert malformed.status_code == 422


def test_oversized_upload_is_413(application: FastAPI) -> None:
    application.state.test_settings.max_upload_bytes = 8

    response = request(
        application,
        "POST",
        "/upload",
        data={"conversation_id": "demo"},
        files={"file": ("large.pdf", b"%PDF-too-large", "application/pdf")},
    )

    assert response.status_code == 413
