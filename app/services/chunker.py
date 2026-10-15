"""Split extracted pages into bounded embedding inputs with citation provenance."""

import re
from dataclasses import dataclass
from typing import Protocol

from app.services.pdf_parser import ParsedPage


class TokenCounter(Protocol):
    """Require only token counting so chunking can use real or controlled test tokenizers."""

    def count_tokens(self, text: str) -> int:
        """Count input tokens before any embedding-time truncation."""
        ...


@dataclass(frozen=True)
class TextChunk:
    """Indexable text with a stable ID and its workspace, document and PDF page."""

    id: str
    document_id: str
    conversation_id: str
    filename: str
    page_number: int
    chunk_index: int
    text: str


def _join(parts: list[str]) -> str:
    """Combine nonempty text units with paragraph breaks for chunk assembly."""

    return "\n\n".join(part for part in parts if part).strip()


def _split_words(text: str, counter: TokenCounter, target_tokens: int) -> list[str]:
    """Split oversized sentences at whitespace; indivisible words remain intact."""

    words = text.split()
    groups: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join([*current, word])
        if current and counter.count_tokens(candidate) > target_tokens:
            groups.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        groups.append(" ".join(current))
    return groups


def _logical_units(text: str, counter: TokenCounter, target_tokens: int) -> list[str]:
    """Prefer paragraphs, then sentences, then words when a unit exceeds the target."""

    # These are text boundaries, not a PDF layout model; tables can still span units.
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    units: list[str] = []
    for paragraph in paragraphs:
        if counter.count_tokens(paragraph) <= target_tokens:
            units.append(paragraph)
            continue
        sentences = [
            part.strip()
            for part in re.split(r"(?<=[.!?])\s+", paragraph)
            if part.strip()
        ]
        for sentence in sentences:
            if counter.count_tokens(sentence) <= target_tokens:
                units.append(sentence)
            else:
                units.extend(_split_words(sentence, counter, target_tokens))
    return units


def _overlap_suffix(text: str, counter: TokenCounter, overlap_tokens: int) -> str:
    """Copy trailing whole words, keeping at least one even if it exceeds the budget."""

    suffix: list[str] = []
    for word in reversed(text.split()):
        candidate = " ".join(reversed([*suffix, word]))
        if suffix and counter.count_tokens(candidate) > overlap_tokens:
            break
        suffix.append(word)
    return " ".join(reversed(suffix))


def _chunk_page(
    text: str,
    counter: TokenCounter,
    target_tokens: int,
    max_tokens: int,
    overlap_tokens: int,
) -> list[str]:
    """Pack one page's units and reuse a suffix when it fits the hard maximum."""

    units = _logical_units(text, counter, target_tokens)
    chunks: list[str] = []
    current: list[str] = []

    for unit in units:
        candidate = _join([*current, unit])
        if current and counter.count_tokens(candidate) > target_tokens:
            completed = _join(current)
            chunks.append(completed)
            overlap = _overlap_suffix(completed, counter, overlap_tokens)
            current = [overlap] if overlap else []
            candidate = _join([*current, unit])
            if counter.count_tokens(candidate) > max_tokens:
                # Drop repeated context rather than the next unit's original text.
                current = []
        current.append(unit)

    if current:
        chunks.append(_join(current))
    if any(counter.count_tokens(chunk) > max_tokens for chunk in chunks):
        # A single unsplittable word can still exceed the limit; fail explicitly.
        raise ValueError("Chunking produced text above the configured token maximum.")
    return chunks


def create_chunks(
    pages: list[ParsedPage],
    *,
    document_id: str,
    conversation_id: str,
    filename: str,
    counter: TokenCounter,
    target_tokens: int,
    max_tokens: int,
    overlap_tokens: int,
) -> list[TextChunk]:
    """Return page-local chunks with IDs derived from document, page and position.

    The supplied counter must match the embedding tokenizer. Invalid settings or
    an indivisible unit above the maximum raise ValueError; no storage is written.
    """

    if not 0 <= overlap_tokens < target_tokens <= max_tokens:
        raise ValueError("Chunk token settings must satisfy 0 <= overlap < target <= max.")

    chunks: list[TextChunk] = []
    for page in pages:
        page_chunks = _chunk_page(
            page.text,
            counter,
            target_tokens,
            max_tokens,
            overlap_tokens,
        )
        for chunk_index, text in enumerate(page_chunks):
            chunks.append(
                TextChunk(
                    id=f"{document_id}:p{page.page_number:04d}:c{chunk_index:04d}",
                    document_id=document_id,
                    conversation_id=conversation_id,
                    filename=filename,
                    page_number=page.page_number,
                    chunk_index=chunk_index,
                    text=text,
                )
            )
    return chunks
