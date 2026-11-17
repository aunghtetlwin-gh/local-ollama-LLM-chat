# Synthetic capacity framework v1 — execution NOT approved

The benchmark draft is unchanged. No capacity approval, freeze, inference, GPU workload,
or database operation was performed by this implementation. Three repetitions remain
provisional: 70 × 3 × 3 = 630 scored benchmark requests; one repetition would mean 210.
Capacity testing uses nine different, synthetic development requests and no references.

## Token accounting and present limitation

`reports/token-census-v1.json` contains 210 rows (70 questions × three models), fully
constructed message hashes, model/template metadata identities, installed manifest/config
hashes, rendering method, and unavailable counts where no compatible backend exists.
Installed manifests match the saved Phase 2 digests. Saved A/B/C counts are listed separately;
they are not substitutes for benchmark prompt counts. No character-based token estimates
are used. The system Python inspected during implementation lacks llama-cpp-python and
other compatible tokenizer packages. **All 210 actual benchmark token counts are currently
unavailable. Capacity preparation and execution therefore fail closed.**

`token_accounting.CpuCounter` implements an optional vocabulary-only CPU path using the
installed GGUF and a compatible llama-cpp-python low-level API. It requests vocab_only,
n_gpu_layers=0, and never constructs a generation context or evaluates tensors. It neither
contacts Ollama nor downloads packages/models. No optional package was installed here.
The adapter supports only the exact saved 0.32.15 model metadata, two text messages, explicit
boolean thinking, and no tools/media or literal special-token spellings in input.

Rendering includes system/user delimiters, assistant prefixes, Qwen think/no_think control,
and Gemma's renderer-specific turn/channel delimiters and tokenizer-supplied BOS. A plain
Gemma `{{ .Prompt }}` template is not sufficient. The narrowed Python profiles follow the
pinned rendering paths and must match *all three* saved A/B/C prompt_eval_count observations
for each model. Any unavailable API, unsupported metadata, renderer/BOS difference, or count
mismatch marks that model unavailable, rather than treating an approximation as exact.
Package/native-library hashes, versions, calibration request/response hashes, rendered
text, token IDs, and count are retained when calibration succeeds. This optional backend
was not exercised against a real vocabulary in this implementation; its compatibility
must be checked in a reviewed CPU-only dependency window before any GPU execution.

Pinned source references for review:
- https://github.com/ollama/ollama/blob/v0.32.15/model/renderers/gemma4.go
- https://github.com/ollama/ollama/blob/v0.32.15/model/renderers/renderer.go
- https://github.com/ollama/ollama/blob/v0.32.15/server/prompt.go
- https://github.com/ollama/ollama/blob/v0.32.15/llm/llama_server.go

Generate a NEW census file offline after dependency review:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m evaluation.token_accounting \
  --output /tmp/NEW-token-census.json
```

The census includes only public dataset prompts. It does not generate evaluation answers.
Calibration to a few saved prompts is a compatibility check, not independent proof that
arbitrary templates or runtime versions are supported. The first synthetic request also
cross-checks local counts against the live server before either long request is sent.

## Test matrix and offline preparation

All requests use the draft's exact generation options, system message, stream=false,
explicit think=false, and development keep_alive=30s. No warm-ups or retries are added.
Model order is Qwen 1.7B, Qwen 8B, Gemma 12B; each runs S, I, IO sequentially.

| Test | Fully rendered input | Expected output | Acceptance |
|---|---|---|---|
| S | Short marker control | Whole JSON containing begin/middle/end codes | Exact retrieval; stop; <=128 generated tokens |
| I | 7936 ±32 tokens | Same whole JSON | Exact early/middle/end retrieval; stop; <=128 tokens |
| IO | 3840 ±32 tokens | First line marker JSON, then continuous neutral numbered output | Exact first-line retrieval; length; exactly 4096 generated tokens |

Marker values are deterministic SHA-256 prefixes bound to generator version/model/case.
Filler is numbered neutral synthetic prose; the early code is not repeated in the final
instruction. Offline binary search adjusts padding using the CPU tokenizer, never inference.
The same recipe targets comparable occupancy across different tokenizers; synthetic text
length may differ by model. No benchmark prompt or reference is used by the generator.

A missing marker is a retrieval failure, not by itself proof of truncation. Actual server
prompt_eval_count must equal the complete offline count. Combined input/output must fit
8192 without shifting. Early EOS on IO leaves capacity insufficient; it is not retried.
JSON format, observed disabled thinking, marker retention, and capacity findings are
separate. IO's JSON first-line parsing is its explicit test contract, not extraction from
surrounding prose. S/I use strict whole-text JSON without extraction.

Prepare only after exact counts are available:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m evaluation.capacity_inference prepare \
  --config evaluation/configs/quality_v2.draft.json \
  --metadata evaluation_dev_runs/dev-2026-11-03T071419.213574+0000-db8509361d9e/metadata.json \
  --output evaluation/capacity-plan-v1.json
```

This currently exits without a plan because the optional CPU prerequisite is unavailable.
The output is exclusively created. Preparation is offline and does not authorize inference.
The v1 profile covers only 8192/4096. Reduced limits require a new reviewed profile and
thinking verification under the changed options; the old thinking index is not rewritten.

## Explicit API/profile decision

Ollama 0.32.15 defines top-level `truncate` and `shift`; its omitted defaults permit input
truncation/context shifting. Capacity requests explicitly set both false. Review this
profile before use; the operator must supply its exact name on the execution command.
No keys are silently inserted into existing benchmark/development payloads, and no server
settings are changed. Capacity results describe this explicit profile, not a benchmark
running with different implicit truncation/residency behavior. Align or separately review
those benchmark policies before any freeze.

Pinned API definitions: https://github.com/ollama/ollama/blob/v0.32.15/api/types.go

## Proposed command — DO NOT RUN without separate approval

After a successfully prepared and reviewed plan, the exact proposed command is:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m evaluation.capacity_inference run \
  --plan evaluation/capacity-plan-v1.json \
  --output-root evaluation_capacity_runs \
  --development-only --allow-inference --exclusive-gpu \
  --accept-safety-profile ollama-0.32.15-no-truncate-no-shift-v1
```

All four acknowledgements are required before backend/service setup. They record operator
intent; they are not an external approval service. No run command was executed here.
A fabricated or edited plan is rejected by regenerating prompts and recounting tokens
before service access. The live metadata must exactly match the planned snapshot.

## Isolation, monitoring, deadlines, and interruption

A shared flock in `evaluation_execution/` coordinates current capacity, development, and
benchmark collectors regardless of their output roots. Old code, alternate coordination
paths, direct clients, and external GPU jobs cannot be excluded by this advisory lock.
An exclusive GPU/Ollama reservation remains necessary; a client using the same runner
cannot reliably be distinguished through residency/process samples.

Initial Ollama residency must be empty. Only the planned model/digest/context may appear.
Resident records must have positive size and equal size_vram. GPU identity/driver must
match this single-GPU profile. The proposed operational safety margin is >=2048 MiB free;
this is a conservative policy needing review, not an architectural memory guarantee.
All listed compute processes must be a single installed llama-server owned directly by
`/usr/local/bin/ollama serve`, verified through /proc. Unknown executables, ownership,
multiple compute processes, malformed data, or monitoring failures stop execution. A
different installation/process topology is unsupported and must be reviewed, not guessed.

GPU/process CSV and /api/ps samples have timestamps and preflight/inflight/final phases.
The target interval is 0.5s plus telemetry latency; peaks/interference between samples can
be missed. Each nvidia-smi and ps operation is bounded. No GPU compute workload is used
for monitoring. At each model transition the harness waits for natural expiry up to 120s,
checking model identity, and never unloads another user's model. keep_alive=10m is not used
by this capacity profile. Changing benchmark residency remains a methodology decision.

Each chat request runs in a spawned local HTTP process. The parent independently checks
a monotonic deadline and monitoring errors; a watchdog also bounds a blocked IPC receive.
Only that local worker is terminated on deadline/unsafe activity. This closes its client
connection but is NOT proof of server cancellation. No next request or automatic retry is
issued. The benchmark runner's original transport is otherwise unchanged.

A durable PENDING.json is saved under the shared coordination root before worker launch.
Confirmed successful response/final monitoring (or safely completed diagnostic rejection)
removes only that request's own pending record. Timeout, uncertain response, or unsafe
monitoring leaves PENDING/BLOCKED state, preventing later cooperating collectors from
contacting the service. SIGKILL/power loss can therefore leave a conservative block too.
There is intentionally no automatic clear/resume command. Separately inspect server and
GPU status and review a recovery procedure before clearing any uncertainty state. The
existing development collector now observes this shared capacity latch; its own historical
error policy and the benchmark's separate resume acknowledgement remain otherwise intact.

Artifacts use unique directories and exclusive creation. Missing responses or partial
bytes not delivered by the transport cannot be reconstructed. Oversized/malformed bodies
use the bounded existing transport envelopes. Storage failure can leave partial artifacts;
absence of complete.json is never treated as successful capacity evidence.

## Offline capacity evidence and review

After a later successful run, build a report OUTSIDE the immutable experiment:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m evaluation.capacity_evidence build \
  --run-dir evaluation_capacity_runs/ACTUAL_RUN_ID \
  --output /tmp/NEW-capacity-report.json
PYTHONDONTWRITEBYTECODE=1 python3 -m evaluation.capacity_evidence validate \
  --report /tmp/NEW-capacity-report.json \
  --config evaluation/configs/quality_v2.draft.json \
  --metadata evaluation_dev_runs/dev-2026-11-03T071419.213574+0000-db8509361d9e/metadata.json \
  --reviewer 'ACTUAL REVIEWER NAME'
```

`capacity-report-v1` hashes every experiment artifact and the validator/collector sources.
Validation regenerates synthetic requests, repeats CPU tokenization, checks actual runtime
counts/completion, marker retrieval, sustained output, timing, GPU/process identity,
positive full residency, monitoring coverage, initial empty state, and model expiration.
It rejects inconsistent saved findings even if their file hashes were recomputed. Reports
bind selected capacity-relevant configuration (models, system, options, stream, timeout)
and exact metadata; unrelated draft/frozen bookkeeping does not invalidate the evidence.
The report covers only think=false. Changing thinking mode cannot reuse this capacity claim.

Report generation and validation always leave capacity_verified=false. A named reviewer
is required for the acceptance check; even that check is not a capacity approval or freeze.
A later reviewed verification file may reference the complete report with path/byte hash
under capacity_evidence. The empirical thinking pathway now invokes this substantive
validator after hash checks; arbitrary hashed notes no longer satisfy that pathway. The
original advertised thinking pathway is preserved. Thinking compatibility, capacity
review, format compliance, and protocol approval remain distinct.

File hashes are not authenticated attestation against an operator who can rewrite both
observations and reports. Independently archive evidence/digests. Reviewer assessment of
exclusive access, server environment/parallelism, calibration validity, and benchmark
methodology applicability remains necessary.

## Offline checks

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s evaluation/tests -v
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests evaluation/tests -q
PYTHONDONTWRITEBYTECODE=1 python3 -m evaluation.validate
```

Use an environment with development dependencies for pytest. Tests use explicitly fake
counts, responses, telemetry and temporary artifacts; no test fixture certifies real
capacity. No service-backed integration tests or historical inference scripts are included.
