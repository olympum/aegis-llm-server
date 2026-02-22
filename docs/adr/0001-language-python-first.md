# ADR 0001: Python-First Implementation for Local Model Serving

Date: 2026-02-22
Status: Accepted

## Context

`aegis-llm-server` is a local model-serving runtime focused on embeddings.
It must move fast on model backend integrations and local hardware/runtime behavior.

## Decision

Implement `aegis-llm-server` Python-first.

## Why

1. Strong local-model ecosystem support (sentence-transformers and adjacent tooling).
2. Fast iteration for backend integration and diagnostics.
3. Lower extraction risk from existing Python-heavy local-serving paths.
4. HTTP contract decouples callers from implementation language.

## Constraints

1. Keep contract stable and versioned.
2. Keep backend adapters isolated behind explicit interfaces.
3. Keep service narrow (embeddings-first) while gateway concerns stay in `aegis-llm-proxy`.

## Rust Port Trigger Criteria

Consider Rust hotspot extraction only when:

1. profiling proves a specific bottleneck in this service (not network/proxy overhead),
2. Python-level tuning is exhausted,
3. there is measurable SLO/cost benefit.
