# NECTEC final research results package

Run: `2026-11-03T114345.873149_0000_35a3d7539e39`. Prepared entirely offline into this NEW directory.

Start with RESULTS_AND_DISCUSSION.md, TABLES.md, and figures/. All seven figures are
provided as 300-DPI PNG and editable SVG. FIGURE_CAPTIONS.md and figure_derivations.json
state each derivation. Tables retain full numeric precision in CSV/JSON; manuscript prose
uses rounded values. No original source, rating, scoring rule, response or frozen setting
was modified. No inference, GPU workload, benchmark rerun, or generated-code execution ran.

## Metric definitions and denominators

- Automatic accuracy: original answer_correct True /58 per model; 50 GSM8K +4 reasoning
  +4 instruction items. Wrong/malformed answers remain failures in the denominator.
- GSM8K: True /50, with 95% Wilson intervals. Center=(p+z²/(2n))/(1+z²/n), half-width=
  z*sqrt(p(1-p)/n+z²/(4n²))/(1+z²/n), z=1.959963984540054. These nominal binomial intervals assume an
  item-sampling interpretation and do not quantify training contamination or run variability.
- Paired comparisons: shared sorted 50 question IDs; comparison minus reference accuracy.
  Resample whole question IDs with replacement for all models together (20000 draws,
  NumPy default_rng seed 42); 2.5/97.5 percentiles, linear interpolation. Discordant
  wins/losses and question-level outcomes are exported. No hypothesis tests/significance
  stars, p-values, or broad superiority claims are supplied. Intervals are pointwise.
- Human correctness: explicit researcher verdicts correct/partly_correct/incorrect/uncertain,
  /12 per model and /4 per category. Partly correct is separate, not half credit. Only
  correctness ratings were entered: original 1–5 means are descriptive, not percentages.
  The other four rubric dimensions remain unrated. No /25 or undocumented /70 composite.
- Latency: original scored complete.json wall_time_s; 70/model; warm-ups and expiration
  waits excluded. Boxes show IQR/median/Tukey whiskers with all raw points; log axis labelled.
  Descriptive P95 tables use linear interpolation at rank (n-1)*0.95; no outliers removed.
- Generation throughput: sum(eval_count)/sum(eval_duration/1e9), per model. Tokens use each
  model's own tokenizer; output lengths differ. This is not wall-clock service throughput
  or time to first token. Prompt/generated token totals and maxima are exported.
- Memory: matching recorded size_vram bytes /1048576 = MiB, not GB and not independent
  GPU peak memory. Residency sampling cannot establish absence of every external workload.

## Figure/table mapping

- `01_automatic_accuracy.png/.svg`: Count answer_correct=True among the 58 objective items/model; no /70 composite.
- `02_gsm8k_accuracy_wilson.png/.svg`: Wilson score interval using z=1.959963984540054, n=50; all wrong/format-failed answers retained.
- `03_human_verdict_distribution.png/.svg`: Explicit imported verdict counts; partly-correct answers are retained separately, without half credit.
- `04_category_correctness.png/.svg`: Left: objective answer_correct proportions. Right: explicit human correct verdicts; not numeric-rating thresholds.
- `05_latency_distributions.png/.svg`: Original complete.json wall_time_s, cross-checked against request_metrics.csv; not time to first token.
- `06_throughput_and_allocation.png/.svg`: Throughput = sum(eval_count)/sum(eval_duration_s), 70 scored requests/model. Memory = consistent recorded size_vram / 2^20.
- `07_gsm8k_paired_differences.png/.svg`: Resample 50 matched question IDs with replacement, preserving all models for each ID; percentile endpoints 2.5/97.5%.

CSV tables: model_results, automatic_categories, human_categories, latency_seconds,
tokens_and_generation, ollama_memory_allocations, gsm8k_paired_comparisons,
gsm8k_question_outcomes, request_metrics, and notable_failures. TABLES.md is the readable
companion. statistics.json preserves all aggregates; model_metadata.json pins model digests,
options, runtime and plot-library versions. source_inventory.csv/json contains source-file
paths, roles, byte sizes and SHA-256 hashes. It inventories private review input identities
without redistributing the private blind mapping or editing those inputs.

## Review provenance and cautions

ONE researcher recorded human ratings with AI-assisted assessment suggestions, as disclosed
by the researcher. No independent inter-rater agreement was measured. Static coding review
is not executed functional correctness. The final human figures report those actual
recorded decisions without re-adjudicating them. Independent review would be additional
future evidence, not something claimed here. The small internal categories, single
repetition, fixed execution order, smoke-question exposure, format sensitivity, possible
public-data contamination and uncertified maximum capacity are discussed in the draft.

## Reproduce without modifying evidence

From the project root, with the existing plotting environment:

```sh
PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/tmp/nectec-final-matplotlib \
  venv/bin/python PATH_TO_THIS_PACKAGE/build_report.py --project /home/lailai/ollama-test
```

Default execution creates another NEW uniquely named directory under evaluation_final_report/.
An optional --output must name a new directory under that root; existing outputs are refused.
Only local CPU plotting/statistics are used. No Ollama endpoints or GPU tools are called.
Do not import the build script as an evaluation module. It runs only through main().

## Output validation

validation/verification.json records recomputed counts, hashes and source/table comparisons.
validation/preservation.json records before/after source hashes. validation/output_checks.json
records image readability/resolution and SVG/table integrity. FILES_SHA256.json inventories
all finished package files (excluding itself). A contact sheet under validation/ is a
preview only; individual figures are the publication artifacts. No review score was invented.

Validate and seal a newly reproduced package (or verify an already sealed package):

```sh
PYTHONDONTWRITEBYTECODE=1 venv/bin/python PATH_TO_THIS_PACKAGE/validate_package.py \
  --package PATH_TO_NEW_PACKAGE
```
