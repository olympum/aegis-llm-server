"""OpenAI-compatible API models for aegis-llm-server."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class EmbeddingRequest(BaseModel):
    """OpenAI-compatible embeddings request."""

    model: str = "nomic-embed-text"
    input: str | list[str]
    encoding_format: Literal["float"] = "float"


class EmbeddingData(BaseModel):
    """Embedding item."""

    object: Literal["embedding"] = "embedding"
    index: int
    embedding: list[float]


class EmbeddingUsage(BaseModel):
    """Embedding usage information."""

    prompt_tokens: int
    total_tokens: int


class EmbeddingResponse(BaseModel):
    """OpenAI-compatible embeddings response."""

    object: Literal["list"] = "list"
    model: str
    data: list[EmbeddingData]
    usage: EmbeddingUsage


class ModelInfo(BaseModel):
    """Model item for /v1/models."""

    id: str
    object: Literal["model"] = "model"
    created: int
    owned_by: str = "aegis-llm-server"


class ModelListResponse(BaseModel):
    """Model listing response."""

    object: Literal["list"] = "list"
    data: list[ModelInfo]


class HealthResponse(BaseModel):
    """Health response."""

    status: Literal["ok", "error"] = "error"
    service: str = "aegis-llm-server"
    version: str = "0.1.0"
    backend: str = "none"
    embedding_enabled: bool = False


class ErrorPayload(BaseModel):
    """Canonical error payload."""

    code: Literal[
        "invalid_request",
        "upstream_error",
        "internal",
    ]
    message: str


class ErrorResponse(BaseModel):
    """Canonical error response."""

    error: ErrorPayload
