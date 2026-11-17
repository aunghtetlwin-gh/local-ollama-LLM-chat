# NECTEC quality evaluation

Status: **offline framework implemented; inference protocol remains DRAFT**.
Phase 2 saved compatibility evidence is preserved; Phase 3 engineering is offline only.
See [PHASE3_READINESS.md](PHASE3_READINESS.md) for empirical verification and remaining gates.
Python 3.10+ standard library only; the collector's file locking requires Linux/POSIX.
Do not run the original benchmark scripts: some perform inference at import time and
write fixed historical output paths.

## Offline validation

From `/home/lailai/ollama-test`:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s evaluation/tests -v
PYTHONDONTWRITEBYTECODE=1 python3 -m evaluation.validate
PYTHONDONTWRITEBYTECODE=1 python3 -m evaluation.runner plan \
  --config evaluation/configs/quality_v2.draft.json \
  --suite internal_v2 --suite gsm8k_50_v1
```

These commands do not contact Ollama or PostgreSQL. Tests inject fake transports and
block socket connections and urllib network opening. The plan is 630 scored requests:
70 questions × 3 models × 3 repetitions, plus excluded warm-ups when eventually run.
The evaluation unittest suite needs no additional dependencies. The full application
offline suite also needs the development dependencies. Tests use disposable storage only.

## Files

- `datasets/pilot_v1/`: five original prompts, read-only historical manifest and hash sidecar.
- `datasets/internal_v2/`: 20 new synthetic questions, evaluator references, dataset manifest.
- `datasets/gsm8k_50_v1/`: 50 selected official questions, references, selection IDs/hashes,
  pinned full upstream test snapshot, README, and MIT license.
- `configs/quality_v2.draft.json`: common candidate generation settings; inference disabled.
- `configs/verification.example.json`: deliberately incomplete evidence template; cannot freeze.
- `common.py`: strict public dataset loading, hashes, exclusive output primitives.
- `runner.py`: offline planning/freezing and separately gated metadata inspection/collection.
- `scoring.py`: exact, JSON, numeric, format, and AST-only checks.
- `score_offline.py`: saved-response scoring and blinded internal manual-review export.
- `validate.py`: dataset, source selection, reference alignment, and historical integrity checks.
- `rubrics/manual_v2.md`: five anchored 1–5 dimensions and review instructions.
- `METHODOLOGY.md`, `PROVENANCE.md`: protocol, limitations, provenance, and report plan.
- `tests/test_evaluation.py`: offline tests for the implemented contracts.

The runner only loads `questions.jsonl` and its public manifest. Public records must have
exactly id, category, difficulty, prompt, and prompt_sha256. References and upstream
solutions are separate evaluator-only files. Payload construction copies only the prompt
into the user message, never an entire question/reference record. This is a software data
boundary, not an OS access-control boundary against a malicious local operator.

## Later approval gates — commands NOT run during Phase 1

First obtain explicit approval for service access and a development compatibility check.
The shipped configuration cannot launch inference even with `--allow-inference`.
Do not fabricate evidence or change the freeze gate to bypass missing compatibility.

1. Create a fresh staging directory. Capture model metadata only after approval:

```bash
mkdir evaluation_preflight_01
PYTHONDONTWRITEBYTECODE=1 python3 -m evaluation.runner inspect \
  --output evaluation_preflight_01/inspection.json --allow-ollama
cp evaluation/configs/verification.example.json evaluation_preflight_01/verification.json
```

`inspect` reads `/api/version`, `/api/tags`, and `/api/show`. It does not generate text,
pull models, stop models, or restart services. All three tags must already exist locally.
It refuses an existing output file. Treat this as service access, not an offline command.

2. Conduct a **separately approved development check on non-evaluation examples**. Verify
thinking controls and the exact context/output/sampling settings on all three artifacts;
record CPU/RAM/GPU/VRAM/driver/offload/concurrent-workload information in the verification
file. Enter the inspected digest for each model, reviewer/date, evidence notes, and
capacity_verified=true only when actually verified. The example starts false/empty.
Phase 1 intentionally does not automate that GPU check. If `/api/show` lacks compatible
boolean thinking metadata, the advertised-metadata pathway fails. The explicit
`empirical-thinking-v1` pathway validates saved evidence instead; see PHASE3_READINESS.md.
Neither pathway permits guessing or silently applying model defaults. A shared supported false mode
may be selected instead of true; document the condition.

3. Freeze only after evidence is complete (the command itself is offline):

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m evaluation.runner freeze \
  --config evaluation/configs/quality_v2.draft.json \
  --inspection evaluation_preflight_01/inspection.json \
  --verification evaluation_preflight_01/verification.json \
  --think true --output evaluation_preflight_01/quality_v2.frozen.json
```

If settings need changing, create a NEW candidate configuration and verify those exact
settings for all models. Never edit frozen run manifests. Freeze trusts the reviewer's
recorded evidence; it is not a hardware benchmark or independent attestation.

4. After an explicit approval to run the pilot, this exact command runs one question per
internal category, three repetitions per model: **45 scored requests**, plus warm-ups.
It is a smoke pilot, excluded from confirmatory claims if used to tune the protocol:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m evaluation.runner run \
  --config evaluation_preflight_01/quality_v2.frozen.json \
  --suite internal_v2 \
  --question-id K01 --question-id R02 --question-id C01 \
  --question-id S01 --question-id I01 \
  --output-root evaluation_runs --allow-inference
```

For a later separately approved full collection, omit the question IDs and include both
`--suite internal_v2 --suite gsm8k_50_v1`. Do not interpret the smoke pilot as fresh test
coverage if its answers influenced configuration choices.

5. The collector prints a unique run directory. Substitute that exact path below:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m evaluation.runner resume \
  --run-dir evaluation_runs/ACTUAL_RUN_ID --allow-inference
PYTHONDONTWRITEBYTECODE=1 python3 -m evaluation.score_offline \
  --run-dir evaluation_runs/ACTUAL_RUN_ID \
  --output-dir evaluation_runs/ACTUAL_RUN_ID/analyses/review_01
```

Resume can generate requests and requires renewed authorization in the session; offline
scoring never does. An existing analysis directory is refused. Completed requests are
skipped; add `--retry-errors` only to authorize one bounded retry of recorded transport
failures. Any uncertain request or warm-up requires separate server inspection and
`--confirm-server-idle` on resume, before service access. This operator acknowledgement
is not a cancellation mechanism or proof supplied by the collector.
Incorrect, malformed, truncated, empty, and HTTP-error responses are terminal;
they are not regenerated to improve scores. All attempt files are retained.

## Interruption and preservation

Each run has UTC time plus random suffix, a manifest, hashed plan, and source hashes.
Each request has its own directory and numbered attempts containing request.json,
response.json, and complete.json. Warm-ups are separate and excluded from scoring.
Responses are published by an exclusive hard link after flush/fsync; existing files
are never replaced. Process locks prevent concurrent collectors within the same run
and output root; different roots and other Ollama/GPU clients remain outside these locks.

An interruption before completion leaves an incomplete attempt. After separate server
inspection and the explicit server-idle acknowledgement, resume preserves it
and starts a new attempt, without overwriting or silently selecting a better answer.
If a response was saved just before completion bookkeeping was interrupted, it remains
in that incomplete attempt and the resumed attempt can repeat the request. This is
at-least-once execution, not an exactly-once guarantee; review attempt_count and document
interruptions. Changes in configuration, source, current public questions, model digest,
model metadata, or Ollama version cause resume to refuse continuation.

Malformed JSON/HTTP errors are retained as base64 body envelopes. Oversized bodies retain
only a clearly marked bounded prefix (2,000,000 bytes); they cannot receive success credit.
Transport failures without a response retain error type/status and timing. Transport,
HTTP/body, server/OOM, wrong-model, malformed-message, and uncertain-completion failures
stop collection immediately, including during warm-ups. Confirmed, structurally valid
length truncation is recorded without retry and does not halt the sequence. A response that
never reached the collector cannot be reconstructed. Interrupted warm-ups are also visible.

Keep `private_blind_mapping.json` away from raters. Manual exports include all internal
questions, including objectively scored ones. Share only the reviewer form and rubric;
copy forms into new reviewer-specific files. JSON/raw responses are authoritative.
CSV exports escape formula-like cells and are presentation artifacts, not exact raw text.

No root-level historical CSV, chart, script, authentication code, database, or service is
modified. The collector never executes generated source. Do not invoke generated code
manually to turn a structural pass into a functional-correctness claim.

## Development-only continuation policy

After separate explicit approval, the next development run command (from the repository root) is:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m evaluation.dev_inference --config evaluation/configs/quality_v2.draft.json --output-root evaluation_dev_runs --allow-inference --development-only
```

This starts a fresh, sequential nine-probe run; it does not resume or retry previous
requests. Existing results are preserved. No benchmark runner, draft configuration,
freeze requirement, or verification gate is changed by this policy.

For A/B, final content must parse in full as JSON and equal `{"answer":323}`.
Prose and fenced JSON remain failures; the harness never extracts embedded JSON.
Only `ResponseValidationError` / `invalid_final_json` may continue, after a confirmed
`done: true`, `done_reason: stop`, matching model, valid message, expected thinking
behavior, and successful monitoring finalization. Other contract failures stop.
C is an intentional output-limit probe, so JSON compliance is not applicable.

Each attempt preserves `request.json`, the returned `response.json`, monitoring,
and completion/timing `summary.json` when available. `output_format.json` records
`passed`, `failed`, `not_applicable`, or `not_evaluated`; `result.json` records request
and probe outcomes separately. A continued format failure also retains `error.json`
with its validation code. `complete.json` means the probe sequence finished, not
that all probes passed: inspect `output_format_failures` and `all_probes_passed`.

Transport failures, timeouts, HTTP/body decoding errors, OOM/error envelopes,
malformed messages, uncertain completion, monitoring failures, or detected foreign
model residency stop the sequence without automatic retries (`stopped.json`).
No further inference is issued after detection. An already active synchronous request
cannot be cancelled by monitoring; a transport failure does not prove server termination.
Raw HTTP decoding failures retain the transport's base64 envelope; oversized bodies
retain only a marked bounded prefix, and missing responses cannot be reconstructed.
The output-root advisory lock excludes collectors using that same root. Residency
sampling cannot detect other clients using the same model, clients between samples,
or collectors using another root; exclusive Ollama/GPU access must be arranged for
an approved run. This is development evidence, not capacity certification or permission
to freeze the benchmark.

Full offline validation (excludes service-backed integration tests and historical
root scripts):

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests evaluation/tests -q
```


The provisional three-repetition design is **70 questions × 3 models × 3 repetitions =
630 scored requests**, plus excluded warm-ups. A one-repetition alternative is **210
scored requests**, plus excluded warm-ups. Three repetitions remain the provisional
proposal; this engineering work does not finalize that decision or alter the draft.

## Synthetic capacity framework (offline implementation)

See [CAPACITY_TESTING.md](CAPACITY_TESTING.md) for the S/I/IO matrix, CPU-only token
accounting, explicit API safety profile, shared coordination, durable uncertainty state,
proposed execution command, and substantive capacity-report validation.

The generated [token census](reports/token-census-v1.json) has 210 rows. Installed manifest
identities match Phase 2, but all benchmark token counts are currently unavailable because
no compatible CPU tokenizer backend is installed. Preparation/execution fail closed;
no model inference or capacity approval was performed. The main draft remains unchanged.
The empirical pathway now requires a substantive versioned capacity report, beyond the
Phase 3B file-hash attachment check. Existing thinking evidence is preserved.

## Recommended fixed-workload path

[SCOPED_WORKLOAD.md](SCOPED_WORKLOAD.md) documents the minimal one-repetition proposal
(210 scored requests), pending human-review preparation, explicit limitations, freeze and
six-request smoke commands. `fixed-workload-readiness-v1` preserves empirical thinking
verification and keeps capacity_verified=false; full synthetic capacity verification is
still available through the existing path. No approval/freeze/inference was performed.
The runner now checks residency before requests and waits for natural expiration at
startup, transitions, and final release. Current collectors share the execution lock
across output roots; external clients remain outside it.
