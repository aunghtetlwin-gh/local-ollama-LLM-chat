# Results and Discussion

## Study condition and analysis scope

The evaluation compared the installed Ollama tags qwen3:1.7b, qwen3:8b and gemma4:12b on
70 fixed English-language questions each: 20 curated internal items and 50 GSM8K items.
One repetition produced 210 scored responses. All requests used the frozen condition:
8192 configured context tokens, 4096 maximum generated tokens, temperature 0, seed 42,
top_k 40, top_p 0.9, repeat_penalty 1.0, repeat_last_n 64, explicit think=false,
non-streaming responses, keep_alive=30s, and a 600-second transport timeout. The runtime
was Ollama 0.32.15 on the recorded RTX 5060 Ti system.
The installed quantized artifacts/templates are the comparison units; parameter count
alone was not isolated experimentally. Exact model digests are in model_metadata.json.

Automatic correctness applies to 58 items/model (50 GSM8K, four reasoning and four
instruction tasks). The remaining 12 items/model received researcher correctness review
(four coding, four knowledge and four summarization). These measurement types are reported
separately. No combined accuracy over 70 items or invented /25 rubric aggregate is used.

## Collection integrity

All 210 scored requests completed with one attempt each. Request/response hashes, plan,
frozen settings, dataset/reference identities and source bindings passed offline checks.
No scored truncation, missing response or recorded infrastructure error occurred. The
three one-token warm-ups ended at their intentional length limit and were excluded from
quality and scored latency summaries. Full 8192/4096 capacity was not certified.

## Automatically scored correctness

| Model | Automatic /58 | GSM8K /50 | GSM8K 95% CI | Human C/P/I/U /12 | Mean human correctness /5 |
|---|---|---|---|---|---|
| qwen3:1.7b | 35/58 (60.3%) | 34/50 (68.0%) | 54.2–79.2% | 7/2/3/0 | 4.00 |
| qwen3:8b | 48/58 (82.8%) | 45/50 (90.0%) | 78.6–95.7% | 9/3/0/0 | 4.75 |
| gemma4:12b | 53/58 (91.4%) | 47/50 (94.0%) | 83.8–97.9% | 10/2/0/0 | 4.83 |


The automatic-subset correctness rates were 60.3%, 82.8% and 91.4%, respectively. Because
50 of the 58 automatic items are GSM8K, this pooled metric is strongly weighted toward
that dataset rather than an equal-category general-quality score (Figure 1).

GSM8K accuracy was 34/50 (68%) for Qwen3 1.7B, 45/50 (90%) for Qwen3 8B, and 47/50 (94%)
for Gemma4 12B. All 150 answers, including wrong and malformed final-answer representations,
received offline outcomes; none was excluded from its denominator. The pointwise Wilson
intervals (Figure 2) quantify nominal item-sampling uncertainty, not run-to-run variation
or uncertainty caused by benchmark contamination. They should not be generalized to all
mathematical reasoning tasks.

The paired contrasts in Figure 7 and tables/gsm8k_paired_comparisons.csv use the same 50
question IDs. They retain discordant outcomes rather than treating model samples as
independent. The following are descriptive, exploratory comparisons, with no formal
hypothesis test, multiplicity-adjusted inference, or claim of statistical significance:

- qwen3:8b minus qwen3:1.7b: +22 percentage points; paired bootstrap 95% interval 10 to 36 points; 12 comparison-only correct versus 1 reference-only correct answers.
- gemma4:12b minus qwen3:1.7b: +26 percentage points; paired bootstrap 95% interval 14 to 38 points; 13 comparison-only correct versus 0 reference-only correct answers.
- gemma4:12b minus qwen3:8b: +4 percentage points; paired bootstrap 95% interval 0 to 10 points; 2 comparison-only correct versus 0 reference-only correct answers.

The observed four-point gap between the two larger models represents only two net
questions; it should not be presented as established general superiority. The much
smaller internal automatic categories also illustrate metric sensitivity: correctness
was 1/4, 0/4 and 3/4 for reasoning, and 0/4, 3/4 and 3/4 for instruction tasks (Figure 4).
Four questions per category are insufficient for broad category-level rankings.

## Researcher correctness review

One researcher (R1) recorded the 36 human ratings using AI-assisted assessment suggestions.
No independent inter-rater agreement was measured. Existing blind IDs were retained, but
the exercise should not be described as independent multi-rater validation. The judgments
and their rationales were imported unchanged; they are not automatic correctness labels.

Fully-correct verdicts were 7/12, 9/12 and 10/12 (58.3%, 75.0% and 83.3%). Partly-correct
verdicts numbered two, three and two, while incorrect verdicts numbered three, zero and
zero. No uncertain verdict was recorded (Figure 3). The mean correctness/fidelity ratings
were 4.00, 4.75 and 4.83 on the original 1–5 scale. These ordinal-rating means are descriptive;
they are not accuracy percentages. The four other rubric dimensions were not rated and
were neither imputed nor treated as zeros.

Coding was reviewed statically by tracing the supplied examples and inspecting the
algorithm; generated code was not executed. The researcher judged 2/4 Qwen3 1.7B coding
answers fully correct and 4/4 for each larger model. All 12 answers passed the automatic
structural checker, demonstrating why parsing/signature compliance cannot establish
functional correctness. Knowledge fully-correct counts were 2/4, 2/4 and 4/4. Summarization
fully-correct counts were 3/4, 3/4 and 2/4. Thus, the highest observed GSM8K score did not
translate into the highest fully-correct summarization count under this researcher's
criteria. The counts are small and sensitive to reviewer interpretation.

## Formatting sensitivity and notable failures

There were 38 automatically incorrect outcomes, including 13 format-contract failures;
five were parser/unsupported-representation failures. These counts overlap. Overall
format compliance was 63/70, 66/70 and 68/70. Exact-answer tasks intentionally couple
format and correctness, so a format failure does not always mean invalid JSON or a
mathematical error. Strict parsing and no fallback extraction were preserved.

Examples include a fenced JSON array for Qwen3 8B I02 and fenced JSON for Gemma4 12B I03.
Both violate the required output contract even when the enclosed values appear suitable.
Gemma4 12B R01 emitted an initial candidate followed by a self-correction and a second
fenced object; the scorer did not extract a favourable final object. Researcher-identified
Qwen3 1.7B code defects included adjacent-only deduplication in C01 and returning an empty
list rather than raising ValueError for nonpositive size in C03. Its K03 answer contradicted
its own rollback statement. Source hashes and exact excerpts are retained in
 tables/notable_failures.csv; no answers or ratings were repaired.

## Latency, generation rate and memory trade-offs

| Model | Mean wall, s | Median wall, s | P95 wall, s | Generated tokens | Generation tokens/s | Ollama MiB |
|---|---|---|---|---|---|---|
| qwen3:1.7b | 0.442 | 0.397 | 0.953 | 7380 | 259.1 | 3028 |
| qwen3:8b | 1.343 | 1.282 | 2.704 | 7038 | 78.5 | 7156 |
| gemma4:12b | 4.589 | 4.122 | 8.821 | 15416 | 50.1 | 8625 |


The observed condition therefore shows a quality/latency trade-off: the larger artifacts
had higher GSM8K correctness but longer median response times and larger recorded model
allocations. This is a descriptive comparison of these runs, not a causal estimate of
model-size effects. Gemma4 generated 15,416 tokens, compared with 7,380 and 7,038, so its
longer responses also contributed to elapsed latency. It had a 30.09-second maximum
request, which remained in the distribution rather than being silently removed (Figure 5).

Aggregate generation rate is total generated tokens divided by summed Ollama eval_duration.
Different tokenizers and generated lengths limit direct hardware-efficiency interpretation
(Figure 6). The requests were warmed; warm-up loading time and residency-expiration waits
are excluded from scored latency. Non-streaming wall time is not time to first token.

All 307 residency snapshots showed at most one expected model, matching digest/context
and equal size and size_vram. Recorded transitions and the final block reached empty
residency. The approximately 3028, 7156 and 8625 MiB figures are Ollama-reported allocations,
not independent GPU peak measurements. No continuous GPU-wide peak/process telemetry was
collected, so external interference between samples or from the same client/model cannot
be ruled out retrospectively.

## Limitations and interpretation

The study used a single repetition, so it provides no estimate of between-run reliability
or seed/hardware/runtime variance. Temperature zero and a fixed seed do not establish
universal determinism. The internal sample contains only four questions/category/model;
the public GSM8K subset has 50 questions and may overlap model training data. Observed
performance must be limited to these tasks and installed quantized model/runtime conditions.

The researcher review used AI-assisted suggestions and only one rater. Anchoring,
confirmation bias, shared assessment errors and subjective treatment of omissions may
influence its outcomes. No inter-rater agreement or independent execution validation is
available. Human verdict proportions should remain separately labelled, particularly for
static code assessment. There is no completed full five-category rubric score.

C03 and I01 were exposed during the smoke test. This exposure must be disclosed; conclusions
assume no tuning, model selection by favourable attempt, prompt rewriting, or changed
scoring rules after exposure. Strict formatting is part of the prespecified task contract,
but lower scores can reflect output-style compliance as well as substantive reasoning.

Question order was shared, but model execution occurred in fixed blocks. Thermal/cache/
shared-system effects were not counterbalanced by repeated runs. Wilson and paired
bootstrap intervals describe conditional item uncertainty only; they do not incorporate
these methodological sources of uncertainty. They are pointwise and exploratory, not
familywise-adjusted significance tests.

Finally, observed prompt counts and generated lengths were far below configured maxima;
no occupied 8192-token context or sustained 4096-token output certification is claimed.
The appropriate report is a completed fixed-workload quality experiment, with separate
automatic and researcher-reviewed findings and transparent performance/memory definitions.

## Statistical references

- NIST/SEMATECH e-Handbook, Wilson confidence intervals: https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm
- SciPy documentation, paired-index and percentile bootstrap definitions: https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html

The implementation uses NumPy for explicit resampling; SciPy was not a runtime dependency.
