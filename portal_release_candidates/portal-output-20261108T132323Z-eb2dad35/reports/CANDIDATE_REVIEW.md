# Final historical-output deployment candidate

**PASS for candidate preparation and offline validation. NOT DEPLOYED.**

Candidate `portal-output-20261108T132323Z-eb2dad35` is based on the currently running authenticated security release `portal-security-v1-b893d3a5f7c1`. Application code matches the sealed 190-test remediation exactly: changed `app.py`, new `job_output.py`, unchanged `auth.py` and `slurm_identity.py`. The prior remediation package seal verified all 30 listed files. Current original/deployed source hashes match its base; no application source or service was changed. API frontend remains an external existing dependency at `/home/lailai/slurm-portal/frontend.html`, whose expected hash is pinned in the manifest; it is not copied or modified.

## Directory policy review

The previous proposed common `jobs` parent was narrowed to **nine explicit per-job directories**, listed in `config/output-roots.json`. No common experiment parent, entire home, arbitrary `/tmp` directory or future job directory is authorized. Nine leaf directories are the smallest directory scopes covering all nine recorded MPS jobs; authorizing only the two error cases would leave the other seven recorded jobs unsupported.

Host metadata (not sandbox-mapped UID metadata) confirms `/` and `/home` root-owned mode 0755; `/home/lailai` UID/GID 1000 mode 0750; the experiment ancestry and each job leaf UID/GID 1000 mode 0775. No inspected directory is symlinked or world-writable. ACLs contain only ordinary owner/group/other entries, with no named or default grants. The write-enabled group `lailai` has no supplementary members and only `lailai` as a primary member. No permission or ACL was changed. Root and the service/application owner remain trusted writers; membership/permissions are point-in-time observations that must be checked again before deployment.

The leaf listings include stdout/stderr plus `identity.json`, `ready.json`, and `result.json`. This is therefore a narrowly approved **job-artifact directory boundary**, not an assertion that only stdout bytes exist there or that file contents were audited for secrets. The resolver still requires Slurm-selected stdout metadata and exact owner UID. The policy does not provide a directory browser or arbitrary client-selected file read. Operators must keep credentials/session databases out of these directories; code does not enforce a `.out` extension restriction.

| Job | Explicit leaf directory | Stdout bytes (metadata only) |
|---:|---|---:|
| 123 | `r1-baseline-job1` | 0 |
| 124 | `r1-concurrent-job1` | 0 |
| 125 | `r1-concurrent-job2` | 0 |
| 126 | `r2-baseline-job1` | 0 |
| 127 | `r2-concurrent-job1` | 0 |
| 128 | `r2-concurrent-job2` | 0 |
| 129 | `r3-baseline-job1` | 0 |
| 130 | `r3-concurrent-job1` | 0 |
| 131 | `r3-concurrent-job2` | 0 |

Only the stdout selected by an ownership-checked scheduler/accounting record can be returned. The endpoint does not separately browse stderr, result JSON or remote-node files. Empty stdout must return 200 with an empty string. Standard exact `/tmp/slurm-<authorized-jobid>.out` remains an intentional exception outside the custom directory roots. Other `/tmp` files are denied. Raw patterns support `%%`, `%j`, and numeric padding `%1j`–`%10j`; expanded fields are literal. Unsupported array/step/node/name patterns, symlink paths, hard links, files with wrong UID and outputs above 1 MiB are denied. The accounting retention lookup remains 90 days.

## Runtime and compatibility

The host snapshot shows managed 8001 PID 1565020 active/running, NRestarts=0, previous release working directory, and original authentication DB `/home/lailai/slurm-portal/portal_users.db`. Fallback PID 2019096 retains its prior start ticks. No service restart or fallback modification occurred. The current production virtualenv matches the recorded production package versions; all 190 tests ran against that matching isolated environment. No database migration, account change, new dependency, Slurm configuration change or UI code change is proposed.

`portal-release/` has mode 0555 and its four source files 0444. It is hash sealed and ready to copy, not kernel-immutable or independently signed: its owner/root can still change permissions. The future release path is `/home/lailai/nectec-changes/portal-output-20261108T132323Z-eb2dad35/portal-release`; that path has NOT been created or installed by this preparation.

## Validation evidence

- **190 passed, zero failures, zero skipped, exit 0**, including foreign researcher/admin denial before output filesystem access, safe standard/custom output, empty files, missing outputs, traversal, symlinks, hard links, wrong UID and limits. Existing test assertions are preserved; only the isolated test import path was adjusted for the candidate layout.
- The exact candidate policy additionally resolves **9/9** saved historical output paths and denies **7/7** out-of-policy paths. These pure resolution checks forbid output opens. File existence/type/UID/link count/size observations came from metadata only, not content reads.
- Candidate hashes, current base hashes, external frontend hash, proposed configuration hash, and source read-only modes verified. Full commands, environment assertions, stdout/stderr and JUnit XML retained under `raw/`.
- One known TestClient/httpx deprecation warning; no incomplete or failed attempt in this candidate test run.

This does not establish live authenticated output success. After separately authorized deployment, owner `lailai` must confirm jobs 127/129 (and another authorized existing standard-output job if available) in the browser. Do not read another user's private output or submit a job merely for acceptance.

## Decision and limitations

Candidate ready for operator review. Deployment still requires a maintenance window, explicit approval of these nine directories, current drift/permission checks, 8001-only restart authorization and post-deployment browser acceptance. The single service UID may not read another user's private filesystem; no chmod or authorization bypass is proposed. Local filesystem assumptions and the existing accounting retention window remain. Port 8002 stays on its current independent source/runtime as fallback. Rollback restores the immediately preceding known authenticated 8001 release and its original drop-in, not the unknown pre-authentication legacy runtime, and intentionally restores the old historical-output limitation.
