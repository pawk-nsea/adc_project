"""Validate and index PDF uploads, coordinating relational state and vector cleanup."""

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
from app.services.policy_metadata import extract_policy_authority


class InvalidPdfError(ValueError):
    """Invalid PDF input with the HTTP status used by the upload endpoint."""

    def __init__(self, message: str, status_code: int = 422) -> None:
        """Attach the endpoint status used to distinguish unsupported input from invalid PDFs."""

        super().__init__(message)
        self.status_code = status_code


class UploadTooLargeError(ValueError):
    """Reject bytes exceeding the configured upload limit."""

    pass


class DuplicateDocumentError(ValueError):
    """Reject identical content already processing or indexed in the same workspace."""

    pass


class IngestionError(RuntimeError):
    """Report indexing or cleanup failure after the service attempts compensating cleanup."""

    pass


@dataclass(frozen=True)
class IngestionResult:
    """Describe a completed upload using the identifiers and counts saved during indexing."""

    conversation_id: str
    document_id: str
    filename: str
    status: str
    chunk_count: int
    uploaded_at: datetime


class IngestionService:
    """Complete extraction, local embedding and storage before confirming an upload."""

    def __init__(
        self,
        *,
        database: Database,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
        settings: Settings,
    ) -> None:
        """Bind storage, local embeddings and size/chunk settings without starting ingestion."""

        self._database = database
        self._embeddings = embedding_provider
        self._vectors = vector_store
        self._settings = settings

    def ingest(self, *, conversation_id: str, filename: str, content: bytes) -> IngestionResult:
        """Create/reuse a workspace, index PDF bytes and return saved upload metadata.

        Reject oversized, non-PDF or duplicate active content within that workspace.
        Success retains the original PDF; processing failures retain a failed record
        and attempt vector cleanup. SQLite and Chroma have no shared transaction.
        """

        if len(content) > self._settings.max_upload_bytes:
            raise UploadTooLargeError("The uploaded PDF is too large.")
        if not filename or not filename.lower().endswith(".pdf"):
            raise InvalidPdfError("The uploaded file must have a .pdf extension.", 415)
        if not content.startswith(b"%PDF-"):
            raise InvalidPdfError("The uploaded file does not have a valid PDF signature.", 415)

        content_hash = sha256(content).hexdigest()
        with self._database.session_factory() as session:
            # Failed attempts remain inspectable but do not prevent retrying the same PDF.
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
            # Persist processing state before indexing so failures remain inspectable.
            session.commit()

            try:
                parsed_pdf = parse_pdf(content)
                authority_metadata = extract_policy_authority(parsed_pdf.pages)
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
                document.content_bytes = content
                document.authority_metadata_json = authority_metadata.to_dict()
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
                # Rolling back SQL does not undo Chroma writes; compensate explicitly.
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
