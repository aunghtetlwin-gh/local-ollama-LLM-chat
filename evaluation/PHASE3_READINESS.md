# Phase 3 offline readiness engineering

The protocol remains draft. No configuration was frozen, capacity approved, server
contacted, or inference performed during this implementation. The three-repetition
proposal remains 70 questions × 3 models × 3 repetitions = **630 scored requests**, plus
normally nine excluded warm-ups. One repetition is **210 scored requests**, plus normally
three excluded warm-ups. Decide before freeze; repetitions are not independent questions.

## Empirical thinking evidence v1

`thinking_evidence.py` implements `empirical-thinking-v1`. The original advertised path
remains the default (`advertised-metadata-v1`), including exact boolean metadata checks.
Unknown methods fail. Original `/api/show` metadata is never rewritten or augmented.

The immutable Phase 2 experiment is:
`evaluation_dev_runs/dev-2026-11-03T071419.213574+0000-db8509361d9e`.
Its byte-hash inventory is `evidence/phase2-thinking-v1.json`, outside that experiment.
It covers all 129 saved files, including monitoring and format-error artifacts. The
inventory builder reads files offline and uses exclusive creation for its output:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m evaluation.thinking_evidence \
  --run-dir evaluation_dev_runs/dev-2026-11-03T071419.213574+0000-db8509361d9e \
  --output /tmp/NEW-phase2-thinking-index.json
```

Use a new output filename. The builder refuses an output inside the evidence tree.
It does not create a verification approval or set `capacity_verified`.

To select this path in a NEW review file, retain all fields from
`configs/verification.example.json` and add:

```json
{
  "thinking_verification": {
    "method": "empirical-thinking-v1",
    "evidence": {"...": "the complete parsed phase2-thinking-v1.json object"},
    "evidence_sha256": "canonical digest of that complete object"
  }
}
```

The ellipsis is explanatory, not usable evidence. Load the actual index with `read_json`
and compute its canonical digest with `evaluation.common.digest`. Embedding the index
binds it into the frozen configuration hash later, if separately approved. Its root is
repository-relative; keep the archived source tree there or explicitly review a relocated
index. The index hashes the validator version's Python source and common/scoring helpers;
source changes invalidate it and require a new reviewed index. The collection manifest
also binds the runner's source. A named, nonblank reviewer remains mandatory.

Validation rechecks all file hashes and rejects missing, added, altered, or symlinked
artifacts. It recomputes A/B behavior for every model and cross-checks saved outcomes,
completion summaries, monitoring, and the complete nine-probe sequence, including C.
It binds model digests, full `/api/show` metadata/templates, Ollama version, exact options,
system text, explicit boolean thinking mode, request messages, and raw parsed responses.
It requires confirmed stop completion for A/B, length completion for C, no tools, valid
assistant messages, thinking text present for B and absent for A/C, successful monitoring,
matching resident digests/context, empty initial residency, and confirmed model expiry.
Contradictory advertised modes cannot be overridden with empirical evidence.

Qwen 1.7B A's preserved JSON failure remains a failed format result. Its confirmed
completion and absent thinking are valid thinking-disabled observations. The validator
never extracts embedded JSON. Output-format results remain separate from thinking
compatibility, and contradictory saved pass/error flags cause rejection. This v1 pathway
is deliberately specific to the existing development probes; changing prompts or probe
structure requires a reviewed validator revision. It is behavioral evidence on these
prompts, not proof of hidden internal computation or universal prompt-level compliance.

Hashes provide reproducibility and accidental-corruption detection, not authenticated
attestation against an operator who can rewrite both artifacts and their index. Retain
an independently archived copy/digest and record reviewer/date/environment information.
The historical development manifest does not contain a source hash of its original
harness; the new index binds the offline validator used now and must not imply otherwise.

## Capacity is a separate gate

Both paths preserve the digest, exact-options, evidence-note, named-reviewer, and
`capacity_verified=true` requirements. The empirical path additionally requires each
model's separately archived capacity evidence files:

```json
"capacity_evidence": [
  {"path": "evaluation_capacity_runs/APPROVED_RUN/report.json", "sha256": "actual byte hash"}
]
```

No such report is created or claimed here. Files must exist, match their hashes, and be
outside the thinking experiment. A reviewer must assess their content and applicability:
this file-reference check is not an automated capacity benchmark or semantic certification
of the report. Do not set the capacity flag merely to make the gate pass.

A separately approved capacity procedure must document, for every exact model/runtime:

- Near-limit occupied context with measured tokenizer/template/system overhead, reserved
  output budget, and evidence that early input was not silently truncated.
- Sustained output approaching the proposed 4096-token limit; actual prompt/output counts,
  completion reasons, and the interpretation of any early stop or length truncation.
- Combined long-input/output feasibility within the 8192-token context, wall/generation
  durations under the 600-second timeout, memory peaks, and full residency observations.
- Exact generation options, baseline thinking mode, model digests/templates, Ollama,
  driver, CPU/RAM/GPU, server settings, cold/warm state, and workload isolation.
- Residency during model transitions under the policy actually proposed for the benchmark.

The tiny Phase 2 prompts, allocated context 8192, and one-token C probes do not establish
these claims. If limits are reduced, create a new candidate configuration and reverify
its exact options. The current draft remains unchanged.

## Benchmark safety changes requiring review

The collector remains sequential. It now holds locks on both the run and its output
root, rejecting concurrent runs using the same root before service access. Other roots,
the development harness's different root, direct clients, and unrelated GPU jobs are
not excluded. An exclusive GPU/Ollama window remains an operational prerequisite.

Scored requests and warm-ups now stop on transport errors/timeouts, HTTP/body errors,
server/OOM error envelopes, incomplete or malformed responses, unexpected model identity,
unknown completion reasons, or unexpected tool calls. Requests and any returned response
are saved before response rejection. Transport failures retain error type and timing for
scored requests; absent responses cannot be recovered. Interrupted attempts are preserved.
Confirmed length truncation with a valid message/model is saved as `truncated`, receives
no correctness credit, and may continue. Completed answer-format/quality failures are
scored offline; the collector does not retry them to improve answers.

An uncertain scored attempt or warm-up blocks resume before metadata access unless an
operator has separately established that server generation stopped and supplies
`--confirm-server-idle` with a separately approved resume. This flag is an acknowledgement,
not a server probe or cancellation. It does not permit overlapping requests or prove the
GPU is exclusive. A transport-error request has at most one explicit `--retry-errors`
retry; otherwise it is skipped after the safety acknowledgement. Incomplete requests
may be repeated after acknowledgement. All prior artifacts remain; execution is still
at least once, not exactly once. Old uncertain artifacts remain visible, so the
acknowledgement is conservatively required on subsequent resumes too. Malformed/HTTP/OOM
responses are terminal for that request, never implicitly regenerated.

These failure/resumption and lock changes require review before collection because they
alter behavior after failures and concurrent launches. Successful-run payloads, ordering,
seeds, limits, warm-up scheduling, keep_alive, and timing boundaries are unchanged.
Source-hash guards prevent silently resuming collections made with older runner code.

## Unresolved methodology and residency decisions

The benchmark still proposes keep_alive=10m; development used 30s and waited for empty
residency. Multiple models may remain resident under the benchmark policy. No automatic
unloading, waiting, new GPU sampler, or keep_alive change is introduced here. A response
model check cannot detect another concurrently loaded model or CPU offload.

Before freeze, explicitly review one-model residency versus retained-model operation,
transition policy, cold/warm latency interpretation, external monitoring, server
parallelism, and isolation enforcement. Any implementation changing those conditions,
request ordering, or measured performance needs a reviewed methodology/configuration
revision and matching capacity evidence. The current collector cannot independently
guarantee GPU residency or detect all shared-GPU interference.

Choose repetitions (three provisionally), baseline thinking (false proposed), context and
output limits, timeout, failure accounting, and scope of repeatability claims before
freeze. Temperature zero and seed 42 do not guarantee deterministic output across runtime
or hardware changes. Use non-evaluation synthetic inputs for all capacity development.

## Offline validation

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s evaluation/tests -v
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests evaluation/tests -q
PYTHONDONTWRITEBYTECODE=1 python3 -m evaluation.validate
```

Use a Python environment containing development dependencies for pytest. These scopes
exclude service-backed integration tests and historical root scripts. Regression fixtures
use disposable copies of Phase 2 artifacts, fake transports, and blocked network/GPU calls.
Synthetic capacity attestations in tests are wiring fixtures, never real capacity evidence.

## Capacity-framework follow-up

CAPACITY_TESTING.md supersedes the hash-only capacity attachment description above:
empirical verification now checks capacity-report-v1 substantively, including recounting,
responses, telemetry, completion and integrity. The original thinking pathway/index remains
unchanged. Capacity execution requires an explicit reviewed no-truncation/no-shifting profile
and an available calibrated CPU vocabulary backend. The current census reports counts
unavailable, so real preparation/execution remains blocked without guessing. No capacity
flag, frozen protocol, benchmark option, or historical artifact is changed by this work.
