# NECTEC full-run offline assessment

Run: `2026-11-03T114345.873149_0000_35a3d7539e39`.

Status: integrity and offline scoring PASS. Human semantic review remains pending.
No inference, generated-code execution, protocol modification, or GPU workload was run.
Original artifacts and the frozen condition were not edited.

## Automatically scored results

Each model has 58 objective items: 50 GSM8K, four reasoning and four instruction tasks.
The other 12 items have no automatic semantic correctness verdict. Do not report the
objective subset as accuracy over all 70 questions or assign coding correctness from AST.

| Model | Objective subset | GSM8K | Format across all 70 |
|---|---|---|---|
| qwen3:1.7b | 35/58 (60.3%) | 34/50 (68.0%) | 63/70 |
| qwen3:8b | 48/58 (82.8%) | 45/50 (90.0%) | 66/70 |
| gemma4:12b | 53/58 (91.4%) | 47/50 (94.0%) | 68/70 |

All 210 requests completed normally with one attempt each. There are zero missing responses,
scored truncations, malformed HTTP envelopes, or recorded transport/server errors. All
150 GSM8K answers have boolean scoring results, including 24 incorrect outcomes (one with
invalid final-answer representation). No failed answer was removed from a denominator.

There are 38 observed objective/format failures, including 13 format-contract failures;
five are parser/unsupported-representation failures. These counts overlap and must not be
added. Exact-answer rules couple correctness and format; not every format failure is a
syntax error. Manual semantic failures cannot yet be counted. `quality_failures.csv`
retains the affected IDs, outcomes, source hashes and diagnostics without repairing text.

## Files and metrics

- scores.json / scores.csv: unchanged existing scorer's per-request results.
- manual_review.csv: existing blinded sheet, 60 internal responses, ratings left blank.
- private_blind_mapping.json: PRIVATE mapping; keep away from raters (mode 0600).
- analysis_manifest.json: scorer input, reference, rubric and source hashes.
- summary.json / model_summary.csv / category_summary.csv: counts and aggregate summaries.
- request_metrics.json / request_metrics.csv: raw-derived timing/token metrics, ready for charts.
- integrity_checks.json: 6,231 passing pre/post scoring identity/integrity checks.
- validation_results.json: regression and dataset-integrity test results.

Latency covers scored requests only, excluding warm-ups and natural-expiry waits.
Aggregate decode throughput is sum(eval_count) / sum(eval_duration in seconds), not an
unweighted average of request rates. Per-request median rates are also retained in JSON.
P95 uses linear interpolation at rank (n-1)*0.95. All 70 requests/model are included;
no outlier is silently excluded. Token counts are model-tokenizer-specific, and output
lengths differ, so throughput does not represent equal work across model architectures.

Ollama-reported VRAM allocations are approximately 3028, 7156, and 8625 MiB. All 307
residency snapshots have at most one model, matching digest, context 8192, and equal
size/size_vram. Empty states precede warm-ups and follow both transitions and the final
model. These are sampled Ollama allocations, NOT independently measured GPU peak memory.
No nvidia-smi GPU-wide peaks or external-workload process telemetry exists in this run.
The shared-client isolation condition cannot be retrospectively proven by /api/ps alone.

## Human review and charts

There are 36 responses requiring human correctness judgment: 12 coding, 12 knowledge,
and 12 summarization. All 12 code responses pass structural checks; functional correctness
and code safety remain unestablished. The existing 60-row sheet also includes 24 objective
internal answers for optional qualitative/rubric review. Never fill missing ratings with
zeros or code AST passes with correctness scores.

1. Give independently copied blinded sheets and the existing rubric to two reviewers
   where feasible; withhold private_blind_mapping.json and avoid inspecting model identities.
2. Record reviewer IDs, rationale and pre-consensus ratings; retain adjudication separately.
   Coding review is manual algorithm assessment, not executed runtime correctness.
3. Once ratings are complete, join through the private mapping while retaining response
   hashes. Summarize dimensions/categories before any aggregate rubric score.
4. Plot GSM8K accuracy (denominator 50; Wilson intervals), paired per-question model
   differences, category format counts, latency distributions and output-token counts.
   Plot Ollama VRAM allocation with that label; do not label it GPU peak memory.
5. Use paired question IDs for comparisons. Do not treat 150 across-model GSM8K answers as
   150 independent problems for a single-model interval. Keep inference warm-ups separate.

## Methodological limitations

Single repetition; small curated English internal categories (four items/category/model);
fixed public GSM8K subset and possible training contamination; native quantized artifacts
and different tokenizers/templates; no functional coding execution; manual semantic review
pending; fixed model-block order; non-streaming wall time is not time to first token.
C03 and I01 were previously exposed in the smoke test. Disclose that exposure and confirm
no tuning/best-attempt selection occurred. Maximum 8192/4096 capacity remains uncertified;
this run provides observed fixed-workload outcomes only. Archive reviewed settings and
report all failures, rather than extracting/repairing answers or rerunning them.
