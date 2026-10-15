"""Wire API routes, storage and providers into the FastAPI application lifecycle."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import chat, conversations, documents, health, upload, web
from app.config import Settings, get_settings
from app.database import Database
from app.providers.embeddings import EmbeddingProvider, OnnxMiniLmEmbeddingProvider
from app.providers.llm import (
    ChatProvider,
    ClaimVerifier,
    GeminiChatProvider,
    GeminiClaimVerifier,
)
from app.providers.vector_store import ChromaVectorStore, VectorStore
from app.services.chat import ChatService
from app.services.conversations import ConversationService
from app.services.ingestion import IngestionService
from app.services.retrieval import RetrievalService


def create_app(
    settings: Settings | None = None,
    embedding_provider: EmbeddingProvider | None = None,
    vector_store: VectorStore | None = None,
    chat_provider: ChatProvider | None = None,
    claim_verifier: ClaimVerifier | None = None,
) -> FastAPI:
    """Build the app; optional providers let tests replace external services.

    Startup creates storage and services; shutdown closes the database engine.
    """

    resolved_settings = settings or get_settings()
    database = Database(resolved_settings.database_url)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        database.create_tables()
        resolved_embedding_provider = embedding_provider or OnnxMiniLmEmbeddingProvider(
            cache_path=resolved_settings.model_cache_path,
            model_name=resolved_settings.embedding_model_name,
            dimension=resolved_settings.embedding_dimension,
        )
        resolved_vector_store = vector_store or ChromaVectorStore(
            path=resolved_settings.vector_store_path,
            collection_name=resolved_settings.vector_collection_name,
        )
        resolved_chat_provider = chat_provider or GeminiChatProvider(
            api_key=(
                resolved_settings.gemini_api_key.get_secret_value()
                if resolved_settings.gemini_api_key
                else None
            ),
            model=resolved_settings.chat_model,
            temperature=resolved_settings.chat_temperature,
            max_tokens=resolved_settings.chat_max_output_tokens,
            timeout_seconds=resolved_settings.chat_timeout_seconds,
            thinking_level=resolved_settings.chat_thinking_level,
        )
        resolved_claim_verifier = claim_verifier or GeminiClaimVerifier(
            api_key=(
                resolved_settings.gemini_api_key.get_secret_value()
                if resolved_settings.gemini_api_key
                else None
            ),
            model=resolved_settings.verification_model,
            max_tokens=resolved_settings.verification_max_output_tokens,
            timeout_seconds=resolved_settings.chat_timeout_seconds,
            thinking_level=resolved_settings.verification_thinking_level,
        )
        application.state.database = database
        application.state.settings = resolved_settings
        application.state.ingestion_service = IngestionService(
            database=database,
            embedding_provider=resolved_embedding_provider,
            vector_store=resolved_vector_store,
            settings=resolved_settings,
        )
        application.state.retrieval_service = RetrievalService(
            embedding_provider=resolved_embedding_provider,
            vector_store=resolved_vector_store,
            default_top_k=resolved_settings.retrieval_top_k,
        )
        application.state.chat_service = ChatService(
            database=database,
            retrieval_service=application.state.retrieval_service,
            chat_provider=resolved_chat_provider,
            claim_verifier=resolved_claim_verifier,
        )
        application.state.conversation_service = ConversationService(
            database,
            resolved_vector_store,
        )
        yield
        database.close()

    application = FastAPI(
        title=resolved_settings.app_name,
        version="0.1.0",
        description="Apex Global policy RAG walking skeleton.",
        lifespan=lifespan,
    )
    application.include_router(health.router)
    application.include_router(upload.router)
    application.include_router(chat.router)
    application.include_router(conversations.router)
    application.include_router(documents.router)
    application.include_router(web.router)
    return application


app = create_app()
