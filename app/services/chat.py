"""Coordinate policy chat, bounded answer verification and completed-turn persistence."""

import logging
from dataclasses import dataclass
from typing import cast

from sqlalchemy import select

from app.database import Database
from app.models import Conversation, Document, Message, MessageRole, utc_now
from app.providers.llm import (
    AnswerStatus,
    ChatMessage,
    ChatProvider,
    ClaimVerifier,
    ChatRole,
    InvalidModelResponseError,
    ModelAnswer,
)
from app.providers.vector_store import RetrievedChunk
from app.schemas import Citation
from app.services.answer_validation import validate_citations
from app.services.conversation_context import (
    EXPANDED_CONTEXT_TOP_K,
    build_retrieval_question,
    conversation_feedback_answer,
    needs_expanded_context,
    resolve_question_context,
)
from app.services.claim_verification import (
    build_verification_messages,
    require_verified_answer,
)
from app.services.pdf_parser import PdfParseError, parse_pdf
from app.services.policy_metadata import (
    AUTHORITY_METADATA_VERSION,
    PolicyAuthorityMetadata,
    extract_policy_authority,
    resolve_policy_authority,
)
from app.services.prompt_builder import HistoryMessage, build_chat_messages
from app.services.retrieval import RetrievalService


logger = logging.getLogger(__name__)
MAX_ANSWER_ATTEMPTS = 2
# A malformed audit recheck consumes the same budget as an answer correction.


class UnknownConversationError(LookupError):
    pass


class ChatPersistenceError(RuntimeError):
    pass


@dataclass(frozen=True)
class ChatResult:
    conversation_id: str
    status: AnswerStatus
    answer: str
    citations: list[Citation]


class ChatService:
    """Orchestrate context resolution, retrieval, generation, and persistence."""

    def __init__(
        self,
        *,
        database: Database,
        retrieval_service: RetrievalService,
        chat_provider: ChatProvider,
        claim_verifier: ClaimVerifier,
    ) -> None:
        self._database = database
        self._retrieval = retrieval_service
        self._provider = chat_provider
        self._claim_verifier = claim_verifier

    def _load_history(self, conversation_id: str) -> list[HistoryMessage]:
        """Read the latest five individual messages in order, rejecting unknown IDs."""

        with self._database.session_factory() as session:
            if session.get(Conversation, conversation_id) is None:
                raise UnknownConversationError("Conversation not found.")
            newest_first = list(
                session.scalars(
                    select(Message)
                    .where(Message.conversation_id == conversation_id)
                    .order_by(Message.created_at.desc(), Message.id.desc())
                    .limit(5)
                ).all()
            )
        return [
            HistoryMessage(role=cast(ChatRole, message.role), content=message.content)
            for message in reversed(newest_first)
        ]

    def _load_authority_metadata(
        self,
        document_ids: list[str],
    ) -> dict[str, dict[str, object]]:
        """Resolve metadata for retrieved documents, refreshing legacy PDFs if retained.

        Refreshes are saved. Unreadable retained PDFs log a warning and leave any
        existing metadata usable; documents absent from retrieval are not compared.
        """

        if not document_ids:
            return {}
        metadata_by_document: dict[str, PolicyAuthorityMetadata] = {}
        changed = False
        with self._database.session_factory() as session:
            documents = list(
                session.scalars(
                    select(Document).where(Document.id.in_(set(document_ids)))
                ).all()
            )
            for document in documents:
                metadata: PolicyAuthorityMetadata | None = None
                if document.authority_metadata_json:
                    metadata = PolicyAuthorityMetadata.from_dict(
                        document.authority_metadata_json
                    )
                needs_refresh = (
                    metadata is None
                    or metadata.metadata_version != AUTHORITY_METADATA_VERSION
                )
                if needs_refresh and document.content_bytes:
                    try:
                        metadata = extract_policy_authority(
                            parse_pdf(document.content_bytes).pages
                        )
                        document.authority_metadata_json = metadata.to_dict()
                        changed = True
                    except PdfParseError:
                        logger.warning(
                            "Could not refresh authority metadata for document %s.",
                            document.id,
                        )
                if metadata is not None:
                    metadata_by_document[document.id] = metadata
            if changed:
                session.commit()
        return {
            document_id: metadata.to_dict()
            for document_id, metadata in resolve_policy_authority(
                metadata_by_document
            ).items()
        }

    def _generate_verified_answer(
        self,
        *,
        messages: list[ChatMessage],
        evidence: list[RetrievedChunk],
        question: str,
        authority_by_document: dict[str, dict[str, object]],
        history: list[HistoryMessage],
    ) -> tuple[ModelAnswer, str, list[Citation]]:
        """Return a validated draft and public answer/citations after a passing audit.

        Two cycles allow one correction or malformed-audit recheck using unchanged
        evidence. Repeated invalid output exhausts the budget; other provider failures escape
        immediately. This method does not save messages.
        """

        attempt_messages = list(messages)
        retry_draft: ModelAnswer | None = None
        for attempt in range(MAX_ANSWER_ATTEMPTS):
            model_answer: ModelAnswer | None = None
            try:
                model_answer = retry_draft or self._provider.generate(attempt_messages)
                retry_draft = None
                # Citation integrity is cheap and deterministic; do it before a
                # semantic call. Only citation markers are mapped for public display.
                public_answer, citations = validate_citations(model_answer, evidence)
                try:
                    verification = self._claim_verifier.verify(
                        build_verification_messages(
                            question=question,
                            answer=model_answer,
                            evidence=evidence,
                            authority_by_document=authority_by_document,
                            history=history,
                        )
                    )
                except InvalidModelResponseError:
                    # Invalid audit JSON is not a semantic rejection. Recheck the
                    # existing draft within the same two-attempt budget.
                    retry_draft = model_answer
                    raise
                require_verified_answer(verification, answer=model_answer)
                return model_answer, public_answer, citations
            except InvalidModelResponseError as error:
                if attempt == MAX_ANSWER_ATTEMPTS - 1:
                    raise InvalidModelResponseError(
                        "The assistant could not produce a verifiable cited answer. "
                        "Please try again."
                    ) from error
                logger.warning("Retrying invalid model response (one correction): %s", error)
                if retry_draft is not None:
                    continue
                attempt_messages = list(messages)
                # Redraft from the original task and defects. Repeating the rejected
                # answer as an assistant turn can anchor the next draft to its error.
                attempt_messages.append(
                    ChatMessage(
                        role="user",
                        content=(
                            "Write a fresh answer using the original question and evidence. "
                            f"Review feedback: {error}. Feedback can be mistaken; "
                            "check it against the applicable sources. Address the actual "
                            "requested decision, preserve supported parts and state any "
                            "missing information. Return the required JSON."
                        ),
                    )
                )

        raise AssertionError("unreachable")

    def _persist_turn(
        self,
        *,
        conversation_id: str,
        question: str,
        answer: str,
        citations: list[Citation],
    ) -> None:
        """Commit both messages together, rolling back on failure; status is not stored."""

        with self._database.session_factory() as session:
            try:
                session.add_all(
                    [
                        Message(
                            conversation_id=conversation_id,
                            role=MessageRole.USER,
                            content=question,
                            citations_json=[],
                            created_at=utc_now(),
                        ),
                        Message(
                            conversation_id=conversation_id,
                            role=MessageRole.ASSISTANT,
                            content=answer,
                            citations_json=[
                                citation.model_dump() for citation in citations
                            ],
                            created_at=utc_now(),
                        ),
                    ]
                )
                session.commit()
            except Exception as exc:
                session.rollback()
                raise ChatPersistenceError(
                    "The completed chat turn could not be saved."
                ) from exc

    def chat(self, *, conversation_id: str, question: str) -> ChatResult:
        """Answer within an existing workspace and save only a completed turn.

        Relevance feedback and empty retrieval use local replies without model calls.
        Policy drafts require both validation layers; failed checks save neither
        message. Provider, retrieval and persistence failures propagate to the API.
        """

        history = self._load_history(conversation_id)
        feedback_answer = conversation_feedback_answer(question)
        if feedback_answer is not None:
            self._persist_turn(
                conversation_id=conversation_id,
                question=question,
                answer=feedback_answer,
                citations=[],
            )
            return ChatResult(
                conversation_id=conversation_id,
                status="answered",
                answer=feedback_answer,
                citations=[],
            )

        resolved_question = resolve_question_context(
            question=question,
            history=history,
        )
        retrieval_question = build_retrieval_question(
            question=question,
            history=history,
        )
        expanded_context = needs_expanded_context(resolved_question)
        evidence = self._retrieval.retrieve(
            conversation_id=conversation_id,
            question=retrieval_question,
            top_k=EXPANDED_CONTEXT_TOP_K if expanded_context else None,
            include_document_context=True,
            expand_selected_pages=expanded_context,
        )
        if not evidence:
            answer = (
                "I cannot find indexed policy evidence in this chat. "
                "Upload a policy PDF before asking about its rules."
            )
            self._persist_turn(
                conversation_id=conversation_id,
                question=question,
                answer=answer,
                citations=[],
            )
            return ChatResult(
                conversation_id=conversation_id,
                status="insufficient_context",
                answer=answer,
                citations=[],
            )

        authority_by_document = self._load_authority_metadata(
            [chunk.document_id for chunk in evidence]
        )
        messages = build_chat_messages(
            history=history,
            evidence=evidence,
            question=question,
            authority_by_document=authority_by_document,
        )
        model_answer, public_answer, citations = self._generate_verified_answer(
            messages=messages,
            evidence=evidence,
            question=question,
            authority_by_document=authority_by_document,
            history=history,
        )
        self._persist_turn(
            conversation_id=conversation_id,
            question=question,
            answer=public_answer,
            citations=citations,
        )
        return ChatResult(
            conversation_id=conversation_id,
            status=model_answer.status,
            answer=public_answer,
            citations=citations,
        )
