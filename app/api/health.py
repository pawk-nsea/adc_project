"""Operational health endpoint."""

from fastapi import APIRouter

from app.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Report only that the API process is available."""

    return HealthResponse(status="ok")
