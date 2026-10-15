"""Provide local MiniLM vectors and tokenizer counts for ingestion and retrieval."""

from pathlib import Path
from typing import Protocol


class EmbeddingProvider(Protocol):
    """Shared document/query vector space and token counter used for chunk sizing."""

    model_name: str
    dimension: int
    max_input_tokens: int

    def count_tokens(self, text: str) -> int: ...

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class OnnxMiniLmEmbeddingProvider:
    """Run all-MiniLM-L6-v2 locally through Chroma's ONNX adapter."""

    max_input_tokens = 256

    def __init__(self, cache_path: str, model_name: str, dimension: int) -> None:
        from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

        self.model_name = model_name
        self.dimension = dimension
        self._model = ONNXMiniLM_L6_V2(preferred_providers=["CPUExecutionProvider"])
        # Chroma otherwise writes to ~/.cache, which makes project state less visible.
        self._model.DOWNLOAD_PATH = Path(cache_path) / "all-MiniLM-L6-v2"
        self._counting_tokenizer = None

    def _tokenizer(self):
        """Lazily load an untruncated counting tokenizer, downloading if needed."""

        if self._counting_tokenizer is None:
            # Chroma has no public prepare method. This verified download also makes
            # tokenizer.json available before the first embedding call.
            self._model._download_model_if_not_exists()
            tokenizer_path = (
                self._model.DOWNLOAD_PATH
                / self._model.EXTRACTED_FOLDER_NAME
                / "tokenizer.json"
            )
            self._counting_tokenizer = self._model.Tokenizer.from_file(
                str(tokenizer_path)
            )
            # tokenizer.json carries inference-time padding/truncation defaults.
            # Disable both so chunk sizing sees the complete, natural token count.
            self._counting_tokenizer.no_padding()
            self._counting_tokenizer.no_truncation()
        return self._counting_tokenizer

    def count_tokens(self, text: str) -> int:
        """Count untruncated model word pieces, including special tokens."""

        return len(self._tokenizer().encode(text).ids)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input, checking dimensions; empty input skips inference.

        The adapter may download/cache the model and truncates inputs at 256 tokens.
        """

        if not texts:
            return []
        embeddings = self._model(texts)
        result = [embedding.tolist() for embedding in embeddings]
        if any(len(embedding) != self.dimension for embedding in result):
            raise ValueError("Embedding model returned an unexpected dimension.")
        return result

    def embed_query(self, text: str) -> list[float]:
        """Embed a question in the same vector space as document chunks."""

        return self.embed_documents([text])[0]
