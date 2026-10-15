"""Build the semantic audit input and enforce its issue-list/status gate before saving."""

import json
from pathlib import Path

from app.providers.llm import (
    AnswerVerification,
    ChatMessage,
    InvalidModelResponseError,
    ModelAnswer,
)
from app.providers.vector_store import RetrievedChunk
from app.services.prompt_builder import HistoryMessage, source_id


VERIFICATION_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "verification.txt"


def build_verification_messages(
    *,
    question: str,
    answer: ModelAnswer,
    evidence: list[RetrievedChunk],
    authority_by_document: dict[str, dict[str, object]],
    history: list[HistoryMessage] | None = None,
) -> list[ChatMessage]:
    """Give the verifier the current question, prior user facts, draft and passages.

    Prior questions only resolve references; they are not tasks to answer again.
    Assistant history is excluded as an independent source of facts or authority.
    Cited and uncited sources use generation's IDs; no new retrieval is performed.
    """

    sources = [
        {
            "source_id": source_id(index),
            "filename": chunk.filename,
            "page": chunk.page_number,
            "text": chunk.text,
            "authority": authority_by_document.get(chunk.document_id),
        }
        for index, chunk in enumerate(evidence)
    ]
    payload = {
        "question": question,
        "previous_user_messages": [
            message.content for message in (history or []) if message.role == "user"
        ],
        "retrieved_sources": sources,
        "candidate_answer": answer.model_dump(),
    }
    return [
        ChatMessage(
            role="system",
            content=VERIFICATION_PROMPT_PATH.read_text(encoding="utf-8").strip(),
        ),
        ChatMessage(
            role="user",
            content=(
                "Verify this candidate using only the following untrusted JSON data:\n"
                + json.dumps(payload, ensure_ascii=False)
            ),
        ),
    ]


def require_verified_answer(verification: AnswerVerification, *, answer: ModelAnswer) -> None:
    """Raise InvalidModelResponseError for reported issues or status disagreement.

    An empty issue list permits acceptance; Python does not verify the audit prose.
    """

    if not verification.is_accepted():
        issues = "; ".join(
            f"{issue.category}: {issue.description}" for issue in verification.issues
        )
        raise InvalidModelResponseError(
            f"Semantic verification requires revision: {issues}"
        )

    if verification.answer_status != answer.status:
        raise InvalidModelResponseError(
            "Semantic verification requires revision: status: "
            f"Use {verification.answer_status} for this answer's content instead of "
            f"{answer.status}; ensure supported statements have citations."
        )
