"""Select workspace evidence using semantic/keyword search and bounded page context."""

import re
from dataclasses import replace

from app.providers.embeddings import EmbeddingProvider
from app.providers.vector_store import RetrievedChunk, VectorStore


class RetrievalService:
    """Rank policy passages and optionally enrich them before either model reads them."""

    def __init__(
        self,
        *,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
        default_top_k: int = 5,
    ) -> None:
        """Bind the shared embedding space and store, rejecting a nonpositive default hit
        count.
        """

        if default_top_k < 1:
            raise ValueError("default_top_k must be at least 1.")
        self._embeddings = embedding_provider
        self._vectors = vector_store
        self._default_top_k = default_top_k

    def retrieve(
        self,
        *,
        conversation_id: str,
        question: str,
        top_k: int | None = None,
        include_document_context: bool = False,
        expand_selected_pages: bool = False,
    ) -> list[RetrievedChunk]:
        """Return evidence filtered by workspace and embedding model.

        top_k limits initial hits to 1–20. Optional context adds headers and page
        companions, then merges selected fragments per page; pages can be partial.
        Embedding/store failures propagate to the caller.
        """

        if not conversation_id.strip():
            raise ValueError("conversation_id must not be blank.")
        if not question.strip():
            raise ValueError("question must not be blank.")
        result_limit = self._default_top_k if top_k is None else top_k
        if not 1 <= result_limit <= 20:
            raise ValueError("top_k must be between 1 and 20.")

        query = question.strip()
        query_embedding = self._embeddings.embed_query(query)
        candidate_limit = min(20, max(result_limit * 2, 10))
        semantic_results = self._vectors.search(
            query_embedding,
            conversation_id=conversation_id.strip(),
            embedding_model=self._embeddings.model_name,
            top_k=candidate_limit,
        )
        keyword_results = self._vectors.keyword_search(
            query,
            conversation_id=conversation_id.strip(),
            embedding_model=self._embeddings.model_name,
            top_k=candidate_limit,
        )
        results = _rerank_hybrid_results(
            semantic_results=semantic_results,
            keyword_results=keyword_results,
            query=query,
            top_k=result_limit,
        )
        if not include_document_context or not results:
            return results

        # A selected page's hit may be an exception detached from its ordinary rule.
        # Fill selected pages before spending the same budget on extra context.
        selected_page_keys = list(
            dict.fromkeys(
                (result.document_id, result.page_number) for result in results
            )
        )
        selected_document_ids = list(dict.fromkeys(result.document_id for result in results))
        document_starts = self._vectors.get_document_start_chunks(
            conversation_id=conversation_id.strip(),
            embedding_model=self._embeddings.model_name,
            document_ids=selected_document_ids,
        )
        # Neighbouring sections can answer a short question even when the best
        # hit is an overview. Keep this expansion local to the strongest hits.
        page_keys = list(selected_page_keys)
        # Definitions, scope and authority can control a passage on another page.
        # Include the first page of every selected document within the same bound.
        for start in document_starts:
            key = (start.document_id, start.page_number)
            if key not in page_keys:
                page_keys.append(key)
        for document_id, page_number in selected_page_keys[:2]:
            for neighbour in (page_number - 1, page_number + 1):
                key = (document_id, neighbour)
                if neighbour >= 1 and key not in page_keys:
                    page_keys.append(key)
        page_chunks = self._vectors.get_page_chunks(
            conversation_id=conversation_id.strip(),
            embedding_model=self._embeddings.model_name,
            page_keys=page_keys,
        )
        known_chunk_ids = {result.id for result in results}
        companions: list[RetrievedChunk] = []
        # Bound additions for large documents; this is context enrichment, not
        # a claim to have reviewed entire documents.
        companion_limit = 24 if expand_selected_pages else 12
        for page_key in page_keys:
            matching = sorted(
                (chunk for chunk in page_chunks
                 if (chunk.document_id, chunk.page_number) == page_key),
                key=lambda chunk: chunk.chunk_index,
            )[:6]
            for chunk in matching:
                if chunk.id not in known_chunk_ids and len(companions) < companion_limit:
                    companions.append(chunk)
                    known_chunk_ids.add(chunk.id)
        document_context = [
            chunk for chunk in document_starts if chunk.id not in known_chunk_ids
        ]
        return _consolidate_pages(results + companions + document_context)


def _consolidate_pages(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """Merge selected fragments per page, removing exact overlap of adjacent chunks.

    This preserves line breaks but does not fetch missing fragments or fill gaps.
    """

    pages: dict[tuple[str, int], list[RetrievedChunk]] = {}
    for chunk in chunks:
        pages.setdefault((chunk.document_id, chunk.page_number), []).append(chunk)
    consolidated: list[RetrievedChunk] = []
    for page_chunks in pages.values():
        ordered = sorted(page_chunks, key=lambda chunk: chunk.chunk_index)
        words: list[str] = []
        fragments: list[str] = []
        previous_index: int | None = None
        for chunk in ordered:
            next_words = chunk.text.split()
            overlap = 0
            if previous_index is not None and chunk.chunk_index == previous_index + 1:
                # Only consecutive chunks have the chunker's deliberate overlap.
                for size in range(min(len(words), len(next_words)), 0, -1):
                    if words[-size:] == next_words[:size]:
                        overlap = size
                        break
            words.extend(next_words[overlap:])
            if overlap < len(next_words):
                # Preserve headings, bullets and table line breaks in the source.
                start = list(re.finditer(r"\S+", chunk.text))[overlap].start()
                fragments.append(chunk.text[start:])
            previous_index = chunk.chunk_index
        # A shared page citation does not imply that every fragment of that page was read.
        consolidated.append(replace(page_chunks[0], text="\n\n".join(fragments)))
    return consolidated


def _rerank_hybrid_results(
    *,
    semantic_results: list[RetrievedChunk],
    keyword_results: list[RetrievedChunk],
    query: str,
    top_k: int,
) -> list[RetrievedChunk]:
    """Fuse dense and keyword ranks, then preserve source-page diversity."""

    chunks = {chunk.id: chunk for chunk in semantic_results}
    chunks.update({chunk.id: chunks.get(chunk.id, chunk) for chunk in keyword_results})
    semantic_rank = {chunk.id: rank for rank, chunk in enumerate(semantic_results, 1)}
    keyword_rank = {chunk.id: rank for rank, chunk in enumerate(keyword_results, 1)}
    keyword_score = {chunk.id: chunk.keyword_score for chunk in keyword_results}
    exact_terms = _exact_query_terms(query)

    scored: list[RetrievedChunk] = []
    for chunk_id, chunk in chunks.items():
        score = 0.0
        if chunk_id in semantic_rank:
            # Dense similarity remains the primary signal required by the case;
            # keyword rank boosts exact terms without overwhelming semantics.
            score += 3.0 / (60 + semantic_rank[chunk_id])
        if chunk_id in keyword_rank:
            score += 0.03 / (60 + keyword_rank[chunk_id])
        normalized_chunk_text = re.sub(r"[\s,]+", "", chunk.text.casefold())
        exact_matches = sum(
            re.sub(r"[\s,]+", "", term) in normalized_chunk_text
            for term in exact_terms
        )
        score += min(exact_matches, 2) * 0.02
        scored.append(
            replace(
                chunk,
                keyword_score=keyword_score.get(chunk_id, 0.0),
                rerank_score=score,
            )
        )
    scored.sort(
        key=lambda chunk: (
            -chunk.rerank_score,
            semantic_rank.get(chunk.id, 10_000),
            keyword_rank.get(chunk.id, 10_000),
        )
    )

    selected: list[RetrievedChunk] = []
    selected_ids: set[str] = set()
    seen_pages: set[tuple[str, int]] = set()
    # Prefer different pages before spending remaining slots on same-page hits.
    for chunk in scored:
        page_key = (chunk.document_id, chunk.page_number)
        if page_key in seen_pages:
            continue
        selected.append(chunk)
        selected_ids.add(chunk.id)
        seen_pages.add(page_key)
        if len(selected) == top_k:
            return selected
    for chunk in scored:
        if chunk.id in selected_ids:
            continue
        selected.append(chunk)
        if len(selected) == top_k:
            break
    return selected


def _exact_query_terms(query: str) -> set[str]:
    """Return identifiers and numeric expressions worth a strong lexical boost."""

    normalized = query.casefold()
    identifiers = re.findall(r"\b[a-z]+(?:[-&][a-z0-9]+)+\b", normalized)
    amounts_and_numbers = re.findall(
        r"(?:\b[a-z]{3}\s*|[$€£¥] ?)\d[\d,]*(?:\.\d+)?\b",
        normalized,
    )
    return set(identifiers + amounts_and_numbers)
