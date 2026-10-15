"""Build isolated test apps with controlled embedding, storage, generation and audit fakes."""

import json

import pytest
from fastapi import FastAPI

from app.config import Settings
from app.main import create_app
from app.providers.llm import (
    AnswerVerification,
    ChatMessage,
    ModelAnswer,
)
from app.providers.vector_store import RetrievedChunk
from app.services.chunker import TextChunk


class FakeEmbeddingProvider:
    """Record queries and return synthetic vectors; no semantic quality is tested."""

    model_name = "test/fake-embedding"
    dimension = 4
    max_input_tokens = 256

    def __init__(self) -> None:
        self.query_texts: list[str] = []

    def count_tokens(self, text: str) -> int:
        return len(text.split()) + 2

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [
            [float(len(text)), float(index), 0.5, 1.0]
            for index, text in enumerate(texts)
        ]

    def embed_query(self, text: str) -> list[float]:
        self.query_texts.append(text)
        return self.embed_documents([text])[0]


class FakeVectorStore:
    """Store uploads in memory and return preset retrieval results for service tests."""

    def __init__(self) -> None:
        self.records: dict[str, dict[str, object]] = {}
        self.deleted_document_ids: list[str] = []
        self.fail_on_add = False
        self.search_results: list[RetrievedChunk] = []
        self.keyword_search_results: list[RetrievedChunk] = []
        self.document_start_results: list[RetrievedChunk] = []
        self.page_chunk_results: list[RetrievedChunk] = []

    def add_chunks(
        self,
        chunks: list[TextChunk],
        embeddings: list[list[float]],
        *,
        embedding_model: str,
        chunking_version: str,
    ) -> None:
        for chunk, embedding in zip(chunks, embeddings, strict=True):
            self.records[chunk.id] = {
                "chunk": chunk,
                "embedding": embedding,
                "embedding_model": embedding_model,
                "chunking_version": chunking_version,
            }
        if self.fail_on_add:
            # Raise after writes to exercise cleanup of partially indexed uploads.
            raise RuntimeError("simulated vector-store failure")

    def delete_document(self, document_id: str) -> None:
        self.deleted_document_ids.append(document_id)
        self.records = {
            key: record
            for key, record in self.records.items()
            if record["chunk"].document_id != document_id
        }

    def count_document_chunks(self, document_id: str) -> int:
        return sum(
            record["chunk"].document_id == document_id
            for record in self.records.values()
        )

    def search(
        self,
        query_embedding: list[float],
        *,
        conversation_id: str,
        embedding_model: str,
        top_k: int,
    ) -> list[RetrievedChunk]:
        return self.search_results[:top_k]

    def keyword_search(
        self,
        query: str,
        *,
        conversation_id: str,
        embedding_model: str,
        top_k: int,
    ) -> list[RetrievedChunk]:
        return self.keyword_search_results[:top_k]

    def get_document_start_chunks(
        self,
        *,
        conversation_id: str,
        embedding_model: str,
        document_ids: list[str],
    ) -> list[RetrievedChunk]:
        return [
            result
            for result in self.document_start_results
            if result.document_id in document_ids
            and result.conversation_id == conversation_id
        ]

    def get_page_chunks(
        self,
        *,
        conversation_id: str,
        embedding_model: str,
        page_keys: list[tuple[str, int]],
    ) -> list[RetrievedChunk]:
        requested_pages = set(page_keys)
        return [
            result
            for result in self.page_chunk_results
            if (result.document_id, result.page_number) in requested_pages
            and result.conversation_id == conversation_id
        ]


class FakeChatProvider:
    """Record prompts and return queued drafts or a configured provider failure."""

    def __init__(self) -> None:
        self.answer = ModelAnswer(
            status="answered",
            answer="The policy answer is supported. [S1]",
        )
        self.error: Exception | None = None
        self.calls: list[list[ChatMessage]] = []
        self.answers: list[ModelAnswer] = []

    def generate(self, messages: list[ChatMessage]) -> ModelAnswer:
        self.calls.append(messages)
        if self.error:
            raise self.error
        return self.answers.pop(0) if self.answers else self.answer


class FakeClaimVerifier:
    """Return configured audits, otherwise approve; this does not inspect evidence."""

    def __init__(self) -> None:
        self.verification: AnswerVerification | None = None
        self.verifications: list[AnswerVerification] = []
        self.calls: list[list[ChatMessage]] = []

    def verify(self, messages: list[ChatMessage]) -> AnswerVerification:
        self.calls.append(messages)
        if self.verifications:
            return self.verifications.pop(0)
        if self.verification is not None:
            return self.verification
        return AnswerVerification(
            evidence_answer="The synthetic evidence supports the complete answer.",
            answer_status=json.loads(messages[-1].content.split("\n", 1)[1])["candidate_answer"]["status"],
            issues=[],
        )


@pytest.fixture
def application(tmp_path) -> FastAPI:
    """Create an app with temporary SQLite and fakes; request helpers run its lifespan."""

    database_path = tmp_path / "test.db"
    settings = Settings(
        database_url=f"sqlite:///{database_path}",
        vector_store_path=str(tmp_path / "chroma"),
        model_cache_path=str(tmp_path / "models"),
    )
    vector_store = FakeVectorStore()
    chat_provider = FakeChatProvider()
    claim_verifier = FakeClaimVerifier()
    application = create_app(
        settings,
        embedding_provider=FakeEmbeddingProvider(),
        vector_store=vector_store,
        chat_provider=chat_provider,
        claim_verifier=claim_verifier,
    )
    application.state.fake_vector_store = vector_store
    application.state.fake_chat_provider = chat_provider
    application.state.fake_claim_verifier = claim_verifier
    application.state.test_settings = settings
    return application
