"""Run the real Stage 2 stack against every supplied policy PDF."""

from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

from sqlalchemy import select

from app.config import Settings
from app.database import Database
from app.models import Document, DocumentStatus
from app.providers.embeddings import OnnxMiniLmEmbeddingProvider
from app.providers.vector_store import ChromaVectorStore
from app.services.ingestion import IngestionService


POLICY_DIRECTORY = Path("data/sampleset_policies/sampleset_policies")


def main() -> None:
    policy_paths = sorted(POLICY_DIRECTORY.glob("*.pdf"))
    if len(policy_paths) != 8:
        raise RuntimeError(f"Expected 8 policy PDFs, found {len(policy_paths)}.")

    with TemporaryDirectory(prefix="adc-stage2-") as temporary_directory:
        temporary_path = Path(temporary_directory)
        settings = Settings(
            database_url=f"sqlite:///{temporary_path / 'verification.db'}",
            vector_store_path=str(temporary_path / "chroma"),
        )
        database = Database(settings.database_url)
        database.create_tables()
        embeddings = OnnxMiniLmEmbeddingProvider(
            cache_path=settings.model_cache_path,
            model_name=settings.embedding_model_name,
            dimension=settings.embedding_dimension,
        )
        assert embeddings.count_tokens("policy reimbursement limit") < 10
        assert embeddings.count_tokens(" ".join(["policy"] * 300)) > 256
        sample_embedding = embeddings.embed_documents(["policy reimbursement limit"])[0]
        assert len(sample_embedding) == settings.embedding_dimension
        assert abs(sum(value * value for value in sample_embedding) - 1.0) < 1e-5
        vectors = ChromaVectorStore(
            path=settings.vector_store_path,
            collection_name=settings.vector_collection_name,
        )
        service = IngestionService(
            database=database,
            embedding_provider=embeddings,
            vector_store=vectors,
            settings=settings,
        )

        started_at = perf_counter()
        for policy_path in policy_paths:
            result = service.ingest(
                conversation_id="stage-2-verification",
                filename=policy_path.name,
                content=policy_path.read_bytes(),
            )
            print(
                f"indexed {result.filename}: "
                f"{result.chunk_count} chunks ({result.document_id})"
            )

        with database.session_factory() as session:
            documents = list(session.scalars(select(Document)).all())
        assert len(documents) == 8
        assert all(document.status == DocumentStatus.INDEXED for document in documents)
        assert all(
            vectors.count_document_chunks(document.id) == document.chunk_count
            for document in documents
        )

        # Reopen the store to prove that records are on disk, not only in memory.
        reopened_vectors = ChromaVectorStore(
            path=settings.vector_store_path,
            collection_name=settings.vector_collection_name,
        )
        assert all(
            reopened_vectors.count_document_chunks(document.id) == document.chunk_count
            for document in documents
        )
        elapsed = perf_counter() - started_at
        total_chunks = sum(document.chunk_count or 0 for document in documents)
        print(
            f"verified 8 documents, {total_chunks} persistent chunks "
            f"in {elapsed:.2f} seconds"
        )
        database.close()


if __name__ == "__main__":
    main()
