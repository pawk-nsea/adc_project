"""Validate draft citation markers and map retrieved sources to public PDF/page references."""

import re

from app.providers.llm import InvalidModelResponseError, ModelAnswer
from app.providers.vector_store import RetrievedChunk
from app.schemas import Citation
from app.services.prompt_builder import source_id


SOURCE_MARKER_PATTERN = re.compile(r"\[(S\d+)\]")
SOURCE_GROUP_PATTERN = re.compile(r"\[(S\d+(?:\s*,\s*S\d+)*)\]")
UNVERIFIED_NUMERIC_MARKER_PATTERN = re.compile(r"\[\s*\d+(?:\s*[,;-]\s*\d+)*\s*\]")


def _expand_grouped_markers(text: str) -> str:
    """Expand [S1, S2] into individual markers before applying the same checks."""

    return SOURCE_GROUP_PATTERN.sub(
        lambda match: " ".join(f"[{item.strip()}]" for item in match[1].split(",")),
        text,
    )


def validate_citations(
    answer: ModelAnswer,
    evidence: list[RetrievedChunk],
) -> tuple[str, list[Citation]]:
    """Return public answer text and citations, or raise InvalidModelResponseError.

    Check known source IDs and status/citation consistency, then number pages in
    first-citation order. This checks provenance, not whether a rule supports prose.
    """

    # Reuse prompt order: the model's source numbers are local to this evidence window.
    evidence_by_id = {
        source_id(index): chunk for index, chunk in enumerate(evidence)
    }
    citation_text = _expand_grouped_markers(answer.answer)
    residue = SOURCE_MARKER_PATTERN.sub("", citation_text)
    if re.search(r"\[[^\]\n]*\bS\d+[^\]\n]*\]", residue, re.I):
        raise InvalidModelResponseError("The model returned a malformed source marker.")
    markers = SOURCE_MARKER_PATTERN.findall(citation_text)
    if UNVERIFIED_NUMERIC_MARKER_PATTERN.search(citation_text):
        raise InvalidModelResponseError("The model returned an unverified numeric citation.")
    ordered_markers = list(dict.fromkeys(markers))
    if any(item not in evidence_by_id for item in ordered_markers):
        raise InvalidModelResponseError("The answer cited an unknown source ID.")
    if answer.status == "insufficient_context" and ordered_markers:
        raise InvalidModelResponseError(
            "An insufficient-context response must not cite sources. "
            "If applicable policy facts or limits support the question, use answered, "
            "retain those facts and cite them, even if the full outcome is unknown. "
            "If no applicable rule supports the topic, explain the absence without "
            "policy facts or citations. Do not discard supported information merely "
            "to retain insufficient_context."
        )
    if answer.status != "insufficient_context" and not ordered_markers:
        raise InvalidModelResponseError("A grounded answer must cite a source.")

    public_answer = citation_text
    citations: list[Citation] = []
    citation_number_by_page: dict[tuple[str, int], int] = {}
    for internal_id in ordered_markers:
        chunk = evidence_by_id[internal_id]
        page_key = (chunk.document_id, chunk.page_number)
        # Different fragments of one page share a link; internal IDs remain distinct.
        citation_number = citation_number_by_page.get(page_key)
        if citation_number is None:
            citation_number = len(citations) + 1
            citation_number_by_page[page_key] = citation_number
            citations.append(
                Citation(
                    id=citation_number,
                    document_id=chunk.document_id,
                    filename=chunk.filename,
                    page=chunk.page_number,
                )
            )
        public_answer = public_answer.replace(f"[{internal_id}]", f"[{citation_number}]")
    public_answer = re.sub(r"(\[\d+\])(?:\s+\1)+", r"\1", public_answer)
    return public_answer, citations
