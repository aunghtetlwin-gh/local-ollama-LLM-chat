# Experimental protocol and proposed report

## Study tracks and freeze

Preserve the September five-task pilot as exploratory historical evidence. Evaluate the
new balanced 20-question internal suite and fixed 50-question GSM8K subset separately.
Approve prompt/reference/rubric versions before collection. Configuration changes after
looking at evaluation answers create a new exploratory condition, not a clean test.
Use non-test development examples for compatibility checks and reviewer calibration.

The draft uses qwen3:1.7b, qwen3:8b, gemma4:12b; shared user/system text, stream=false,
context 8192, output limit 4096, temperature 0, seed 42, top_k 40, top_p 0.9,
repeat_last_n 64, repeat_penalty 1.0, keep_alive 10m, timeout 600 seconds. These are
candidate settings, not verified supported settings. Freeze requires a common explicitly verified boolean thinking value, through advertised
metadata or the versioned empirical pathway in PHASE3_READINESS.md, matching model digests,
a named reviewer, exact option verification, and separate recorded capacity evidence. No thinking mode is selected in the draft.
Verify the installed Ollama implementation instead of inferring support from model names.

Native model templates and quantization are recorded by /api/show and not overwritten.
Same request options do not mean equal compute, equal effective token budget, or optimal
settings for every architecture. Context truncation must be checked in development;
reserving context space alone is not proof all prompts fit every tokenizer/template.
The collector has no tools/retrieval, shared conversation history, or reference answers.

## Collection and repetitions

One request is active at a time. Repetition 1 model order is Qwen 1.7B, Qwen 8B, Gemma;
repetitions 2 and 3 rotate the order. Questions are hash-ordered per repetition using
`SHA256(UTF8(question_order_seed + ':' + repetition + ':' + question_id))`, then ID as
tie-breaker. Every model receives the same question order for that repetition. One short
warm-up precedes each active repetition/model block (num_predict=1); it is excluded.
A resumed process warms any newly active blocks again, and keeps those warm-ups separate.
Infrastructure failures now stop the sequence, including during warm-ups. Resuming an
uncertain request requires separate server inspection and `--confirm-server-idle`. These
are safety changes requiring review before collection; successful-run ordering, options,
and warm-up count are unchanged.

There are 630 scored requests in the full plan: 180 internal and 450 GSM8K. Use repetition
1 as the primary quality result and repeats 2–3 as repeatability/timing evidence; never
select the best response. Repeated deterministic outputs are not new independent questions.

Reserve an approved exclusive GPU window. This collector intentionally does not stop or
unload other users' models or services. With keep_alive=10m, prior models may remain
resident; Ollama placement/offloading and concurrent workloads can affect timing. Verify
and record residency/offload behavior during the later approved preflight. Phase 1 is
not a cold-start performance or GPU-power measurement harness. Raw durations/token counts
are saved, but non-streaming wall time is not time to first token. Do not combine these
measurements with historical GPU charts as if collected under the same workload.

## Scoring

Automatic results separate answer_correct, format_compliant, static_checks_pass, completion
status, and manual_review_required. Null correctness means not objectively evaluated;
it is not a failure or pass. No generated code is executed, compiled, imported, or invoked.

- R01 and R04 use typed JSON reference equality (R04 accepts either valid ordering).
- R02/R03 and I04 use exact text after CRLF normalization and at most one final newline.
  For these tasks the exact-answer and exact-format outcomes are intentionally coupled.
- I01–I03 use typed JSON values and exact shape/keys. Duplicate keys, nonfinite constants,
  booleans in place of integers, floats in place of integers, extra keys, or fences fail.
  JSON whitespace and object key order do not affect correctness.
- GSM8K requires exactly one FINAL_ANSWER marker on the last line, a signed ASCII integer
  or decimal (properly grouped optional commas), and Decimal equality to the reference.
  No fractions, exponents, units, fallback extraction, or eval-based arithmetic are allowed.
  Strict formatting failures are distinct diagnostics but receive no correctness credit.
- Knowledge/summary checks measure only bullet/sentence form. Semantic correctness needs
  human review. Sentence splitting is a controlled English heuristic and can miscount
  abbreviations; reviewers may annotate it, never silently rewrite automatic outcomes.
- Coding uses AST parse, exactly one synchronous named function, required plain arguments,
  no decorators/defaults/annotations/import nodes, and no fences. A structurally valid
  function returning None can pass; malicious calls inside a function can also pass.
  AST success certifies neither functional correctness nor safety. Manual examples are
  inspection aids and never executed.

Inputs over 100,000 characters are rejected by the scorer. Transport bodies are capped
at 2,000,000 bytes. These limits reduce resource exposure but are not a general parser
sandbox. Run offline scoring on trusted local infrastructure, with no generated-code
execution. Escape model text before any future HTML rendering; current exports are
JSON and formula-escaped CSV.

## Manual review

The rubric defines correctness/fidelity, instruction following, relevance, completeness,
and conciseness/clarity, each 1–5. All 20 internal questions appear in blinded forms.
Use two independent reviewers where possible; retain reviewer IDs, rationale, pre-consensus
ratings, and a separate adjudication file. On coding, call the correctness dimension
"manual algorithm assessment"; runtime correctness is not evaluated. Model names are
removed from metadata, but self-identification in response content can reveal identity.

Do not confuse missing ratings with zeros. Failure statuses receive no aggregate success
credit and must be reported. A completed but wrong answer may still be relevant or clear.
Report category/dimension scores before the secondary /25 aggregate. Macro-average the
five equally sized categories. Agreement statistics and aggregate reports remain a later
analysis step; Phase 1 exports review forms and per-response scores, not invented ratings.

## Uncertainty and limitations

Report counts/denominators, failures, parser failures, and truncations. For primary GSM8K
accuracy use a 95% Wilson interval over 50 questions. Compare models on paired questions;
if bootstrapping differences, resample question IDs while keeping repetitions grouped.
For the curated internal suite, uncertainty is descriptive and does not establish general
population accuracy. Report median/mean and spread for latency, with workload and
completion status identified. Do not treat 150 repeated GSM8K answers as 150 independent
problems or call a /25 rubric percentage objective accuracy.

Limits: small English-only sample; possible public-benchmark contamination; author-assigned
difficulty; rater subjectivity; no executed coding tests; installed quantized artifacts,
not pure parameter-count effects; tokenizer/template differences; unverified thinking and
context feasibility until preflight; hardware/residency effects; local filesystem checks
are not cryptographic protection against a privileged operator. The statistical summaries,
confidence-interval plots, rater agreement computation, and final human ratings are planned
for the later analysis phase and are not claimed as already implemented.

## Internship completion plan

1. Review Phase 1 questions, references, rubric, provenance, and offline test report.
2. Approve a compatibility/development window; record exact metadata and hardware evidence.
3. Freeze a supported common protocol, then separately approve a bounded smoke pilot.
4. Resolve defects using development examples. If evaluation items influence tuning,
   label that run exploratory and disclose the exposure in the report.
5. Approve full collection; archive responses and statuses. Review repetition 1 first,
   reuse identical response-hash ratings only with recorded provenance, assess changed repeats.
6. Complete independent review, paired analysis, uncertainty, and report figures.

With two working weeks: two days for review/preflight, two for approved smoke/full collection
and troubleshooting, three for ratings/adjudication, two for analysis/report, one buffer.
Estimate inference time from approved development measurements, not parameter count.
If time is tight, freeze a one-repetition candidate before collection (210 requests),
prioritizing question coverage and independent review over repeated deterministic output.
Three repetitions remain provisional; neither alternative is finalized by offline engineering.

## Proposed AIT report structure

1. Research question and scope; distinguish historical pilot from new study.
2. Dataset provenance, selection algorithm, exact counts, and licenses.
3. Installed model artifacts, digests, quantization, templates, runtime/hardware metadata.
4. Frozen request settings, thinking condition, ordering, repetitions, failure policy.
5. Correctness checks, strict output rules, manual rubric, and non-execution safety boundary.
6. Results: per-question outcomes, category/dimension summaries, GSM8K accuracy and interval,
   paired differences, completion/truncation rates, and workload-specific latency.
7. Reviewer agreement and adjudications; representative failures without cherry-picking.
8. Limitations, reproducibility commands, immutable artifact hashes, and future work.

Every reported number must identify its run ID, dataset/rubric/evaluator versions, denominator,
and source response hashes. No results section should contain estimated model scores.

## Fixed-workload one-repetition proposal

SCOPED_WORKLOAD.md defines the separately reviewed alternative: one repetition, 210 scored
requests, keep_alive=30s and empty residency at model transitions. This does not modify the
preserved three-repetition draft. Scoped readiness is bound to the fixed question/model/
runtime/settings/source hashes and named affirmative human review. It keeps full capacity
unverified and does not claim occupied 8192-token context or sustained 4096-token output.
The full-capacity verification path remains intact. Natural-expiry waits and pre-request
residency checks change block-boundary scheduling, outside scored timing; request order
and warm-up behavior are unchanged. Exclusive GPU/Ollama access remains necessary.
