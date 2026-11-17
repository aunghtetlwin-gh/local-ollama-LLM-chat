# NECTEC final deployment-readiness assessment

## Decision

**Compatibility gate passed. Deployment remains pending separate operator authorization and portal cutover decisions.** The reviewed fixes were applied only to isolated staging copies; no production source, environment, image, container, account or service was changed. Assessment time: 2026-11-05T00:44:23+07:00. The directory timestamp uses UTC; local Bangkok date is 5 November 2026.

## Portal runtime inventory and intended use

Port 8001 is slurm-portal.service (PID3148336), launched 8 October from /home/lailai/slurm-portal with that directory's .venv Python/Uvicorn. Port 8002 is a separate Uvicorn process (PID2019096), launched 28 October from the same directory. Neither command uses reload. They advertise the same API title/version 0.2.0, which is insufficient to identify the loaded implementation.

Read-only OpenAPI capture found 10 operations on 8001 and 16 on 8002. The newer instance adds: GET /admin/users, GET /auth/me, PATCH /admin/users/{username}/status, POST /admin/users, POST /auth/login, POST /auth/logout. Its common private job/cluster operations advertise session-cookie parameters; mutation paths additionally advertise the portal CSRF header. The legacy document lacks those parameters and authentication/admin routes. Request schemas common to both, including JobRequest, match; only LoginRequest, CreateResearcherRequest and UpdateResearcherStatusRequest are additional. portal_route_comparison.csv records every operation and parameter difference.

Both documents advertise potentially sensitive job submission, cancellation, requeue and output retrieval. This inventory does not establish unauthorized execution: no private/job endpoint was probed, and absent OpenAPI authentication metadata is not itself proof of bypass. The exact in-memory 8001 source revision cannot be recovered through this nonintrusive review. The earliest recorded Git commits are from 21 October, later than its process start. Current on-disk files cannot be substituted for proof of its loaded code.

Operational intent is split. The installed systemd unit designates8001. The newer multi-user tests predominantly target8002, historical8002 logs contain2,881 HTTP request records, and note.coffee:36 documents `ssh -N -L 18002:127.0.0.1:8002 lai512`. Logs do not identify principals or distinguish researcher activity from tests; they support use history, not proof of current real-user activity or public ingress.

**Recommendation:** use the multi-user implementation currently represented by8002 as the functional baseline, and converge on one operator-managed canonical service. The minimal management option is to promote the reviewed current source plus fixes under the existing systemd service on port 8001, then deliberately migrate the documented SSH-forward target and retire8002 only after confirming its consumers. If preserving port8002 is required, the operator may instead approve a managed-service port change. Neither port choice nor retirement is performed here.

Restarting port 8001 activates current authentication, administrator/researcher rules, onboarding, ownership filtering and CSRF behavior accumulated since its legacy process started. It is therefore a broader application upgrade, not merely a reload of the three security findings. A simple source rollback would restore prepatch on-disk multi-user code, not necessarily recreate the unknown legacy in-memory implementation. Operator approval must explicitly cover this scope and rollback limitation.

## Cloudflare routing: resolved for the running connector

A safe read-only local metadata route was available despite the absent journal/config files. The cloudflared metrics listener's GET/config reports loaded configuration version1; GET/diag/tunnel identifies tunnel `9e2093df-2a57-4116-afc8-6b96cacc9f64` and connector `d58df686-5a7d-4849-bf5e-2f2ab734c15c` with4 connections. Cloudflared version: cloudflared version 2026.8.2 (built 2026-08-14-12:17 UTC). No connector token, API credential, cookie, private key or credential file content was read/printed.

The active rules are:

| Hostname | Service |
|---|---|
| ssh-lai512.aunghtetlwin.com | ssh://localhost:22 |
| Catch-all | http_status:404 |

**This connector publishes SSH only. It has no direct HTTP route to port 8000,8001 or8002.** Global and per-route httpHostHeader are empty, with no origin hostname override. The documented localhost SSH forward is consistent with web access through SSH rather than a public HTTP tunnel rule. No public browser hostname for portal/chat was verified. Other connectors, gateways or account-wide Access policies were not audited, so this does not prove global absence of exposure.

For authoritative dashboard confirmation, the authorized operator should open Cloudflare dashboard → Networking → Tunnels → select the tunnel UUID above → Routes → Published application (older Zero Trust UI: Networks → Connectors → tunnel → Published Application Routes/Public Hostnames). Inspect each hostname/path rule's **Service Type/URL**, **HTTP Host Header**, and relevant origin settings. It should show the SSH rule and404 fallback. If another public browser URL is actually used, inspect its own tunnel/route and corresponding Access application policy; do not add or change a route merely to complete this assessment. [Cloudflare routing documentation](https://developers.cloudflare.com/tunnel/concepts/routing/), [dashboard setup](https://developers.cloudflare.com/tunnel/get-started/).

## Production-compatible staging

Portal staging used a new Python 3.10.12 environment containing copies of all 24 installed portal package versions. Chat's main and forwarded-origin tests ran in NEW disposable containers from the deployed immutable image, using the same Python 3.10.21 and all 30 runtime package versions. Containers had network=none, read-only filesystem/source mounts, no GPU devices, dropped capabilities and no production environment/database mount. Only temporary memory/files and new test-output storage were writable. Production images were neither rebuilt nor modified.

Test-only pytest/httpx support packages were copied offline into separate staging locations; existing runtime versions were not replaced. No network download/pip upgrade was used. The exact reviewed patches were applied to staging base copies, and edited hashes match the sealed remediation package.

| Suite | Passed | Failed/errors/skipped |
|---|---:|---:|
| Portal |108|0/0/0|
| Chat authentication/ownership/origin |77|0/0/0|
| Local-forward Host/Origin compatibility |2|0/0/0|
| Additional disposable PostgreSQL isolation |11|0/0/0|
| Total |198|0/0/0|

All suite processes exited0. Exact commands, runtime assertions, raw output and JUnit are preserved. The PostgreSQL supplement used all deployed chat client-package versions on host Python 3.10.12 with a new private PostgreSQL14 cluster; its interpreter patch level differs from production. The 79 main chat/forwarding cases used the exact production Python 3.10.21 inside the deployed image. These scopes must remain distinct. Deprecation warnings concern TestClient/httpx and AnyIO compatibility; no assertion failed. Browser automation, real SSH connectivity, deployed account logins and live Slurm authorization were not tested.

Installed versions now exercised include FastAPI0.141.1/Pydantic2.13.5 on both systems, Starlette1.7.0/Uvicorn0.54.0 for portal and Starlette1.6.0/Uvicorn0.53.0/psycopg3.3.5 for chat. These differ from prior remediation tests with FastAPI0.162.0/Pydantic2.14.2. Portal metadata describes installed packages that a restart will load; it cannot prove versions already imported by the old in-memory process.

## Compatibility, sessions and remaining risks

The existing approved identity set remains lailai/mangkud/apple; bootstrap restrictions remain narrower. No production accounts were queried or changed. Confirm actual researcher needs before cutover; additional names require explicit policy/Linux/Slurm approval. No database migration or session-schema change is needed. Persisted sessions should survive if database locations, cookie names, hostname and settings remain stable, but this was not tested with live sessions.

Chat mutations without a matching Origin or Referer now return403, including headerless scripts. In-memory checks confirmed registration/session/logout for localhost:18000 and127.0.0.1:18000, with hostile Origin denied. They simulate the documented forwarding shape, not a real browser or SSH session. Cookie hostnames remain significant; ports do not provide browser-cookie isolation. If a public HTTPS proxy is introduced or discovered, verify its Host/scheme handling and trusted forwarding rather than trusting arbitrary X-Forwarded-Host. [Uvicorn settings](https://uvicorn.dev/settings/).

Chat's container has no source bind mount; changing host server.py cannot update its running code. Its selected deployed settings are SESSION_COOKIE_SECURE=false and TTL86400. Portal Secure defaults false in source; process initial environment does not establish every effective runtime setting. Changing cookie/TLS policy is a separately reviewed deployment choice. This task does not alter filesystem/GPU/MPS permissions, rate limiting, production DB privileges or other audit findings.

## Minimal deployment sequence — NOT EXECUTED

1. Obtain explicit approval for the canonical portal port, broader legacy port 8001 upgrade or retirement, client-forward changes, affected instance restarts, maintenance window and any production test-user/session writes. Confirm whether users actually use another browser gateway.
2. Recheck original-source hashes and patch dry runs; back up the four source files and launch configuration privately. Retain the chat image ID and a rollback tag. Preserve existing DB locations/volume/environment; no migration or routine database restore is required.
3. Drain active streams and portal mutations; wait for uncertain submissions to resolve without automatic retry. An empty connection/queue snapshot is not proof of absent sessions or exclusive use.
4. Apply portal app.py/auth.py/slurm_identity.py and chat server.py only after approval. Do not copy staging databases, test tools, reports or entire source trees into production.
5. Restart the operator-selected portal instances using their verified launch method. Managed8001 uses systemctl restart slurm-portal.service; standalone port 8002 needs an approved PID-verified procedure. Avoid broad process-kill commands. Keep the documented researcher path available until migration is confirmed.
6. Prepare a uniquely tagged chat candidate from the retained deployed image plus patched server.py, preserving the now-tested dependency set. Recreate only Compose service app with an approved image override and --no-deps --no-build. Keep the DB container/volume unchanged. No production build/recreate/restart was performed here.
7. Run the focused verification checklist, record evidence and monitor. Retire an extra portal instance only with explicit approval and confirmed consumer migration.

See DEPLOYMENT_CHECKLIST.md and ROLLBACK_CHECKLIST.md. Downtime is not measured; budget a maintenance window. API requests/streams can be interrupted; existing Slurm jobs should continue because scheduler daemons are untouched.

## Conclusion

The dependency compatibility gate is closed by 198 passing isolated cases, and this connector's SSH-only ingress is verified. Remaining deployment gates are operator selection/approval of the portal cutover and legacy upgrade, confirmation of actual client paths/settings, and separately authorized deployment/browser smoke tests. The fixes remain NOT DEPLOYED. All source and sealed evidence files are unchanged: 1727 protected files are byte-identical; one live access log appended only the read-only OpenAPI request, with its original prefix hash verified; the production chat container/image/start time and filesystem are unchanged, service PIDs are stable, and disposable test containers were removed.
