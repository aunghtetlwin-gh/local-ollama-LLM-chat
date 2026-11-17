# Application security remediation summary

## Status and scope

Implemented and tested in isolated source copies. **NOT DEPLOYED.** Original portal/chat source, user records, services and prior evidence remain unchanged. No live Slurm jobs, inference or GPU workloads ran. The only PostgreSQL process started/stopped was a new private disposable test cluster. No host, filesystem, NVIDIA MPS, Slurm, firewall or cookie deployment setting was changed.

## 1. Portal password validation disclosure

Changed portal/app.py and portal/auth.py. All portal request-validation errors now return HTTP 422 with a generic detail, without serializing validation inputs, request bodies or exception strings. Password fields in login and researcher-creation models use SecretStr; plaintext is unwrapped only at the verification/creation boundary. This also redacts model representations. A SecretStr field alone would not fix missing-field errors that include the whole request body, so the sanitized exception handler is required. No new credential or secret was introduced.

Tests assert that submitted password sentinels do not appear in malformed-login/admin-create responses or captured application logs; model representations are redacted; valid login and researcher creation still pass. The handler removes detailed field-level validation diagnostics across portal routes while preserving status 422. Deployment/proxy request-body logging is outside these application checks and must not record credentials.

## 2. Consistent researcher authorization policy

Changed portal/slurm_identity.py, portal/auth.py and portal/app.py. A shared is_allowed_slurm_user predicate uses the existing explicit approved identities (lailai, mangkud, apple). HTTP eligibility checking, direct researcher creation and credential issuance all enforce that base policy. Linux-account eligibility, nectec association validation, administrator restrictions and backend username selection remain in place. No dynamic arbitrary-user credential issuance or skip flag was introduced.

The bootstrap add_user CLI retains its original narrower identities (lailai and mangkud) and role restrictions, additionally honoring the common base policy; apple was not newly permitted to bootstrap an administrator. Researcher onboarding still creates role=user. Tests approve synthetic names only inside monkeypatch scopes and verify both approved real-name mappings and rejection before account creation/command execution for unapproved identities. All Linux/Slurm/token calls are mocked.

Existing approved identities and their credentials/session records require no migration. Existing unapproved records are not disabled or changed; their job credentials were already rejected by the old helper. New unsupported onboarding is now rejected early. If the laboratory needs another researcher, an operator must explicitly approve its identity and corresponding Linux/Slurm/sudo configuration; do not remove default-deny checks as a workaround. Production accounts were not enumerated or altered.

## 3. Chat request-origin protection

Changed chat/server.py only. Before authentication/DB work, all POST/PUT/PATCH/DELETE requests require a valid Origin exactly matching the ASGI request scheme, hostname and effective port. If Origin is absent, a matching Referer is accepted. A present but invalid/mismatched Origin is never rescued by Referer. Missing, null, malformed, duplicate and hostile origins fail with generic HTTP 403/no-store. Default HTTP/HTTPS ports and hostname case are canonicalized; port zero is rejected. The application does not trust X-Forwarded-Host to decide the expected origin.

The policy covers delete/logout plus login/register/chat, avoiding a neighboring unprotected mutation or login-CSRF path. Existing authentication, SQL ownership checks and role rules remain unchanged. No CSRF-token/session schema change or database migration is needed. Unsafe requests without origin evidence now return 403, potentially before an anonymous request's former 401/404 response; GET behavior is unchanged.

Same-origin browser fetch normally supplies Origin for these methods; Referer is a fallback. Headerless scripts/API clients must send a matching Origin (or valid Referer). This is a browser-origin defense, not authentication for clients that can set arbitrary headers, and does not defend same-origin XSS or stolen sessions. Deployments behind a TLS proxy must preserve the intended Host and configure trusted ASGI scheme forwarding correctly; blindly trusting arbitrary proxy headers is not an acceptable fix. No real-browser or proxy deployment test was performed.

## Regression evidence

Final application suites: **108 portal + 77 chat + 11 disposable PostgreSQL = 196 passed**, with zero failed/error/skipped application cases and exit code zero. Raw output, JUnit and exact commands are retained in raw/. Tests cover secure replacements for the audit characterizations, malformed-password redaction/log checks, approved/unapproved identity consistency, bootstrap compatibility, hostile/missing/duplicate Origin, scheme/port mismatches, matching Origin/Referer success, session lifecycle and two-user ownership. Existing chat tests were adapted only to send the required legitimate Origin header. PostgreSQL used real copied migration SQL and synthetic accounts; Ollama was mocked.

A deliberately failing, separately selected harness self-check returned exit code 1. It proves failure propagation and is not an application regression or counted among the 196 passing cases. An earlier portal attempt with 106 passes is retained but superseded after the bootstrap compatibility refinement, and is not double-counted. A TestClient/httpx dependency deprecation warning remains; deployed dependency equivalence is unverified. The unchanged portal database-outage characterization still records generic 500 denial, outside the requested three fixes.

## Changed files and review artifacts

Runtime files: portal/app.py, portal/auth.py, portal/slurm_identity.py, chat/server.py. Patches are in patches/portal-application.patch and patches/chat-application.patch. Both pass read-only git apply --check against the current original files; no patch was applied. Exact original/remediated hashes are in reports/changed_application_files.csv/json. Test-adapter changes are separate in patches/chat-test-adapters.patch; packet-local tests are in tests/. Source inventory, environment versions, raw logs and preservation checks are included.

## Operator decisions before deployment

1. Review the four runtime-file diffs and verify original hashes still match before integration; preserve unrelated Git edits. Select an integration branch/change window rather than copying the whole isolated test tree into a running deployment.
2. Confirm the approved researcher identity list and corresponding Linux/Slurm/sudo privileges. No automatic account migration or permission grant is proposed.
3. Confirm actual public TLS/tunnel access, trusted proxy Host/scheme handling and Secure cookie settings. Verify same-origin browser login, chat, deletion and logout plus a denied cross-origin request in staging. Update legitimate headerless clients deliberately.
4. Review test/deployment dependency versions. Deploy/restart only after separate approval. Existing services still contain the original weaknesses until a reviewed deployment occurs.

## Residual risks

This work does not remediate world-readable job outputs, GPU-device access controls, MPS socket permissions, production database privileges/RLS/backups, rate limiting, XSS, session races, or generic portal auth-DB outage handling. It is focused application remediation, not penetration testing or comprehensive security certification. Source-level password redaction cannot constrain independent reverse-proxy/debug body logging. Browser/proxy behavior and real Slurm trust boundaries remain separate deployment checks.
