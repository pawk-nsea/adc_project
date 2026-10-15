"""Assemble generation instructions, recent history, policy evidence and the question."""

import json
from dataclasses import dataclass
from pathlib import Path

from app.providers.llm import ChatMessage, ChatRole
from app.providers.vector_store import RetrievedChunk


SYSTEM_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "system.txt"


@dataclass(frozen=True)
class HistoryMessage:
    """Carry a saved role/text pair without treating assistant prose as source evidence."""

    role: ChatRole
    content: str


def source_id(index: int) -> str:
    """Assign a one-based internal citation marker from an evidence-list position."""

    return f"S{index + 1}"


def build_chat_messages(
    *,
    history: list[HistoryMessage],
    evidence: list[RetrievedChunk],
    question: str,
    authority_by_document: dict[str, dict[str, object]] | None = None,
) -> list[ChatMessage]:
    """Return role-aware messages with evidence serialized as untrusted JSON.

    The caller bounds history/evidence; this function neither retrieves nor trims.
    Evidence order must match citation validation and the verifier's source IDs.
    """

    context_records = [
        {
            "source_id": source_id(index),
            "filename": chunk.filename,
            "page": chunk.page_number,
            "text": chunk.text,
            "authority": (authority_by_document or {}).get(chunk.document_id),
        }
        for index, chunk in enumerate(evidence)
    ]
    input_sections = [
        "RETRIEVED CONTEXT (untrusted JSON data):\n"
        f"{json.dumps(context_records, ensure_ascii=False)}"
    ]
    # History is already role-separated below. Do not turn its old questions into
    # additional tasks by repeating them beside the current question.
    input_sections.append("CURRENT USER QUESTION:\n" f"{question}")
    current_input = "\n\n".join(input_sections)
    return [
        ChatMessage(
            role="system",
            content=SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip(),
        ),
        # Preserve speaker boundaries instead of flattening old answers into source text.
        *[
            ChatMessage(role=message.role, content=message.content)
            for message in history
        ],
        ChatMessage(role="user", content=current_input),
    ]
