#!/usr/bin/env python3
"""
LLM Benchmark Script — Token Usage & Latency Measurement

Standalone benchmarking tool that hits a Llama Stack Responses API endpoint,
measures token usage and response latency across multiple prompts and runs,
and outputs detailed CSV results with aggregate statistics.

Zero external dependencies — uses only Python stdlib (3.9+).

Usage:
    python benchmark.py --url https://your-llamastack.example.com \
                        --model "gemini/models/gemini-2.5-flash" \
                        --label gemini --runs 5

    python benchmark.py --url https://your-llamastack.example.com \
                        --model "vllm-inference/llama-32-3b-instruct" \
                        --label rhoai --runs 5
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import ssl
import statistics
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class PromptDef:
    id: str
    input: str
    category: str = "general"


@dataclass
class RunResult:
    label: str
    model: str
    prompt_id: str
    prompt_category: str
    run: int
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0
    reasoning_tokens: int = 0
    thinking_overhead: int = 0
    latency_ms: int = 0
    usage_reported: bool = False
    timestamp: str = ""
    error: str = ""
    output_preview: str = ""


@dataclass
class BenchmarkSummary:
    label: str
    model: str
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    usage_reported_count: int = 0
    avg_input_tokens: float = 0.0
    avg_output_tokens: float = 0.0
    avg_total_tokens: float = 0.0
    sum_input_tokens: int = 0
    sum_output_tokens: int = 0
    sum_total_tokens: int = 0
    avg_thinking_overhead: float = 0.0
    avg_latency_ms: float = 0.0
    median_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    min_latency_ms: int = 0
    max_latency_ms: int = 0
    avg_cached_tokens: float = 0.0
    per_category: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Default prompts (used when --prompts is not supplied)
# ---------------------------------------------------------------------------

DEFAULT_PROMPTS: list[PromptDef] = [
    PromptDef("simple-qa", "What is Kubernetes? Answer in two sentences.", "simple"),
    PromptDef(
        "code-generation",
        "Write a Python function that reads a CSV file, filters rows where the "
        "'status' column equals 'active', and returns the filtered data as a "
        "list of dictionaries. Include error handling and type hints.",
        "code",
    ),
    PromptDef(
        "reasoning-math",
        "A train leaves station A at 9:00 AM traveling at 60 mph. Another train "
        "leaves station B (300 miles away) at 10:00 AM traveling toward station A "
        "at 90 mph. At what time do they meet? Show your reasoning step by step.",
        "reasoning",
    ),
]


# ---------------------------------------------------------------------------
# HTTP helper (stdlib only, no requests/httpx)
# ---------------------------------------------------------------------------

def _build_ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def api_request(
    url: str,
    payload: dict[str, Any],
    token: Optional[str] = None,
    timeout: int = 120,
) -> tuple[dict[str, Any], int]:
    """POST JSON to url, return (response_dict, latency_ms)."""
    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    ctx = _build_ssl_context()

    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"HTTP {exc.code}: {err_body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Connection error: {exc.reason}") from exc
    latency_ms = int((time.monotonic() - t0) * 1000)
    return data, latency_ms


# ---------------------------------------------------------------------------
# Core benchmark logic
# ---------------------------------------------------------------------------

def extract_usage(response: dict[str, Any]) -> dict[str, Any]:
    """Pull token usage fields from a Llama Stack Responses API response."""
    usage = response.get("usage") or {}
    input_tokens = usage.get("input_tokens", 0) or 0
    output_tokens = usage.get("output_tokens", 0) or 0
    total_tokens = usage.get("total_tokens", 0) or 0

    input_details = usage.get("input_tokens_details") or {}
    output_details = usage.get("output_tokens_details") or {}

    cached = (input_details.get("cached_tokens", 0) or 0) if input_details else 0
    reasoning = (output_details.get("reasoning_tokens", 0) or 0) if output_details else 0

    thinking_overhead = max(0, total_tokens - input_tokens - output_tokens)

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "cached_tokens": cached,
        "reasoning_tokens": reasoning,
        "thinking_overhead": thinking_overhead,
        "usage_reported": bool(usage and (input_tokens > 0 or output_tokens > 0)),
    }


def extract_output_text(response: dict[str, Any]) -> str:
    """Get the model's text output for preview."""
    output = response.get("output", [])
    if not output:
        return ""
    for item in output:
        content = item.get("content", [])
        for c in content:
            if c.get("type") == "output_text":
                text = c.get("text", "")
                return text[:200].replace("\n", " ")
    return ""


def run_single(
    endpoint: str,
    model: str,
    prompt: PromptDef,
    label: str,
    run_num: int,
    token: Optional[str],
    timeout: int,
) -> RunResult:
    """Execute a single benchmark request."""
    ts = datetime.now(timezone.utc).isoformat()
    payload = {
        "model": model,
        "input": prompt.input,
        "stream": False,
        "store": False,
    }

    try:
        response, latency_ms = api_request(endpoint, payload, token=token, timeout=timeout)
    except Exception as exc:
        return RunResult(
            label=label,
            model=model,
            prompt_id=prompt.id,
            prompt_category=prompt.category,
            run=run_num,
            timestamp=ts,
            error=str(exc)[:300],
        )

    usage = extract_usage(response)
    preview = extract_output_text(response)

    return RunResult(
        label=label,
        model=model,
        prompt_id=prompt.id,
        prompt_category=prompt.category,
        run=run_num,
        input_tokens=usage["input_tokens"],
        output_tokens=usage["output_tokens"],
        total_tokens=usage["total_tokens"],
        cached_tokens=usage["cached_tokens"],
        reasoning_tokens=usage["reasoning_tokens"],
        thinking_overhead=usage["thinking_overhead"],
        latency_ms=latency_ms,
        usage_reported=usage["usage_reported"],
        timestamp=ts,
        output_preview=preview,
    )


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

def percentile(data: list[float], pct: float) -> float:
    """Compute the pct-th percentile of a sorted list."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * (pct / 100.0)
    f = int(k)
    c = f + 1
    if c >= len(sorted_data):
        return sorted_data[-1]
    return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])


def compute_summary(results: list[RunResult], label: str, model: str) -> BenchmarkSummary:
    """Compute aggregate statistics from benchmark results."""
    successful = [r for r in results if not r.error]
    failed = [r for r in results if r.error]
    with_usage = [r for r in successful if r.usage_reported]

    summary = BenchmarkSummary(label=label, model=model)
    summary.total_runs = len(results)
    summary.successful_runs = len(successful)
    summary.failed_runs = len(failed)
    summary.usage_reported_count = len(with_usage)

    if with_usage:
        summary.avg_input_tokens = statistics.mean([r.input_tokens for r in with_usage])
        summary.avg_output_tokens = statistics.mean([r.output_tokens for r in with_usage])
        summary.avg_total_tokens = statistics.mean([r.total_tokens for r in with_usage])
        summary.sum_input_tokens = sum(r.input_tokens for r in with_usage)
        summary.sum_output_tokens = sum(r.output_tokens for r in with_usage)
        summary.sum_total_tokens = sum(r.total_tokens for r in with_usage)
        summary.avg_thinking_overhead = statistics.mean([r.thinking_overhead for r in with_usage])
        summary.avg_cached_tokens = statistics.mean([r.cached_tokens for r in with_usage])

    if successful:
        latencies = [float(r.latency_ms) for r in successful]
        summary.avg_latency_ms = statistics.mean(latencies)
        summary.median_latency_ms = statistics.median(latencies)
        summary.p95_latency_ms = percentile(latencies, 95)
        summary.p99_latency_ms = percentile(latencies, 99)
        summary.min_latency_ms = int(min(latencies))
        summary.max_latency_ms = int(max(latencies))

    categories: dict[str, list[RunResult]] = {}
    for r in with_usage:
        categories.setdefault(r.prompt_category, []).append(r)

    for cat, cat_results in categories.items():
        summary.per_category[cat] = {
            "count": len(cat_results),
            "avg_input_tokens": round(statistics.mean([r.input_tokens for r in cat_results]), 1),
            "avg_output_tokens": round(statistics.mean([r.output_tokens for r in cat_results]), 1),
            "avg_total_tokens": round(statistics.mean([r.total_tokens for r in cat_results]), 1),
            "avg_latency_ms": round(statistics.mean([r.latency_ms for r in cat_results]), 1),
        }

    return summary


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

CSV_COLUMNS = [
    "label", "model", "prompt_id", "prompt_category", "run",
    "input_tokens", "output_tokens", "total_tokens",
    "cached_tokens", "reasoning_tokens", "thinking_overhead",
    "latency_ms", "usage_reported", "timestamp", "error",
]


def write_csv(results: list[RunResult], path: str) -> None:
    """Write results to a CSV file."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for r in results:
            row = asdict(r)
            row.pop("output_preview", None)
            writer.writerow(row)


def write_json(results: list[RunResult], summary: BenchmarkSummary, path: str) -> None:
    """Write results and summary to a JSON file."""
    data = {
        "summary": asdict(summary),
        "results": [asdict(r) for r in results],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def fmt(n: float, decimals: int = 1) -> str:
    """Format a number with comma separators."""
    if decimals == 0:
        return f"{int(n):,}"
    return f"{n:,.{decimals}f}"


def print_summary(summary: BenchmarkSummary) -> None:
    """Print a formatted summary to stdout."""
    sep = "=" * 66
    print(f"\n{sep}")
    print(f"  BENCHMARK SUMMARY")
    print(sep)
    print(f"  Label:            {summary.label}")
    print(f"  Model:            {summary.model}")
    print(f"  Total runs:       {summary.total_runs}")
    print(f"  Successful:       {summary.successful_runs}")
    print(f"  Failed:           {summary.failed_runs}")
    print(f"  Usage reported:   {summary.usage_reported_count}/{summary.successful_runs}"
          f" ({summary.usage_reported_count/max(summary.successful_runs,1)*100:.0f}%)")
    print()

    if summary.usage_reported_count > 0:
        print("  TOKEN USAGE")
        print(f"  {'─' * 46}")
        print(f"  Avg input tokens/req:   {fmt(summary.avg_input_tokens)}")
        print(f"  Avg output tokens/req:  {fmt(summary.avg_output_tokens)}")
        print(f"  Avg total tokens/req:   {fmt(summary.avg_total_tokens)}")
        print(f"  Sum input tokens:       {fmt(summary.sum_input_tokens, 0)}")
        print(f"  Sum output tokens:      {fmt(summary.sum_output_tokens, 0)}")
        print(f"  Sum total tokens:       {fmt(summary.sum_total_tokens, 0)}")

        if summary.avg_thinking_overhead > 0:
            print(f"  Avg thinking overhead:  {fmt(summary.avg_thinking_overhead)} tokens"
                  f"  (total - input - output)")

        if summary.avg_cached_tokens > 0:
            print(f"  Avg cached tokens:      {fmt(summary.avg_cached_tokens)}")
        print()

    if summary.successful_runs > 0:
        print("  LATENCY")
        print(f"  {'─' * 46}")
        print(f"  Avg:    {fmt(summary.avg_latency_ms, 0)} ms")
        print(f"  Median: {fmt(summary.median_latency_ms, 0)} ms")
        print(f"  P95:    {fmt(summary.p95_latency_ms, 0)} ms")
        print(f"  P99:    {fmt(summary.p99_latency_ms, 0)} ms")
        print(f"  Min:    {fmt(summary.min_latency_ms, 0)} ms")
        print(f"  Max:    {fmt(summary.max_latency_ms, 0)} ms")
        print()

    if summary.per_category:
        print("  PER CATEGORY")
        print(f"  {'─' * 46}")
        for cat, stats in sorted(summary.per_category.items()):
            print(f"  [{cat}]  runs={stats['count']}  "
                  f"in={fmt(stats['avg_input_tokens'])}  "
                  f"out={fmt(stats['avg_output_tokens'])}  "
                  f"total={fmt(stats['avg_total_tokens'])}  "
                  f"latency={fmt(stats['avg_latency_ms'], 0)}ms")
        print()

    print(sep)


# ---------------------------------------------------------------------------
# Prompt loading
# ---------------------------------------------------------------------------

def load_prompts(path: Optional[str]) -> list[PromptDef]:
    """Load prompts from a JSON file or return defaults."""
    if not path:
        print(f"  Using {len(DEFAULT_PROMPTS)} built-in prompts")
        return DEFAULT_PROMPTS

    p = Path(path)
    if not p.exists():
        print(f"  WARNING: Prompts file not found: {path} — using built-in defaults")
        return DEFAULT_PROMPTS

    with open(p, encoding="utf-8") as f:
        data = json.load(f)

    prompt_list = data.get("prompts", data) if isinstance(data, dict) else data
    prompts = []
    for item in prompt_list:
        prompts.append(PromptDef(
            id=item.get("id", f"prompt-{len(prompts)+1}"),
            input=item["input"],
            category=item.get("category", "general"),
        ))

    print(f"  Loaded {len(prompts)} prompts from {path}")
    return prompts


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

def health_check(base_url: str) -> bool:
    """Quick health check against the Llama Stack server."""
    url = f"{base_url.rstrip('/')}/v1/health"
    ctx = _build_ssl_context()
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return "ok" in body.lower() or "healthy" in body.lower() or resp.status == 200
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark token usage and latency against a Llama Stack Responses API.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --url https://llamastack.example.com \\
           --model "gemini/models/gemini-2.5-flash" \\
           --label gemini --runs 5

  %(prog)s --url https://llamastack.example.com \\
           --model "vllm-inference/llama-32-3b-instruct" \\
           --label rhoai --runs 5 --output results-rhoai.csv
        """,
    )
    parser.add_argument(
        "--url",
        default=os.environ.get("LLAMA_STACK_URL"),
        help="Llama Stack base URL (env: LLAMA_STACK_URL) [required]",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("MODEL"),
        help="Model identifier (env: MODEL) [required]",
    )
    parser.add_argument(
        "--label",
        default=None,
        help="Label for this benchmark run (default: derived from model name)",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("LLAMA_STACK_TOKEN"),
        help="Bearer token for auth (env: LLAMA_STACK_TOKEN)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=5,
        help="Number of repetitions per prompt (default: 5)",
    )
    parser.add_argument(
        "--prompts",
        default=None,
        help="Path to a JSON file with test prompts (uses built-in defaults if omitted)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output CSV path (default: results-{label}.csv)",
    )
    parser.add_argument(
        "--output-json",
        default=None,
        help="Also write full results + summary to JSON",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=1,
        help="Number of warmup requests before benchmarking (default: 1)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Request timeout in seconds (default: 120)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.url:
        print("ERROR: --url is required (or set LLAMA_STACK_URL env var)")
        sys.exit(1)
    if not args.model:
        print("ERROR: --model is required (or set MODEL env var)")
        sys.exit(1)

    base_url = args.url.rstrip("/")
    endpoint = f"{base_url}/v1/openai/v1/responses"
    model = args.model
    label = args.label or model.split("/")[-1]
    output_csv = args.output or f"results-{label}.csv"

    print()
    print("=" * 66)
    print("  LLM BENCHMARK — Token Usage & Latency")
    print("=" * 66)
    print(f"  URL:      {base_url}")
    print(f"  Endpoint: POST {endpoint}")
    print(f"  Model:    {model}")
    print(f"  Label:    {label}")
    print(f"  Runs:     {args.runs} per prompt")
    print(f"  Warmup:   {args.warmup}")
    print(f"  Timeout:  {args.timeout}s")
    print(f"  Output:   {output_csv}")
    print()

    # Health check
    print("  [1/4] Health check...", end=" ", flush=True)
    if health_check(base_url):
        print("OK")
    else:
        print("WARN — server may be unreachable, continuing anyway")
    print()

    # Load prompts
    print("  [2/4] Loading prompts...", end=" ", flush=True)
    prompts = load_prompts(args.prompts)
    print()

    # Warmup
    if args.warmup > 0:
        print(f"  [3/4] Warmup ({args.warmup} request(s))...", flush=True)
        for i in range(args.warmup):
            warmup_prompt = PromptDef("warmup", "Say hello.", "warmup")
            result = run_single(
                endpoint, model, warmup_prompt, label, i + 1, args.token, args.timeout
            )
            status = "OK" if not result.error else f"ERROR: {result.error[:80]}"
            print(f"    warmup {i+1}: {result.latency_ms}ms — {status}")
        print()

    # Benchmark
    total = len(prompts) * args.runs
    print(f"  [4/4] Running benchmark ({len(prompts)} prompts x {args.runs} runs = {total} requests)")
    print()

    results: list[RunResult] = []
    completed = 0

    for prompt in prompts:
        for run_num in range(1, args.runs + 1):
            completed += 1
            progress = f"[{completed}/{total}]"

            result = run_single(
                endpoint, model, prompt, label, run_num, args.token, args.timeout
            )
            results.append(result)

            if result.error:
                print(f"    {progress} {prompt.id} run {run_num}: "
                      f"ERROR — {result.error[:80]}")
            else:
                usage_flag = "+" if result.usage_reported else "!"
                thinking = ""
                if result.thinking_overhead > 0:
                    thinking = f" think={result.thinking_overhead}"
                print(f"    {progress} {prompt.id} run {run_num}: "
                      f"{result.latency_ms}ms  "
                      f"in={result.input_tokens} out={result.output_tokens} "
                      f"total={result.total_tokens}{thinking}  "
                      f"[{usage_flag}usage]")

    # Summary
    summary = compute_summary(results, label, model)
    print_summary(summary)

    # Write CSV
    write_csv(results, output_csv)
    print(f"  Results written to: {output_csv}")

    # Write JSON if requested
    if args.output_json:
        write_json(results, summary, args.output_json)
        print(f"  JSON written to:   {args.output_json}")

    print()


if __name__ == "__main__":
    main()
