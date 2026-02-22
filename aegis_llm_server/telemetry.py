"""OpenTelemetry setup for aegis-llm-server."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from fastapi import FastAPI
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

from aegis_llm_server.config import Settings


class EmbeddingsMetrics(Protocol):
    """Embeddings metrics recorder contract."""

    def record(
        self,
        *,
        model: str,
        status: str,
        input_count: int,
        prompt_tokens: int | None,
        duration_ms: float,
    ) -> None:
        """Record a single embeddings request measurement."""


@dataclass(slots=True)
class NoopEmbeddingsMetrics:
    """No-op implementation used when telemetry is disabled."""

    def record(
        self,
        *,
        model: str,
        status: str,
        input_count: int,
        prompt_tokens: int | None,
        duration_ms: float,
    ) -> None:
        del model, status, input_count, prompt_tokens, duration_ms


@dataclass(slots=True)
class OTelEmbeddingsMetrics:
    """OpenTelemetry-backed embeddings metrics recorder."""

    request_counter: object
    input_texts_counter: object
    duration_histogram: object
    prompt_tokens_histogram: object

    def record(
        self,
        *,
        model: str,
        status: str,
        input_count: int,
        prompt_tokens: int | None,
        duration_ms: float,
    ) -> None:
        attributes = {"model": model, "status": status}
        self.request_counter.add(1, attributes=attributes)
        self.input_texts_counter.add(max(0, input_count), attributes=attributes)
        self.duration_histogram.record(max(0.0, duration_ms), attributes=attributes)
        if prompt_tokens is not None:
            self.prompt_tokens_histogram.record(max(0, prompt_tokens), attributes=attributes)


def resolve_otlp_traces_endpoint(endpoint: str) -> str:
    """Normalize collector endpoint to an OTLP traces path."""
    cleaned = endpoint.rstrip("/")
    if cleaned.endswith("/v1/traces"):
        return cleaned
    return f"{cleaned}/v1/traces"


def resolve_otlp_metrics_endpoint(endpoint: str) -> str:
    """Normalize collector endpoint to an OTLP metrics path."""
    cleaned = endpoint.rstrip("/")
    if cleaned.endswith("/v1/metrics"):
        return cleaned
    return f"{cleaned}/v1/metrics"


@dataclass(slots=True)
class TelemetryRuntime:
    """Holds telemetry runtime state for app lifespan."""

    enabled: bool = False
    tracer_provider: TracerProvider | None = None
    meter_provider: MeterProvider | None = None
    instrumentor: FastAPIInstrumentor | None = None
    embeddings_metrics: EmbeddingsMetrics = field(default_factory=NoopEmbeddingsMetrics)


def setup_telemetry(app: FastAPI, settings: Settings) -> TelemetryRuntime:
    """Initialize OpenTelemetry SDK and FastAPI instrumentation."""
    if not settings.telemetry.enabled:
        return TelemetryRuntime()

    resource = Resource.create(
        {
            "service.name": settings.service_name,
            "service.version": settings.service_version,
        }
    )
    tracer_provider = TracerProvider(
        resource=resource,
        sampler=TraceIdRatioBased(settings.telemetry.sample_ratio),
    )

    exporter = OTLPSpanExporter(
        endpoint=resolve_otlp_traces_endpoint(settings.telemetry.otlp_endpoint),
        headers=settings.telemetry.otlp_headers or None,
        timeout=settings.telemetry.otlp_timeout_seconds,
    )
    tracer_provider.add_span_processor(BatchSpanProcessor(exporter))

    metric_exporter = OTLPMetricExporter(
        endpoint=resolve_otlp_metrics_endpoint(settings.telemetry.otlp_endpoint),
        headers=settings.telemetry.otlp_headers or None,
        timeout=settings.telemetry.otlp_timeout_seconds,
    )
    metric_reader = PeriodicExportingMetricReader(
        metric_exporter,
        export_interval_millis=settings.telemetry.metrics_export_interval_ms,
    )
    meter_provider = MeterProvider(
        resource=resource,
        metric_readers=[metric_reader],
    )
    meter = meter_provider.get_meter("aegis-llm-server")

    embeddings_metrics = OTelEmbeddingsMetrics(
        request_counter=meter.create_counter(
            name="aegis_llm_server_embeddings_requests_total",
            unit="1",
            description="Count of /v1/embeddings requests by model and status.",
        ),
        input_texts_counter=meter.create_counter(
            name="aegis_llm_server_embeddings_input_texts_total",
            unit="1",
            description="Total number of input texts processed by /v1/embeddings.",
        ),
        duration_histogram=meter.create_histogram(
            name="aegis_llm_server_embeddings_duration_ms",
            unit="ms",
            description="Latency of /v1/embeddings requests.",
        ),
        prompt_tokens_histogram=meter.create_histogram(
            name="aegis_llm_server_embeddings_prompt_tokens",
            unit="1",
            description="Estimated prompt token count for /v1/embeddings requests.",
        ),
    )

    instrumentor = FastAPIInstrumentor()
    instrumentor.instrument_app(
        app,
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
    )

    return TelemetryRuntime(
        enabled=True,
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
        instrumentor=instrumentor,
        embeddings_metrics=embeddings_metrics,
    )


def shutdown_telemetry(app: FastAPI, runtime: TelemetryRuntime) -> None:
    """Shutdown OpenTelemetry instrumentation/export pipeline."""
    if not runtime.enabled:
        return

    if runtime.instrumentor is not None:
        runtime.instrumentor.uninstrument_app(app)

    if runtime.meter_provider is not None:
        runtime.meter_provider.shutdown()

    if runtime.tracer_provider is not None:
        runtime.tracer_provider.shutdown()
