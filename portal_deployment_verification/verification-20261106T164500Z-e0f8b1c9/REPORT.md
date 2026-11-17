# Portal post-deployment verification

Status: SUCCESS. Automated read-only/non-destructive scope only; authenticated browser acceptance remains pending.

Release: portal-security-v1-b893d3a5f7c1

Port8001: active PID1565020, expected16 operations, prepared source hashes and original authentication DB path verified. Port8002: unchanged PID2019096,16 operations and matching API fingerprint.

Checks passed: 31; failed: 0. See acceptance.json for exact cases. Password sentinel values, cookie/session tokens and raw journal messages were not recorded.

Pending:

- Owner performs normal login/session/logout through actual browser/SSH forward
- Authenticated missing/invalid CSRF must return403 and preserve session
- Researcher administrator access must return403; authorized administrator read access must work
- Owner-scoped read/list behavior with explicitly designated authorized test resources; no job mutations

No restart, configuration/database/account change, live job action, GPU workload or inference was performed. Read-only API calls naturally append access logs.

Verified at: 2026-11-06T23:45:03.424362+07:00 (Asia/Bangkok).

31 automated checks passed. This is SUCCESS for automated post-deployment verification, not final authenticated-user acceptance. Use a private browser profile and an approved existing account; do not send passwords, cookies or CSRF/session tokens to the assistant. Port8002 remains the functional fallback and shares the session database. No service or configuration changes were made by verification.
