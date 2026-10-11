"""Synchronous PDF ingestion orchestration."""

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256

from sqlalchemy import select

from app.config import Settings
from app.database import Database
from app.models import Conversation, Document, DocumentStatus
from app.providers.embeddings import EmbeddingProvider
from app.providers.vector_store import VectorStore
from app.services.chunker import create_chunks
from app.services.pdf_parser import PdfParseError, parse_pdf


class InvalidPdfError(ValueError):
    def __init__(self, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.status_code = status_code


class UploadTooLargeError(ValueError):
    pass


class DuplicateDocumentError(ValueError):
    pass


class IngestionError(RuntimeError):
    pass


@dataclass(frozen=True)
class IngestionResult:
    conversation_id: str
    document_id: str
    filename: str
    status: str
    chunk_count: int
    uploaded_at: datetime


class IngestionService:
    def __init__(
        self,
        *,
        database: Database,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
        settings: Settings,
    ) -> None:
        self._database = database
        self._embeddings = embedding_provider
        self._vectors = vector_store
        self._settings = settings

    def ingest(self, *, conversation_id: str, filename: str, content: bytes) -> IngestionResult:
        """Index one validated PDF, cleaning up vectors after partial failure."""

        if len(content) > self._settings.max_upload_bytes:
            raise UploadTooLargeError("The uploaded PDF is too large.")
        if not filename or not filename.lower().endswith(".pdf"):
            raise InvalidPdfError("The uploaded file must have a .pdf extension.", 415)
        if not content.startswith(b"%PDF-"):
            raise InvalidPdfError("The uploaded file does not have a valid PDF signature.", 415)

        content_hash = sha256(content).hexdigest()
        with self._database.session_factory() as session:
            duplicate = session.scalar(
                select(Document).where(
                    Document.conversation_id == conversation_id,
                    Document.content_sha256 == content_hash,
                    Document.status.in_([
                        DocumentStatus.PROCESSING,
                        DocumentStatus.INDEXED,
                    ]),
                )
            )
            if duplicate:
                raise DuplicateDocumentError(
                    f"This PDF is already indexed as document {duplicate.id}."
                )

            if session.get(Conversation, conversation_id) is None:
                session.add(Conversation(id=conversation_id))
            document = Document(
                conversation_id=conversation_id,
                filename=filename,
                content_sha256=content_hash,
                status=DocumentStatus.PROCESSING,
            )
            session.add(document)
            session.commit()

            try:
                parsed_pdf = parse_pdf(content)
                chunks = create_chunks(
                    parsed_pdf.pages,
                    document_id=document.id,
                    conversation_id=conversation_id,
                    filename=filename,
                    counter=self._embeddings,
                    target_tokens=self._settings.chunk_target_tokens,
                    max_tokens=self._settings.chunk_max_tokens,
                    overlap_tokens=self._settings.chunk_overlap_tokens,
                )
                embeddings = self._embeddings.embed_documents(
                    [chunk.text for chunk in chunks]
                )
                self._vectors.add_chunks(
                    chunks,
                    embeddings,
                    embedding_model=self._embeddings.model_name,
                    chunking_version=self._settings.chunking_version,
                )
                if self._vectors.count_document_chunks(document.id) != len(chunks):
                    raise IngestionError("Vector-store count verification failed.")

                document.page_count = parsed_pdf.page_count
                document.chunk_count = len(chunks)
                document.status = DocumentStatus.INDEXED
                session.commit()
                return IngestionResult(
                    conversation_id=conversation_id,
                    document_id=document.id,
                    filename=document.filename,
                    status=document.status,
                    chunk_count=document.chunk_count,
                    uploaded_at=document.uploaded_at,
                )
            except Exception as exc:
                session.rollback()
                cleanup_error: Exception | None = None
                try:
                    self._vectors.delete_document(document.id)
                except Exception as cleanup_exc:
                    cleanup_error = cleanup_exc
                finally:
                    failed_document = session.get(Document, document.id)
                    if failed_document is not None:
                        failed_document.status = DocumentStatus.FAILED
                        session.commit()
                if cleanup_error is not None:
                    raise IngestionError(
                        "PDF indexing failed and vector cleanup was incomplete."
                    ) from cleanup_error
                if isinstance(exc, PdfParseError):
                    raise InvalidPdfError(str(exc)) from exc
                if isinstance(exc, IngestionError):
                    raise
                raise IngestionError("PDF indexing failed.") from exc
