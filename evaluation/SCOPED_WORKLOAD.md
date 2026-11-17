# Fixed-workload readiness v1

This is a narrow alternative to full-capacity verification, implemented in
`workload_readiness.py` and the existing runner. No tokenizer, new inference engine, or
synthetic stress experiment is required for this path. No real approval, frozen protocol,
model request, GPU workload, or database operation was performed during implementation.
The preserved main draft and prior evidence are unchanged.

## Scope and evidence

`fixed-workload-readiness-v1` permits only the three existing models, explicit think=false,
one repetition, stream=false, keep_alive=30s, timeout=600s, and the complete proposed
options: num_ctx=8192, num_predict=4096, temperature=0, seed=42, top_k=40, top_p=0.9,
repeat_last_n=64, repeat_penalty=1.0. The scope pins all 20 internal and 50 GSM8K items;
ordinary subsets such as a six-request smoke test are allowed. Unknown items/suites are
rejected. Full collection is 70 × 3 × 1 = 210 scored requests, normally plus three
excluded warm-ups. The smoke selection below is six scored requests plus three warm-ups.

The verification file embeds a versioned binding with:

- Exact candidate settings, including system text, ordering seed and notes. Only freeze
  bookkeeping is excluded; the CLI-selected thinking value is explicitly bound.
- Full model/runtime snapshot, digests, templates/metadata, and Ollama version.
- Both dataset manifest byte hashes, complete manifests, question-file hashes, and the
  ordered public question IDs/prompt hashes. Reference hashes are pinned through manifests.
- Runner version and all evaluation Python source hashes.
- The fixed limitations below, which the reviewer must affirmatively acknowledge.

The existing empirical thinking index and its artifact hashes are revalidated, including
its otherwise valid completed JSON-format failure. Per-model digest, exact-option and
nonempty evidence-note checks remain enforced. The scope cannot replace empirical thinking
verification, and an invalid scoped record does not fall back to another path.

Offline preparation also runs dataset/reference/historical validation. Collection continues
to read only public questions/manifests, not reference contents. Offline scoring separately
rechecks actual reference-file hashes before exporting results; altered references cannot
produce accepted scoring output. No reference answers are inserted into requests.

The preparer produces a pending template with reviewer/date empty, acknowledgement false,
and every model's capacity_verified=false. Acceptance requires a nonblank human reviewer,
a timezone-aware verified_at, decision exactly "approved", acknowledgement exactly true,
and an unchanged binding/digest. Every model must still have capacity_verified=false on
this scoped path. A changed setting, dataset, source, snapshot, corrupted thinking artifact,
or missing approval fails closed. Source edits require preparing and reviewing a new file.

The full-capacity path is preserved: without a scoped record, its existing capacity flag,
notes/options/digest checks and empirical capacity-report validation remain mandatory.
There is no skip-verification flag. A reviewer name/decision is an auditable local record,
not cryptographic proof of human identity; independently retain the reviewed file/digest.

## Mandatory limitations

The binding includes these substantive limitations, not a claim of certified capacity:

- 8192 context and 4096 output are configured limits, not occupied-context or sustained
  output capacities established by stress testing.
- Readiness is limited to the pinned fixed workload, one repetition, and its subsets.
- Exact offline tokenization is not required. Runtime counts, malformed outputs,
  infrastructure failures, and truncations must remain visible. No success credit is
  given to truncated or malformed answers, and there are no automatic quality retries.
- Exclusive GPU/Ollama access is an operator prerequisite. Locks and residency samples
  cannot exclude all external clients or non-Ollama GPU jobs.
- Smoke answers must not guide tuning of a condition later presented as confirmatory;
  disclose exposure and label affected changes exploratory.

The scope does not change the benchmark API payload beyond the explicitly reviewed
candidate keep_alive/thinking settings. In particular, it does not silently introduce
truncate/shift controls. The 600-second setting remains the existing transport timeout,
not the separate capacity harness's independent wall-clock watchdog. Non-streaming wall
latency is not time to first token. Report the configured limits and observed outcomes.

## Residency and interruption behavior

Under the existing shared execution/output-root/run locks, the runner now:

1. Reads bounded /api/ps metadata and requires empty residency before the first warm-up.
   A single known planned model with the expected digest may expire naturally first.
2. At every active repetition/model block transition, waits until the previous model has
   expired. It never loads the next model while the previous one is still reported resident.
3. Before warm-ups and scored requests, checks that residency is empty or the permitted
   current model, as appropriate. A foreign model, wrong digest, overlapping models,
   malformed response, or metadata transport failure stops collection before another chat.
4. Waits for final model expiration after the last collected block.

Waiting has a 120-second polling budget and each metadata HTTP operation has at most a
five-second socket timeout; an in-progress metadata operation may add latency to that
budget. Only natural expiration is used. No stop/unload endpoint is invoked. A 30-second
keep_alive is proposed so ordinary expiration fits the polling budget; older 10-minute
conditions may time out safely rather than proceed with overlap.

Observations, including failing /api/ps envelopes/errors, are saved in exclusively created
session-*-residency-*.json files with phase/timestamp. Waits and checks occur outside scored
request timing. The original hash question order, model order, payload options and one
warm-up per active block remain unchanged. Resuming still preserves attempts and may add
warm-ups for newly active blocks as before.

This is a reviewed methodology change at block boundaries, not cold-start certification
or continuous GPU monitoring. It detects foreign residency at polling/request boundaries;
an in-flight synchronous request is not forcibly cancelled by a new external model. No
subsequent request is issued after detection. Same-model external clients cannot reliably
be detected, so reserve exclusive access. Existing transport/OOM/malformed/incomplete
response stops and explicit server-idle acknowledgement for uncertain resume remain.
Never resume merely because a timeout elapsed; inspect server termination separately.

## Remaining approved steps — commands NOT executed here

Run from `/home/lailai/ollama-test`. Choose a new directory; exclusive writes refuse reuse.

### 1. Create a separate one-repetition candidate (offline)

```sh
mkdir evaluation_preflight_scoped_01
PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'
from evaluation.common import BASE, read_json, write_new
config = read_json(BASE / 'configs/quality_v2.draft.json')
config.update(repetitions=1, think=False, keep_alive='30s',
    notes='Fixed 70-question quality workload; full context/output capacity not certified.')
write_new(BASE.parent / 'evaluation_preflight_scoped_01/candidate.json', config)
PY
```

The original draft is not edited.

### 2. After separate metadata-access approval, capture the installed identities

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m evaluation.runner inspect \
  --output evaluation_preflight_scoped_01/inspection.json --allow-ollama
```

This contacts Ollama but does not perform inference. It must match the preserved empirical
thinking evidence; changed runtime/model metadata needs separate compatibility review.

### 3. Prepare a pending scoped review file (offline)

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m evaluation.workload_readiness \
  --config evaluation_preflight_scoped_01/candidate.json \
  --inspection evaluation_preflight_scoped_01/inspection.json \
  --output evaluation_preflight_scoped_01/verification.json
```

A human must inspect settings, datasets, Phase 2 artifacts, residency policy and limitations.
Only after affirmative review, edit the NEW verification file: set reviewer to the actual
human's name, verified_at to an actual timezone-aware ISO timestamp, workload_readiness.decision
to "approved", and workload_readiness.limitations_acknowledged to true. Update evidence notes
as appropriate. Do not change the binding/hash or capacity flags to make a check pass.
Retain an archived copy/digest of the reviewed file. Nothing in preparation approves it.

### 4. After separate protocol approval, freeze the reviewed candidate (offline)

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m evaluation.runner freeze \
  --config evaluation_preflight_scoped_01/candidate.json \
  --inspection evaluation_preflight_scoped_01/inspection.json \
  --verification evaluation_preflight_scoped_01/verification.json \
  --think false --output evaluation_preflight_scoped_01/frozen.json
PYTHONDONTWRITEBYTECODE=1 python3 -m evaluation.runner plan \
  --config evaluation_preflight_scoped_01/frozen.json \
  --suite internal_v2 --suite gsm8k_50_v1
```

Expected full plan: 210 scored requests. Freeze remains blocked until real human review.
No frozen artifact was created during implementation; frozen objects in tests are fixtures.

### 5. After separate inference approval, reserve exclusive access and run the smoke test

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m evaluation.runner run \
  --config evaluation_preflight_scoped_01/frozen.json \
  --suite internal_v2 --question-id C03 --question-id I01 \
  --output-root evaluation_smoke_runs --allow-inference
```

This sends six scored requests plus three warm-ups. C03 exercises the longest internal
prompt/code-output handling; I01 exercises strict JSON. Judge infrastructure, artifact
preservation and scoring separately from model correctness. Do not retry wrong answers.
Score the printed run directory offline:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m evaluation.score_offline \
  --run-dir evaluation_smoke_runs/ACTUAL_RUN_ID \
  --output-dir evaluation_smoke_runs/ACTUAL_RUN_ID/analyses/review_01
```

After reviewing smoke results and separate full-collection approval, use the same frozen
condition with both suites and no question-id filter for 210 scored requests plus warm-ups.
The original three-repetition draft remains preserved as a different provisional design.
