"""Embedding backend protocol."""

from __future__ import annotations

from typing import Protocol


class EmbeddingBackend(Protocol):
    """Backend contract for local embedding generation."""

    name: str
    model_name: str
    dimension: int

    async def embed(self, inputs: list[str]) -> list[list[float]]:
        """Generate one embedding vector for each input text."""

    def advertised_models(self) -> list[str]:
        """Model identifiers to advertise via /v1/models."""
