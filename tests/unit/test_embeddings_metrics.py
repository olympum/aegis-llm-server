from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from aegis_llm_server.config import reset_settings
from aegis_llm_server.main import create_app


class FakeEmbeddingsMetrics:
    def __init__(self) -> None:
        self.records: list[dict[str, object]] = []

    def record(
        self,
        *,
        model: str,
        status: str,
        input_count: int,
        prompt_tokens: int | None,
        duration_ms: float,
    ) -> None:
        self.records.append(
            {
                "model": model,
                "status": status,
                "input_count": input_count,
                "prompt_tokens": prompt_tokens,
                "duration_ms": duration_ms,
            }
        )


@pytest.fixture(autouse=True)
def clear_env(monkeypatch):
    keys = [
        "AEGIS_LLM_SERVER_EMBEDDING__ENABLED",
        "AEGIS_LLM_SERVER_EMBEDDING__BACKEND",
        "AEGIS_LLM_SERVER_EMBEDDING__MODEL_NAME",
        "AEGIS_LLM_SERVER_EMBEDDING__TRUST_REMOTE_CODE",
        "AEGIS_LLM_SERVER_EMBEDDING__DIMENSION",
        "AEGIS_LLM_SERVER_EMBEDDING__NORMALIZE",
        "AEGIS_LLM_SERVER_EMBEDDING__MAX_BATCH_SIZE",
        "AEGIS_LLM_SERVER_EMBEDDING__MAX_INPUT_CHARS",
        "AEGIS_LLM_SERVER_EMBEDDING__MAX_TOTAL_CHARS",
        "AEGIS_LLM_SERVER_EMBEDDING__BACKEND_TIMEOUT_SECONDS",
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


def test_embeddings_metrics_recorded_success():
    with TestClient(create_app()) as client:
        fake = FakeEmbeddingsMetrics()
        client.app.state.embeddings_metrics = fake

        response = client.post(
            "/v1/embeddings",
            json={"model": "nomic-embed-text", "input": "hello world"},
        )

        assert response.status_code == 200
        assert len(fake.records) == 1
        record = fake.records[0]
        assert record["model"] == "nomic-embed-text"
        assert record["status"] == "ok"
        assert record["input_count"] == 1
        assert record["prompt_tokens"] == 2
        assert isinstance(record["duration_ms"], float)
        assert record["duration_ms"] >= 0.0


def test_embeddings_metrics_recorded_invalid_model():
    with TestClient(create_app()) as client:
        fake = FakeEmbeddingsMetrics()
        client.app.state.embeddings_metrics = fake

        response = client.post(
            "/v1/embeddings",
            json={"model": "unsupported-model", "input": "hello world"},
        )

        assert response.status_code == 400
        assert len(fake.records) == 1
        record = fake.records[0]
        assert record["model"] == "unsupported-model"
        assert record["status"] == "invalid_request"
        assert record["input_count"] == 1
        assert record["prompt_tokens"] is None
