# Agentic Chat — LLM Token Usage & Latency Benchmarking Report

**Date**: March 4, 2026
**Workload**: Agentic Chat plugin (Backstage community plugin)
**Llama Stack Server**: `https://your-llamastack-server.example.com`
**Methodology**: 10 representative prompts x 3 runs each = 30 requests per model, non-streaming, via Llama Stack Responses API (`POST /v1/openai/v1/responses`)
**Estimated daily volume**: ~600 conversations/day (~50-200 users)

---

## What Was Tested vs What the Email Asks

The email asks for benchmarking data across these deployment options:

| Deployment Option (from email) | Tested? | What we used instead |
|---|---|---|
| **Stellar: Shared Throughput** | NO | No Stellar-hosted model available on our Llama Stack instance |
| **Stellar: Provisioned Throughput** | NO | Same -- no Stellar backend |
| **Stellar: Dedicated Hardware** | NO | Same -- no Stellar backend |
| **Stellar: Batch Processing** | NO | Same -- no Stellar backend |
| **Dedicated HW + Self-Hosted Model** | YES | RHOAI/vLLM with Llama 3.2 3B on OpenShift |

**Additionally tested (not in the email but available on our Llama Stack):**
- **Google Gemini 2.5 Flash** (cloud API) -- provides a cloud model baseline for comparison

**To fill in the Stellar rows**, we need either:
- A Stellar-hosted model registered on the Llama Stack instance, OR
- Direct access to a Stellar API endpoint

The `benchmark.py` script is ready to run against Stellar once access is available.

---

## Models Tested

| Label | Model Identifier | Backend | Model Size |
|---|---|---|---|
| **RHOAI** | `vllm-inference/llama-32-3b-instruct` | vLLM on Red Hat OpenShift AI | 3B params |
| **Gemini** | `gemini/models/gemini-2.5-flash` | Google Gemini API (via Llama Stack) | Large (proprietary, reasoning model) |

Both hit the same Llama Stack URL. The `--model` parameter routes to different backends. Neither backend is Stellar.

---

## Benchmarking Table

| Deployment Option | Token Count (per request avg) | Daily Estimate (600 conv/day, 3x agentic) | Max Response Time | Avg Response Time | SLA | Pricing |
|---|---|---|---|---|---|---|
| **Stellar: Shared Throughput** | NOT TESTED | -- | -- | -- | None | $$ / 1M tokens |
| **Stellar: Provisioned Throughput** | NOT TESTED | -- | -- | -- | Moderate | $$$ / Month |
| **Stellar: Dedicated Hardware** | NOT TESTED | -- | -- | -- | Strong | $$$$$ / Year |
| **Stellar: Batch Processing** | NOT TESTED | -- | -- | -- | None | $ / 1M tokens |
| **Dedicated HW + Self-Hosted (RHOAI)** | **538 total** (117 in / 422 out) | ~1.0M tokens/day | **32.7 sec** | **11.9 sec** | N/A | Hardware cost only |
| *Google Gemini 2.5 Flash (reference)* | *73,675 total (1,674 in / 25,751 out / 46,250 thinking)* | *~132.6M tokens/day* | *28.5 sec* | *12.5 sec* | *N/A* | *Google Vertex pricing* |

**SLA values** are from the Stellar tier definitions. Token counts, response times, and daily estimates are only available for the two models we tested.

**Daily estimate calculation:**
- RHOAI: 538 tokens/req x 3 calls/conv x 600 conv/day = **968,400 tokens/day** (~1M)
- Gemini: 73,675 tokens/req x 3 calls/conv x 600 conv/day = **132,615,000 tokens/day** (~133M)

---

## Detailed Measured Metrics

### RHOAI / vLLM (Self-Hosted) -- `vllm-inference/llama-32-3b-instruct`

Maps to: **Dedicated HW + Self-Hosted Model** in the email.

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

### Google Gemini 2.5 Flash (Cloud API) -- `gemini/models/gemini-2.5-flash`

Maps to: **Google Vertex** in the cost calculator (NOT Stellar).

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

### 1. Stellar tiers are not testable with current setup

Our Llama Stack instance does not have any Stellar-hosted models registered. It has:
- **vLLM/RHOAI models** (self-hosted on OpenShift): `vllm-inference/llama-32-3b-instruct`, `vllm-orchestrator/orchestrator-8b`
- **Google Gemini models** (cloud API): `gemini/models/gemini-2.5-flash`, `gemini/models/gemini-2.0-flash`, and others

To benchmark the Stellar tiers, we need a Stellar-hosted model endpoint or a Stellar model registered on the Llama Stack instance. Once available, run:
```bash
python3 benchmark.py --url <LLAMA_STACK_URL> --model "<stellar-model-id>" --label stellar --runs 5
```

### 2. Thinking token overhead (Gemini 2.5 Flash)

Gemini 2.5 Flash is a reasoning model. Its `total_tokens` includes internal chain-of-thought tokens NOT reflected in `input_tokens` or `output_tokens`. On average, **64% of total tokens are thinking tokens**.

| Prompt Category | Visible (in + out) | Total | Thinking % |
|---|---|---|---|
| Simple Q&A | 461 | 3,460 | 87% |
| Code generation | 66,685 | 169,753 | 61% |
| Reasoning | 44,513 | 121,589 | 63% |
| Long-context | 3,367 | 6,965 | 52% |
| Creative writing | 1,889 | 14,394 | 87% |
| Structured extraction | 1,159 | 4,194 | 72% |

This is relevant if the production model (on Stellar or elsewhere) is also a reasoning model. Non-reasoning models (like Gemini 2.0 Flash or Llama 3.2 3B) do not have this overhead.

### 3. Self-hosted model is a 3B model (small)

The RHOAI benchmark used Llama 3.2 **3B** Instruct -- a small model. The cost calculator spreadsheet references Llama **13b** and **70b**, and Mixtral **7b** and **8x7b**, all significantly larger. A production self-hosted deployment would likely use a larger model, which would:
- Produce more tokens per response (longer, more detailed answers)
- Have higher latency
- Require more GPU resources (more V100/A100 cards)

The 538 tokens/request average for the 3B model is likely an **underestimate** of what a production-grade model would produce.

### 4. Agentic overhead not captured

These benchmarks measure single inference calls. In production, each user conversation involves:
- 1 initial inference call
- 1-4 additional calls for MCP tool execution
- Possible additional calls for HITL approval flows

The 3x multiplier used in daily estimates is conservative. Complex multi-tool conversations could be 5x+.

### 5. Latency comparison

| Metric | RHOAI (3B, self-hosted) | Gemini 2.5 Flash (cloud) |
|---|---|---|
| Avg | 11.9 sec | 12.5 sec |
| Median | 10.5 sec | 9.1 sec |
| P95 | 23.6 sec | 25.4 sec |
| Max | 32.7 sec | 28.5 sec |

Similar overall, but RHOAI has higher variance. A larger self-hosted model (70B) would be significantly slower.

### 6. Batch Processing suitability

Batch Processing ($/1M tokens) is only suitable for offline workloads. The Agentic Chat plugin is real-time interactive, so Batch Processing would NOT be appropriate for the primary use case.

---

## What is still needed to complete the email response

| Item | Status | Who provides it |
|---|---|---|
| Stellar tier token counts & latency | **NOT TESTED** | Need Stellar model access, then re-run benchmark.py |
| Self-hosted (RHOAI) token counts & latency | **MEASURED** (3B model) | Done -- but re-run with production model (70B) for accurate numbers |
| Google Gemini token counts & latency | **MEASURED** (reference only) | Done -- maps to Google Vertex, not Stellar |
| SLA commitment per tier | **KNOWN** | From Stellar tier definitions |
| Actual dollar pricing per tier | **NOT AVAILABLE** | Stellar team provides this |
| GPU costs for on-prem | **NOT AVAILABLE** | From Stellar/infrastructure team |
| Daily user/conversation volume | **ESTIMATED** (~600 conv/day) | Refine based on actual usage data |

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

- `results-rhoai.csv` / `results-rhoai.json` -- RHOAI benchmark data (Llama 3.2 3B)
- `results-gemini.csv` / `results-gemini.json` -- Gemini benchmark data (Gemini 2.5 Flash)
- `benchmark.py` -- reusable script (works with any Llama Stack model)
- `prompts.json` -- test prompts used
