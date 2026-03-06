#!/usr/bin/env python3
"""Run a sustained-load soak test for POST /v1/embeddings."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
import json
import math
from pathlib import Path
import statistics
import string
import sys
import time


def percentile(values: list[float], p: float) -> float:
    """Compute a percentile using linear interpolation."""
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]

    pos = (len(values) - 1) * (p / 100.0)
    lower = math.floor(pos)
    upper = math.ceil(pos)
    if lower == upper:
        return values[int(pos)]

    lower_val = values[lower]
    upper_val = values[upper]
    return lower_val + (upper_val - lower_val) * (pos - lower)


def make_input_text(chars: int, index: int) -> str:
    """Build a deterministic input string with approximate length."""
    if chars <= 0:
        return f"sample-{index}"

    seed = f"snippet-{index} "
    if len(seed) >= chars:
        return seed[:chars]

    filler = string.ascii_lowercase + " "
    repeats = (chars - len(seed)) // len(filler) + 1
    text = seed + (filler * repeats)
    return text[:chars]


@dataclass(slots=True)
class RequestResult:
    ok: bool
    status_code: int
    latency_ms: float
    error_code: str | None
    completed_at_s: float


def summarize_latencies(values: list[float]) -> dict[str, float]:
    """Build latency summary fields."""
    sorted_values = sorted(values)
    if not sorted_values:
        return {
            "min": 0.0,
            "mean": 0.0,
            "p50": 0.0,
            "p95": 0.0,
            "p99": 0.0,
            "max": 0.0,
        }
    return {
        "min": sorted_values[0],
        "mean": statistics.fmean(sorted_values),
        "p50": percentile(sorted_values, 50),
        "p95": percentile(sorted_values, 95),
        "p99": percentile(sorted_values, 99),
        "max": sorted_values[-1],
    }


async def send_embeddings_request(
    client,
    *,
    url: str,
    model: str,
    batch_size: int,
    input_chars: int,
    req_index: int,
    started_at: float,
) -> RequestResult:
    """Send one embeddings request and time it."""
    if batch_size == 1:
        payload_input: str | list[str] = make_input_text(input_chars, req_index)
    else:
        payload_input = [
            make_input_text(input_chars, req_index * batch_size + offset)
            for offset in range(batch_size)
        ]

    payload = {
        "model": model,
        "input": payload_input,
    }

    request_started = time.perf_counter()
    try:
        response = await client.post(url, json=payload)
        elapsed_ms = (time.perf_counter() - request_started) * 1000.0
        completed_at_s = time.perf_counter() - started_at
        if response.status_code == 200:
            return RequestResult(
                ok=True,
                status_code=response.status_code,
                latency_ms=elapsed_ms,
                error_code=None,
                completed_at_s=completed_at_s,
            )

        error_code: str | None = None
        try:
            body = response.json()
            error_code = body.get("error", {}).get("code")
        except Exception:
            error_code = None

        return RequestResult(
            ok=False,
            status_code=response.status_code,
            latency_ms=elapsed_ms,
            error_code=error_code,
            completed_at_s=completed_at_s,
        )
    except Exception:
        elapsed_ms = (time.perf_counter() - request_started) * 1000.0
        return RequestResult(
            ok=False,
            status_code=0,
            latency_ms=elapsed_ms,
            error_code="request_exception",
            completed_at_s=time.perf_counter() - started_at,
        )


async def run_soak(args: argparse.Namespace) -> tuple[list[RequestResult], float]:
    """Run concurrent requests for a fixed duration."""
    try:
        import httpx
    except ModuleNotFoundError:
        print(
            "Missing dependency: httpx. Install dev dependencies "
            "with `pip install -e \".[dev]\"`.",
            file=sys.stderr,
        )
        raise SystemExit(2)

    url = f"{args.base_url.rstrip('/')}/v1/embeddings"
    timeout = httpx.Timeout(args.timeout_seconds)
    limits = httpx.Limits(max_connections=args.concurrency, max_keepalive_connections=args.concurrency)

    results: list[RequestResult] = []
    req_counter = 0
    counter_lock = asyncio.Lock()
    results_lock = asyncio.Lock()

    async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
        for warmup_index in range(args.warmup_requests):
            await send_embeddings_request(
                client,
                url=url,
                model=args.model,
                batch_size=args.batch_size,
                input_chars=args.input_chars,
                req_index=warmup_index,
                started_at=time.perf_counter(),
            )

        started = time.perf_counter()

        async def worker() -> None:
            nonlocal req_counter
            while True:
                now = time.perf_counter()
                if (now - started) >= args.duration_seconds:
                    return

                async with counter_lock:
                    current = req_counter
                    req_counter += 1

                result = await send_embeddings_request(
                    client,
                    url=url,
                    model=args.model,
                    batch_size=args.batch_size,
                    input_chars=args.input_chars,
                    req_index=current + args.warmup_requests,
                    started_at=started,
                )
                async with results_lock:
                    results.append(result)

        workers = [asyncio.create_task(worker()) for _ in range(args.concurrency)]
        await asyncio.gather(*workers)
        total_seconds = time.perf_counter() - started

    return results, total_seconds


def build_windows(
    results: list[RequestResult],
    bucket_seconds: int,
    total_seconds: float,
) -> list[dict[str, object]]:
    """Group per-request results into fixed time windows."""
    if not results:
        return []

    bucket_count = max(1, math.ceil(total_seconds / bucket_seconds))
    windows: list[dict[str, object]] = []
    for bucket_index in range(bucket_count):
        window_start = bucket_index * bucket_seconds
        window_end = (bucket_index + 1) * bucket_seconds
        bucket_items = [
            item for item in results if window_start <= item.completed_at_s < window_end
        ]
        successes = [item for item in bucket_items if item.ok]
        failures = [item for item in bucket_items if not item.ok]
        latencies = [item.latency_ms for item in successes]
        windows.append(
            {
                "window_index": bucket_index,
                "start_second": window_start,
                "end_second": window_end,
                "complete_window": window_end <= total_seconds,
                "request_count": len(bucket_items),
                "success_requests": len(successes),
                "failed_requests": len(failures),
                "error_rate_pct": ((len(failures) / len(bucket_items)) * 100.0) if bucket_items else 0.0,
                "latency_ms": summarize_latencies(latencies),
            }
        )
    return windows


def build_error_breakdown(results: list[RequestResult]) -> dict[str, int]:
    """Count errors by code."""
    breakdown: dict[str, int] = {}
    for item in results:
        if item.ok:
            continue
        key = item.error_code or f"http_{item.status_code}"
        breakdown[key] = breakdown.get(key, 0) + 1
    return breakdown


def compute_drift(windows: list[dict[str, object]]) -> dict[str, float | None]:
    """Compare the first and last populated windows."""
    complete_populated = [
        window for window in windows if window["request_count"] and window["complete_window"]
    ]
    populated = complete_populated or [window for window in windows if window["request_count"]]
    if len(populated) < 2:
        return {
            "first_window_index": None,
            "last_window_index": None,
            "p95_latency_drift_pct": None,
            "error_rate_drift_pct": None,
        }

    first = populated[0]
    last = populated[-1]
    first_p95 = float(first["latency_ms"]["p95"])
    last_p95 = float(last["latency_ms"]["p95"])
    if first_p95 > 0:
        p95_drift_pct = ((last_p95 - first_p95) / first_p95) * 100.0
    else:
        p95_drift_pct = 0.0 if last_p95 == 0 else None

    return {
        "first_window_index": int(first["window_index"]),
        "last_window_index": int(last["window_index"]),
        "p95_latency_drift_pct": p95_drift_pct,
        "error_rate_drift_pct": float(last["error_rate_pct"]) - float(first["error_rate_pct"]),
    }


def evaluate_rubric(
    *,
    results: list[RequestResult],
    windows: list[dict[str, object]],
    drift: dict[str, float | None],
    max_error_rate_pct: float,
    max_window_p95_ms: float,
    max_p95_drift_pct: float,
) -> dict[str, object]:
    """Apply a simple pass/fail rubric for the soak run."""
    total_requests = len(results)
    failures = len([item for item in results if not item.ok])
    overall_error_rate_pct = (failures / total_requests) * 100.0 if total_requests else 0.0
    full_windows = [window for window in windows if window["complete_window"] and window["request_count"]]
    evaluated_windows = full_windows or [window for window in windows if window["request_count"]]
    worst_window_p95_ms = max(
        (float(window["latency_ms"]["p95"]) for window in evaluated_windows),
        default=0.0,
    )
    p95_drift_pct = drift["p95_latency_drift_pct"]
    if p95_drift_pct is None:
        drift_pass = True
    else:
        drift_pass = p95_drift_pct <= max_p95_drift_pct

    checks = [
        {
            "name": "overall_error_rate",
            "passed": overall_error_rate_pct <= max_error_rate_pct,
            "observed": overall_error_rate_pct,
            "threshold": max_error_rate_pct,
            "unit": "pct",
        },
        {
            "name": "worst_window_p95_latency",
            "passed": worst_window_p95_ms <= max_window_p95_ms,
            "observed": worst_window_p95_ms,
            "threshold": max_window_p95_ms,
            "unit": "ms",
        },
        {
            "name": "p95_latency_drift",
            "passed": drift_pass,
            "observed": p95_drift_pct,
            "threshold": max_p95_drift_pct,
            "unit": "pct",
        },
    ]
    return {
        "passed": all(check["passed"] for check in checks),
        "checks": checks,
    }


def build_summary(args: argparse.Namespace, results: list[RequestResult], total_seconds: float) -> dict[str, object]:
    """Build the final soak report payload."""
    successes = [item for item in results if item.ok]
    latencies = [item.latency_ms for item in successes]
    windows = build_windows(results, args.bucket_seconds, total_seconds)
    drift = compute_drift(windows)
    rubric = evaluate_rubric(
        results=results,
        windows=windows,
        drift=drift,
        max_error_rate_pct=args.max_error_rate_pct,
        max_window_p95_ms=args.max_window_p95_ms,
        max_p95_drift_pct=args.max_p95_drift_pct,
    )

    return {
        "config": {
            "base_url": args.base_url,
            "model": args.model,
            "duration_seconds": args.duration_seconds,
            "warmup_requests": args.warmup_requests,
            "concurrency": args.concurrency,
            "batch_size": args.batch_size,
            "input_chars": args.input_chars,
            "timeout_seconds": args.timeout_seconds,
            "bucket_seconds": args.bucket_seconds,
            "max_error_rate_pct": args.max_error_rate_pct,
            "max_window_p95_ms": args.max_window_p95_ms,
            "max_p95_drift_pct": args.max_p95_drift_pct,
        },
        "results": {
            "total_requests": len(results),
            "success_requests": len(successes),
            "failed_requests": len(results) - len(successes),
            "error_breakdown": build_error_breakdown(results),
            "elapsed_seconds": total_seconds,
            "requests_per_second": (len(results) / total_seconds) if total_seconds > 0 else 0.0,
            "texts_per_second": (
                (len(successes) * args.batch_size) / total_seconds if total_seconds > 0 else 0.0
            ),
            "latency_ms": summarize_latencies(latencies),
        },
        "windows": windows,
        "drift": drift,
        "rubric": rubric,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Soak test aegis-llm-server embeddings endpoint.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8181")
    parser.add_argument("--model", default="nomic-embed-text")
    parser.add_argument("--duration-seconds", type=int, default=600)
    parser.add_argument("--warmup-requests", type=int, default=30)
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--input-chars", type=int, default=256)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--bucket-seconds", type=int, default=60)
    parser.add_argument("--max-error-rate-pct", type=float, default=0.1)
    parser.add_argument("--max-window-p95-ms", type=float, default=250.0)
    parser.add_argument("--max-p95-drift-pct", type=float, default=100.0)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if args.duration_seconds <= 0:
        raise SystemExit("--duration-seconds must be > 0")
    if args.warmup_requests < 0:
        raise SystemExit("--warmup-requests must be >= 0")
    if args.concurrency <= 0:
        raise SystemExit("--concurrency must be > 0")
    if args.batch_size <= 0:
        raise SystemExit("--batch-size must be > 0")
    if args.input_chars <= 0:
        raise SystemExit("--input-chars must be > 0")
    if args.timeout_seconds <= 0:
        raise SystemExit("--timeout-seconds must be > 0")
    if args.bucket_seconds <= 0:
        raise SystemExit("--bucket-seconds must be > 0")
    if args.max_error_rate_pct < 0:
        raise SystemExit("--max-error-rate-pct must be >= 0")
    if args.max_window_p95_ms <= 0:
        raise SystemExit("--max-window-p95-ms must be > 0")
    if args.max_p95_drift_pct < 0:
        raise SystemExit("--max-p95-drift-pct must be >= 0")


def main() -> None:
    args = parse_args()
    validate_args(args)
    results, total_seconds = asyncio.run(run_soak(args))
    summary = build_summary(args, results, total_seconds)

    print(json.dumps(summary, indent=2))

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote soak report: {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
