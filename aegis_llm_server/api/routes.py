"""FastAPI routes for local embedding service."""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from aegis_llm_server.api.models import (
    EmbeddingData,
    EmbeddingRequest,
    EmbeddingResponse,
    EmbeddingUsage,
    ErrorPayload,
    ErrorResponse,
    HealthResponse,
    ModelInfo,
    ModelListResponse,
)
from aegis_llm_server.backends.base import EmbeddingBackend
from aegis_llm_server.config import get_settings
from aegis_llm_server.telemetry import EmbeddingsMetrics, NoopEmbeddingsMetrics

router = APIRouter()
logger = logging.getLogger(__name__)


def error_response(status_code: int, code: str, message: str) -> JSONResponse:
    """Build canonical error payload."""
    payload = ErrorResponse(error=ErrorPayload(code=code, message=message))
    return JSONResponse(status_code=status_code, content=payload.model_dump())


def get_backend(request: Request) -> EmbeddingBackend:
    backend = getattr(request.app.state, "embedding_backend", None)
    if backend is None:
        raise RuntimeError("Embedding backend is not initialized")
    return backend


def get_embeddings_metrics(request: Request) -> EmbeddingsMetrics:
    metrics = getattr(request.app.state, "embeddings_metrics", None)
    if metrics is None:
        return NoopEmbeddingsMetrics()
    return metrics


@router.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check(request: Request) -> HealthResponse:
    """Service health and embedding backend readiness."""
    settings = get_settings()
    backend = getattr(request.app.state, "embedding_backend", None)
    return HealthResponse(
        status="ok" if settings.embedding.enabled and backend is not None else "error",
        service=settings.service_name,
        version=settings.service_version,
        backend=backend.name if backend is not None else "none",
        embedding_enabled=settings.embedding.enabled,
    )


@router.get("/v1/models", response_model=ModelListResponse, tags=["Models"])
async def list_models(request: Request) -> ModelListResponse:
    """List advertised embedding model aliases."""
    created = int(time.time())
    settings = get_settings()
    if not settings.embedding.enabled:
        return ModelListResponse(data=[])

    backend = get_backend(request)
    models = [
        ModelInfo(id=model_id, created=created)
        for model_id in backend.advertised_models()
    ]
    return ModelListResponse(data=models)


@router.post(
    "/v1/embeddings",
    response_model=EmbeddingResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    tags=["Embeddings"],
)
async def create_embeddings(request: Request, body: EmbeddingRequest):
    """OpenAI-compatible embeddings endpoint."""
    started_at = time.perf_counter()
    metrics = get_embeddings_metrics(request)

    def record_metrics(status: str, input_count: int, prompt_tokens: int | None) -> None:
        elapsed_ms = (time.perf_counter() - started_at) * 1000.0
        metrics.record(
            model=body.model,
            status=status,
            input_count=input_count,
            prompt_tokens=prompt_tokens,
            duration_ms=elapsed_ms,
        )

    settings = get_settings()
    if not settings.embedding.enabled:
        record_metrics(status="upstream_error", input_count=0, prompt_tokens=None)
        return error_response(
            status_code=503,
            code="upstream_error",
            message="Embeddings are disabled.",
        )

    resolved_model = settings.resolve_embedding_model(body.model)
    if resolved_model is None:
        input_count = 1 if isinstance(body.input, str) else len(body.input)
        record_metrics(status="invalid_request", input_count=input_count, prompt_tokens=None)
        return error_response(
            status_code=400,
            code="invalid_request",
            message=f"Unsupported embedding model '{body.model}'.",
        )

    backend = get_backend(request)
    inputs = [body.input] if isinstance(body.input, str) else body.input
    if not inputs:
        record_metrics(status="invalid_request", input_count=0, prompt_tokens=None)
        return error_response(
            status_code=400,
            code="invalid_request",
            message="Embedding input list cannot be empty.",
        )
    if len(inputs) > settings.embedding.max_batch_size:
        record_metrics(status="invalid_request", input_count=len(inputs), prompt_tokens=None)
        return error_response(
            status_code=400,
            code="invalid_request",
            message=(
                f"Embedding input batch size {len(inputs)} exceeds configured limit "
                f"{settings.embedding.max_batch_size}."
            ),
        )

    too_long_idx = next((idx for idx, text in enumerate(inputs) if len(text) > settings.embedding.max_input_chars), None)
    if too_long_idx is not None:
        record_metrics(status="invalid_request", input_count=len(inputs), prompt_tokens=None)
        return error_response(
            status_code=400,
            code="invalid_request",
            message=(
                f"Embedding input at index {too_long_idx} exceeds configured character limit "
                f"{settings.embedding.max_input_chars}."
            ),
        )

    total_chars = sum(len(text) for text in inputs)
    if total_chars > settings.embedding.max_total_chars:
        record_metrics(status="invalid_request", input_count=len(inputs), prompt_tokens=None)
        return error_response(
            status_code=400,
            code="invalid_request",
            message=(
                f"Total embedding input size {total_chars} exceeds configured character limit "
                f"{settings.embedding.max_total_chars}."
            ),
        )

    prompt_tokens = sum(len(text.split()) for text in inputs)

    try:
        vectors = await backend.embed(inputs)
    except Exception:
        logger.exception("Embedding generation failed")
        record_metrics(status="internal", input_count=len(inputs), prompt_tokens=prompt_tokens)
        return error_response(
            status_code=500,
            code="internal",
            message="Embedding generation failed.",
        )

    if len(vectors) != len(inputs):
        record_metrics(status="internal", input_count=len(inputs), prompt_tokens=prompt_tokens)
        return error_response(
            status_code=500,
            code="internal",
            message="Embedding backend returned mismatched vector count.",
        )

    items = [EmbeddingData(index=i, embedding=vector) for i, vector in enumerate(vectors)]
    record_metrics(status="ok", input_count=len(inputs), prompt_tokens=prompt_tokens)

    return EmbeddingResponse(
        model=body.model,
        data=items,
        usage=EmbeddingUsage(prompt_tokens=prompt_tokens, total_tokens=prompt_tokens),
    )
