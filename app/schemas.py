"""Define Pydantic request validation and public API response shapes."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictTextModel(BaseModel):
    """Strip surrounding whitespace from public text fields."""

    model_config = ConfigDict(str_strip_whitespace=True)


class HealthResponse(BaseModel):
    status: str


class UploadResponse(BaseModel):
    conversation_id: str
    document_id: str
    filename: str
    status: str
    chunks_indexed: int
    uploaded_at: datetime
    source_view_available: bool = True


class ChatRequest(StrictTextModel):
    conversation_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=10_000)


class Citation(BaseModel):
    # Numbers are local to an answer; document ID and one-based page locate the PDF.
    id: int = Field(ge=1)
    document_id: str | None = None
    filename: str
    page: int = Field(ge=1)


class ChatResponse(BaseModel):
    conversation_id: str
    status: Literal["answered", "insufficient_context", "conflicting_sources"]
    answer: str
    citations: list[Citation]


class ConversationDocumentResponse(BaseModel):
    document_id: str
    filename: str
    status: str
    chunks_indexed: int
    uploaded_at: datetime
    source_view_available: bool


class ConversationMessageResponse(BaseModel):
    # Restored messages retain citations, but the stored record has no status field.
    role: Literal["user", "assistant"]
    content: str
    citations: list[Citation]
    created_at: datetime


class ConversationResponse(BaseModel):
    conversation_id: str
    created_at: datetime
    documents: list[ConversationDocumentResponse]
    messages: list[ConversationMessageResponse]


class ConversationListItemResponse(BaseModel):
    conversation_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    document_count: int
    message_count: int


class ConversationListResponse(BaseModel):
    conversations: list[ConversationListItemResponse]
