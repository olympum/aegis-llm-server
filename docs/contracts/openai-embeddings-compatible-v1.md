# OpenAI-Compatible Embeddings Contract v1

Last updated: 2026-02-22

## Purpose

Define the stable HTTP contract for local embedding generation in `aegis-llm-server`.

This service is embeddings-first and intentionally narrow:

1. `GET /health`
2. `GET /v1/models`
3. `POST /v1/embeddings`

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
    "code": "invalid_request|upstream_error|internal",
    "message": "string"
  }
}
```

Status mapping:

1. `400 invalid_request` for unsupported model, malformed input, or configured input-size limit violations.
2. `503 upstream_error` when embeddings are disabled/unavailable.
3. `500 internal` for backend failures or invalid backend output shape (with client-safe error messages).

## Non-goals (v1)

1. Chat/completions API.
2. Multi-node scheduling.
3. Provider policy/routing behavior (owned by `aegis-llm-proxy`).
