"""Vector-store boundary and persistent Chroma implementation."""

from dataclasses import dataclass
from typing import Protocol

from app.services.chunker import TextChunk


@dataclass(frozen=True)
class RetrievedChunk:
    """One ranked vector-search result with citation provenance."""

    id: str
    text: str
    conversation_id: str
    document_id: str
    filename: str
    page_number: int
    chunk_index: int
    distance: float
    similarity: float


class VectorStore(Protocol):
    def add_chunks(
        self,
        chunks: list[TextChunk],
        embeddings: list[list[float]],
        *,
        embedding_model: str,
        chunking_version: str,
    ) -> None: ...

    def delete_document(self, document_id: str) -> None: ...

    def count_document_chunks(self, document_id: str) -> int: ...

    def search(
        self,
        query_embedding: list[float],
        *,
        conversation_id: str,
        embedding_model: str,
        top_k: int,
    ) -> list[RetrievedChunk]: ...

    def get_document_start_chunks(
        self,
        *,
        conversation_id: str,
        embedding_model: str,
        document_ids: list[str],
    ) -> list[RetrievedChunk]: ...

    def get_page_chunks(
        self,
        *,
        conversation_id: str,
        embedding_model: str,
        page_keys: list[tuple[str, int]],
    ) -> list[RetrievedChunk]: ...


class ChromaVectorStore:
    """Store precomputed vectors and source provenance in local Chroma."""

    def __init__(self, path: str, collection_name: str) -> None:
        import chromadb

        self._client = chromadb.PersistentClient(path=path)
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            embedding_function=None,
            configuration={"hnsw": {"space": "cosine"}},
        )

    def add_chunks(
        self,
        chunks: list[TextChunk],
        embeddings: list[list[float]],
        *,
        embedding_model: str,
        chunking_version: str,
    ) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("Each chunk must have exactly one embedding.")
        self._collection.add(
            ids=[chunk.id for chunk in chunks],
            embeddings=embeddings,
            documents=[chunk.text for chunk in chunks],
            metadatas=[
                {
                    "conversation_id": chunk.conversation_id,
                    "document_id": chunk.document_id,
                    "filename": chunk.filename,
                    "page_number": chunk.page_number,
                    "chunk_index": chunk.chunk_index,
                    "embedding_model": embedding_model,
                    "chunking_version": chunking_version,
                }
                for chunk in chunks
            ],
        )

    def delete_document(self, document_id: str) -> None:
        self._collection.delete(where={"document_id": document_id})

    def count_document_chunks(self, document_id: str) -> int:
        records = self._collection.get(
            where={"document_id": document_id},
            include=[],
        )
        return len(records["ids"])

    def search(
        self,
        query_embedding: list[float],
        *,
        conversation_id: str,
        embedding_model: str,
        top_k: int,
    ) -> list[RetrievedChunk]:
        """Return nearest chunks from one conversation and model version."""

        result = self._collection.query(
            query_embeddings=[query_embedding],
            # Fetch extra candidates, then prevent adjacent chunks from one PDF
            # page from consuming the entire context budget.
            n_results=top_k * 3,
            where={
                "$and": [
                    {"conversation_id": conversation_id},
                    {"embedding_model": embedding_model},
                ]
            },
            include=["documents", "metadatas", "distances"],
        )
        ids = result.get("ids") or [[]]
        documents = result.get("documents") or [[]]
        metadatas = result.get("metadatas") or [[]]
        distances = result.get("distances") or [[]]

        candidates: list[RetrievedChunk] = []
        seen_pages: set[tuple[str, int]] = set()
        for chunk_id, text, metadata, distance in zip(
            ids[0], documents[0], metadatas[0], distances[0], strict=True
        ):
            if text is None or metadata is None:
                raise ValueError("Vector result is missing text or provenance metadata.")
            document_id = str(metadata["document_id"])
            page_number = int(metadata["page_number"])
            cosine_distance = float(distance)
            candidates.append(
                RetrievedChunk(
                    id=chunk_id,
                    text=text,
                    conversation_id=str(metadata["conversation_id"]),
                    document_id=document_id,
                    filename=str(metadata["filename"]),
                    page_number=page_number,
                    chunk_index=int(metadata["chunk_index"]),
                    distance=cosine_distance,
                    similarity=1.0 - cosine_distance,
                )
            )

        # First preserve the page diversity that protects cross-page questions.
        # If fewer than `top_k` distinct pages exist, use the remaining budget for
        # additional relevant chunks from those pages. A strict one-chunk-per-page
        # rule can otherwise hide a baseline rule when an exception is split into
        # a neighboring chunk on the same PDF page.
        retrieved: list[RetrievedChunk] = []
        selected_ids: set[str] = set()
        for candidate in candidates:
            page_key = (candidate.document_id, candidate.page_number)
            if page_key in seen_pages:
                continue
            seen_pages.add(page_key)
            selected_ids.add(candidate.id)
            retrieved.append(candidate)
            if len(retrieved) == top_k:
                return retrieved

        for candidate in candidates:
            if candidate.id in selected_ids:
                continue
            selected_ids.add(candidate.id)
            if len(selected_ids) == top_k:
                break
        return [candidate for candidate in candidates if candidate.id in selected_ids]

    def get_document_start_chunks(
        self,
        *,
        conversation_id: str,
        embedding_model: str,
        document_ids: list[str],
    ) -> list[RetrievedChunk]:
        """Return the first stored chunk for each requested document in order."""

        starts: list[RetrievedChunk] = []
        for document_id in dict.fromkeys(document_ids):
            result = self._collection.get(
                where={
                    "$and": [
                        {"conversation_id": conversation_id},
                        {"embedding_model": embedding_model},
                        {"document_id": document_id},
                    ]
                },
                include=["documents", "metadatas"],
            )
            candidates: list[tuple[str, str, dict[str, object]]] = []
            for chunk_id, text, metadata in zip(
                result.get("ids") or [],
                result.get("documents") or [],
                result.get("metadatas") or [],
                strict=True,
            ):
                if text is None or metadata is None:
                    raise ValueError(
                        "Vector result is missing text or provenance metadata."
                    )
                candidates.append((chunk_id, text, metadata))
            if not candidates:
                continue

            chunk_id, text, metadata = min(
                candidates,
                key=lambda item: (
                    int(item[2]["page_number"]),
                    int(item[2]["chunk_index"]),
                ),
            )
            starts.append(
                RetrievedChunk(
                    id=chunk_id,
                    text=text,
                    conversation_id=str(metadata["conversation_id"]),
                    document_id=str(metadata["document_id"]),
                    filename=str(metadata["filename"]),
                    page_number=int(metadata["page_number"]),
                    chunk_index=int(metadata["chunk_index"]),
                    distance=1.0,
                    similarity=0.0,
                )
            )
        return starts

    def get_page_chunks(
        self,
        *,
        conversation_id: str,
        embedding_model: str,
        page_keys: list[tuple[str, int]],
    ) -> list[RetrievedChunk]:
        """Return every stored chunk for requested document pages in page order."""

        page_chunks: list[RetrievedChunk] = []
        for document_id, page_number in dict.fromkeys(page_keys):
            result = self._collection.get(
                where={
                    "$and": [
                        {"conversation_id": conversation_id},
                        {"embedding_model": embedding_model},
                        {"document_id": document_id},
                        {"page_number": page_number},
                    ]
                },
                include=["documents", "metadatas"],
            )
            candidates: list[RetrievedChunk] = []
            for chunk_id, text, metadata in zip(
                result.get("ids") or [],
                result.get("documents") or [],
                result.get("metadatas") or [],
                strict=True,
            ):
                if text is None or metadata is None:
                    raise ValueError(
                        "Vector result is missing text or provenance metadata."
                    )
                candidates.append(
                    RetrievedChunk(
                        id=chunk_id,
                        text=text,
                        conversation_id=str(metadata["conversation_id"]),
                        document_id=str(metadata["document_id"]),
                        filename=str(metadata["filename"]),
                        page_number=int(metadata["page_number"]),
                        chunk_index=int(metadata["chunk_index"]),
                        distance=1.0,
                        similarity=0.0,
                    )
                )
            page_chunks.extend(
                sorted(candidates, key=lambda chunk: chunk.chunk_index)
            )
        return page_chunks
