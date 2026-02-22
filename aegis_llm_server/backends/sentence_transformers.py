"""Sentence-transformers backend for real local embedding generation."""

from __future__ import annotations

import asyncio
from typing import Iterable

import numpy as np


class SentenceTransformersEmbeddingBackend:
    """Embeddings backend powered by sentence-transformers."""

    name = "sentence_transformers"

    def __init__(
        self,
        *,
        model_name: str,
        aliases: Iterable[str],
        normalize: bool,
        trust_remote_code: bool,
    ) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ModuleNotFoundError as exc:  # pragma: no cover - depends on optional extra
            raise RuntimeError(
                "sentence-transformers backend selected but dependency is missing. "
                "Install with: pip install -e '.[local]'"
            ) from exc

        self.model_name = model_name
        self._aliases = list(aliases)
        self._normalize = normalize
        self._model = SentenceTransformer(
            model_name,
            trust_remote_code=trust_remote_code,
        )
        dim = self._model.get_sentence_embedding_dimension()
        self.dimension = int(dim) if dim else 0

    def _encode_sync(self, inputs: list[str]) -> list[list[float]]:
        vectors = self._model.encode(
            inputs,
            normalize_embeddings=self._normalize,
            convert_to_numpy=True,
        )
        if isinstance(vectors, np.ndarray):
            return vectors.astype(np.float32).tolist()
        return [np.asarray(item, dtype=np.float32).tolist() for item in vectors]

    async def embed(self, inputs: list[str]) -> list[list[float]]:
        return await asyncio.to_thread(self._encode_sync, inputs)

    def advertised_models(self) -> list[str]:
        output = list(self._aliases)
        if self.model_name not in output:
            output.append(self.model_name)
        return output
