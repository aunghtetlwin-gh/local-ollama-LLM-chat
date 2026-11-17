# Historical-output post-deployment verification

**FAILED for the requested historical-output deployment. The existing portal itself is healthy.**

Verified at 2026-11-09T03:56:45.722026+00:00 (2026-11-09 10:56 Asia/Bangkok). Read-only scope; no service/config/account/database record changes or real output reads.

## Observed deployment discrepancy

- Expected version: `portal-output-20261108T132323Z-eb2dad35`.
- Actual 8001: `portal-security-v1-b893d3a5f7c1`, PID **1565020**, working directory `/home/lailai/nectec-changes/portal-security-20261106T125653Z-30beac16/portal-release`. Same PID and release as before the attempted update.
- Expected release directory `/home/lailai/nectec-changes/portal-output-20261108T132323Z-eb2dad35/portal-release` is absent at verification.
- Running source hashes do not match the historical-output candidate; `job_output.py` is absent from the actual release. The previous source/base hash checks still pass.
- Effective drop-in bytes remain different from the proposed candidate drop-in. The process environment has the original DB path but **no `PORTAL_OUTPUT_ROOTS`**. The nine-directory policy is therefore NOT active.
- Expected private backup directory is absent. No claim is made that the manual commands succeeded or why they did not affect this observed service; possible terminal/host/command differences require operator investigation rather than assumption.

## Healthy controls verified

- 8001 active/running, normal localhost binding, daemon reload state clean, stable PID, 16 exact expected API operations.
- Safe anonymous GETs to auth, administrator, job listing/history/detail/output and node routes return 401; a synthetic invalid session is rejected. No authenticated job query or output is retrieved.
- Malformed login bodies return redacted 422 responses without echoing the synthetic password sentinel. No valid login/session creation occurred.
- OpenAPI session/CSRF parameter metadata remains present on all six relevant mutation routes. No job mutation request was sent. This metadata is not a fresh authenticated CSRF/role enforcement test.
- 8002 HTTP 200 with 16 operations and API equal to the earlier baseline; PID, arguments, working directory, start ticks and original source hashes unchanged.
- Journal review: startup complete observed; **0 error-marker categories**, sentinel not seen in reviewed current-PID logs. Raw journal messages/cookies were not retained. See `evidence/startup-log-review.json` for counts and limitations.

## Output and fixture evidence

The sealed candidate and its existing 190-test evidence still verify. Nine real stdout paths were inspected using metadata only; no real contents opened. The deployed-helper path-resolution check was NOT executed because the new helper and policy are absent. The candidate's prior pure-policy and isolated owner/admin/UID/symlink/hardlink/size results do not establish production activation. Current output behavior remains that of the previous release and its historical path limitation.

Automated verification: **29 passing checks and 5 failed checks**, all five failures concern the missing candidate activation/policy, not a newly observed authentication outage. Initial interrupted verification record is preserved separately at `/home/lailai/ollama-test/portal_output_verification/verification-20261109T035604Z-b4e35b57`; the script encountered an absent expected source file, then a follow-up read-only run completed the broader assessment against the actual release. Neither attempt tried to repair or restart anything.

## Rollback and next acceptance

The previous authenticated release remains intact, hash verified and is currently serving 8001; no rollback is needed now. The candidate's expected private pre-deployment backup is absent, so backup completion cannot be asserted. Follow the reviewed deployment checklist in the correct authorized SSH terminal after resolving the discrepancy and confirming the maintenance window. Verification has not authorized or performed another deployment.

Only after actual activation: verify release/policy hashes again; owner `lailai` checks jobs 127/129 (expected empty output if files/accounting remain current); test existing administrator/researcher login, role controls and session/logout; approved authenticated CSRF denial; and authorized standard-output retrieval if available. Do not use another researcher's private output or mutate live jobs.

Evidence: `result.json`, `checks.json`, selected process/systemd/source/policy records and redacted startup-log summary under `evidence/`. Full raw responses, production cookies, credentials, DB contents and real job-output contents were not saved. HTTP verification naturally adds access-log entries.
