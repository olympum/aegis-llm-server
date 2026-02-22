"""Application entrypoint for aegis-llm-server."""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from aegis_llm_server.api.routes import router
from aegis_llm_server.backends.factory import create_embedding_backend
from aegis_llm_server.config import get_settings
from aegis_llm_server.telemetry import TelemetryRuntime, setup_telemetry, shutdown_telemetry


def configure_logging() -> None:
    """Configure process logging."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Create and attach embedding backend."""
    settings = get_settings()
    telemetry_runtime = TelemetryRuntime()

    try:
        telemetry_runtime = setup_telemetry(app, settings)
    except Exception:
        logging.exception("OpenTelemetry initialization failed; continuing without telemetry")

    app.state.telemetry_runtime = telemetry_runtime
    app.state.embeddings_metrics = telemetry_runtime.embeddings_metrics

    if settings.embedding.enabled:
        app.state.embedding_backend = create_embedding_backend(settings)
    else:
        app.state.embedding_backend = None

    try:
        yield
    finally:
        try:
            shutdown_telemetry(app, telemetry_runtime)
        except Exception:
            logging.exception("OpenTelemetry shutdown failed")


def create_app() -> FastAPI:
    """Build FastAPI app."""
    settings = get_settings()
    configure_logging()

    app = FastAPI(
        title="Aegis LLM Server",
        description="OpenAI-compatible local embedding server",
        version=settings.service_version,
        lifespan=lifespan,
    )
    app.include_router(router)
    return app


app = create_app()


def run() -> None:
    """Run uvicorn server."""
    settings = get_settings()
    port = int(os.environ.get("PORT", settings.server.port))
    uvicorn.run(
        "aegis_llm_server.main:app",
        host=settings.server.host,
        port=port,
        workers=1,
    )


if __name__ == "__main__":
    run()
