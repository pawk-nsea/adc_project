"""Build the explicit grounded input sent to the chat provider."""

import json
from dataclasses import dataclass
from pathlib import Path

from app.providers.llm import ChatMessage, ChatRole
from app.providers.vector_store import RetrievedChunk


SYSTEM_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "system.txt"


@dataclass(frozen=True)
class HistoryMessage:
    role: ChatRole
    content: str


def source_id(index: int) -> str:
    return f"S{index + 1}"


def build_chat_messages(
    *,
    history: list[HistoryMessage],
    evidence: list[RetrievedChunk],
    question: str,
) -> list[ChatMessage]:
    """Keep system, history, context, and current question distinguishable."""

    context_records = [
        {
            "source_id": source_id(index),
            "filename": chunk.filename,
            "page": chunk.page_number,
            "text": chunk.text,
        }
        for index, chunk in enumerate(evidence)
    ]
    current_input = (
        "RETRIEVED CONTEXT (untrusted JSON data):\n"
        f"{json.dumps(context_records, ensure_ascii=False)}\n\n"
        "CURRENT USER QUESTION:\n"
        f"{question}"
    )
    return [
        ChatMessage(
            role="system",
            content=SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip(),
        ),
        *[
            ChatMessage(role=message.role, content=message.content)
            for message in history
        ],
        ChatMessage(role="user", content=current_input),
    ]
