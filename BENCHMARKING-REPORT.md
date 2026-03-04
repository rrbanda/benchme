# Agentic Chat — LLM Token Usage & Latency Benchmarking Report

**Date**: March 4, 2026
**Workload**: Agentic Chat plugin (Backstage community plugin)
**Llama Stack Server**: `https://your-llamastack-server.example.com`
**Methodology**: 10 representative prompts x 3 runs each = 30 requests per model, non-streaming, via Llama Stack Responses API (`POST /v1/openai/v1/responses`)
**Estimated daily volume**: ~600 conversations/day (~50-200 users)

---

## Important Caveats (read before using this data)

1. **Models tested are not the production models.** We tested what was available on the Llama Stack instance: Llama 3.2 3B (RHOAI/vLLM) and Gemini 2.5 Flash (Google). The cost calculator spreadsheet references GPT-4o, Gemini 1.5 Flash/Pro, Llama 13b/70b, Mixtral 7b/8x7b. To get numbers directly comparable to the spreadsheet, re-run with the actual production model.

2. **Single-inference-call measurements only.** Agentic-chat involves multiple inference calls per user conversation (tool calls, HITL approvals). A typical conversation uses ~3x the tokens of a single call. The daily projections below apply this 3x multiplier as an estimate.

3. **Token counts are what the API reported -- not estimated.** All token numbers come directly from the Llama Stack `usage` field. We did not compute tokens client-side.

---

## Models Tested

| Label | Model Identifier | Backend | Model Size |
|---|---|---|---|
| **RHOAI** | `vllm-inference/llama-32-3b-instruct` | vLLM on Red Hat OpenShift AI | 3B params |
| **Gemini** | `gemini/models/gemini-2.5-flash` | Google Gemini API (via Llama Stack) | Large (proprietary) |

Both hit the same Llama Stack URL. The `--model` parameter routes to different backends.

---

## Benchmarking Table (per the email format)

| Deployment Option | Token Count (per request avg) | Token Count (daily estimate at 600 conv/day, 3x agentic multiplier) | Max Response Time | Avg Response Time | SLA Commitment | Pricing Model |
|---|---|---|---|---|---|---|
| **Stellar: Shared Throughput** | 73,675 total | ~132.6M tokens/day | 28.5 sec | 12.5 sec | None | $$ / 1M tokens |
| **Stellar: Provisioned Throughput** | 73,675 total | ~132.6M tokens/day | 28.5 sec | 12.5 sec | Moderate | $$$ / Month |
| **Stellar: Dedicated Hardware** | 73,675 total | ~132.6M tokens/day | 28.5 sec | 12.5 sec | Strong | $$$$$ / Year |
| **Stellar: Batch Processing** | 73,675 total | ~132.6M tokens/day | N/A (offline) | N/A (offline) | None | $ / 1M tokens |
| **Dedicated HW + Self-Hosted (RHOAI)** | 538 total | ~1.0M tokens/day | 32.7 sec | 11.9 sec | N/A (self-managed) | Hardware cost only |

**How daily estimate was calculated:**
- Gemini: 73,675 tokens/request x 3 calls/conversation x 600 conversations/day = **132,615,000 tokens/day** (~133M)
- RHOAI: 538 tokens/request x 3 calls/conversation x 600 conversations/day = **968,400 tokens/day** (~1M)

**Comparison to cost calculator assumptions:** The spreadsheet assumes 50M input + 25M output = 75M total tokens/day. Our Gemini estimate of ~133M/day is **higher** because Gemini 2.5 Flash includes ~46,250 thinking tokens per request (64% of total) that are not visible as input or output. If thinking tokens are excluded from billing, the billable volume drops to ~49M/day -- close to the spreadsheet's assumption.

---

## Cost Calculator Inputs (to plug into the spreadsheet)

Based on ~600 conversations/day with a 3x agentic multiplier:

### If thinking tokens ARE billed (total_tokens):

| Input | Gemini (Stellar tiers) | RHOAI (Self-Hosted) |
|---|---|---|
| **Input tokens / day** | ~3,013,200 (~3M) | ~210,600 (~0.2M) |
| **Output tokens / day** | ~46,351,800 (~46M) | ~759,600 (~0.8M) |
| **Thinking tokens / day** | ~83,250,000 (~83M) | 0 |
| **Total tokens / day** | ~132,615,000 (~133M) | ~970,200 (~1M) |
| **% increase YoY** | 10% (per spreadsheet) | 10% |

### If thinking tokens are NOT billed (input + output only):

| Input | Gemini (Stellar tiers) | RHOAI (Self-Hosted) |
|---|---|---|
| **Input tokens / day** | ~3,013,200 (~3M) | ~210,600 (~0.2M) |
| **Output tokens / day** | ~46,351,800 (~46M) | ~759,600 (~0.8M) |
| **Total billable / day** | ~49,365,000 (~49M) | ~970,200 (~1M) |

The ~49M total (without thinking) is close to the cost calculator's 75M baseline (50M input + 25M output). The difference is because our prompts are representative of the agentic-chat workload -- your actual mix may differ.

---

## Detailed Measured Metrics

### RHOAI / vLLM (Self-Hosted) -- `vllm-inference/llama-32-3b-instruct`

```
Runs:              30 / 30 successful (100%)
Usage reported:    30 / 30 (100%)

TOKEN USAGE (per request)
  Avg input:       117 tokens
  Avg output:      422 tokens
  Avg total:       538 tokens
  Thinking:        0 (total = input + output exactly)
  Sum (all runs):  16,151 tokens

LATENCY
  Avg:     11,885 ms  (11.9 sec)
  Median:  10,518 ms  (10.5 sec)
  P95:     23,622 ms  (23.6 sec)
  Min:      2,030 ms  ( 2.0 sec)
  Max:     32,734 ms  (32.7 sec)

BY PROMPT CATEGORY
  simple:       avg 187 tokens,  avg  3,971 ms
  code:         avg 738 tokens,  avg 18,111 ms
  reasoning:    avg 736 tokens,  avg 18,095 ms
  long-context: avg 584 tokens,  avg  5,848 ms
  creative:     avg 394 tokens,  avg  9,393 ms
  structured:   avg 347 tokens,  avg  5,163 ms
```

### Gemini (Cloud API) -- `gemini/models/gemini-2.5-flash`

```
Runs:              30 / 30 successful (100%)
Usage reported:    30 / 30 (100%)

TOKEN USAGE (per request)
  Avg input:        1,674 tokens
  Avg output:      25,751 tokens
  Avg total:       73,675 tokens
  Avg thinking:    46,250 tokens (64% of total)
  Sum (all runs):  2,210,243 tokens

LATENCY
  Avg:     12,488 ms  (12.5 sec)
  Median:   9,114 ms  ( 9.1 sec)
  P95:     25,421 ms  (25.4 sec)
  Min:      1,355 ms  ( 1.4 sec)
  Max:     28,485 ms  (28.5 sec)

BY PROMPT CATEGORY
  simple:        avg   3,460 tokens,  avg  4,348 ms
  code:          avg 169,753 tokens,  avg 20,602 ms
  reasoning:     avg 121,589 tokens,  avg 18,979 ms
  long-context:  avg   6,965 tokens,  avg  4,353 ms
  creative:      avg  14,394 tokens,  avg  9,937 ms
  structured:    avg   4,194 tokens,  avg  3,749 ms
```

---

## Notable Findings / Key Considerations

### 1. Thinking Token Overhead

Gemini 2.5 Flash is a reasoning model. Its `total_tokens` includes internal chain-of-thought tokens NOT reflected in `input_tokens` or `output_tokens`. On average, **64% of total tokens are thinking tokens**.

| Prompt Category | Visible (in + out) | Total | Thinking % |
|---|---|---|---|
| Simple Q&A | 461 | 3,460 | 87% |
| Code generation | 66,685 | 169,753 | 61% |
| Reasoning | 44,513 | 121,589 | 63% |
| Long-context | 3,367 | 6,965 | 52% |
| Creative writing | 1,889 | 14,394 | 87% |
| Structured extraction | 1,159 | 4,194 | 72% |

**This is the single biggest factor for cost.** If the Shared Throughput tier ($$/1M tokens) bills on `total_tokens`, the effective cost is ~3x higher than what input + output alone would suggest.

### 2. Models tested are not the models in the cost calculator

The cost calculator spreadsheet references: GPT-4o, GPT-4, GPT-3.5, Gemini 1.5 Flash/Pro, Llama 13b/70b, Mixtral 7b/8x7b.

We tested: Llama 3.2 3B (much smaller than Llama 70b) and Gemini 2.5 Flash (a different, newer model than Gemini 1.5 Flash). The token counts and latency will differ with the production model. To get spreadsheet-ready numbers:
- Re-run `benchmark.py` with the actual model you plan to deploy
- The script works with any model registered on Llama Stack

### 3. Agentic overhead not captured in these numbers

These benchmarks measure single inference calls. In production, each user conversation involves:
- 1 initial inference call
- 1-4 additional calls for MCP tool execution (tool call -> tool result -> model processes)
- Possible additional calls for HITL approval flows

The 3x multiplier used in daily estimates is conservative. Complex multi-tool conversations could be 5x+.

### 4. Latency comparison

Both backends showed similar average latency (~12 sec), but different profiles:
- **RHOAI**: Higher variance (2-33 sec range), slower on complex prompts but faster on simple ones
- **Gemini**: More consistent (1-28 sec range), faster median (9.1 sec vs 10.5 sec)

For real-time SLA-dependent workloads, the P95 latency matters: ~24 sec (RHOAI) vs ~25 sec (Gemini).

### 5. Batch Processing suitability

Batch Processing ($/1M tokens, lowest cost) is only suitable for offline workloads. The Agentic Chat plugin is real-time interactive, so Batch Processing would NOT be appropriate for the primary use case. It could be used for background tasks like knowledge base indexing or conversation summarization.

---

## What you need to provide to complete the email response

| Item | Status | Notes |
|---|---|---|
| Token count per request | MEASURED | From benchmark runs above |
| Max / Avg response time | MEASURED | From benchmark runs above |
| SLA commitment per tier | KNOWN | From Stellar tier definitions (Image 1) |
| Daily token volume | ESTIMATED | ~133M/day (with thinking) or ~49M/day (without). Depends on actual user volume and whether thinking tokens count. |
| Actual $$ pricing per tier | NOT AVAILABLE | We have the pricing model ($$/1M, $$$/month, etc.) but not the actual dollar amounts. These come from the Stellar team. |
| GPU costs for on-prem | NOT AVAILABLE | The spreadsheet has V100/A100 costs. These are from the Stellar/infrastructure team, not from benchmarking. |
| Production model token counts | NOT MEASURED | Re-run benchmark.py with the actual production model for accurate numbers. |

---

## Methodology

- **10 prompts** across 6 categories: simple Q&A, code generation/review, math reasoning, architecture design, long-context summarization, creative writing, multi-step analysis, structured data extraction
- **3 runs** per prompt, 1 warmup request, non-streaming mode
- **Standalone script** (`benchmark.py`) hitting the API directly, not through the plugin
- **Wall-clock timing** from request to complete response
- **No MCP tools** -- these are single-inference benchmarks

---

## How to re-run with a different model

```bash
cd ~/tokens/llm-benchmark

python3 benchmark.py \
  --url https://your-llamastack-server.example.com \
  --model "YOUR_MODEL_IDENTIFIER" \
  --label your-label \
  --runs 5 \
  --prompts prompts.json \
  --output results-your-label.csv \
  --output-json results-your-label.json
```

## Raw Data Files

- `results-rhoai.csv` / `results-rhoai.json` -- RHOAI benchmark data
- `results-gemini.csv` / `results-gemini.json` -- Gemini benchmark data
- `benchmark.py` -- reusable script
- `prompts.json` -- test prompts used
