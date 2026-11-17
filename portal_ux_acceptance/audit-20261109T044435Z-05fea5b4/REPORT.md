# Final portal UX and historical-output investigation

**Assessment: expected output behavior; minor history-ordering/empty-state UX issues. No new security or output-path defect established.** The portal remains suitable for engineering acceptance with disclosed UX notes, unless strict descending Job ID is a mandatory acceptance requirement; in that case, close that small requirement through a separately approved change. This review does not declare all earlier pending authenticated CSRF/logout/role checks completed.

Read-only snapshot: 2026-11-09T04:44:35.832447+00:00. Both ports HTTP 200, 16 operations. Managed 8001 PID 2610502, active/running, Result=success, NRestarts=0, historical-output release `portal-output-20261108T132323Z-eb2dad35`. Deployed source hashes, frontend hash, exact nine-directory policy and original DB path match the reviewed configuration. The fallback PID 2019096/start ticks remain unchanged, as do original/fallback source hashes. No code, service, account, permission, DB or job changes occurred. Only this new audit package was written.

## A. Why history is ordered this way

Backend `app.py:1044` sorts `history` with `key=lambda job: job.get("submit_time") or ""`, `reverse=True`. `submit_time` is the ISO-formatted **submission** timestamp from accounting `time.submission` (`summarize_history_job`, near lines 764–766), via `datetime.fromtimestamp(...).isoformat()` (`format_timestamp`, lines 661–668). It does not sort by end time, start time or numerical Job ID.

Frontend `/home/lailai/slurm-portal/frontend.html:2557–2602` assigns `data.jobs` directly to `historyJobsCache`. `renderHistoryPage` takes an array slice before rendering (near 2694); no history sort overrides the backend. The keyed object is for details lookup, not row enumeration.

Slurm timestamps below are **UTC on 2026-11-04** (add seven hours for Asia/Bangkok). Raw `sacct` invocation and output are in `evidence.json`; submit/eligible/start/end/state are exported in `accounting-timestamps.csv`.

| Job | Submitted UTC | Started UTC | Ended UTC |
|---:|---|---|---|
| 123 | 08:23:32 | 08:23:32 | 08:24:13 |
| 124 | 08:24:16 | 08:24:16 | 08:24:59 |
| 125 | 08:24:16 | 08:24:16 | 08:24:59 |
| 126 | 08:25:02 | 08:25:02 | 08:25:42 |
| 127 | 08:25:44 | 08:25:45 | 08:26:27 |
| 128 | 08:25:44 | 08:25:45 | 08:26:27 |
| 129 | 08:26:30 | 08:26:30 | 08:27:11 |
| 130 | 08:27:14 | 08:27:14 | 08:27:57 |
| 131 | 08:27:14 | 08:27:14 | 08:27:57 |

Ties occur for 124/125, 127/128 and 130/131. Python's stable sort preserves the accounting response order within equal submission timestamps. No numeric tie-breaker is defined. The reported `130,131,129,127,128,126,124,125,123` is valid descending submission-time ordering. We verified it against the recorded timestamps without fetching authenticated history or assuming the CLI's row order equals the REST API's order.

**Smallest proposed change, not applied:** change the backend history sort key to a validated numeric `job_id` with `reverse=True`, before pagination, e.g. `key=lambda job: int(job["job_id"])` when the API's scalar Job ID invariant has been validated. Do not sort only the visible frontend page or sort IDs lexicographically. Preserve owner filtering and all other behavior. Regression cases should cover same-second timestamps, numeric rather than string ordering, and pagination retaining the backend order. Changing to a timestamp-plus-ID tuple is an alternative if the requirement remains chronology-first, but does not strictly implement global numeric-ID ordering. Existing route uses scalar integer job IDs; arrays/heterogeneous identifiers need explicit handling if later supported.

## B. Authorized researcher output observations

No real stdout file was opened, hashed or read; no authenticated output request was made. Files were inspected using `lstat` and directory metadata only. Browser observations are operator-reported; journal entries corroborate HTTP status but do not identify the authenticated account.

| Job | Accounting | Stdout metadata | Observed HTTP | Assessment |
|---:|---|---|---|---|
| 112 | mangkud; COMPLETED; 121 s | `/tmp/slurm-112.out`; regular, UID/GID 1001, mode 0644, nlink 1, **41 bytes** | 200 | Expected successful nonempty output; content not independently inspected. |
| 114 | mangkud; CANCELLED by 1001; no recorded start; 0 s | `/tmp/slurm-114.out` **absent** | 404 | Expected unavailable output, consistent with cancellation before execution. No evidence of a path-resolution defect or authorization failure. |
| 115 | mangkud; COMPLETED; 120 s | `/tmp/slurm-115.out`; regular, UID/GID 1001, mode 0644, nlink 1, **0 bytes** | 200 | Successful empty stdout; blank UI is expected rendering of an empty response, not request failure. |

All three accounting records specify `StdOut=slurm-%j.out`, `WorkDir=/tmp`. The deployed resolver permits their exact standard paths through the intentional legacy exception; no directory allowlist expansion is needed. For existing files UID 1001 matches `mangkud`'s Linux UID. `/tmp` is root-owned sticky mode 01777, not a symlink. File metadata is compatible with the endpoint's regular-file, ownership, link-count and size checks. The missing job 114 file cannot establish whether it never existed or was later removed; cancellation/no start makes noncreation plausible, not proven history.

Frontend `showOutput` near lines 3478–3529 sets `textContent = data.output` whenever `data.output !== undefined`. An empty string therefore clears the panel. Together, job 115's HTTP 200, current zero-byte metadata, endpoint implementation and reported blank panel establish expected successful-empty behavior; raw response bodies were deliberately not captured. The frontend otherwise displays JSON `detail`, explaining job 114's message. It does not explicitly check `response.ok` in this function, a possible clarity improvement rather than an observed access-control bypass.

Distinctions:

- Missing file: job 114's permitted target is absent, with matching observed 404. No permission widening or file recreation is warranted.
- Unsupported/out-of-policy path: not present for these three jobs; all resolve to approved exact standard paths.
- Ownership denial: existing owner-first guard returns concealed `Job not found` for foreign jobs; no admin bypass. These browser observations do not show such a denial. Prior sealed ownership fixtures remain the enforcement evidence; no foreign-output request was made here.
- Filesystem denial can also yield generic `Job output not found`; a 404 body alone is insufficient diagnosis. Current metadata provides the missing-file explanation for 114.
- Genuine server/application error: none established by these outcomes; observed 200/404 statuses match defined behavior. This audit reviewed relevant request-status metadata, not a new comprehensive error-log scan.

## C. Minimal follow-up and acceptance

No additional backend output-path remediation is warranted for jobs 112/114/115. Do not create missing files, change accounting, relax UID/symlink checks or widen the allowlist.

Two small optional UX changes can be separately approved:

1. Numeric descending Job ID ordering in the backend, if that is the agreed history contract. Current chronology-first behavior is explainable, but differs from the operator's stated preference.
2. Show an explicit **“No stdout content is recorded for this job.”** only after a successful response containing an empty string; retain safe `textContent` rendering and distinguish unsuccessful HTTP responses. For cancelled/no-start jobs, describe missing output as potentially never created; do not claim every 404 is benign cancellation or deletion.

These do not require changes to the underlying security policy. The successful authorized researcher output observation supplies useful live owner-workflow evidence, but does not by itself close all earlier pending authenticated session/CSRF/role checks or specifically establish custom-path browser success for 127/129. Retain those earlier outstanding checks unless separately recorded as completed.

## Evidence and preservation

`evidence.json`: exact read-only accounting command, UTC timestamps, selected host/process metadata, source hashes, stdout `lstat` metadata, and journal path/status timestamps only. `accounting-timestamps.csv`: clean timestamp table. `validation.json`: offline consistency/source/policy/fallback checks. `investigate_readonly.py`: command source. `FILES_SHA256.json`: package seal. Original evidence/deployed files remain unchanged. No private output contents or real credentials are included.
