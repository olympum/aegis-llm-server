# Aegis -> aegis-llm-server Phased Rewrite / Port Plan

Last updated: 2026-02-22

## Execution Rebaseline (2026-02-22)

This repository now prioritizes local, cloud-agnostic deliverables only.

Local deliverables stay in this repo:

1. embeddings API contract and conformance,
2. local backend runtime behavior and hardening,
3. local telemetry and observability artifacts,
4. local performance baselines.

Deferred external deliverables move out of this repo:

1. corp/NAP/proxy integration and routing rollout,
2. cross-system cutover orchestration in consumer stacks.

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

Primary extraction source:

1. local embedding-related behavior currently mixed into legacy local-serving stacks.

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

Goal: stable local service with deterministic and real in-process model backends.

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

## Phase 3: Legacy Cutover

Goal: remove duplicated local model-serving concerns from legacy stacks.

Deliverables:

1. Deploy and route local embedding calls to `aegis-llm-server` via proxy strategy.
2. Remove legacy local-serving codepaths in upstream caller stacks.
3. Keep rollback path artifact/version based.

Exit gate:

1. Callers stable on extracted service.
2. Legacy code removed.

## Acceptance Metrics

1. Contract conformance: zero unresolved schema mismatches.
2. Reliability: low error-rate and stable health checks.
3. Performance: agreed p50/p95 embeddings latency and throughput.
4. De-dup completion: legacy local-serving code removed.

## Status Scorecard (Local vs External)

Scoring scale:

1. `100` = complete and evidenced in this repo.
2. `50-99` = partially complete; at least one required artifact missing.
3. `0` = not started in this repo or intentionally deferred external.

| Workstream | Scope | Status | Score | Evidence |
| --- | --- | --- | --- | --- |
| Phase 0: Contract Freeze | Local | Complete | 100 | `docs/contracts/openai-embeddings-compatible-v1.md`, `tests/unit/test_embeddings_api.py`, `aegis_llm_server/api/routes.py` |
| Phase 1: Local Runtime Baseline | Local | Complete | 100 | Backends + tests in `aegis_llm_server/backends/*` and `tests/unit/*`; perf baseline published in `docs/perf/embeddings-baseline-2026-02-22.md` |
| Phase 2: Proxy Integration | External (deferred) | Deferred | 0 | Managed by caller-facing gateway/consumer integration tracks |
| Phase 3: Legacy Cutover | External (deferred) | Deferred | 0 | Managed by upstream consumer rollout/cutover tracks |
| Acceptance metric 1 (contract conformance) | Local | Complete | 100 | Contract + API tests aligned |
| Acceptance metric 2 (reliability) | Local | Mostly complete | 80 | Error handling/hardening + health endpoints in place; no long-run reliability report artifact yet |
| Acceptance metric 3 (performance) | Local | Complete | 100 | p50/p95 and throughput baselines published in `docs/perf/embeddings-baseline-2026-02-22.md` |
| Acceptance metric 4 (de-dup completion) | External (deferred) | Deferred | 0 | Depends on external legacy code retirement |

Local-only weighted readiness (Phase 0 + Phase 1 + local acceptance metrics): `96/100`.

## Deferred External Tracks

The following work is intentionally pushed out of this repo:

1. `aegis-llm-proxy` backend routing integration,
2. corp load balancer/NAP-specific integration concerns,
3. cross-service cutover and rollback orchestration.

## Next Local Work Item (Selected)

Publish a reliability soak and robustness report artifact.

Deliverables:

1. Add a repeatable soak script/profile for sustained embeddings load (for example 10-30 minutes).
2. Capture error-rate and latency drift over time as a report under `docs/perf/`.
3. Define a local reliability pass/fail rubric (for example error-rate threshold + tail latency guardrail).

Exit gate for this item:

1. At least one soak run report is published with reproducible commands.
2. Reliability guardrails are explicitly documented for future regressions.
