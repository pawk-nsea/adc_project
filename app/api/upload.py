"""PDF upload and synchronous indexing endpoint."""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status

from app.schemas import UploadResponse
from app.services.ingestion import (
    DuplicateDocumentError,
    IngestionError,
    InvalidPdfError,
    UploadTooLargeError,
)

router = APIRouter(tags=["documents"])


@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    request: Request,
    conversation_id: Annotated[
        str,
        Form(min_length=1, max_length=128, pattern=r".*\S.*"),
    ],
    file: Annotated[UploadFile, File(description="Policy PDF")],
) -> UploadResponse:
    """Validate and synchronously index one PDF for a conversation."""

    settings = request.app.state.settings
    uploaded_bytes = await file.read(settings.max_upload_bytes + 1)
    await file.close()
    if len(uploaded_bytes) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"PDF exceeds the {settings.max_upload_bytes} byte upload limit.",
        )

    # Path.name handles local separators; replacing backslashes also sanitizes
    # filenames sent by Windows clients while running the API on Linux.
    filename = Path((file.filename or "").replace("\\", "/")).name

    try:
        result = request.app.state.ingestion_service.ingest(
            conversation_id=conversation_id,
            filename=filename,
            content=uploaded_bytes,
        )
    except UploadTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except InvalidPdfError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except DuplicateDocumentError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IngestionError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return UploadResponse(
        conversation_id=result.conversation_id,
        document_id=result.document_id,
        filename=result.filename,
        status=result.status,
        chunks_indexed=result.chunk_count,
        uploaded_at=result.uploaded_at,
        source_view_available=True,
    )
