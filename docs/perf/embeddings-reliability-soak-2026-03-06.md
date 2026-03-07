# Embeddings Reliability Soak Report (2026-03-06)

This document is a dated local soak artifact, not primary operator guidance.

Use [README.md](../../README.md) for current setup and configuration guidance. Use [docs/contracts/openai-embeddings-compatible-v1.md](../contracts/openai-embeddings-compatible-v1.md) for the normative HTTP contract.

This document publishes a repeatable sustained-load reliability run for
`POST /v1/embeddings`.

## Environment

- Date: 2026-03-06
- Host OS: Darwin arm64
- Python: 3.14.2
- Service: `aegis-llm-server` local run

## Soak Profile

- Server command:

```bash
uv run uvicorn aegis_llm_server.main:app --host 127.0.0.1 --port 8193 --no-access-log
```

- Soak command:

```bash
uv run python scripts/soak_embeddings.py \
  --base-url http://127.0.0.1:8193 \
  --duration-seconds 600 \
  --bucket-seconds 60 \
  --concurrency 20 \
  --batch-size 1 \
  --input-chars 256 \
  --output docs/perf/results/deterministic-soak-10m-20260306.json
```

- Raw result artifact: `docs/perf/results/deterministic-soak-10m-20260306.json`

## Reliability Rubric

The local reliability pass/fail rubric for this deterministic soak profile is:

1. Overall error rate must be `<= 0.1%`.
2. Worst full-window p95 latency must be `<= 250 ms`.
3. p95 latency drift from the first full window to the last full window must be `<= 100%`.

These guardrails leave room for normal local-machine variance while still
catching sustained regressions in error rate or tail latency.

This rubric is specific to this local deterministic soak profile and should not be read as a general service-wide SLO.

## Result

Status: `PASS`

Summary:

- Total requests: `325,408`
- Failed requests: `0`
- Overall error rate: `0.0%`
- Overall throughput: `542.32 req/s`
- Overall p50 latency: `15.95 ms`
- Overall p95 latency: `125.34 ms`
- Overall p99 latency: `211.76 ms`
- Worst full-window p95 latency: `164.95 ms`
- p95 drift (first full window -> last full window): `43.18%`

Rubric evaluation:

| Check | Observed | Threshold | Result |
| --- | --- | --- | --- |
| Overall error rate | `0.0%` | `<= 0.1%` | Pass |
| Worst full-window p95 latency | `164.95 ms` | `<= 250 ms` | Pass |
| p95 latency drift | `43.18%` | `<= 100%` | Pass |

## Window Summary

| Window | Requests | Error rate | p50 ms | p95 ms | p99 ms |
| --- | --- | --- | --- | --- | --- |
| `0-60s` | `35,405` | `0.0%` | `14.89` | `115.21` | `189.14` |
| `60-120s` | `33,553` | `0.0%` | `15.26` | `121.95` | `203.54` |
| `120-180s` | `33,794` | `0.0%` | `15.43` | `121.13` | `202.51` |
| `180-240s` | `36,087` | `0.0%` | `14.58` | `115.05` | `188.61` |
| `240-300s` | `33,815` | `0.0%` | `15.95` | `121.73` | `203.11` |
| `300-360s` | `32,548` | `0.0%` | `16.17` | `124.53` | `209.40` |
| `360-420s` | `31,771` | `0.0%` | `16.72` | `128.30` | `210.57` |
| `420-480s` | `31,424` | `0.0%` | `16.26` | `129.74` | `211.14` |
| `480-540s` | `32,672` | `0.0%` | `15.93` | `126.19` | `211.76` |
| `540-600s` | `24,319` | `0.0%` | `20.15` | `164.95` | `342.01` |

## Notes

1. The published artifact intentionally uses an isolated localhost port and
   disabled access logging to reduce ambient local noise during the soak.
2. The final window showed the highest tail latency but remained within the
   selected guardrail and did not produce errors.
3. Future regressions should be compared against the same profile and rubric
   before tightening thresholds.
