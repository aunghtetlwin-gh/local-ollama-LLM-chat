# Dataset and historical provenance

## Original five-task pilot

`datasets/pilot_v1/manifest.json` inventories the historical CSVs, reports, charts, and
benchmark scripts with SHA-256 and byte size. CSV counts, model labels, and available
recorded timestamp ranges are included. It captures the current Git HEAD and capture
time, but does not mislabel uncommitted/current source as the exact September source.
The five prompts were copied from the saved CSV, not by importing a benchmark script.

The manifest, prompts, and hash sidecar have read-only permissions. The validator verifies
the sidecar, prompt hash, and every inventoried original file. This is immutable-by-policy
and tamper-evident against accidental changes, not WORM storage or protection from an
administrator who can rewrite both manifest and sidecar. For institutional archival,
retain the checksum separately or commit/archive the manifest in a protected repository.
No existing artifact has been moved, rewritten, or retroactively re-scored.

Historical quality rows: 15, covering three models and five tasks. Settings visible in the
current script are 4096 context, temperature 0, seed 42, non-streaming, keep_alive 10m;
these are inferred provenance, not proof of the old requests. Historical model digests,
Ollama version, explicit thinking/output limits, reviewer identity, and timestamp timezone
were not saved. The old coding tests_pass fields are legacy claims; current AST checks
cannot reproduce or endorse runtime correctness. A later retrospective scoring run must
write a new analysis directory and be labeled separately from original results.

## New internal questions

`internal_v2` contains 20 newly authored synthetic questions: K01–K04, R01–R04, C01–C04,
S01–S04, I01–I04. No original pilot prompt is reused. Categories are equally weighted.
Difficulty is author-assigned (easy/medium/hard), not empirically calibrated. The public
question file contains exact prompt text and its UTF-8 SHA-256. References contain the
oracle or acceptance criteria, scoring rules, and code signatures/manual examples.
No real user records or production conversations are used. The R01 draft wording was
clarified before collection to specify integer VALUES under named JSON keys.

## Official GSM8K snapshot and selection

Source: https://github.com/openai/grade-school-math

Pinned revision: `3101c7d5072418e28b9008a6636bde82a006892c`

Pinned files:

- https://raw.githubusercontent.com/openai/grade-school-math/3101c7d5072418e28b9008a6636bde82a006892c/grade_school_math/data/test.jsonl
- https://raw.githubusercontent.com/openai/grade-school-math/3101c7d5072418e28b9008a6636bde82a006892c/LICENSE
- https://raw.githubusercontent.com/openai/grade-school-math/3101c7d5072418e28b9008a6636bde82a006892c/README.md

Attribution: OpenAI, GSM8K / Grade School Math; Cobbe et al., *Training Verifiers to Solve
Math Word Problems* (2021), https://arxiv.org/abs/2110.14168. The downloaded repository
LICENSE is MIT, Copyright (c) 2021 OpenAI; the exact license text is bundled. The pinned
README describes the question/answer fields and the reference final-answer marker ####.
The full upstream test file has 1,319 records and remains bundled for offline verification;
no upstream code, calculator, dependency, or evaluation program is executed.

Selection is independent of model outputs and Python PRNG versions:

1. Let i be each zero-based original test row index, 0 through 1318.
2. Compute SHA256 of ASCII `nectec-gsm8k-50-v1-seed42:<i>` (decimal index, no padding).
3. Sort ascending by the hexadecimal hash, with index as the deterministic tie-breaker.
4. Select the first 50 and preserve this rank order.
5. Assign ID `gsm8k-test-` plus the index padded to four decimal digits.

`selection.json` stores every selected index, ID, rank hash, original UTF-8 question hash,
and canonical source-record hash. Canonical record hashing uses JSON with sorted keys,
UTF-8, ensure_ascii=false, separators comma/colon, and no extra spaces. `manifest.json`
pins hashes of selection, full upstream test data, public questions, private references,
README, and license. `python3 -m evaluation.validate` reconstructs and verifies selection
and reference extraction entirely offline.

The wrapper requests a final `FINAL_ANSWER: <number>` line. Only the original question and
this fixed wrapper are model-visible. Reference numbers are extracted offline after ####
and stored in references.jsonl; full upstream solutions stay in upstream_test.jsonl, which
the runner never opens. All 50 reference answers pass the defined numeric oracle in tests.

Report this as "GSM8K fixed 50-question test subset, zero-shot, NECTEC protocol v2", not
as a full official benchmark result. No model performance results exist yet. Public
benchmark exposure/training contamination cannot be excluded.
