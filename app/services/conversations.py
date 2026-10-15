"""Read saved workspaces and original PDFs, and coordinate deletion across both stores."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, cast

from sqlalchemy import delete, select

from app.database import Database
from app.models import Conversation, Document, DocumentStatus, Message
from app.providers.vector_store import VectorStore
from app.schemas import Citation


class ConversationNotFoundError(LookupError):
    pass


class ConversationDeletionError(RuntimeError):
    pass


class DocumentContentNotFoundError(LookupError):
    pass


class DocumentContentUnavailableError(LookupError):
    pass


@dataclass(frozen=True)
class DocumentSummary:
    document_id: str
    filename: str
    status: str
    chunks_indexed: int
    uploaded_at: datetime
    source_view_available: bool


@dataclass(frozen=True)
class MessageSummary:
    role: Literal["user", "assistant"]
    content: str
    citations: list[Citation]
    created_at: datetime


@dataclass(frozen=True)
class ConversationSummary:
    conversation_id: str
    created_at: datetime
    documents: list[DocumentSummary]
    messages: list[MessageSummary]


@dataclass(frozen=True)
class ConversationListItem:
    conversation_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    document_count: int
    message_count: int


@dataclass(frozen=True)
class DocumentContent:
    filename: str
    content: bytes


class ConversationService:
    """Manage durable conversation state used by the lightweight web client."""

    def __init__(self, database: Database, vector_store: VectorStore) -> None:
        self._database = database
        self._vectors = vector_store

    @staticmethod
    def _title(first_question: str | None, first_filename: str | None) -> str:
        source = first_question or first_filename or "Policy workspace"
        normalized = " ".join(source.split())
        if len(normalized) <= 56:
            return normalized
        return normalized[:55].rstrip() + "…"

    def list_conversations(self) -> list[ConversationListItem]:
        """List nonempty workspaces by activity, deriving titles from question or filename.

        Indexed documents and all saved messages count; empty/failed-only uploads
        without messages are omitted. This reads all workspaces without user filtering.
        """

        with self._database.session_factory() as session:
            conversations = list(session.scalars(select(Conversation)).all())
            items: list[ConversationListItem] = []
            for conversation in conversations:
                documents = list(
                    session.scalars(
                        select(Document)
                        .where(
                            Document.conversation_id == conversation.id,
                            Document.status == DocumentStatus.INDEXED,
                        )
                        .order_by(Document.uploaded_at, Document.id)
                    ).all()
                )
                messages = list(
                    session.scalars(
                        select(Message)
                        .where(Message.conversation_id == conversation.id)
                        .order_by(Message.created_at, Message.id)
                    ).all()
                )
                if not documents and not messages:
                    continue
                first_question = next(
                    (
                        message.content
                        for message in messages
                        if message.role == "user"
                    ),
                    None,
                )
                activity_times = [conversation.created_at]
                activity_times.extend(document.uploaded_at for document in documents)
                activity_times.extend(message.created_at for message in messages)
                items.append(
                    ConversationListItem(
                        conversation_id=conversation.id,
                        title=self._title(
                            first_question,
                            documents[0].filename if documents else None,
                        ),
                        created_at=conversation.created_at,
                        updated_at=max(activity_times),
                        document_count=len(documents),
                        message_count=len(messages),
                    )
                )
        return sorted(items, key=lambda item: item.updated_at, reverse=True)

    def get_summary(self, conversation_id: str) -> ConversationSummary:
        """Restore indexed sources and chronological messages, or reject an unknown ID."""

        with self._database.session_factory() as session:
            conversation = session.get(Conversation, conversation_id)
            if conversation is None:
                raise ConversationNotFoundError("Conversation not found.")

            documents = list(
                session.scalars(
                    select(Document)
                    .where(
                        Document.conversation_id == conversation_id,
                        Document.status == DocumentStatus.INDEXED,
                    )
                    .order_by(Document.uploaded_at, Document.id)
                ).all()
            )
            messages = list(
                session.scalars(
                    select(Message)
                    .where(Message.conversation_id == conversation_id)
                    .order_by(Message.created_at, Message.id)
                ).all()
            )

        return ConversationSummary(
            conversation_id=conversation.id,
            created_at=conversation.created_at,
            documents=[
                DocumentSummary(
                    document_id=document.id,
                    filename=document.filename,
                    status=document.status,
                    chunks_indexed=document.chunk_count or 0,
                    uploaded_at=document.uploaded_at,
                    source_view_available=document.content_bytes is not None,
                )
                for document in documents
            ],
            messages=[
                MessageSummary(
                    role=cast(Literal["user", "assistant"], message.role),
                    content=message.content,
                    citations=[
                        Citation.model_validate(citation)
                        for citation in message.citations_json
                    ],
                    created_at=message.created_at,
                )
                for message in messages
            ],
        )

    def get_document_content(
        self,
        *,
        conversation_id: str,
        document_id: str,
    ) -> DocumentContent:
        """Return retained PDF bytes for an indexed document in the requested workspace.

        Missing membership raises DocumentContentNotFoundError; legacy uploads
        without bytes raise DocumentContentUnavailableError. No caller is authenticated.
        """

        with self._database.session_factory() as session:
            document = session.scalar(
                select(Document).where(
                    Document.id == document_id,
                    Document.conversation_id == conversation_id,
                    Document.status == DocumentStatus.INDEXED,
                )
            )
            if document is None:
                raise DocumentContentNotFoundError("PDF source not found.")
            if document.content_bytes is None:
                raise DocumentContentUnavailableError(
                    "The original PDF was indexed before source viewing was enabled. "
                    "Upload it again in a new chat to make it viewable."
                )
            return DocumentContent(
                filename=document.filename,
                content=document.content_bytes,
            )

    def delete_conversation(self, conversation_id: str) -> None:
        """Delete document vectors, then commit deletion of SQL messages/uploads/workspace.

        Failure raises ConversationDeletionError. SQL records remain after a vector
        failure, but earlier vector deletions cannot be rolled back across stores.
        """

        with self._database.session_factory() as session:
            if session.get(Conversation, conversation_id) is None:
                raise ConversationNotFoundError("Conversation not found.")
            document_ids = list(
                session.scalars(
                    select(Document.id).where(
                        Document.conversation_id == conversation_id
                    )
                ).all()
            )

        try:
            for document_id in document_ids:
                self._vectors.delete_document(document_id)
        except Exception as exc:
            raise ConversationDeletionError(
                "The conversation could not be removed from the vector store."
            ) from exc

        with self._database.session_factory() as session:
            try:
                session.execute(
                    delete(Message).where(Message.conversation_id == conversation_id)
                )
                session.execute(
                    delete(Document).where(Document.conversation_id == conversation_id)
                )
                session.execute(
                    delete(Conversation).where(Conversation.id == conversation_id)
                )
                session.commit()
            except Exception as exc:
                session.rollback()
                raise ConversationDeletionError(
                    "The conversation could not be removed from the database."
                ) from exc
