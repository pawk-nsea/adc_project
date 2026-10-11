"""Run one real grounded Gemini turn against temporary local storage."""

from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy import select

from app.config import Settings
from app.database import Database
from app.models import Message
from app.providers.embeddings import OnnxMiniLmEmbeddingProvider
from app.providers.llm import GeminiChatProvider
from app.providers.vector_store import ChromaVectorStore
from app.services.chat import ChatService
from app.services.ingestion import IngestionService
from app.services.retrieval import RetrievalService


POLICY_DIRECTORY = Path("data/sampleset_policies/sampleset_policies")
POLICIES = ["travel_expenses_2022.pdf", "reimbursement_2025.pdf"]


def main() -> None:
    base_settings = Settings()
    if base_settings.gemini_api_key is None:
        raise SystemExit(
            "Set ADC_GEMINI_API_KEY in .env before running the live Stage 4 check."
        )
    if not base_settings.chat_model.startswith("gemini-"):
        raise SystemExit(
            "Set ADC_CHAT_MODEL to a Gemini model such as gemini-3.5-flash-lite."
        )

    with TemporaryDirectory(prefix="adc-stage4-") as temporary_directory:
        temporary_path = Path(temporary_directory)
        settings = Settings(
            database_url=f"sqlite:///{temporary_path / 'live-chat.db'}",
            vector_store_path=str(temporary_path / "chroma"),
        )
        database = Database(settings.database_url)
        database.create_tables()
        embeddings = OnnxMiniLmEmbeddingProvider(
            cache_path=settings.model_cache_path,
            model_name=settings.embedding_model_name,
            dimension=settings.embedding_dimension,
        )
        vectors = ChromaVectorStore(
            path=settings.vector_store_path,
            collection_name=settings.vector_collection_name,
        )
        retrieval = RetrievalService(
            embedding_provider=embeddings,
            vector_store=vectors,
            default_top_k=settings.retrieval_top_k,
        )
        ingestion = IngestionService(
            database=database,
            embedding_provider=embeddings,
            vector_store=vectors,
            settings=settings,
        )
        provider = GeminiChatProvider(
            api_key=settings.gemini_api_key.get_secret_value(),
            model=settings.chat_model,
            temperature=settings.chat_temperature,
            max_tokens=settings.chat_max_output_tokens,
            timeout_seconds=settings.chat_timeout_seconds,
        )
        chat = ChatService(
            database=database,
            retrieval_service=retrieval,
            chat_provider=provider,
        )

        for filename in POLICIES:
            policy_path = POLICY_DIRECTORY / filename
            ingestion.ingest(
                conversation_id="stage-4-live",
                filename=filename,
                content=policy_path.read_bytes(),
            )

        result = chat.chat(
            conversation_id="stage-4-live",
            question=(
                "What is the current standard Asia-Pacific lodging limit, and did "
                "the older policy state a different amount?"
            ),
        )
        if not result.citations:
            raise RuntimeError("The live answer did not contain a verified citation.")
        with database.session_factory() as session:
            messages = list(session.scalars(select(Message)).all())
        if len(messages) != 2:
            raise RuntimeError("The live chat turn was not persisted completely.")

        print(f"status: {result.status}")
        print(f"answer: {result.answer}")
        print("citations:")
        for citation in result.citations:
            print(f"  [{citation.id}] {citation.filename}, page {citation.page}")
        database.close()


if __name__ == "__main__":
    main()
