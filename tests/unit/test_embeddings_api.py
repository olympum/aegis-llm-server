from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from aegis_llm_server.config import reset_settings
from aegis_llm_server.main import create_app


@pytest.fixture(autouse=True)
def clear_env(monkeypatch):
    keys = [
        "AEGIS_LLM_SERVER_EMBEDDING__ENABLED",
        "AEGIS_LLM_SERVER_EMBEDDING__BACKEND",
        "AEGIS_LLM_SERVER_EMBEDDING__MODEL_NAME",
        "AEGIS_LLM_SERVER_EMBEDDING__DIMENSION",
        "AEGIS_LLM_SERVER_EMBEDDING__NORMALIZE",
        "AEGIS_LLM_SERVER_TELEMETRY__ENABLED",
        "AEGIS_LLM_SERVER_TELEMETRY__OTLP_ENDPOINT",
        "AEGIS_LLM_SERVER_TELEMETRY__OTLP_TIMEOUT_SECONDS",
        "AEGIS_LLM_SERVER_TELEMETRY__METRICS_EXPORT_INTERVAL_MS",
        "AEGIS_LLM_SERVER_TELEMETRY__SAMPLE_RATIO",
    ]
    for key in keys:
        monkeypatch.delenv(key, raising=False)
    reset_settings()
    yield
    reset_settings()


def test_health_ready_default_backend():
    with TestClient(create_app()) as client:
        response = client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["backend"] == "deterministic"


def test_models_lists_embedding_aliases():
    with TestClient(create_app()) as client:
        response = client.get("/v1/models")
        assert response.status_code == 200
        ids = [item["id"] for item in response.json()["data"]]
        assert "nomic-embed-text" in ids
        assert "nomic-ai/nomic-embed-text-v1.5" in ids
        assert "nomic-embed-code" in ids
        assert "nomic-ai/nomic-embed-code" in ids
        assert "text-embedding-3-small" in ids


def test_embeddings_single_input_success():
    with TestClient(create_app()) as client:
        response = client.post(
            "/v1/embeddings",
            json={"model": "nomic-embed-text", "input": "hello world"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["model"] == "nomic-embed-text"
        assert len(body["data"]) == 1
        assert len(body["data"][0]["embedding"]) == 768
        assert body["usage"]["total_tokens"] == 2


def test_embeddings_multi_input_success():
    with TestClient(create_app()) as client:
        response = client.post(
            "/v1/embeddings",
            json={"model": "text-embedding-3-small", "input": ["a b", "c d e"]},
        )
        assert response.status_code == 200
        body = response.json()
        assert len(body["data"]) == 2
        assert body["data"][0]["index"] == 0
        assert body["data"][1]["index"] == 1
        assert body["usage"]["prompt_tokens"] == 5


def test_embeddings_unknown_model_rejected():
    with TestClient(create_app()) as client:
        response = client.post(
            "/v1/embeddings",
            json={"model": "unknown-model", "input": "hello"},
        )
        assert response.status_code == 400
        body = response.json()
        assert body["error"]["code"] == "invalid_request"


def test_embeddings_nomic_code_alias_success():
    with TestClient(create_app()) as client:
        response = client.post(
            "/v1/embeddings",
            json={"model": "nomic-embed-code", "input": "def hello(): return 1"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["model"] == "nomic-embed-code"
        assert len(body["data"]) == 1
        assert len(body["data"][0]["embedding"]) == 768


def test_embeddings_disabled_returns_503(monkeypatch):
    monkeypatch.setenv("AEGIS_LLM_SERVER_EMBEDDING__ENABLED", "false")
    reset_settings()
    with TestClient(create_app()) as client:
        models = client.get("/v1/models")
        assert models.status_code == 200
        assert models.json()["data"] == []

        response = client.post(
            "/v1/embeddings",
            json={"model": "nomic-embed-text", "input": "hello"},
        )
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "upstream_error"
