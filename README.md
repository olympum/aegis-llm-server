# aegis-llm-server

OpenAI-compatible local LLM server for embeddings-first workloads.

## Mission

Provide a dedicated local model server, separate from `aegis-llm-proxy`, so local inference concerns (model loading, embedding generation, hardware tuning) stay isolated from gateway concerns.

## Product Contract

Primary docs:
- `docs/contracts/openai-embeddings-compatible-v1.md`
- `docs/man/aegis-llm-server.1`
- `docs/plans/aegis-llm-server-phased-plan.md`
- `docs/adr/0001-language-python-first.md`

## Scope

In scope:
- OpenAI-compatible `POST /v1/embeddings`
- `GET /v1/models` model introspection for clients
- Local embedding backend management

Out of scope (for this phase):
- Chat/completions API
- Multi-node scheduling
- Gateway policy/routing

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Optional: real local embedding backend
pip install -e ".[local]"

uvicorn aegis_llm_server.main:app --reload --port 8181
```

## API

```bash
# health
curl -sS http://127.0.0.1:8181/health

# model introspection
curl -sS http://127.0.0.1:8181/v1/models

# embeddings
curl -sS -X POST http://127.0.0.1:8181/v1/embeddings \
  -H 'content-type: application/json' \
  -d '{"model":"nomic-embed-text","input":"hello world"}'

# embeddings (code alias)
curl -sS -X POST http://127.0.0.1:8181/v1/embeddings \
  -H 'content-type: application/json' \
  -d '{"model":"nomic-embed-code","input":"def hello(): return 1"}'
```

## Configuration

Environment prefix: `AEGIS_LLM_SERVER_`

- `AEGIS_LLM_SERVER_SERVER__HOST` (default `0.0.0.0`)
- `AEGIS_LLM_SERVER_SERVER__PORT` (default `8181`)
- `AEGIS_LLM_SERVER_EMBEDDING__ENABLED` (default `true`)
- `AEGIS_LLM_SERVER_EMBEDDING__BACKEND` (`deterministic` or `sentence_transformers`, default `deterministic`)
- `AEGIS_LLM_SERVER_EMBEDDING__MODEL_NAME` (default `nomic-ai/nomic-embed-text-v1.5`)
- `AEGIS_LLM_SERVER_EMBEDDING__DIMENSION` (default `768`, used by deterministic backend)
- `AEGIS_LLM_SERVER_EMBEDDING__NORMALIZE` (default `true`)

## Backend Notes

- `deterministic` backend is lightweight for development/testing only.
- `sentence_transformers` backend performs real local embedding generation.

## License

Apache-2.0. See `LICENSE`.
