from __future__ import annotations

import asyncio

from aegis_llm_server.backends.deterministic import DeterministicEmbeddingBackend


def test_deterministic_embeddings_are_stable():
    backend = DeterministicEmbeddingBackend(
        model_name="nomic-ai/nomic-embed-text-v1.5",
        aliases=["nomic-embed-text"],
        dimension=16,
        normalize=True,
    )

    first = asyncio.run(backend.embed(["hello world"]))
    second = asyncio.run(backend.embed(["hello world"]))

    assert first == second
    assert len(first[0]) == 16
