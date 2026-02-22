"""Embedding backend factory."""

from __future__ import annotations

from aegis_llm_server.backends.base import EmbeddingBackend
from aegis_llm_server.backends.deterministic import DeterministicEmbeddingBackend
from aegis_llm_server.backends.sentence_transformers import SentenceTransformersEmbeddingBackend
from aegis_llm_server.config import Settings


def create_embedding_backend(settings: Settings) -> EmbeddingBackend:
    """Build embedding backend from settings."""
    aliases = settings.public_embedding_models()

    if settings.embedding.backend == "sentence_transformers":
        return SentenceTransformersEmbeddingBackend(
            model_name=settings.embedding.model_name,
            aliases=aliases,
            normalize=settings.embedding.normalize,
        )

    return DeterministicEmbeddingBackend(
        model_name=settings.embedding.model_name,
        aliases=aliases,
        dimension=settings.embedding.dimension,
        normalize=settings.embedding.normalize,
    )
