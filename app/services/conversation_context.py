"""Use wording heuristics to resolve follow-ups and select broader retrieval context."""

import re

from app.services.prompt_builder import HistoryMessage


_FOLLOW_UP_REFERENCE = re.compile(
    r"\b(it|that|this|those|these|they|them|one|ones)\b",
    re.IGNORECASE,
)
_FOLLOW_UP_OPENING = re.compile(
    r"^\s*(?:what about\b|how about\b|which one\b|for\b|to\b|in\b|on\b|why\??$)",
    re.IGNORECASE,
)
_DISCOURSE_OPENING = re.compile(r"^\s*(?:(?:and|but|so|then|also)\b[\s,]*)+", re.I)
# Closed-class grammar words help distinguish a demonstrative reference from
# a relative clause after a content word. This is a hint, not a language parser.
_REFERENCE_PREFIXES = {
    "is", "are", "was", "were", "do", "does", "did", "can", "could",
    "should", "would", "will", "may", "might", "must", "about", "for",
    "from", "in", "of", "on", "to", "with", "without", "by", "not",
}
_FOLLOW_UP_CONFIRMATION = re.compile(
    r"^\s*(are you sure|are you certain|is that correct|really|"
    r"what is the source|what's the source|where did that come from|"
    r"are they conflicting|do they conflict)\b",
    re.IGNORECASE,
)
_BARE_SOURCE_FOLLOW_UP = re.compile(
    r"^\s*which\s+(?:documents?|polic(?:y|ies))(?:\s+(?:are|is)\s+"
    r"(?:(?:that|this|it|those|these)(?:\s+from)?|"
    r"current|applicable|conflicting|contradictory|inconsistent))?\s*\??\s*$",
    re.IGNORECASE,
)
_CONVERSATION_FEEDBACK = re.compile(
    r"(?:\b(?:i|we)\s+(?:did\s+not|didn't|never)\s+ask\b|"
    r"\b(?:that|this)\s+(?:is|was)\s+not\s+what\s+(?:i|we)\s+asked\b|"
    r"\bwhy\s+did\s+you\s+(?:mention|include|bring\s+up)\b)",
    re.IGNORECASE,
)
_AUTHORITY_OR_COMPARISON = re.compile(
    r"\b(current|latest|newest|older|old|historical|version|"
    r"supersed\w*|replac\w*|interim|temporary|effective|applicable|"
    r"conflict\w*|contradict\w*|inconsisten\w*|compare|which policy|"
    r"which document|should i use)\b",
    re.IGNORECASE,
)
_EXHAUSTIVE_REQUEST = re.compile(
    r"\b(all|every|each|complete|entire|across the (?:uploaded )?documents)\b",
    re.IGNORECASE,
)

_AUTHORITY_SEARCH_HINT = (
    "Document applicability details: title, policy or reference ID, version, "
    "effective date, organizational and geographic scope, employee group, and "
    "explicit lifecycle language such as supersedes, replacement, interim, "
    "temporary, amendment, or expiration."
)

EXPANDED_CONTEXT_TOP_K = 12


def is_conversation_feedback(question: str) -> bool:
    """Match common relevance complaints; this wording heuristic can misclassify intent."""

    return bool(_CONVERSATION_FEEDBACK.search(question))


def is_dependent_follow_up(question: str) -> bool:
    """Hint whether retrieval needs the previous user topic, using general wording.

    Models receive the current question separately, so this approximate heuristic
    cannot require answering an earlier question again.
    """

    stripped = _DISCOURSE_OPENING.sub("", question).strip()
    words = re.findall(r"\b[\w'-]+\b", stripped.casefold())
    word_count = len(words)
    if (
        _FOLLOW_UP_OPENING.search(stripped)
        or _FOLLOW_UP_CONFIRMATION.search(stripped)
        or _BARE_SOURCE_FOLLOW_UP.fullmatch(stripped)
    ):
        return True
    if word_count <= 8 and re.search(r"\bthe\s+[a-z][\w'-]*\s*\??$", stripped, re.I):
        return True
    if word_count > 12:
        return False
    for index, word in enumerate(words):
        if not _FOLLOW_UP_REFERENCE.fullmatch(word):
            continue
        if (
            word == "that"
            and 0 < index < word_count - 1
            and words[index - 1] not in _REFERENCE_PREFIXES
        ):
            # A clause such as "items that require approval" supplies its own topic.
            continue
        return True
    return False


def resolve_question_context(
    *,
    question: str,
    history: list[HistoryMessage],
) -> str:
    """Build a retrieval hint from a continuation and the latest relevant user turn.

    This combined string is never the task supplied to generation or verification.
    """

    if not is_dependent_follow_up(question):
        return question
    previous_question = next(
        # Assistant prose is not policy evidence; inherit the latest user topic only.
        (
            message.content
            for message in reversed(history)
            if message.role == "user" and not is_conversation_feedback(message.content)
        ),
        None,
    )
    if previous_question is None:
        return question
    return f"{previous_question}\nFollow-up: {question}"


def conversation_feedback_answer(question: str) -> str | None:
    """Acknowledge relevance feedback without pretending it is policy evidence."""

    if not is_conversation_feedback(question):
        return None
    return (
        "You're right. I included information you did not ask for. "
        "I should have kept the answer focused on your question."
    )


def needs_expanded_context(question: str) -> bool:
    """Use a larger evidence window for broad or authority-sensitive questions."""

    return bool(
        _AUTHORITY_OR_COMPARISON.search(question)
        or _EXHAUSTIVE_REQUEST.search(question)
    )


def build_retrieval_question(
    *,
    question: str,
    history: list[HistoryMessage],
) -> str:
    """Give retrieval resolved intent and general authority vocabulary when needed."""

    resolved_question = resolve_question_context(question=question, history=history)
    parts = ["Resolved question: " + resolved_question]
    if _AUTHORITY_OR_COMPARISON.search(resolved_question):
        parts.append(_AUTHORITY_SEARCH_HINT)
    return "\n".join(parts)
