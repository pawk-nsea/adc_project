"""Conversation history endpoints for the employee-facing workspace."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Request, status

from app.schemas import (
    ConversationDocumentResponse,
    ConversationListItemResponse,
    ConversationListResponse,
    ConversationMessageResponse,
    ConversationResponse,
)
from app.services.conversations import (
    ConversationDeletionError,
    ConversationNotFoundError,
)


router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=ConversationListResponse)
async def list_conversations(request: Request) -> ConversationListResponse:
    """Return saved conversations ordered by their latest activity."""

    items = request.app.state.conversation_service.list_conversations()
    return ConversationListResponse(
        conversations=[
            ConversationListItemResponse(
                conversation_id=item.conversation_id,
                title=item.title,
                created_at=item.created_at,
                updated_at=item.updated_at,
                document_count=item.document_count,
                message_count=item.message_count,
            )
            for item in items
        ]
    )


@router.get("/{conversation_id:path}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: Annotated[str, Path(min_length=1, max_length=128)],
    request: Request,
) -> ConversationResponse:
    """Return indexed sources and saved messages for one conversation."""

    try:
        summary = request.app.state.conversation_service.get_summary(conversation_id)
    except ConversationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return ConversationResponse(
        conversation_id=summary.conversation_id,
        created_at=summary.created_at,
        documents=[
            ConversationDocumentResponse(
                document_id=document.document_id,
                filename=document.filename,
                status=document.status,
                chunks_indexed=document.chunks_indexed,
                uploaded_at=document.uploaded_at,
            )
            for document in summary.documents
        ],
        messages=[
            ConversationMessageResponse(
                role=message.role,
                content=message.content,
                citations=message.citations,
                created_at=message.created_at,
            )
            for message in summary.messages
        ],
    )


@router.delete("/{conversation_id:path}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: Annotated[str, Path(min_length=1, max_length=128)],
    request: Request,
) -> None:
    """Permanently delete one conversation, its documents, and its vectors."""

    try:
        request.app.state.conversation_service.delete_conversation(conversation_id)
    except ConversationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ConversationDeletionError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
