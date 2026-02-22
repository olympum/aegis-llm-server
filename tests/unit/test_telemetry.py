from __future__ import annotations

from fastapi.testclient import TestClient

from aegis_llm_server.config import get_settings, reset_settings
from aegis_llm_server.main import create_app
from aegis_llm_server.telemetry import resolve_otlp_metrics_endpoint, resolve_otlp_traces_endpoint


def test_resolve_otlp_traces_endpoint_base_url():
    assert resolve_otlp_traces_endpoint("http://127.0.0.1:4318") == "http://127.0.0.1:4318/v1/traces"


def test_resolve_otlp_traces_endpoint_passthrough():
    assert resolve_otlp_traces_endpoint("http://collector:4318/v1/traces") == "http://collector:4318/v1/traces"


def test_resolve_otlp_metrics_endpoint_base_url():
    assert resolve_otlp_metrics_endpoint("http://127.0.0.1:4318") == "http://127.0.0.1:4318/v1/metrics"


def test_resolve_otlp_metrics_endpoint_passthrough():
    assert resolve_otlp_metrics_endpoint("http://collector:4318/v1/metrics") == "http://collector:4318/v1/metrics"


def test_telemetry_settings_from_env(monkeypatch):
    monkeypatch.setenv("AEGIS_LLM_SERVER_TELEMETRY__ENABLED", "true")
    monkeypatch.setenv("AEGIS_LLM_SERVER_TELEMETRY__OTLP_ENDPOINT", "http://127.0.0.1:4318")
    monkeypatch.setenv("AEGIS_LLM_SERVER_TELEMETRY__OTLP_TIMEOUT_SECONDS", "1")
    monkeypatch.setenv("AEGIS_LLM_SERVER_TELEMETRY__METRICS_EXPORT_INTERVAL_MS", "1000")
    monkeypatch.setenv("AEGIS_LLM_SERVER_TELEMETRY__SAMPLE_RATIO", "0.25")
    reset_settings()

    settings = get_settings()
    assert settings.telemetry.enabled is True
    assert settings.telemetry.otlp_endpoint == "http://127.0.0.1:4318"
    assert settings.telemetry.otlp_timeout_seconds == 1
    assert settings.telemetry.metrics_export_interval_ms == 1000
    assert settings.telemetry.sample_ratio == 0.25

    reset_settings()


def test_app_starts_with_telemetry_enabled(monkeypatch):
    monkeypatch.setenv("AEGIS_LLM_SERVER_TELEMETRY__ENABLED", "true")
    monkeypatch.setenv("AEGIS_LLM_SERVER_TELEMETRY__OTLP_ENDPOINT", "http://127.0.0.1:65535")
    monkeypatch.setenv("AEGIS_LLM_SERVER_TELEMETRY__OTLP_TIMEOUT_SECONDS", "0.1")
    reset_settings()

    with TestClient(create_app()) as client:
        response = client.get("/health")
        assert response.status_code == 200

    reset_settings()
