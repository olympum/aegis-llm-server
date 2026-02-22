# Embeddings Performance Baseline (2026-02-22)

This document publishes reproducible local performance baselines for
`POST /v1/embeddings`.

## Environment

- Date: 2026-02-22
- Host OS: macOS 15.6.1 (arm64)
- Python: 3.14.3
- `uv`: 0.10.3
- Service: `aegis-llm-server` at commit `main` (local run)

## Benchmark Harness

- Script: `scripts/bench_embeddings.py`
- Raw result artifacts: `docs/perf/results/*.json`

The harness sends concurrent HTTP requests, records request-level latency, and
reports:

- success/failure counts,
- requests/sec and texts/sec,
- latency min/mean/p50/p95/p99/max (successful requests).

## Run Commands

Deterministic backend:

```bash
PORT=8191 \
AEGIS_LLM_SERVER_SERVER__PORT=8191 \
AEGIS_LLM_SERVER_EMBEDDING__BACKEND=deterministic \
uv run aegis-llm-server
```

Sentence-transformers backend (in-process local model runtime):

```bash
PORT=8192 \
AEGIS_LLM_SERVER_SERVER__PORT=8192 \
AEGIS_LLM_SERVER_EMBEDDING__BACKEND=sentence_transformers \
AEGIS_LLM_SERVER_EMBEDDING__MODEL_NAME=nomic-ai/nomic-embed-text-v1.5 \
AEGIS_LLM_SERVER_EMBEDDING__TRUST_REMOTE_CODE=true \
uv run aegis-llm-server
```

Example benchmark invocation:

```bash
uv run python scripts/bench_embeddings.py \
  --base-url http://127.0.0.1:8191 \
  --model nomic-embed-text \
  --requests 300 \
  --warmup 30 \
  --concurrency 20 \
  --batch-size 1 \
  --input-chars 256 \
  --output docs/perf/results/deterministic-batch1.json
```

## Results Summary

| Backend | Profile | Requests | Concurrency | Batch size | Input chars | Success | Fail | Req/s | Texts/s | p50 ms | p95 ms | p99 ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `deterministic` | `deterministic-batch1` | 300 | 20 | 1 | 256 | 300 | 0 | 791.55 | 791.55 | 23.52 | 31.03 | 55.86 |
| `deterministic` | `deterministic-batch8` | 300 | 20 | 8 | 128 | 300 | 0 | 122.76 | 982.10 | 142.42 | 306.99 | 1117.72 |
| `sentence_transformers` | `sentence-transformers-batch1` | 120 | 8 | 1 | 256 | 120 | 0 | 35.97 | 35.97 | 221.99 | 256.27 | 270.67 |
| `sentence_transformers` | `sentence-transformers-batch8` | 120 | 8 | 8 | 128 | 120 | 0 | 14.03 | 112.21 | 558.00 | 654.34 | 680.18 |

## Notes

1. These values are local-machine baselines, not absolute SLO guarantees.
2. Tail latency is workload and hardware sensitive; compare future runs using
   the same profile definitions above.
3. `model` in requests uses compatibility aliases (for example
   `nomic-embed-text`); server-side model loading is controlled by
   `AEGIS_LLM_SERVER_EMBEDDING__MODEL_NAME`.
4. Nomic sentence-transformers path requires `AEGIS_LLM_SERVER_EMBEDDING__TRUST_REMOTE_CODE=true`
   and local extra deps (`pip install -e ".[local]"`).
