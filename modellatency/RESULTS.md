# Gemini 3.5 Flash Latency: europe-west2 (single-region) vs eu (multi-region)

**Context:** Customer-reported latency difference between endpoints
**Date:** 2026-10-29 (UTC)
**Reported issue:** With a ~13k-token classification prompt (`test_prompt.json`, not published), the single-region endpoint (`gemini-3.5-flash`, `europe-west2`) is noticeably faster than the EU multi-region endpoint (`gemini-3.5-flash`, `eu`).

## TL;DR

- **Reproduced.** With uncached prompts, which matches the production workload (a different input on every call), **europe-west2 is ~0.33s (~20%) faster on mean and ~0.45s faster on median** than eu.
- Single-region won **9/10** parallel rounds. The difference is statistically significant (paired t-test, **p ≈ 0.027**).
- **The outputs were equivalent on every round (10/10 passed the check).** Prompt size, output size, classification and finish reason all matched, so both endpoints did the same work.
- Time to first token (TTFT) ≈ total latency. The extra time on eu is spent **before the first token** (processing the ~13k-token prompt, queuing or routing), not on generating output.
- eu is **slower but steadier** (stdev 0.14s vs 0.37s).

## Setup

| Item | Value |
|---|---|
| Model | `gemini-3.5-flash` |
| Project | `duetai-399118` |
| Single-region endpoint | `https://europe-west2-aiplatform.googleapis.com/v1/projects/duetai-399118/locations/europe-west2/publishers/google/models/gemini-3.5-flash` |
| Multi-region endpoint | `https://aiplatform.eu.rep.googleapis.com/v1/projects/duetai-399118/locations/eu/publishers/google/models/gemini-3.5-flash` |
| Request body | `test_prompt.json`, unchanged (temperature 0, topK 1, seed 42, thinking `MINIMAL`, maxOutputTokens 256, JSON response schema) |
| Prompt size | 12,989 tokens (13,036 with the cache-busting prefix) |
| Concurrency | Both endpoints called **in parallel**, released at the same instant (thread barrier), one request per endpoint per round |
| Warm-up | 1 unmeasured round so connection setup (TLS) isn't timed |
| Measurement | Client-side wall clock (`time.perf_counter`) using reused HTTP connections; TTFT from SSE streaming |
| Client location | Google Cloudtop (not the customer's network) |
| Script | [`latency_benchmark.py`](./latency_benchmark.py) |

### Output equivalence check

Each round passes only if all of these hold for the two responses:

- Both returned HTTP 200
- Same prompt token count
- Same cache-hit status (both cached or both uncached)
- Same `finishReason` and `modelVersion`
- Output tokens and thinking tokens within `max(15 tokens, 25%)` of each other
- Both outputs are valid JSON matching the `responseSchema` (required keys, allowed enum values)
- Same `selection` classification

## Run 2 (main result): unique prompt per round, streaming, 10 rounds

```bash
../.venv/bin/python latency_benchmark.py --rounds 10 --bust-cache --stream
```

`--bust-cache` adds a unique ID to the start of the prompt each round. Both endpoints get the same ID in a given round, so the prompt is still identical between them, but neither can hit Vertex AI's automatic prompt cache.

### Per-round latency (seconds)

| Round | europe-west2 total (TTFT) | eu total (TTFT) | Δ (single − multi) | Check |
|---|---|---|---|---|
| 1 | 2.272 (2.265) | 1.669 (1.666) | +0.603 | PASS |
| 2 | 1.203 (1.195) | 1.664 (1.662) | −0.461 | PASS |
| 3 | 1.514 (1.499) | 1.723 (1.719) | −0.209 | PASS |
| 4 | 1.393 (1.387) | 1.740 (1.734) | −0.347 | PASS |
| 5 | 1.306 (1.305) | 1.808 (1.805) | −0.502 | PASS |
| 6 | 1.255 (1.254) | 1.688 (1.687) | −0.433 | PASS |
| 7 | 1.044 (1.043) | 1.550 (1.548) | −0.506 | PASS |
| 8 | 1.035 (1.031) | 1.847 (1.845) | −0.812 | PASS |
| 9 | 1.017 (1.016) | 1.647 (1.646) | −0.630 | PASS |
| 10 | 1.352 (1.350) | 1.356 (1.353) | −0.004 | PASS |

### Summary statistics (seconds)

| Endpoint | Metric | n | Mean | Median | Stdev | Min | p90 | Max |
|---|---|---|---|---|---|---|---|---|
| europe-west2 (single-region) | Total | 10 | **1.339** | **1.280** | 0.367 | 1.017 | 1.514 | 2.272 |
| europe-west2 (single-region) | TTFT | 10 | 1.335 | 1.279 | 0.365 | 1.016 | 1.499 | 2.265 |
| eu (multi-region) | Total | 10 | **1.669** | **1.678** | 0.138 | 1.356 | 1.808 | 1.847 |
| eu (multi-region) | TTFT | 10 | 1.666 | 1.676 | 0.138 | 1.353 | 1.805 | 1.845 |

**Paired difference (single − multi):** mean **−0.330s**, median **−0.447s**, t = −2.64, **p ≈ 0.027**. europe-west2 is **19.8% faster** on mean and won **9/10** rounds.

### Output equivalence

| Endpoint | Mean output tokens | Mean output chars | Prompt tokens | Cache hits |
|---|---|---|---|---|
| europe-west2 | 52.9 | 238.5 | 13,036 | 0/10 |
| eu | 54.2 | 246.6 | 13,036 | 0/10 |

10/10 rounds passed the check.

## Run 1 (for reference): prompt as-is, unary, 5 rounds

```bash
../.venv/bin/python latency_benchmark.py --rounds 5
```

| Round | europe-west2 | eu | Δ (single − multi) | Check |
|---|---|---|---|---|
| 1 | 1.936 | 1.311 | +0.625 | PASS |
| 2 | 1.547 | 1.631 | −0.084 | PASS |
| 3 | 1.456 | 1.766 | −0.311 | PASS |
| 4 | 1.548 | 1.645 | −0.097 | PASS |
| 5 | 3.698 | 1.536 | +2.162 | PASS |

| Endpoint | n | Mean | Median | Stdev | Min | Max | Cache hits |
|---|---|---|---|---|---|---|---|
| europe-west2 | 5 | 2.037 | 1.548 | 0.947 | 1.456 | 3.698 | 5/5 |
| eu | 5 | 1.578 | 1.631 | 0.170 | 1.311 | 1.766 | 5/5 |

Paired difference: mean +0.459s, median −0.084s, t = +1.01, p ≈ 0.369 (**not significant**).

**Why this run is less useful:** sending the same prompt repeatedly meant **every request on both endpoints hit the automatic prompt cache**, which removes most of the prompt-processing time where the gap appears. The mean was also skewed by one 3.7s europe-west2 outlier. The medians were nearly equal.

## Interpretation

1. **The customer's report holds for real traffic.** When the prompt isn't cached (different input each call), single-region europe-west2 consistently answers faster than the eu multi-region endpoint, by about 0.3–0.5s on a ~1.3–1.7s request.
2. **The extra time is before the first token.** TTFT is within a few ms of total latency in every round (output is only ~50 tokens), so the difference comes from routing, queuing or processing the ~13k-token prompt, not from output speed.
3. **Caching hides the gap.** Repeated identical prompts make the two endpoints look similar. Use `--bust-cache` for an apples-to-apples comparison of the production workload.
4. **Trade-off:** eu showed lower variance (stdev 0.14s vs 0.37s) and avoided europe-west2's occasional spikes (2.27s, 3.70s). In exchange, its typical latency was higher.

## Caveats and next steps

- **Client location:** these tests ran from a Google Cloudtop, not the customer's network. Network distance to each endpoint affects the numbers. Ask the customer to run the script from their own environment.
- **Sample size and timing:** 10 rounds in a single session. Repeat with `--rounds 20` or more at several times of day (peak and off-peak) to confirm.
- **Not separated:** client-side timing can't split network time from server queuing and processing. If further investigation is needed, escalate with the request IDs saved in the results JSON (`response_id`).

## Raw data

Kept locally and not committed (`results/` is gitignored because it contains model outputs):

- Run 1: `results/latency_20261029T094200Z.csv` / `.json`
- Run 2: `results/latency_20261029T094251Z.csv` / `.json`
