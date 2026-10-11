"""Chat-model boundary and Gemini implementation."""

from dataclasses import dataclass
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError


ChatRole = Literal["system", "user", "assistant"]
AnswerStatus = Literal["answered", "insufficient_context", "conflicting_sources"]


@dataclass(frozen=True)
class ChatMessage:
    role: ChatRole
    content: str


class ModelAnswer(BaseModel):
    """Strict structure expected from every chat provider."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: AnswerStatus
    answer: str = Field(min_length=1)
    source_ids: list[str]


class ChatConfigurationError(RuntimeError):
    pass


class ChatProviderError(RuntimeError):
    pass


class ChatProviderTimeoutError(ChatProviderError):
    pass


class ChatProviderRateLimitError(ChatProviderError):
    pass


class InvalidModelResponseError(ChatProviderError):
    pass


class ChatProvider(Protocol):
    def generate(self, messages: list[ChatMessage]) -> ModelAnswer: ...


def _gemini_generation_schema() -> dict[str, object]:
    """Remove an SDK-incompatible keyword; final Pydantic validation stays strict."""

    schema = ModelAnswer.model_json_schema()
    schema.pop("additionalProperties", None)
    return schema


class GeminiChatProvider:
    """Call Gemini with role-aware messages and validate structured output."""

    def __init__(
        self,
        *,
        api_key: str | None,
        model: str,
        temperature: float,
        max_tokens: int,
        timeout_seconds: int,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._timeout_ms = timeout_seconds * 1000

    def generate(self, messages: list[ChatMessage]) -> ModelAnswer:
        if not self._api_key:
            raise ChatConfigurationError(
                "Gemini is not configured. Set ADC_GEMINI_API_KEY."
            )

        try:
            from google import genai
            from google.genai import types

            system_instructions = [
                message.content for message in messages if message.role == "system"
            ]
            conversation = [
                types.Content(
                    role="model" if message.role == "assistant" else "user",
                    parts=[types.Part.from_text(text=message.content)],
                )
                for message in messages
                if message.role != "system"
            ]
            client = genai.Client(
                api_key=self._api_key,
                http_options=types.HttpOptions(timeout=self._timeout_ms),
            )
            response = client.models.generate_content(
                model=self._model,
                contents=conversation,
                config=types.GenerateContentConfig(
                    system_instruction="\n\n".join(system_instructions),
                    temperature=self._temperature,
                    max_output_tokens=self._max_tokens,
                    response_mime_type="application/json",
                    response_json_schema=_gemini_generation_schema(),
                ),
            )
        except Exception as exc:
            status_code = getattr(exc, "code", None)
            if status_code is None:
                status_code = getattr(exc, "status_code", None)
            if status_code is None and getattr(exc, "response", None) is not None:
                status_code = getattr(exc.response, "status_code", None)
            if isinstance(status_code, str) and status_code.isdigit():
                status_code = int(status_code)
            provider_status = getattr(exc, "status", None)
            if status_code == 504 or provider_status == "DEADLINE_EXCEEDED":
                raise ChatProviderTimeoutError(
                    "Gemini did not respond before the provider deadline. Try again."
                ) from exc
            if status_code == 429 or provider_status == "RESOURCE_EXHAUSTED":
                raise ChatProviderRateLimitError(
                    "Gemini is temporarily rate-limited. Try again later."
                ) from exc
            raise ChatProviderError("The Gemini request failed.") from exc

        try:
            return ModelAnswer.model_validate_json(response.text or "")
        except ValidationError as exc:
            raise InvalidModelResponseError(
                "Gemini returned an invalid answer structure."
            ) from exc
