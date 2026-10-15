"""Persist workspaces, uploaded PDFs and completed chat messages in SQLAlchemy."""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utc_now() -> datetime:
    """Return a timezone-aware timestamp for persisted records."""

    return datetime.now(UTC)


def new_id() -> str:
    """Return a portable string identifier."""

    return str(uuid4())


class DocumentStatus(StrEnum):
    """Track whether an upload is being processed, available for use, or failed."""

    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"


class MessageRole(StrEnum):
    """Identify the speaker of a persisted conversation message."""

    USER = "user"
    ASSISTANT = "assistant"


class Conversation(Base):
    """Caller-supplied workspace ID linking its uploads and message history."""

    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )


class Document(Base):
    """Upload identity, indexing state, original bytes and extracted authority signals."""

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id"),
        index=True,
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    content_sha256: Mapped[str | None] = mapped_column(String(64))
    # Keeping the original upload makes page citations inspectable. This is a
    # pragmatic prototype choice; production deployments should normally put
    # larger files in access-controlled object storage instead of SQLite.
    content_bytes: Mapped[bytes | None] = mapped_column(LargeBinary)
    authority_metadata_json: Mapped[dict[str, object] | None] = mapped_column(JSON)
    page_count: Mapped[int | None] = mapped_column(Integer)
    chunk_count: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(
        String(32),
        default=DocumentStatus.PROCESSING,
        nullable=False,
    )


class Message(Base):
    """One saved user or assistant message; answer status is not stored separately."""

    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id"),
        index=True,
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations_json: Mapped[list[dict[str, object]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        index=True,
        nullable=False,
    )
