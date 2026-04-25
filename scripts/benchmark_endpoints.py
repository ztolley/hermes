#!/usr/bin/env python3
"""Benchmark the local Hermes/Qwen endpoints.

The script intentionally uses only the Python standard library so it can run on
the DGX Spark host without setting up a project virtualenv.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


TEST_IMAGE_PNG = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0l"
    "EQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


@dataclass
class EndpointResult:
    name: str
    ok: bool
    latency_s: float
    completion_tokens: int | None = None
    output_tok_s: float | None = None
    ttft_s: float | None = None
    error: str | None = None


def load_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def request_json(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str] | None = None,
    timeout: int = 180,
) -> tuple[dict[str, Any], float]:
    body = json.dumps(payload).encode("utf-8")
    request_headers = {"Content-Type": "application/json"}
    if headers:
        request_headers.update(headers)
    request = urllib.request.Request(url, data=body, headers=request_headers)
    start = time.perf_counter()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.loads(response.read().decode("utf-8"))
    return data, time.perf_counter() - start


def request_stream_ttft(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str] | None = None,
    timeout: int = 180,
) -> float | None:
    stream_payload = dict(payload)
    stream_payload["stream"] = True
    body = json.dumps(stream_payload).encode("utf-8")
    request_headers = {"Content-Type": "application/json"}
    if headers:
        request_headers.update(headers)
    request = urllib.request.Request(url, data=body, headers=request_headers)
    start = time.perf_counter()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        for raw_line in response:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line.startswith("data: "):
                continue
            chunk = line.removeprefix("data: ").strip()
            if chunk == "[DONE]":
                break
            try:
                data = json.loads(chunk)
            except json.JSONDecodeError:
                continue
            choices = data.get("choices") or []
            if not choices:
                continue
            choice = choices[0]
            delta = choice.get("delta") or {}
            text = delta.get("content") or choice.get("text") or ""
            if text:
                return time.perf_counter() - start
    return None


def result_from_response(
    name: str,
    data: dict[str, Any],
    latency_s: float,
    ttft_s: float | None,
) -> EndpointResult:
    usage = data.get("usage") or {}
    completion_tokens = usage.get("completion_tokens")
    output_tok_s = None
    if isinstance(completion_tokens, int) and latency_s > 0:
        output_tok_s = completion_tokens / latency_s
    return EndpointResult(
        name=name,
        ok=True,
        latency_s=latency_s,
        completion_tokens=completion_tokens,
        output_tok_s=output_tok_s,
        ttft_s=ttft_s,
    )


def benchmark_endpoint(
    name: str,
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str] | None,
    runs: int,
    timeout: int,
) -> list[EndpointResult]:
    results: list[EndpointResult] = []
    for _ in range(runs):
        try:
            ttft_s = request_stream_ttft(url, payload, headers, timeout)
            data, latency_s = request_json(url, payload, headers, timeout)
            results.append(result_from_response(name, data, latency_s, ttft_s))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError) as exc:
            results.append(
                EndpointResult(name=name, ok=False, latency_s=0.0, error=str(exc))
            )
    return results


def median(values: list[float | None]) -> float | None:
    clean = [value for value in values if value is not None]
    if not clean:
        return None
    return statistics.median(clean)


def print_results(results: list[EndpointResult]) -> int:
    failed = False
    by_name: dict[str, list[EndpointResult]] = {}
    for result in results:
        by_name.setdefault(result.name, []).append(result)

    for name, endpoint_results in by_name.items():
        failures = [result for result in endpoint_results if not result.ok]
        successes = [result for result in endpoint_results if result.ok]
        print(f"\n{name}")
        print("-" * len(name))
        if failures:
            failed = True
            for result in failures:
                print(f"FAILED: {result.error}")
        if successes:
            latency = median([result.latency_s for result in successes])
            ttft = median([result.ttft_s for result in successes])
            toks = median([result.output_tok_s for result in successes])
            completion = median(
                [
                    float(result.completion_tokens)
                    for result in successes
                    if result.completion_tokens is not None
                ]
            )
            print(f"runs: {len(successes)}")
            if ttft is not None:
                print(f"median_ttft_s: {ttft:.3f}")
            if latency is not None:
                print(f"median_latency_s: {latency:.3f}")
            if completion is not None:
                print(f"median_completion_tokens: {completion:.0f}")
            if toks is not None:
                print(f"median_output_tok_s: {toks:.2f}")
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--hermes-runs", type=int, default=1)
    parser.add_argument("--include-vision", action="store_true")
    parser.add_argument("--vision-runs", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()

    env = {**load_dotenv(Path(args.env_file)), **os.environ}
    qwen_port = env.get("QWEN_PORT", "3001")
    qwen_vl_port = env.get("QWEN_VL_PORT", "3003")
    hermes_port = env.get("HERMES_GATEWAY_PORT", "8000")
    qwen_model = env.get("QWEN_MODEL", "saricles/Qwen3-Coder-Next-NVFP4-GB10")
    qwen_vl_model = env.get("QWEN_VL_MODEL", "Qwen/Qwen3-VL-8B-Instruct-FP8")

    results: list[EndpointResult] = []
    results.extend(
        benchmark_endpoint(
            name="qwen-large",
            url=f"http://127.0.0.1:{qwen_port}/v1/chat/completions",
            payload={
                "model": qwen_model,
                "messages": [
                    {
                        "role": "user",
                        "content": "Write a compact Python function that checks whether a string is a palindrome. Return only code.",
                    }
                ],
                "max_tokens": 96,
                "temperature": 0,
            },
            headers=None,
            runs=args.runs,
            timeout=args.timeout,
        )
    )
    if args.include_vision:
        results.extend(
            benchmark_endpoint(
                name="qwen-vl",
                url=f"http://127.0.0.1:{qwen_vl_port}/v1/chat/completions",
                payload={
                    "model": qwen_vl_model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "Describe this test image in one short sentence.",
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{TEST_IMAGE_PNG}",
                                    },
                                },
                            ],
                        }
                    ],
                    "max_tokens": 32,
                    "temperature": 0,
                },
                headers=None,
                runs=args.vision_runs,
                timeout=args.timeout,
            )
        )
    hermes_key = env.get("HERMES_API_KEY")
    if hermes_key:
        results.extend(
            benchmark_endpoint(
                name="hermes-gateway",
                url=f"http://127.0.0.1:{hermes_port}/v1/chat/completions",
                payload={
                    "model": "hermes-agent",
                    "messages": [
                        {
                            "role": "user",
                            "content": "Reply exactly: benchmark ok",
                        }
                    ],
                    "max_tokens": 16,
                    "temperature": 0,
                },
                headers={"Authorization": f"Bearer {hermes_key}"},
                runs=args.hermes_runs,
                timeout=args.timeout,
            )
        )
    else:
        print("Skipping hermes-gateway: HERMES_API_KEY is not set", file=sys.stderr)

    return print_results(results)


if __name__ == "__main__":
    raise SystemExit(main())
