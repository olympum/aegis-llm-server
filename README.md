# aegis-llm-server

OpenAI-compatible local model runtime for embeddings.

This project provides an embeddings-focused HTTP service with a stable API:
- `GET /health`
- `GET /v1/models`
- `POST /v1/embeddings`

## Scope

In scope:
- OpenAI-compatible embeddings endpoint
- Local model loading/inference for embeddings
- OpenTelemetry traces and metrics export (optional)

Out of scope:
- Chat/completions API
- Gateway/provider policy routing
- Multi-node scheduling

Architecture note:
- `aegis-llm-server` is the local model runtime.
- `aegis-llm-proxy` is the caller-facing router/gateway.

## Install

From source (recommended):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Optional local-model runtime dependencies:

```bash
pip install -e ".[local]"
```

## Run

Option 1:

```bash
aegis-llm-server
```

Option 2:

```bash
uvicorn aegis_llm_server.main:app --host 0.0.0.0 --port 8181
```

Configuration template:

```bash
cp .env.example .env
set -a
source .env
set +a
aegis-llm-server
```

`aegis-llm-server` does not parse `.env` directly; load env vars externally
(shell, service manager, wrapper script).

## Use As A Library

You can embed the FastAPI app directly in another Python process:

```python
from aegis_llm_server.main import create_app

app = create_app()
```

## Required Config By Scenario

`deterministic` backend (default, good for development/testing):
- no extra env vars required

`sentence_transformers` backend (real in-process local model runtime):
- install optional local deps: `pip install -e ".[local]"`
- set `AEGIS_LLM_SERVER_EMBEDDING__BACKEND=sentence_transformers`
- set `AEGIS_LLM_SERVER_EMBEDDING__MODEL_NAME` to the local embedding model to load
- for Nomic models, keep `AEGIS_LLM_SERVER_EMBEDDING__TRUST_REMOTE_CODE=true`

Production local-model backend:
- run the model runtime inside `aegis-llm-server` (no proxy hop, no remote forward)
- set `AEGIS_LLM_SERVER_EMBEDDING__BACKEND` to the local runtime backend implementation
- set `AEGIS_LLM_SERVER_EMBEDDING__MODEL_NAME` to your local embedding model

Telemetry disabled (default):
- no telemetry env vars required

Telemetry enabled (OTLP HTTP):
- set `AEGIS_LLM_SERVER_TELEMETRY__ENABLED=true`
- set `AEGIS_LLM_SERVER_TELEMETRY__OTLP_ENDPOINT` to your collector base URL

Example `.env` (deterministic + telemetry off):

```bash
AEGIS_LLM_SERVER_SERVER__HOST=0.0.0.0
AEGIS_LLM_SERVER_SERVER__PORT=8181
AEGIS_LLM_SERVER_EMBEDDING__BACKEND=deterministic
```

Example `.env` (production local-model runtime + telemetry on):

```bash
AEGIS_LLM_SERVER_SERVER__HOST=0.0.0.0
AEGIS_LLM_SERVER_SERVER__PORT=8181
AEGIS_LLM_SERVER_EMBEDDING__BACKEND=sentence_transformers
AEGIS_LLM_SERVER_EMBEDDING__MODEL_NAME=nomic-ai/nomic-embed-text-v1.5
AEGIS_LLM_SERVER_EMBEDDING__TRUST_REMOTE_CODE=true
AEGIS_LLM_SERVER_EMBEDDING__BACKEND_TIMEOUT_SECONDS=60
AEGIS_LLM_SERVER_TELEMETRY__ENABLED=true
AEGIS_LLM_SERVER_TELEMETRY__OTLP_ENDPOINT=http://otel-collector:4318
AEGIS_LLM_SERVER_TELEMETRY__SAMPLE_RATIO=1.0
```

## Configuration Reference

Environment prefix: `AEGIS_LLM_SERVER_`

Server:
- `AEGIS_LLM_SERVER_SERVER__HOST` (default `0.0.0.0`)
- `AEGIS_LLM_SERVER_SERVER__PORT` (default `8181`)
- `PORT` overrides server port when set

Embedding backend:
- `AEGIS_LLM_SERVER_EMBEDDING__ENABLED` (default `true`)
- `AEGIS_LLM_SERVER_EMBEDDING__BACKEND` (`deterministic` or `sentence_transformers`; default `deterministic`)
- `AEGIS_LLM_SERVER_EMBEDDING__MODEL_NAME` (default `nomic-ai/nomic-embed-text-v1.5`)
- `AEGIS_LLM_SERVER_EMBEDDING__TRUST_REMOTE_CODE` (default `true`; required by some local models such as Nomic HF repos)
- `AEGIS_LLM_SERVER_EMBEDDING__DIMENSION` (default `768`; deterministic backend only)
- `AEGIS_LLM_SERVER_EMBEDDING__NORMALIZE` (default `true`)

Hardening controls:
- `AEGIS_LLM_SERVER_EMBEDDING__MAX_BATCH_SIZE` (default `64`)
- `AEGIS_LLM_SERVER_EMBEDDING__MAX_INPUT_CHARS` (default `32768`)
- `AEGIS_LLM_SERVER_EMBEDDING__MAX_TOTAL_CHARS` (default `262144`)
- `AEGIS_LLM_SERVER_EMBEDDING__BACKEND_TIMEOUT_SECONDS` (default `30`)

Telemetry:
- `AEGIS_LLM_SERVER_TELEMETRY__ENABLED` (default `false`)
- `AEGIS_LLM_SERVER_TELEMETRY__OTLP_ENDPOINT` (default `http://127.0.0.1:4318`)
- `AEGIS_LLM_SERVER_TELEMETRY__OTLP_TIMEOUT_SECONDS` (default `10`)
- `AEGIS_LLM_SERVER_TELEMETRY__METRICS_EXPORT_INTERVAL_MS` (default `5000`)
- `AEGIS_LLM_SERVER_TELEMETRY__SAMPLE_RATIO` (default `1.0`)
- `AEGIS_LLM_SERVER_TELEMETRY__OTLP_HEADERS__<NAME>` (optional OTLP HTTP header map)

## API Examples

```bash
# health
curl -sS http://127.0.0.1:8181/health

# models
curl -sS http://127.0.0.1:8181/v1/models

# embeddings
curl -sS -X POST http://127.0.0.1:8181/v1/embeddings \
  -H 'content-type: application/json' \
  -d '{"model":"nomic-embed-text","input":"hello world"}'
```

## Model Alias Behavior

Accepted public model IDs currently include:
- `nomic-embed-text`
- `nomic-ai/nomic-embed-text-v1.5`
- `nomic-embed-code`
- `nomic-ai/nomic-embed-code`
- `text-embedding-3-small`

Important:
- accepted aliases map to the configured local backend model (`EMBEDDING__MODEL_NAME`)
- aliases are compatibility identifiers, not separate loaded models

## Error Semantics

`POST /v1/embeddings` canonical error codes:
- `400 invalid_request` invalid model/input/limit violation
- `503 upstream_error` local backend disabled or unavailable
- `504 upstream_timeout` backend call exceeded timeout
- `500 internal` internal processing/backend output validation failure

## Telemetry Output Contract

When telemetry is enabled, OTLP HTTP traces and metrics are exported.

Embeddings metrics:
- `aegis_llm_server_embeddings_requests_total`
- `aegis_llm_server_embeddings_input_texts_total`
- `aegis_llm_server_embeddings_duration_ms`
- `aegis_llm_server_embeddings_prompt_tokens`

Current metric attributes:
- `model`
- `status`

## Performance Benchmarking

Use `scripts/bench_embeddings.py` to collect reproducible local latency and
throughput baselines for `POST /v1/embeddings`.

Example:

```bash
uv run python scripts/bench_embeddings.py \
  --base-url http://127.0.0.1:8181 \
  --model nomic-embed-text \
  --requests 300 \
  --warmup 30 \
  --concurrency 20 \
  --batch-size 1 \
  --input-chars 256 \
  --output docs/perf/results/local-baseline.json
```

Published baseline report:
- `docs/perf/embeddings-baseline-2026-02-22.md`

## More Docs

- Contract: `docs/contracts/openai-embeddings-compatible-v1.md`
- MAN page: `docs/man/aegis-llm-server.1`
- Phased plan + status scorecard: `docs/plans/aegis-llm-server-phased-plan.md`
- Performance baseline report: `docs/perf/embeddings-baseline-2026-02-22.md`
- ADR: `docs/adr/0001-language-python-first.md`
- Template: `.env.example`

## Roadmap Scope Status

Current prioritization is local-only deliverables in this repo.

Implemented locally:
- embeddings contract/runtime/hardening
- local embeddings backends (deterministic control + in-process model runtime)
- telemetry hooks and metrics/traces export support

Deferred to external consumer/gateway tracks:
- proxy/corp/NAP integration and routing rollout
- upstream legacy-cutover orchestration

## License

Apache-2.0. See `LICENSE`.
