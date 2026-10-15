"""Grounded policy chat endpoint."""

from fastapi import APIRouter, HTTPException, Request

from app.schemas import ChatRequest, ChatResponse
from app.providers.llm import (
    ChatConfigurationError,
    ChatProviderError,
    ChatProviderRateLimitError,
    ChatProviderTimeoutError,
    ChatProviderUnavailableError,
    InvalidModelResponseError,
)
from app.services.chat import ChatPersistenceError, UnknownConversationError

router = APIRouter(tags=["chat"])


@router.post(
    "/chat",
    response_model=ChatResponse,
)
async def chat(request: Request, body: ChatRequest) -> ChatResponse:
    """Retrieve policy evidence, generate a grounded answer, and save the turn."""

    try:
        result = request.app.state.chat_service.chat(
            conversation_id=body.conversation_id,
            question=body.message,
        )
    except UnknownConversationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ChatConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (ChatProviderRateLimitError, ChatProviderUnavailableError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ChatProviderTimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except (InvalidModelResponseError, ChatProviderError) as exc:
        # Failed model output is an upstream failure, not an accepted policy abstention.
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ChatPersistenceError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return ChatResponse(
        conversation_id=result.conversation_id,
        status=result.status,
        answer=result.answer,
        citations=result.citations,
    )
