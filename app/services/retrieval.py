"""Question embedding and conversation-scoped semantic retrieval."""

from app.providers.embeddings import EmbeddingProvider
from app.providers.vector_store import RetrievedChunk, VectorStore


class RetrievalService:
    """Coordinate the small, testable retrieval path used by Stage 4 later."""

    def __init__(
        self,
        *,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
        default_top_k: int = 5,
    ) -> None:
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
        """Retrieve ranked evidence without generating or inferring an answer."""

        if not conversation_id.strip():
            raise ValueError("conversation_id must not be blank.")
        if not question.strip():
            raise ValueError("question must not be blank.")
        result_limit = self._default_top_k if top_k is None else top_k
        if not 1 <= result_limit <= 20:
            raise ValueError("top_k must be between 1 and 20.")

        query_embedding = self._embeddings.embed_query(question.strip())
        results = self._vectors.search(
            query_embedding,
            conversation_id=conversation_id.strip(),
            embedding_model=self._embeddings.model_name,
            top_k=result_limit,
        )
        if not include_document_context or not results:
            return results

        page_limit = result_limit if expand_selected_pages else 2
        strongest_page_keys = list(
            dict.fromkeys(
                (result.document_id, result.page_number) for result in results
            )
        )[:page_limit]
        page_chunks = self._vectors.get_page_chunks(
            conversation_id=conversation_id.strip(),
            embedding_model=self._embeddings.model_name,
            page_keys=strongest_page_keys,
        )
        strongest_document_ids = list(
            dict.fromkeys(result.document_id for result in results)
        )[:2]
        document_starts = self._vectors.get_document_start_chunks(
            conversation_id=conversation_id.strip(),
            embedding_model=self._embeddings.model_name,
            document_ids=strongest_document_ids,
        )
        known_chunk_ids = {result.id for result in results}
        page_companions: list[RetrievedChunk] = []
        for chunk in page_chunks:
            if chunk.id in known_chunk_ids:
                continue
            page_companions.append(chunk)
            known_chunk_ids.add(chunk.id)
            if len(page_companions) == page_limit:
                break
        document_context = [
            chunk for chunk in document_starts if chunk.id not in known_chunk_ids
        ]
        return results + page_companions + document_context
