# Research tables

Automatic correctness and researcher verdicts remain separate; C/P/I/U = correct/partly correct/incorrect/uncertain.

| Model | Automatic /58 | GSM8K /50 | GSM8K 95% CI | Human C/P/I/U /12 | Mean human correctness /5 |
|---|---|---|---|---|---|
| qwen3:1.7b | 35/58 (60.3%) | 34/50 (68.0%) | 54.2–79.2% | 7/2/3/0 | 4.00 |
| qwen3:8b | 48/58 (82.8%) | 45/50 (90.0%) | 78.6–95.7% | 9/3/0/0 | 4.75 |
| gemma4:12b | 53/58 (91.4%) | 47/50 (94.0%) | 83.8–97.9% | 10/2/0/0 | 4.83 |

## Automatic categories

| model | category | correct_n | questions_n | automatic_accuracy_percent | format_compliant_n | format_percent |
|---|---|---|---|---|---|---|
| qwen3:1.7b | reasoning | 1 | 4 | 25.0000 | 1 | 25.0000 |
| qwen3:1.7b | instruction | 0 | 4 | 0.0000 | 1 | 25.0000 |
| qwen3:1.7b | gsm8k | 34 | 50 | 68.0000 | 49 | 98.0000 |
| qwen3:8b | reasoning | 0 | 4 | 0.0000 | 1 | 25.0000 |
| qwen3:8b | instruction | 3 | 4 | 75.0000 | 3 | 75.0000 |
| qwen3:8b | gsm8k | 45 | 50 | 90.0000 | 50 | 100.0000 |
| gemma4:12b | reasoning | 3 | 4 | 75.0000 | 3 | 75.0000 |
| gemma4:12b | instruction | 3 | 4 | 75.0000 | 3 | 75.0000 |
| gemma4:12b | gsm8k | 47 | 50 | 94.0000 | 50 | 100.0000 |

## Human-reviewed categories

| model | category | reviewed_n | correct_n | partly_correct_n | incorrect_n | uncertain_n | human_fully_correct_percent | correctness_mean_1_to_5 | runtime_correctness |
|---|---|---|---|---|---|---|---|---|---|
| qwen3:1.7b | coding | 4 | 2 | 0 | 2 | 0 | 50.0000 | 3.5000 | not evaluated |
| qwen3:1.7b | knowledge | 4 | 2 | 1 | 1 | 0 | 50.0000 | 3.7500 | not applicable |
| qwen3:1.7b | summarization | 4 | 3 | 1 | 0 | 0 | 75.0000 | 4.7500 | not applicable |
| qwen3:8b | coding | 4 | 4 | 0 | 0 | 0 | 100.0000 | 5 | not evaluated |
| qwen3:8b | knowledge | 4 | 2 | 2 | 0 | 0 | 50.0000 | 4.5000 | not applicable |
| qwen3:8b | summarization | 4 | 3 | 1 | 0 | 0 | 75.0000 | 4.7500 | not applicable |
| gemma4:12b | coding | 4 | 4 | 0 | 0 | 0 | 100.0000 | 5 | not evaluated |
| gemma4:12b | knowledge | 4 | 4 | 0 | 0 | 0 | 100.0000 | 5 | not applicable |
| gemma4:12b | summarization | 4 | 2 | 2 | 0 | 0 | 50.0000 | 4.5000 | not applicable |

## Scored-request latency, seconds

| model | requests_n | mean_s | median_s | p05_s | p95_s | min_s | max_s | sum_s |
|---|---|---|---|---|---|---|---|---|
| qwen3:1.7b | 70 | 0.4424 | 0.3971 | 0.1218 | 0.9526 | 0.0817 | 1.2252 | 30.9703 |
| qwen3:8b | 70 | 1.3430 | 1.2820 | 0.2274 | 2.7040 | 0.0846 | 3.1720 | 94.0114 |
| gemma4:12b | 70 | 4.5891 | 4.1217 | 0.3878 | 8.8214 | 0.2108 | 30.0926 | 321.2398 |

## Token counts and generation rate

| model | requests_n | prompt_tokens_total | prompt_tokens_median | prompt_tokens_max | generated_tokens_total | generated_tokens_median | generated_tokens_max | generation_duration_total_s | aggregate_generation_tokens_per_s |
|---|---|---|---|---|---|---|---|---|---|
| qwen3:1.7b | 70 | 9498 | 135.0000 | 206 | 7380 | 94.0000 | 310 | 28.4810 | 259.1198 |
| qwen3:8b | 70 | 9498 | 135.0000 | 206 | 7038 | 97.0000 | 245 | 89.6144 | 78.5365 |
| gemma4:12b | 70 | 9365 | 132.5000 | 201 | 15416 | 196.5000 | 1467 | 307.4836 | 50.1360 |

## Ollama allocation, bytes and MiB

| model | size_bytes | size_vram_bytes | ollama_allocation_mib | independent_gpu_peak_measured |
|---|---|---|---|---|
| qwen3:1.7b | 3174805011 | 3174805011 | 3027.7300 | False |
| qwen3:8b | 7503400140 | 7503400140 | 7155.8000 | False |
| gemma4:12b | 9044009942 | 9044009942 | 8625.0400 | False |

## Paired GSM8K comparisons, percentage points

| reference_model | comparison_model | question_pairs_n | comparison_only_correct_n | reference_only_correct_n | both_correct_n | both_incorrect_n | accuracy_difference_percentage_points | paired_bootstrap95_low_percentage_points | paired_bootstrap95_high_percentage_points | bootstrap_resamples | bootstrap_seed | hypothesis_test_performed |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen3:1.7b | qwen3:8b | 50 | 12 | 1 | 33 | 4 | 22.0000 | 10.0000 | 36.0000 | 20000 | 42 | False |
| qwen3:1.7b | gemma4:12b | 50 | 13 | 0 | 34 | 3 | 26.0000 | 14.0000 | 38.0000 | 20000 | 42 | False |
| qwen3:8b | gemma4:12b | 50 | 2 | 0 | 45 | 3 | 4.0000 | 0.0000 | 10.0000 | 20000 | 42 | False |
