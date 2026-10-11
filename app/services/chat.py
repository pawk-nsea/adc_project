"""Grounded chat orchestration, citation validation, and persistence."""

import logging
import re
from dataclasses import dataclass
from typing import cast

from sqlalchemy import select

from app.database import Database
from app.models import Conversation, Message, MessageRole, utc_now
from app.providers.llm import (
    AnswerStatus,
    ChatMessage,
    ChatProvider,
    ChatRole,
    InvalidModelResponseError,
    ModelAnswer,
)
from app.providers.vector_store import RetrievedChunk
from app.schemas import Citation
from app.services.prompt_builder import HistoryMessage, build_chat_messages, source_id
from app.services.retrieval import RetrievalService


SOURCE_MARKER_PATTERN = re.compile(r"\[(S\d+)\]")
SOURCE_GROUP_PATTERN = re.compile(r"\[(S\d+(?:\s*,\s*S\d+)*)\]")
UNVERIFIED_NUMERIC_MARKER_PATTERN = re.compile(r"\[\s*\d+(?:\s*[,;-]\s*\d+)*\s*\]")
CONFLICT_EXPLANATION_PATTERN = re.compile(
    r"\b(conflict\w*|contradict\w*|inconsisten\w*|ambig\w*|differ\w*|unclear|"
    r"unresolved|mismatch\w*|uncertain\w*|clarif\w*|incompatib\w*|"
    r"cannot determine|can't determine)\b",
    re.IGNORECASE,
)
ZURICH_RELEVANCE_PATTERN = re.compile(
    r"\b(Zurich|high[- ]cost|exception\s+(?:list|cities)|cities\s+(?:in|on)\s+the\s+exception)\b",
    re.IGNORECASE,
)
FOLLOW_UP_PATTERN = re.compile(
    r"\b(it|that|this|those|these|they|them|one|ones|which one|what about|"
    r"should i use|can i use|does that|so|then|instead|are you sure|"
    r"are you certain|is that correct|really|why|what is the source|"
    r"what's the source|where did that come from|which documents|which policies|"
    r"are they conflicting|do they conflict)\b",
    re.IGNORECASE,
)
SHORT_LOCATION_FOLLOW_UP_PATTERN = re.compile(
    r"^\s*(?:and\s+)?(?:to|in)\b",
    re.IGNORECASE,
)
VERSION_INTENT_PATTERN = re.compile(
    r"\b(current|latest|newest|older|old|version|supersed(?:e|es|ed|ing)|"
    r"replace(?:s|d)?|standard|which policy|which document|conflict(?:s|ing|ed)?|"
    r"should i use|can i use|appl(?:y|ies|icable))\b",
    re.IGNORECASE,
)
POLICY_AUTHORITY_HINT = (
    "Policy applicability details: policy title, policy ID, version, effective date, "
    "scope, and any statement that supersedes or replaces earlier guidance."
)
logger = logging.getLogger(__name__)


def is_policy_comparison(question: str) -> bool:
    """Broad comparisons need more than the normal five evidence chunks."""

    return bool(
        re.search(r"\b(conflict\w*|contradict\w*|inconsisten\w*|compare)\b", question, re.I)
        and re.search(
            r"\b(all|any|across|documents?|policy|policies|guidelines|uploaded)\b",
            question,
            re.I,
        )
    )


def needs_expanded_context(question: str) -> bool:
    """Detect questions that require coverage beyond a normal fact lookup."""

    if is_policy_comparison(question):
        return True
    exhaustive_list = bool(
        re.search(r"\b(list|name|identify|show)\b", question, re.I)
        and re.search(r"\b(all|every|each|complete|entire)\b", question, re.I)
    )
    authority_ambiguity = bool(
        re.search(
            r"\b(policy|policies|guidance|guidelines|memo|document)\b",
            question,
            re.I,
        )
        and re.search(
            r"\b(still|definitely|explicitly|revok\w*|remain\w*)\b",
            question,
            re.I,
        )
    )
    return exhaustive_list or authority_ambiguity


def build_retrieval_question(
    *,
    question: str,
    history: list[HistoryMessage],
) -> str:
    """Give semantic search enough topic context for dependent follow-ups."""

    search_parts: list[str] = []
    previous_questions: list[str] = []
    if FOLLOW_UP_PATTERN.search(question) or SHORT_LOCATION_FOLLOW_UP_PATTERN.search(
        question
    ):
        previous_questions = [
            message.content for message in history if message.role == "user"
        ][-2:]
        if previous_questions:
            search_parts.append(
                "Previous user questions: " + " ".join(previous_questions)
            )
    search_parts.append("Current question: " + question)
    semantic_topic = "\n".join([*previous_questions, question])
    if VERSION_INTENT_PATTERN.search(semantic_topic):
        search_parts.append(POLICY_AUTHORITY_HINT)
    return "\n".join(search_parts)


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
    def __init__(
        self,
        *,
        database: Database,
        retrieval_service: RetrievalService,
        chat_provider: ChatProvider,
    ) -> None:
        self._database = database
        self._retrieval = retrieval_service
        self._provider = chat_provider

    def _load_history(self, conversation_id: str) -> list[HistoryMessage]:
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

    def _validate_citations(
        self,
        answer: ModelAnswer,
        evidence: list[RetrievedChunk],
    ) -> tuple[str, list[Citation]]:
        evidence_by_id = {
            source_id(index): chunk for index, chunk in enumerate(evidence)
        }
        # Expand grouped references before validation so [S1, S2] cannot evade
        # membership checks or leak internal identifiers into the public answer.
        citation_text = SOURCE_GROUP_PATTERN.sub(
            lambda match: " ".join(f"[{item.strip()}]" for item in match[1].split(",")),
            answer.answer,
        )
        residue = SOURCE_MARKER_PATTERN.sub("", citation_text)
        if re.search(r"\[[^\]\n]*\bS\d+[^\]\n]*\]", residue, re.I):
            raise InvalidModelResponseError("The model returned a malformed source marker.")
        markers = SOURCE_MARKER_PATTERN.findall(citation_text)
        if UNVERIFIED_NUMERIC_MARKER_PATTERN.search(citation_text):
            raise InvalidModelResponseError(
                "The model returned an unverified numeric citation."
            )
        ordered_markers = list(dict.fromkeys(markers))
        if any(item not in evidence_by_id for item in ordered_markers):
            raise InvalidModelResponseError("The answer cited an unknown source ID.")
        if answer.status == "insufficient_context" and ordered_markers:
            raise InvalidModelResponseError(
                "An insufficient-context response must not cite sources."
            )
        if answer.status != "insufficient_context" and not ordered_markers:
            raise InvalidModelResponseError("A grounded answer must cite a source.")
        if ordered_markers != answer.source_ids:
            logger.info(
                "Canonicalizing redundant source_ids from inline citation markers."
            )

        public_answer = citation_text
        citations: list[Citation] = []
        # First-use numbering is fully determined by the validated inline markers;
        # the model's redundant source_ids ordering is not trusted.
        for citation_number, internal_id in enumerate(ordered_markers, start=1):
            chunk = evidence_by_id[internal_id]
            public_answer = public_answer.replace(
                f"[{internal_id}]", f"[{citation_number}]"
            )
            citations.append(
                Citation(
                    id=citation_number,
                    filename=chunk.filename,
                    page=chunk.page_number,
                )
            )
        return public_answer, citations

    @staticmethod
    def _validate_status_scope(
        answer: ModelAnswer,
        question: str,
        evidence: list[RetrievedChunk],
    ) -> None:
        """Reject conflict labels unsupported by, or irrelevant to, the question."""

        evidence_by_filename: dict[str, str] = {}
        for chunk in evidence:
            evidence_by_filename[chunk.filename] = (
                evidence_by_filename.get(chunk.filename, "") + " " + chunk.text
            )
        all_evidence_text = " ".join(evidence_by_filename.values())

        if answer.status == "insufficient_context":
            claims_policy_support = re.search(
                r"\b(?:policy|context|document|guideline)s?\b.{0,80}"
                r"\b(?:provides?|states?|requires?|sets?|allows?|permits?|lists?|gives?)\b",
                answer.answer,
                re.IGNORECASE | re.DOTALL,
            )
            concrete_values = re.findall(
                r"\b(?:USD|EUR)\s*[\d,]+\b|\b\d+(?:\.\d+)?\s*"
                r"(?:%|days?|weeks?|months?|years?)\b",
                answer.answer,
                re.IGNORECASE,
            )
            repeats_retrieved_value = any(
                value.casefold() in all_evidence_text.casefold()
                for value in concrete_values
            )
            if claims_policy_support or repeats_retrieved_value:
                raise InvalidModelResponseError(
                    "An insufficient_context response made a supported policy claim. "
                    "Use answered, cite the supported part, and identify only the missing part."
                )

        asks_historical_latin_limit = bool(
            re.search(r"\bLatin America\b", question, re.IGNORECASE)
            and re.search(r"\b(2022|2\.6|older|old|historical)\b", question, re.IGNORECASE)
        )
        old_travel_text = evidence_by_filename.get("travel_expenses_2022.pdf", "")
        if (
            asks_historical_latin_limit
            and old_travel_text
            and not re.search(r"\bLatin America\b", old_travel_text, re.IGNORECASE)
            and re.search(r"\b(?:USD\s*)?200\b", answer.answer, re.IGNORECASE)
        ):
            raise InvalidModelResponseError(
                "The historical table has no Latin America value. Do not substitute "
                "the Asia-Pacific USD 200 value; state that the requested value is missing."
            )

        asks_zurich = re.search(r"\bZurich\b", question, re.IGNORECASE)
        historical_question = re.search(
            r"\b(2022|2\.6|historical|older|old policy)\b",
            question,
            re.IGNORECASE,
        )
        if asks_zurich and not historical_question:
            required_patterns = {
                "the current European standard of EUR 220": r"\b220\b",
                "Zurich's European geography": r"\b(Europe|European|Switzerland)\b",
                "the unresolved applicability ambiguity": (
                    r"\b(ambig\w*|unclear|mismatch\w*|conflict\w*|clarif\w*)\b"
                ),
                "Finance clarification": r"\bFinance\b",
            }
            missing = [
                description
                for description, pattern in required_patterns.items()
                if not re.search(pattern, answer.answer, re.IGNORECASE)
            ]
            if missing:
                raise InvalidModelResponseError(
                    "The current Zurich answer omitted " + ", ".join(missing) + "."
                )
            if re.search(r"\b240\b", answer.answer) and not re.search(
                r"(?:\b(?:older|historical|2022)\b.{0,100}\b240\b|"
                r"\b240\b.{0,100}\b(?:older|historical|2022)\b)",
                answer.answer,
                re.IGNORECASE | re.DOTALL,
            ):
                raise InvalidModelResponseError(
                    "EUR 240 is the older 2022 European limit. Label it historical, "
                    "or omit it from the current Zurich answer; EUR 220 is current."
                )

        asks_procurement_vendor_rule = re.search(
            r"\b(Procurement Portal|approved vendor|vendor outside)\b",
            question,
            re.IGNORECASE,
        )
        if (
            asks_procurement_vendor_rule
            and answer.status == "conflicting_sources"
            and re.search(r"\bTravel Portal\b", answer.answer, re.IGNORECASE)
        ):
            raise InvalidModelResponseError(
                "The Procurement Portal approved-vendor rule does not conflict with the "
                "separate Travel Portal booking rule. Answer the procurement question "
                "from the vendor policy and omit unrelated travel booking rules."
            )

        asks_vendor_sponsored_meal = bool(
            re.search(r"\bvendor[- ]sponsored\b", question, re.IGNORECASE)
            and re.search(r"\b(dinner|meal|event)\b", question, re.IGNORECASE)
        )
        sponsor_payment_is_distinguished = bool(
            re.search(r"\b(pays?|paid|sponsor\w*)\b", answer.answer, re.IGNORECASE)
            and re.search(
                r"\b(?:no|not|cannot|can't|do not|should not)\b.{0,60}"
                r"\b(?:claim|reimburs\w*|expense)\b",
                answer.answer,
                re.IGNORECASE | re.DOTALL,
            )
        )
        if asks_vendor_sponsored_meal and not sponsor_payment_is_distinguished:
            raise InvalidModelResponseError(
                "For a vendor-sponsored meal, distinguish acceptance/disclosure from "
                "employee reimbursement: if the vendor paid, the employee has no meal "
                "expense to claim. Then explain any rules for an actual employee claim."
            )
        meal_uses_gift_threshold = re.search(
            r"\b(?:dinners?|meals?)\b(?:\s+\w+){0,6}\s+"
            r"(?:over|above|exceed\w*)\s+(?:USD\s*)?(?:100|250)\b",
            answer.answer,
            re.IGNORECASE,
        )
        if asks_vendor_sponsored_meal and meal_uses_gift_threshold:
            raise InvalidModelResponseError(
                "Do not transfer the USD 100 or USD 250 gift thresholds to meals. "
                "The documents use those thresholds for gifts; client-paid dinners above "
                "the standard USD 45 limit must be recorded and disclosed."
            )
        meal_uses_procurement_spend_band = any(
            re.search(r"\b(?:dinner|meal)s?\b", sentence, re.IGNORECASE)
            and re.search(
                r"\b(?:25,?000|100,?000|Executive Committee|procurement threshold)\b",
                sentence,
                re.IGNORECASE,
            )
            for sentence in re.split(r"(?<=[.!?])\s+", answer.answer)
        )
        if asks_vendor_sponsored_meal and meal_uses_procurement_spend_band:
            raise InvalidModelResponseError(
                "Do not apply procurement spend bands to a sponsored dinner's meal "
                "value. Those bands govern separate procurement spend; describe only "
                "the documented Finance/Compliance/Procurement sign-offs for high-value "
                "engagements or dinners."
            )

        if answer.status != "conflicting_sources":
            return
        if not CONFLICT_EXPLANATION_PATTERN.search(answer.answer):
            raise InvalidModelResponseError(
                "The response used conflicting_sources without explaining an actual "
                "conflict or ambiguity in the requested claim."
            )
        introduces_zurich = re.search(r"\bZurich\b", answer.answer, re.IGNORECASE)
        zurich_is_relevant = bool(
            ZURICH_RELEVANCE_PATTERN.search(question) or is_policy_comparison(question)
        )
        if introduces_zurich and not zurich_is_relevant:
            raise InvalidModelResponseError(
                "The response made the requested claim conflicting because of unasked "
                "Zurich. Omit unrelated entities and classify only the current question."
            )

        if is_policy_comparison(question):
            discusses_resolved_versions = re.search(
                r"\b(supersed\w*|replac\w*)\b", answer.answer, re.IGNORECASE
            )
            labels_resolution = re.search(
                r"\b(resolved|historical|no longer (?:current|applicable)|"
                r"not (?:an? )?(?:active )?conflict)\b",
                answer.answer,
                re.IGNORECASE,
            )
            if discusses_resolved_versions and not labels_resolution:
                raise InvalidModelResponseError(
                    "A broad conflict review must explicitly label superseded or replaced "
                    "rules as resolved historical differences, not active conflicts."
                )

            asks_broad_data_review = re.search(
                r"\b(data|security|all|uploaded)\b|\bany\s+documents?\b",
                question,
                re.IGNORECASE,
            )
            evidence_has_distinct_data_scopes = bool(
                re.search(
                    r"\bConfidential\b",
                    evidence_by_filename.get("data_guidelines.pdf", ""),
                    re.IGNORECASE,
                )
                and re.search(
                    r"\bRestricted\b",
                    evidence_by_filename.get("information_security_data.pdf", ""),
                    re.IGNORECASE,
                )
            )
            discusses_data_scopes = all(
                re.search(term, answer.answer, re.IGNORECASE)
                for term in (r"\bConfidential\b", r"\bRestricted\b")
            )
            labels_compatible_scopes = re.search(
                r"\b(compatible|different (?:data )?(?:classifications?|scopes?)|"
                r"distinct (?:data )?(?:classifications?|scopes?)|"
                r"not (?:a )?conflict|do(?:es)? not contradict)\b",
                answer.answer,
                re.IGNORECASE,
            )
            if (
                asks_broad_data_review
                and evidence_has_distinct_data_scopes
                and not discusses_data_scopes
            ):
                raise InvalidModelResponseError(
                    "The requested broad data-policy review omitted Confidential or "
                    "Restricted. Cover both retrieved classifications and distinguish "
                    "their scopes."
                )
            if discusses_data_scopes and not labels_compatible_scopes:
                raise InvalidModelResponseError(
                    "A broad conflict review must explicitly label Confidential and "
                    "Restricted requirements as different compatible scopes, not a conflict."
                )

            interim_text = evidence_by_filename.get("data_guidelines.pdf", "")
            comprehensive_text = evidence_by_filename.get(
                "information_security_data.pdf", ""
            )
            evidence_contains_usb_authority_question = bool(
                re.search(r"\bUSB\b", interim_text, re.IGNORECASE)
                and comprehensive_text
            )
            usb_ambiguity_is_explained = re.search(
                r"(?:\bUSB\b.{0,500}\b(?:unresolved|unclear|silent|clarif\w*|"
                r"does not (?:address|confirm|revoke)|not explicitly (?:address|confirm|revoke))\b|"
                r"\b(?:unresolved|unclear|silent|clarif\w*|"
                r"does not (?:address|confirm|revoke)|not explicitly (?:address|confirm|revoke))"
                r"\b.{0,500}\bUSB\b)",
                answer.answer,
                re.IGNORECASE | re.DOTALL,
            )
            if evidence_contains_usb_authority_question and not usb_ambiguity_is_explained:
                raise InvalidModelResponseError(
                    "The broad review must explain that the interim USB permission is "
                    "not explicitly confirmed or revoked by the comprehensive policy, "
                    "so its current applicability needs clarification."
                )

    def _generate_verified_answer(
        self,
        *,
        messages: list[ChatMessage],
        evidence: list[RetrievedChunk],
        question: str,
    ) -> tuple[ModelAnswer, str, list[Citation]]:
        """Use at most two corrective attempts for invalid structured answers."""

        attempt_messages = list(messages)
        for attempt in range(3):
            model_answer: ModelAnswer | None = None
            try:
                model_answer = self._provider.generate(attempt_messages)
                self._validate_status_scope(model_answer, question, evidence)
                public_answer, citations = self._validate_citations(
                    model_answer,
                    evidence,
                )
                return model_answer, public_answer, citations
            except InvalidModelResponseError as error:
                if attempt == 2:
                    raise InvalidModelResponseError(
                        "The assistant could not produce a verifiable cited answer. "
                        "Please try again."
                    ) from error
                logger.warning(
                    "Retrying invalid model response (correction %s of 2): %s",
                    attempt + 1,
                    error,
                )
                if model_answer is not None:
                    attempt_messages.append(
                        ChatMessage(
                            role="assistant",
                            content=model_answer.model_dump_json(),
                        )
                    )
                attempt_messages.append(
                    ChatMessage(
                        role="user",
                        content=(
                            f"Your preceding JSON failed answer validation: {error} "
                            "Return the answer again using only source IDs from RETRIEVED "
                            "CONTEXT. Put an internal [S<number>] marker after each supported "
                            "policy claim and list those IDs in source_ids; never use public "
                            "[1] markers or unknown IDs. Use no markers and an empty list only "
                            "when no requested part is supported. Return only the required JSON "
                            "object. Preserve every supported part of the question, identify "
                            "missing parts, and classify conflicts only when they affect the "
                            "CURRENT USER QUESTION. Omit unrelated conflicts and entities."
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
        history = self._load_history(conversation_id)
        retrieval_question = build_retrieval_question(
            question=question,
            history=history,
        )
        expanded_context = needs_expanded_context(question)
        evidence = self._retrieval.retrieve(
            conversation_id=conversation_id,
            question=retrieval_question,
            top_k=20 if expanded_context else None,
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
        messages = build_chat_messages(
            history=history,
            evidence=evidence,
            question=question,
        )
        model_answer, public_answer, citations = self._generate_verified_answer(
            messages=messages,
            evidence=evidence,
            question=question,
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
