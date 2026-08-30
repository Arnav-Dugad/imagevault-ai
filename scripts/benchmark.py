#!/usr/bin/env python3
"""Measure actual local embedding and authenticated API latency without inventing results."""

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))


def timed(function, repetitions: int) -> list[float]:
    samples = []
    for _ in range(repetitions):
        started = time.perf_counter()
        function()
        samples.append(time.perf_counter() - started)
    return samples


def summarize(samples: list[float]) -> dict[str, float]:
    ordered = sorted(samples)
    return {
        "samples": len(samples),
        "average_ms": statistics.mean(samples) * 1000,
        "median_ms": statistics.median(samples) * 1000,
        "p95_ms": ordered[max(0, round(0.95 * len(ordered)) - 1)] * 1000,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--base-url")
    parser.add_argument("--token")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not args.image.is_file():
        raise SystemExit(f"Image not found: {args.image}")

    from app.worker.embedder import embedder

    image_bytes = args.image.read_bytes()
    warmup = embedder.image_embedding(image_bytes)
    embedding_times = timed(lambda: embedder.image_embedding(image_bytes), args.repetitions)
    results: dict[str, object] = {
        "image": str(args.image),
        "device": warmup[2],
        "embedding": summarize(embedding_times),
    }
    if args.base_url and args.token:
        headers = {"Authorization": f"Bearer {args.token}"}
        with httpx.Client(base_url=args.base_url, headers=headers, timeout=30) as client:
            results["gallery_query"] = summarize(
                timed(lambda: client.get("/api/images?page_size=24").raise_for_status(), args.repetitions)
            )
    print(json.dumps(results, indent=2))
    if args.output:
        args.output.write_text(json.dumps(results, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
