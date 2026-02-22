"""Deterministic lightweight embedding backend for local testing."""

from __future__ import annotations

import hashlib
from typing import Iterable

import numpy as np


class DeterministicEmbeddingBackend:
    """Stable hash-based embeddings with fixed dimension."""

    name = "deterministic"

    def __init__(self, *, model_name: str, aliases: Iterable[str], dimension: int, normalize: bool) -> None:
        self.model_name = model_name
        self._aliases = list(aliases)
        self.dimension = dimension
        self._normalize = normalize

    def _vectorize(self, text: str) -> list[float]:
        values = np.zeros(self.dimension, dtype=np.float32)
        if not text:
            return values.tolist()

        for idx in range(self.dimension):
            digest = hashlib.sha256(f"{text}:{idx}".encode("utf-8")).digest()
            raw = int.from_bytes(digest[:4], byteorder="big", signed=False)
            values[idx] = (raw / 2**31) - 1.0

        if self._normalize:
            norm = float(np.linalg.norm(values))
            if norm > 0:
                values = values / norm
        return values.tolist()

    async def embed(self, inputs: list[str]) -> list[list[float]]:
        return [self._vectorize(item) for item in inputs]

    def advertised_models(self) -> list[str]:
        output = list(self._aliases)
        if self.model_name not in output:
            output.append(self.model_name)
        return output
