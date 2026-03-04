# benchme

Standalone LLM benchmarking tool for measuring token usage and response latency against a [Llama Stack](https://github.com/meta-llama/llama-stack) Responses API.

Zero external dependencies -- uses only Python 3.9+ stdlib.

## Quick Start

```bash
python benchmark.py \
  --url https://your-llamastack-server.example.com \
  --model "gemini/models/gemini-2.5-flash" \
  --label gemini \
  --runs 5

python benchmark.py \
  --url https://your-llamastack-server.example.com \
  --model "vllm-inference/llama-32-3b-instruct" \
  --label rhoai \
  --runs 5
```

## What It Measures

Per request:
- `input_tokens`, `output_tokens`, `total_tokens` (from API `usage` field)
- `cached_tokens`, `reasoning_tokens` (if available)
- `thinking_overhead` (total - input - output, relevant for reasoning models like Gemini 2.5)
- `latency_ms` (wall-clock time)
- `usage_reported` (boolean -- did the API actually return usage data?)

Aggregate:
- Mean / median / P95 / P99 / min / max latency
- Average and total token counts
- Per-category breakdowns (simple, code, reasoning, etc.)
- Usage reporting rate

## CLI Options

```
--url          Llama Stack base URL (env: LLAMA_STACK_URL) [required]
--model        Model identifier (env: MODEL) [required]
--label        Label for this run (default: derived from model name)
--token        Bearer token for auth (env: LLAMA_STACK_TOKEN)
--runs         Repetitions per prompt (default: 5)
--prompts      Path to prompts JSON file (uses built-in defaults if omitted)
--output       Output CSV path (default: results-{label}.csv)
--output-json  Also write full results + summary to JSON
--warmup       Warmup requests before benchmarking (default: 1)
--timeout      Request timeout in seconds (default: 120)
```

## Custom Prompts

Provide a JSON file with your own prompts:

```json
{
  "prompts": [
    {
      "id": "my-prompt",
      "category": "code",
      "input": "Write a function that sorts a list of dictionaries by a given key."
    }
  ]
}
```

```bash
python benchmark.py --url ... --model ... --prompts my-prompts.json
```

## Output

- **CSV file** -- one row per request with all metrics
- **JSON file** (optional) -- full results plus computed summary
- **Console** -- formatted summary with statistics

## Example Results

See the `results-*.csv` and `results-*.json` files for example benchmark output, and `BENCHMARKING-REPORT.md` for a full analysis report.

## License

Apache-2.0
