"""FastAPI routes for local embedding service."""

from __future__ import annotations

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

router = APIRouter()


def error_response(status_code: int, code: str, message: str) -> JSONResponse:
    """Build canonical error payload."""
    payload = ErrorResponse(error=ErrorPayload(code=code, message=message))
    return JSONResponse(status_code=status_code, content=payload.model_dump())


def get_backend(request: Request) -> EmbeddingBackend:
    backend = getattr(request.app.state, "embedding_backend", None)
    if backend is None:
        raise RuntimeError("Embedding backend is not initialized")
    return backend


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
    settings = get_settings()
    if not settings.embedding.enabled:
        return error_response(
            status_code=503,
            code="upstream_error",
            message="Embeddings are disabled.",
        )

    resolved_model = settings.resolve_embedding_model(body.model)
    if resolved_model is None:
        return error_response(
            status_code=400,
            code="invalid_request",
            message=f"Unsupported embedding model '{body.model}'.",
        )

    backend = get_backend(request)
    inputs = [body.input] if isinstance(body.input, str) else body.input

    try:
        vectors = await backend.embed(inputs)
    except Exception as exc:
        return error_response(
            status_code=500,
            code="internal",
            message=f"Embedding generation failed: {exc}",
        )

    if len(vectors) != len(inputs):
        return error_response(
            status_code=500,
            code="internal",
            message="Embedding backend returned mismatched vector count.",
        )

    items = [EmbeddingData(index=i, embedding=vector) for i, vector in enumerate(vectors)]
    prompt_tokens = sum(len(text.split()) for text in inputs)

    return EmbeddingResponse(
        model=body.model,
        data=items,
        usage=EmbeddingUsage(prompt_tokens=prompt_tokens, total_tokens=prompt_tokens),
    )
