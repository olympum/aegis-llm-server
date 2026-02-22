# NAP + Aegis -> aegis-llm-server Phased Rewrite / Port Plan

Last updated: 2026-02-22

## Locked Decisions

1. `aegis-llm-server` is embeddings-first.
2. HTTP-only service surface.
3. `aegis-llm-proxy` remains caller-facing gateway; `aegis-llm-server` is backend local model runtime.
4. Local-first implementation and validation before hosted deployment variants.
5. No long compatibility window; prefer one-time cutover per caller path.

## Scope and Constraints

`aegis-llm-server` owns:

1. local model loading/runtime concerns,
2. embedding generation endpoint behavior,
3. local backend health and model introspection.

Out of scope:

1. provider routing/auth policies,
2. OpenAI chat/completions gateway behavior,
3. domain triage logic.

## Source Inventory

Primary extraction source (NAP):

1. local embedding-related behavior currently mixed into `platform/llm-inference/...`.

Primary integration consumers:

1. `aegis-llm-proxy` backend routing path for local embeddings,
2. RAG and tuple-space embedding callers via proxy contract.

## Phase Plan

## Phase 0: Contract Freeze

Goal: freeze embeddings-first contract.

Deliverables:

1. Contract doc for `/health`, `/v1/models`, `/v1/embeddings`.
2. Canonical error envelope and status code behavior.
3. Conformance fixtures for success and failure cases.

Exit gate:

1. Contract fixtures pass.
2. Caller expectations documented.

## Phase 1: Local Runtime Baseline

Goal: stable local service with deterministic and real backends.

Deliverables:

1. Backend abstraction (`deterministic`, `sentence_transformers`).
2. Embeddings endpoint correctness tests.
3. Startup/health behavior for backend initialization failures.

Exit gate:

1. Unit tests pass.
2. Latency and throughput baseline published.

## Phase 2: Proxy Integration

Goal: integrate `aegis-llm-proxy` with `aegis-llm-server` local backend path.

Deliverables:

1. Proxy backend routing to local embeddings server.
2. Compatibility tests through proxy endpoint.
3. Failure/timeout fallback behavior defined.

Exit gate:

1. Proxy-to-server integration tests pass.
2. Local embeddings path meets agreed SLO.

## Phase 3: NAP Cutover

Goal: remove duplicated local model-serving concerns from NAP.

Deliverables:

1. Deploy and route local embedding calls to `aegis-llm-server` via proxy strategy.
2. Remove legacy local-serving codepaths in NAP llm-inference stack.
3. Keep rollback path artifact/version based.

Exit gate:

1. NAP callers stable on extracted service.
2. Legacy code removed.

## Acceptance Metrics

1. Contract conformance: zero unresolved schema mismatches.
2. Reliability: low error-rate and stable health checks.
3. Performance: agreed p50/p95 embeddings latency and throughput.
4. De-dup completion: legacy NAP local-serving code removed.
