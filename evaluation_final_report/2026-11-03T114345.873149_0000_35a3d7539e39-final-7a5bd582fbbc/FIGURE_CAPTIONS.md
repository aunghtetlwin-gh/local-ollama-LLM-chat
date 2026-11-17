# Figure captions and derivations

## Figure 1: 01_automatic_accuracy

50 GSM8K + 4 reasoning + 4 instruction items per model; human-reviewed items excluded.

Derivation: Count answer_correct=True among the 58 objective items/model; no /70 composite.

## Figure 2: 02_gsm8k_accuracy_wilson

Same 50 questions/model; pointwise binomial intervals describe item sampling, not run-to-run variability.

Derivation: Wilson score interval using z=1.959963984540054, n=50; all wrong/format-failed answers retained.

## Figure 3: 03_human_verdict_distribution

One researcher, AI-assisted assessment suggestions; no independent inter-rater agreement was measured.

Derivation: Explicit imported verdict counts; partly-correct answers are retained separately, without half credit.

## Figure 4: 04_category_correctness

Automatic and human metrics are distinct. Internal cells have only 4 questions; coding review was static, without execution.

Derivation: Left: objective answer_correct proportions. Right: explicit human correct verdicts; not numeric-rating thresholds.

## Figure 5: 05_latency_distributions

70 requests/model; points retain all observations. Box = IQR; line = median; whiskers = 1.5×IQR. Warm-ups excluded.

Derivation: Original complete.json wall_time_s, cross-checked against request_metrics.csv; not time to first token.

## Figure 6: 06_throughput_and_allocation

Throughput uses each model’s tokenizer and variable-length outputs. Allocations are NOT independent GPU peak measurements.

Derivation: Throughput = sum(eval_count)/sum(eval_duration_s), 70 scored requests/model. Memory = consistent recorded size_vram / 2^20.

## Figure 7: 07_gsm8k_paired_differences

95% paired percentile bootstrap; 20,000 shared-ID resamples, seed 42. Descriptive pointwise intervals; no significance claims.

Derivation: Resample 50 matched question IDs with replacement, preserving all models for each ID; percentile endpoints 2.5/97.5%.

