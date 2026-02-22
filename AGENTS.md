# Aegis LLM Server

OpenAI-compatible local model server (embeddings-first) for Aegis and NAP.

## Development Commands

```bash
uv sync                    # Install dependencies
uv run pytest              # Run tests
uv run ruff check .        # Lint
```

## Code Style

- Python 3.11+ with explicit request/response schemas.
- Keep API behavior contract-first (`docs/contracts/*`) before implementation changes.
- Keep local model runtime concerns isolated from gateway policy/routing concerns.

## Architecture

Primary references:

- `docs/contracts/openai-embeddings-compatible-v1.md`
- `docs/man/aegis-llm-server.1`
- `docs/plans/nap-to-aegis-llm-server-phased-plan.md`

## Constraints

- HTTP server only.
- Embeddings-first scope; chat/completions are out of scope unless explicitly planned.
- `aegis-llm-proxy` is the gateway; this repo is a backend local model-serving runtime.
- Keep implementation cloud-agnostic and portable.
