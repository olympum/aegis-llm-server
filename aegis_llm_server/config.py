"""Runtime settings for aegis-llm-server."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_EMBEDDING_ALIASES = (
    "nomic-embed-text",
    "nomic-ai/nomic-embed-text-v1.5",
    "nomic-embed-code",
    "nomic-ai/nomic-embed-code",
    "text-embedding-3-small",
)


class ServerConfig(BaseModel):
    """HTTP server settings."""

    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8181)


class EmbeddingConfig(BaseModel):
    """Embedding backend settings."""

    enabled: bool = Field(default=True)
    backend: Literal["deterministic", "sentence_transformers"] = Field(default="deterministic")
    model_name: str = Field(default="nomic-ai/nomic-embed-text-v1.5")
    trust_remote_code: bool = Field(default=True)
    dimension: int = Field(default=768, ge=8, le=8192)
    normalize: bool = Field(default=True)
    max_batch_size: int = Field(default=64, ge=1, le=2048)
    max_input_chars: int = Field(default=32768, ge=1, le=1_000_000)
    max_total_chars: int = Field(default=262144, ge=1, le=5_000_000)
    backend_timeout_seconds: float = Field(default=30.0, gt=0.0, le=600.0)


class TelemetryConfig(BaseModel):
    """OpenTelemetry configuration."""

    enabled: bool = Field(default=False)
    otlp_endpoint: str = Field(default="http://127.0.0.1:4318")
    otlp_timeout_seconds: float = Field(default=10.0, gt=0.0, le=120.0)
    metrics_export_interval_ms: int = Field(default=5000, ge=250, le=60000)
    sample_ratio: float = Field(default=1.0, ge=0.0, le=1.0)
    otlp_headers: dict[str, str] = Field(default_factory=dict)


class Settings(BaseSettings):
    """Service settings loaded from environment."""

    model_config = SettingsConfigDict(
        env_prefix="AEGIS_LLM_SERVER_",
        env_nested_delimiter="__",
    )

    service_name: str = Field(default="aegis-llm-server")
    service_version: str = Field(default="0.1.0")

    server: ServerConfig = Field(default_factory=ServerConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    telemetry: TelemetryConfig = Field(default_factory=TelemetryConfig)

    def resolve_embedding_model(self, requested_model: str) -> str | None:
        """Map accepted public aliases to the configured local backend model."""
        if not requested_model:
            return self.embedding.model_name
        if requested_model == self.embedding.model_name:
            return self.embedding.model_name
        if requested_model in DEFAULT_EMBEDDING_ALIASES:
            return self.embedding.model_name
        return None

    def public_embedding_models(self) -> list[str]:
        """Public model identifiers advertised to clients."""
        values = list(DEFAULT_EMBEDDING_ALIASES)
        if self.embedding.model_name not in values:
            values.append(self.embedding.model_name)
        return values


_settings: Settings | None = None


def get_settings() -> Settings:
    """Get cached settings."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Reset settings cache (test helper)."""
    global _settings
    _settings = None
