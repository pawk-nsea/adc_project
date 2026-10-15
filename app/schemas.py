"""Define Pydantic request validation and public API response shapes."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictTextModel(BaseModel):
    """Strip surrounding whitespace from public text fields."""

    model_config = ConfigDict(str_strip_whitespace=True)


# Process availability only; this does not report provider or index health.
class HealthResponse(BaseModel):
    status: str


# Confirmation returned after vector indexing and relational finalization succeed.
class UploadResponse(BaseModel):
    conversation_id: str
    document_id: str
    filename: str
    status: str
    chunks_indexed: int
    uploaded_at: datetime
    source_view_available: bool = True


# Bound and trim workspace/question inputs before passing them to the chat service.
class ChatRequest(StrictTextModel):
    conversation_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=10_000)


# Public provenance for a cited PDF page; legacy records may lack a document ID.
class Citation(BaseModel):
    # Numbers are local to an answer; document ID and one-based page locate the PDF.
    id: int = Field(ge=1)
    document_id: str | None = None
    filename: str
    page: int = Field(ge=1)


# Expose the accepted answer and its support status alongside mapped source references.
class ChatResponse(BaseModel):
    conversation_id: str
    status: Literal["answered", "insufficient_context", "conflicting_sources"]
    answer: str
    citations: list[Citation]


# Metadata needed to display an indexed source and decide whether it can be opened.
class ConversationDocumentResponse(BaseModel):
    document_id: str
    filename: str
    status: str
    chunks_indexed: int
    uploaded_at: datetime
    source_view_available: bool


# Saved speaker, text and citations; historical rows have no separate answer status.
class ConversationMessageResponse(BaseModel):
    # Restored messages retain citations, but the stored record has no status field.
    role: Literal["user", "assistant"]
    content: str
    citations: list[Citation]
    created_at: datetime


# Restore indexed documents and saved messages for one workspace.
class ConversationResponse(BaseModel):
    conversation_id: str
    created_at: datetime
    documents: list[ConversationDocumentResponse]
    messages: list[ConversationMessageResponse]


# Sidebar title, activity dates and counts for a nonempty saved workspace.
class ConversationListItemResponse(BaseModel):
    conversation_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    document_count: int
    message_count: int


# Wrap the saved-workspace list in a stable public response object.
class ConversationListResponse(BaseModel):
    conversations: list[ConversationListItemResponse]
