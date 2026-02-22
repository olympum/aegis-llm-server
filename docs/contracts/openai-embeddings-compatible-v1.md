# OpenAI-Compatible Embeddings Contract v1

Last updated: 2026-02-22

## Purpose

Define the stable HTTP contract for local embedding generation in `aegis-llm-server`.

This service is embeddings-first and intentionally narrow:

1. `GET /health`
2. `GET /v1/models`
3. `POST /v1/embeddings`

Service role:

1. Runs local embedding model inference.
2. Serves as backend runtime behind caller-facing gateway layers (for example `aegis-llm-proxy`).
3. Does not own gateway routing/policy behavior.

## Endpoint: `GET /health`

### Response `200`

```json
{
  "status": "ok",
  "service": "aegis-llm-server",
  "version": "0.1.0",
  "backend": "deterministic",
  "embedding_enabled": true
}
```

### Response semantics

1. `status` is `ok` when embeddings backend is enabled and initialized.
2. `status` is `error` when embeddings are disabled or backend initialization failed.

## Endpoint: `GET /v1/models`

### Response `200`

```json
{
  "object": "list",
  "data": [
    {
      "id": "nomic-embed-text",
      "object": "model",
      "created": 1771777777,
      "owned_by": "aegis-llm-server"
    }
  ]
}
```

### Response semantics

1. Returns advertised embedding model aliases.
2. Returns an empty list when embeddings are disabled.

## Endpoint: `POST /v1/embeddings`

### Request

```json
{
  "model": "nomic-embed-text",
  "input": "hello world"
}
```

`input` may also be an array of strings:

```json
{
  "model": "nomic-embed-text",
  "input": ["hello world", "def f(): return 1"]
}
```

### Model ID semantics

1. Request `model` accepts public compatibility aliases.
2. Accepted aliases map to the configured backend model (`AEGIS_LLM_SERVER_EMBEDDING__MODEL_NAME`).
3. Alias acceptance does not imply multiple backend models are loaded.

### Backend semantics

1. `AEGIS_LLM_SERVER_EMBEDDING__BACKEND=deterministic` uses local deterministic vectors for testing/control.
2. `AEGIS_LLM_SERVER_EMBEDDING__BACKEND=sentence_transformers` uses an in-process local model runtime backend.
3. `AEGIS_LLM_SERVER_EMBEDDING__TRUST_REMOTE_CODE` controls model-specific remote-code loading in sentence-transformers (default `true` for Nomic compatibility).
4. This contract intentionally does not define inter-service forwarding behavior; caller-side routing is owned by `aegis-llm-proxy`.

### Input limit semantics

Configured limits that produce `400 invalid_request` when violated:

1. `AEGIS_LLM_SERVER_EMBEDDING__MAX_BATCH_SIZE`
2. `AEGIS_LLM_SERVER_EMBEDDING__MAX_INPUT_CHARS`
3. `AEGIS_LLM_SERVER_EMBEDDING__MAX_TOTAL_CHARS`

Backend timeout behavior:

1. `AEGIS_LLM_SERVER_EMBEDDING__BACKEND_TIMEOUT_SECONDS` controls max backend embed time.
2. Timeout returns `504 upstream_timeout`.

### Response `200`

```json
{
  "object": "list",
  "data": [
    {
      "object": "embedding",
      "index": 0,
      "embedding": [0.013, -0.021, 0.117]
    }
  ],
  "model": "nomic-embed-text",
  "usage": {
    "prompt_tokens": 2,
    "total_tokens": 2
  }
}
```

### Error responses

Canonical envelope:

```json
{
  "error": {
    "code": "invalid_request|upstream_error|upstream_timeout|internal",
    "message": "string"
  }
}
```

Status mapping:

1. `400 invalid_request` for unsupported model, malformed input, or configured input-size limit violations.
2. `503 upstream_error` when embeddings are disabled or unavailable.
3. `504 upstream_timeout` when embedding generation exceeds configured backend timeout.
4. `500 internal` for backend failures or invalid backend output shape (with client-safe error messages).

## Non-goals (v1)

1. Chat/completions API.
2. Multi-node scheduling.
3. Provider policy/routing behavior (owned by `aegis-llm-proxy`).
