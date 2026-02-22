#!/usr/bin/env python3
"""Benchmark POST /v1/embeddings latency and throughput."""

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


@dataclass
class RequestResult:
    ok: bool
    status_code: int
    latency_ms: float
    error_code: str | None


async def send_embeddings_request(
    client,
    *,
    url: str,
    model: str,
    batch_size: int,
    input_chars: int,
    req_index: int,
) -> RequestResult:
    """Send one embeddings request and time it."""
    if batch_size == 1:
        payload_input: str | list[str] = make_input_text(input_chars, req_index)
    else:
        payload_input = [
            make_input_text(input_chars, req_index * batch_size + i)
            for i in range(batch_size)
        ]

    payload = {
        "model": model,
        "input": payload_input,
    }

    started = time.perf_counter()
    try:
        response = await client.post(url, json=payload)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        if response.status_code == 200:
            return RequestResult(
                ok=True,
                status_code=response.status_code,
                latency_ms=elapsed_ms,
                error_code=None,
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
        )
    except Exception:
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        return RequestResult(
            ok=False,
            status_code=0,
            latency_ms=elapsed_ms,
            error_code="request_exception",
        )


async def run_load(args) -> tuple[list[RequestResult], float]:
    """Run concurrent requests and collect request-level results."""
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
    lock = asyncio.Lock()
    req_counter = 0

    async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
        for i in range(args.warmup):
            await send_embeddings_request(
                client,
                url=url,
                model=args.model,
                batch_size=args.batch_size,
                input_chars=args.input_chars,
                req_index=i,
            )

        async def worker() -> None:
            nonlocal req_counter
            while True:
                async with lock:
                    if req_counter >= args.requests:
                        return
                    current = req_counter
                    req_counter += 1

                result = await send_embeddings_request(
                    client,
                    url=url,
                    model=args.model,
                    batch_size=args.batch_size,
                    input_chars=args.input_chars,
                    req_index=current + args.warmup,
                )
                results.append(result)

        workers = [asyncio.create_task(worker()) for _ in range(args.concurrency)]
        started = time.perf_counter()
        await asyncio.gather(*workers)
        total_seconds = time.perf_counter() - started

    return results, total_seconds


def build_summary(args, results: list[RequestResult], total_seconds: float) -> dict[str, object]:
    """Build benchmark summary metrics."""
    success = [r for r in results if r.ok]
    failures = [r for r in results if not r.ok]
    success_latencies = sorted(r.latency_ms for r in success)

    error_breakdown: dict[str, int] = {}
    for item in failures:
        key = item.error_code or f"http_{item.status_code}"
        error_breakdown[key] = error_breakdown.get(key, 0) + 1

    summary = {
        "config": {
            "base_url": args.base_url,
            "model": args.model,
            "requests": args.requests,
            "warmup": args.warmup,
            "concurrency": args.concurrency,
            "batch_size": args.batch_size,
            "input_chars": args.input_chars,
            "timeout_seconds": args.timeout_seconds,
        },
        "results": {
            "total_requests": len(results),
            "success_requests": len(success),
            "failed_requests": len(failures),
            "error_breakdown": error_breakdown,
            "elapsed_seconds": total_seconds,
            "requests_per_second": (len(results) / total_seconds) if total_seconds > 0 else 0.0,
            "texts_per_second": (
                (len(success) * args.batch_size) / total_seconds if total_seconds > 0 else 0.0
            ),
            "latency_ms": {
                "min": success_latencies[0] if success_latencies else 0.0,
                "mean": statistics.fmean(success_latencies) if success_latencies else 0.0,
                "p50": percentile(success_latencies, 50),
                "p95": percentile(success_latencies, 95),
                "p99": percentile(success_latencies, 99),
                "max": success_latencies[-1] if success_latencies else 0.0,
            },
        },
    }
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark aegis-llm-server embeddings endpoint.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8181")
    parser.add_argument("--model", default="nomic-embed-text")
    parser.add_argument("--requests", type=int, default=300)
    parser.add_argument("--warmup", type=int, default=30)
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--input-chars", type=int, default=256)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if args.requests <= 0:
        raise SystemExit("--requests must be > 0")
    if args.warmup < 0:
        raise SystemExit("--warmup must be >= 0")
    if args.concurrency <= 0:
        raise SystemExit("--concurrency must be > 0")
    if args.batch_size <= 0:
        raise SystemExit("--batch-size must be > 0")
    if args.input_chars <= 0:
        raise SystemExit("--input-chars must be > 0")
    if args.timeout_seconds <= 0:
        raise SystemExit("--timeout-seconds must be > 0")


def main() -> None:
    args = parse_args()
    validate_args(args)
    results, total_seconds = asyncio.run(run_load(args))
    summary = build_summary(args, results, total_seconds)

    print(json.dumps(summary, indent=2))

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote benchmark report: {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
