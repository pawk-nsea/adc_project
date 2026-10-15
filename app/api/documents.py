"""Serve original PDFs after checking workspace membership, without authentication."""

from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Path, Query, Request, status
from fastapi.responses import Response

from app.services.conversations import (
    DocumentContentNotFoundError,
    DocumentContentUnavailableError,
)


router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/{document_id}/content", response_class=Response)
async def get_document_content(
    document_id: Annotated[str, Path(min_length=1, max_length=128)],
    conversation_id: Annotated[str, Query(min_length=1, max_length=128)],
    request: Request,
) -> Response:
    """Open a PDF only within the workspace that owns it."""

    try:
        document = request.app.state.conversation_service.get_document_content(
            conversation_id=conversation_id,
            document_id=document_id,
        )
    except DocumentContentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except DocumentContentUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    encoded_filename = quote(document.filename, safe="")
    # Encode the uploaded name for the response header; never use it as a file path.
    return Response(
        content=document.content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{encoded_filename}",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox",
        },
    )
