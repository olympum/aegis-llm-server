from __future__ import annotations

import sys
from types import ModuleType

import numpy as np
import pytest

from aegis_llm_server.backends.factory import create_embedding_backend
from aegis_llm_server.backends.sentence_transformers import SentenceTransformersEmbeddingBackend
from aegis_llm_server.config import Settings


def test_sentence_transformers_backend_missing_dependency(monkeypatch):
    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        del globals, locals, fromlist, level
        if name == "sentence_transformers":
            raise ModuleNotFoundError("No module named 'sentence_transformers'")
        return original_import(name)

    import builtins

    original_import = builtins.__import__
    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(RuntimeError, match=r"Install with: pip install -e '\.\[local\]'"):
        SentenceTransformersEmbeddingBackend(
            model_name="custom/embed-model",
            aliases=["nomic-embed-text"],
            normalize=True,
            trust_remote_code=False,
        )


@pytest.mark.asyncio
async def test_factory_builds_sentence_transformers_backend_with_fake_module(monkeypatch):
    fake_module = ModuleType("sentence_transformers")
    created_models: list[object] = []

    class FakeSentenceTransformer:
        def __init__(self, model_name: str, trust_remote_code: bool) -> None:
            self.model_name = model_name
            self.trust_remote_code = trust_remote_code
            self.encode_calls: list[dict[str, object]] = []
            created_models.append(self)

        def get_sentence_embedding_dimension(self) -> int:
            return 3

        def encode(
            self,
            inputs: list[str],
            *,
            normalize_embeddings: bool,
            convert_to_numpy: bool,
        ) -> np.ndarray:
            self.encode_calls.append(
                {
                    "inputs": inputs,
                    "normalize_embeddings": normalize_embeddings,
                    "convert_to_numpy": convert_to_numpy,
                }
            )
            return np.asarray([[1.0, 2.0, 3.0] for _ in inputs], dtype=np.float32)

    fake_module.SentenceTransformer = FakeSentenceTransformer
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)

    settings = Settings(
        embedding={
            "backend": "sentence_transformers",
            "model_name": "custom/embed-model",
            "normalize": False,
            "trust_remote_code": False,
        }
    )

    backend = create_embedding_backend(settings)

    assert isinstance(backend, SentenceTransformersEmbeddingBackend)
    assert backend.model_name == "custom/embed-model"
    assert backend.dimension == 3
    assert "nomic-embed-text" in backend.advertised_models()
    assert "custom/embed-model" in backend.advertised_models()

    vectors = await backend.embed(["first", "second"])

    assert vectors == [[1.0, 2.0, 3.0], [1.0, 2.0, 3.0]]
    assert len(created_models) == 1
    assert created_models[0].model_name == "custom/embed-model"
    assert created_models[0].trust_remote_code is False
    assert created_models[0].encode_calls == [
        {
            "inputs": ["first", "second"],
            "normalize_embeddings": False,
            "convert_to_numpy": True,
        }
    ]
