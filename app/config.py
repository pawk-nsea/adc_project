"""Application settings loaded from environment variables."""

from functools import lru_cache

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings with safe local defaults."""

    app_name: str = "Apex Global Policy Assistant"
    database_url: str = "sqlite:///data/runtime/app.db"
    vector_store_path: str = "data/runtime/chroma"
    vector_collection_name: str = "policy_chunks"
    model_cache_path: str = "data/model-cache"
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = Field(default=384, gt=0)
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, gt=0)
    chunk_target_tokens: int = Field(default=180, gt=0)
    chunk_max_tokens: int = Field(default=220, gt=0)
    chunk_overlap_tokens: int = Field(default=30, ge=0)
    chunking_version: str = "v1"
    retrieval_top_k: int = Field(default=5, ge=1, le=20)
    gemini_api_key: SecretStr | None = None
    chat_model: str = "gemini-3.5-flash-lite"
    chat_temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    chat_max_output_tokens: int = Field(default=1000, gt=0)
    chat_timeout_seconds: int = Field(default=60, gt=0)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="ADC_",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_chunk_window(self) -> "Settings":
        if not (
            self.chunk_overlap_tokens
            < self.chunk_target_tokens
            <= self.chunk_max_tokens
        ):
            raise ValueError(
                "Chunk settings must satisfy overlap < target <= maximum."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Return one settings instance for the default application."""

    return Settings()
