# Development inference probes (separate approval required)

Implemented by `evaluation.dev_inference`. Nothing runs at import time. This tool does
not freeze the protocol, approve capacity, score datasets, execute
model code, access PostgreSQL, pull models, unload models, or restart services.

After explicit session approval for real development inference, from the project root:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m evaluation.dev_inference \
  --config evaluation/configs/quality_v2.draft.json \
  --output-root evaluation_dev_runs \
  --development-only --allow-inference
```

Both flags are required before any service access. They are operator acknowledgments,
not an external approval service. Reserve an exclusive GPU window and verify no other
clients will issue requests. A lock prevents simultaneous harness processes using the
same output root; it cannot exclude other clients or harnesses using different roots.
Do not run original benchmark scripts or the frozen benchmark collector for this check.

The tool requires an empty initial `/api/ps`. It captures `/api/version`, `/api/tags`,
and full `/api/show` metadata (including templates, parameters, and digests).
It runs Qwen 1.7B, Qwen 8B, then Gemma 12B, sequentially. For each model:

1. A: `Compute 17 × 19. Return only {"answer":323}.`, think=false, num_predict=4096.
2. B: same prompt, think=true, num_predict=4096.
3. C: `Write the integers from 1 through 1000, separated by spaces.`, think=false,
   num_predict=1.

Other options and system text are copied from the supplied draft, including context
8192, temperature 0, seed 42, top_k 40, top_p 0.9, and repetition controls. Requests are
non-streaming. Development keep_alive is explicitly overridden to 30 seconds. There
are at most nine requests, no warm-ups and no retries. After each model, including the
last, the tool polls for an empty `/api/ps` for up to 120 seconds. It never unloads anything.

A/B must return done=true, stop, final JSON equal to {"answer":323}, no tool calls,
and the expected presence/absence of nonempty thinking. C must report length truncation.
These are diagnostic expectations. Non-format contract and infrastructure failures stop
the sequence. A safely completed JSON-syntax failure may continue as described below;
no failure proves a model cannot support a feature on another prompt.

Final-answer text is distinct from the JSON HTTP envelope. If a model adds prose or
Markdown around the required JSON, the harness records `ResponseValidationError` with
code `invalid_final_json` and phase `response_validation`, preserving the entire answer.
It does not extract an embedded object or relax the JSON-only requirement. A completed
HTTP response may therefore have summary status `completed` while the probe fails;
consult output_format.json, result.json, and error.json for validation outcome. Error records separately state
whether a response was received and whether server completion remains unconfirmed.
Only a confirmed, otherwise valid A/B response with `ResponseValidationError` /
`invalid_final_json` may continue. Completion, model identity, thinking behavior, message
structure, and monitoring must already have passed. The failed request is never retried.
Transport errors, timeouts, OOM/error envelopes, malformed HTTP or assistant messages,
unconfirmed completion, monitoring failure, foreign model residency, and other contract
failures stop further requests. No JSON is extracted from prose.

Each attempt records output-format compliance separately: `passed`, `failed`,
`not_applicable` (C), or `not_evaluated`. `result.json` separates request completion from
probe outcome. `complete.json` means all nine probes finished, not that all passed;
inspect `output_format_failures` and `all_probes_passed`. The preserved Phase 2 run
completed nine requests with eight passing probes and one format failure. A stopped
sequence has `stopped.json`; a continued format failure has per-probe `error.json`.
The development JSON checker is a whole-text parser plus expected-answer comparison;
the benchmark scorer additionally rejects duplicate keys and enforces typed equality.

Before, during, and after requests, monitoring saves GPU CSV and `/api/ps` snapshots.
The loop targets 0.5-second intervals, but command/API latency adds to this interval;
peaks may be missed. nvidia-smi is read-only and has a five-second timeout, as does ps.
Initial monitoring failure prevents inference; a later monitoring failure stops further
requests once the current request returns. Generation itself uses the draft's 600-second
timeout. Sampling uses a background thread; model requests never run concurrently.

Each unique dev directory contains a manifest, metadata, initial ps, per-request payload,
raw parsed response, summary with thinking/completion/token/duration fields, timestamped
monitoring samples, expiration records, and either complete.json or stopped.json.
Errors and KeyboardInterrupt are saved, with request timing, when writable storage remains
available. Responses use the existing bounded transport: malformed JSON and HTTP failures
are retained as body envelopes; oversized responses retain a marked bounded prefix.
All artifacts use exclusive creation. Historical outputs are never reused. There is no
resume command; re-running creates new evidence and may repeat requests.

On error, timeout, or interruption, do not immediately retry: client exit does not prove
server generation stopped. Inspect service status separately before any newly approved
run. SIGKILL, power loss, or storage failure can leave a partial artifact; absence of
complete.json means the run is not complete. Saved requests identify pending work.

This checks basic compatibility and observed memory, not occupied 8192-token context,
sustained 4096-token output, exact VRAM requirements, full GPU offload guarantees, model
quality, determinism, or capacity certification. Record CPU/RAM, server settings and
concurrent workloads separately before any later capacity verification or protocol freeze.
The main draft configuration remains unchanged. Saved evidence can now be indexed by
the offline, versioned empirical thinking validator described in PHASE3_READINESS.md.
This provides a reviewed alternative to advertised thinking metadata, while preserving
the metadata pathway, named reviewer, digest/options checks, and separate capacity gate.

Offline validation only:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s evaluation/tests -v
PYTHONDONTWRITEBYTECODE=1 python3 -m evaluation.validate
```

Current collectors also take the shared `evaluation_execution/` advisory lock described
in CAPACITY_TESTING.md. A capacity PENDING/BLOCKED state prevents new development service
access until separately reviewed recovery. This does not broaden the development flags,
change its prompts/options, or automatically clear uncertainty from earlier requests.
