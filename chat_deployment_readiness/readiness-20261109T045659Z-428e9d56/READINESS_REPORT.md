# Ollama chat final deployment readiness

**CONDITIONAL GO — technically compatible app-only update; deployment/build not authorized or performed by this review.**

Snapshot: 2026-11-09T04:56:59.896382+00:00. Pending conditions: confirm the actual browser URL/forward and any non-browser clients; arrange a drained maintenance window; explicitly approve candidate image build, validation and app-only recreation. No known source/dependency drift blocks the reviewed patch. A protected, recent recovery backup should be confirmed according to operator policy, without rolling back or changing the database for this schema-free update.

## Current runtime and preservation

- Container `local-ollama-chat`, ID `a6526b0cbd1401c78416747f93a1f4e174e5e790b319a38cf1bb1653113aead6`, unchanged from prior tested evidence; running since 2026-09-16T02:21:35.009136395Z, zero restarts, no filesystem diff, no source/data bind mounts.
- Image **`sha256:fb589d346de905895e8b3746a98735fd0001958899684a2223692977e866ddae`**, tag `local-ollama-chat:1.0`, local RepoDigest `local-ollama-chat@sha256:fb589d346de905895e8b3746a98735fd0001958899684a2223692977e866ddae`. Config/image ID and repository digest are recorded separately in `inventory.json`; do not substitute a mutable tag for verification. The retained image is available locally but has not been assigned a new rollback tag by this review.
- Host networking, Uvicorn bound to **127.0.0.1:8000**; no Docker app port-publishing rule. `/health` and `/openapi.json` HTTP 200, **13 operations**. No Docker app healthcheck is defined. `/health` is a static application response, not proof of DB contents, migration state or Ollama readiness.
- PostgreSQL container `ollama-chat-db`, ID `3568ff1916f8eec35c6d6290b0d5471e12a5c5771a418ec07841004cf523d9cd`, running/healthy, zero restarts, image `sha256:156f0b253fd61366d5fc2107ad45955027d5612f695a8436ce20167f3fa79bff`. Loopback **5433 → 5432**. Persistent named volume **`ollama-test_postgres_data`** mounted at `/var/lib/postgresql/data`.
- Compose project `ollama-test`, file `/home/lailai/ollama-test/docker-compose.yml`, service `app`; image/dependency layout matches live settings. All **7 app** and **3 DB** Compose environment values match live values (compared in memory; credentials not saved). App selected settings: DB host 127.0.0.1, port 5433, cookie Secure=false, TTL 86400 seconds.
- Current container Python **3.10.21** and all 30 recorded runtime package versions match tested image evidence, including FastAPI 0.141.1, Starlette 1.6.0, Pydantic 2.13.5, Uvicorn 0.53.0 and psycopg 3.3.5. Host source/UI/SQL hashes match current image files. The image is still **pre-patch**: server.py `19f4c324aeea22333412dc3c58b4d158881e70859dfca159498ad3777a203967`. Reviewed patched server.py is `3e8993bbbc0c0fea98224d568f5a4bd27704e5908b9e04723948484f0502bccc`. Patch dry-run succeeds on unchanged workspace source; no source was edited.

## Reviewed patch and evidence

Only `/app/server.py` changes. Raw source, modified-file hash, patch diff, and test evidence are sealed in the existing remediation/readiness packages; both seals verify (61 and 79 indexed files). The patch canonicalizes HTTP(S) origins, compares scheme/hostname/effective port, rejects malformed/null/duplicate Origin values, and uses a matching Referer only when Origin is absent. Present invalid Origin cannot be rescued by Referer. It rejects mutation requests without a matching source before route handling and adds no-store responses. Authentication/session and conversation-owner authorization remain in force; Origin headers are not credentials.

The middleware covers **all POST/PUT/PATCH/DELETE**, including login, registration, chat, logout and deletion; it is broader than only delete/logout. Headerless scripts now receive 403 and must deliberately send a matching Origin/Referer. Foreign clients cannot gain access merely by supplying Origin; authentication and ownership are still required.

Recorded exact-image tests: **77 chat + 2 forwarded-origin cases**, zero failure/error/skip, exit 0; independent **11 disposable-PostgreSQL isolation cases** passed with production client packages on host Python 3.10.12 (different interpreter patch level). Main/forwarding cases used exact image Python 3.10.21. JUnit counts/exit records and seals were verified today; suites were not rerun and no new test or container was launched. They cover hostile/missing/duplicate/mismatched Origin, Referer fallback, same-origin workflows, sessions and two-user isolation. This is regression evidence, not browser automation or comprehensive penetration testing.

## SSH forwarding compatibility

Browser requests through a normal SSH TCP forward preserve the HTTP Host header, including the browser-facing port. With browser URL `http://127.0.0.1:18000`, both Host and Origin therefore identify 127.0.0.1:18000 even though the tunnel connects to backend 8000. The separate `http://localhost:18000` shape also passed recorded compatibility tests. Frontend fetches use relative URLs and same-origin credentials. Changing between localhost and 127.0.0.1 can change cookie scope and is not a harmless alias change for the origin check.

The exact current operator chat browser URL was requested but has not yet been confirmed. Compatibility is established for the saved shapes, not a newly exercised SSH/browser session. Other same-origin forwarded ports should follow the same comparison logic but need actual-browser acceptance. This review did not inspect a new public HTTP route; earlier tunnel evidence identified SSH-only routing, not direct web publication. No Cloudflare setting was changed or revalidated.

Keep current Host/scheme/cookie behavior for this patch. Secure=false is compatible with the current HTTP loopback browser URL; SSH encrypts the tunnel, not the local HTTP application itself. Do not claim general HTTPS deployment readiness from this. A reverse proxy that rewrites Host or terminates HTTPS without correctly trusted scheme handling needs separate review. The patch ignores X-Forwarded-Host; trusted-proxy/scheme configuration is a server/deployment responsibility. Do not switch Secure cookies or proxy trust automatically.

## Data/session preservation and limits

No schema, SQL migration, auth.py, database.py, cookie name (`ollama_session`), session hashing or TTL change is needed. PostgreSQL holds users, sessions and conversations independently of the app image. Recreating **only app with --no-deps --no-build** preserves the DB container, named volume, project name and environment. Cookie/session continuity is expected if existing hostname/settings and persisted DB remain unchanged; it is NOT proven by an authenticated live-session test here. No conversation rows, credentials, session tokens or DB contents were queried.

Do not run migrations, `compose down`, volume removal/pruning, DB recreation, package upgrades, or whole-project rebuilds. The existing Dockerfile has unpinned requirements and a pip-install layer, so rebuilding it from `python:3.10-slim` would violate this minimal compatibility scope. Derive from the retained local image and COPY only the reviewed server.py. Retain an explicit old-image rollback tag and record its immutable ID. A code rollback must not restore a stale data/session snapshot; it reintroduces the known CSRF weakness and requires a follow-up fix window.

## Smallest acceptance scope and remaining conditions

After separately approved image preparation, verify only server.py changed and every dependency/unmodified source hash remains equal. Drain active streams and coordinate users before app recreation; source inspection or an empty socket sample cannot prove an idle user has no pending stream. No GPU load or inference is needed for security acceptance.

After deployment: same health/API/image/hash checks, DB container/volume identity unchanged; missing/hostile Origin mutations rejected 403; matching-origin logout without cookie returns 200 without session DB writes; matching-origin chat without cookie returns 401 and cannot reach inference. Browser login/session/logout through the actual SSH URL is an operator check; any authenticated synthetic deletion requires explicit approval and a designated newly created disposable conversation. Never delete an existing research conversation merely for testing. Session mutation/browser checks are not performed by this read-only assessment.

Residual limitations: rate limiting/abuse controls, XSS, public registration policy, trusted proxy exposure and host-level isolation are not remediated here. Same-origin checks supplement authentication/ownership; they do not replace them. Volume attachment/DB health do not establish conversation integrity, backup restorability or current schema contents. All portal services, Slurm/GPU/Ollama runtimes, existing evidence and deployed code remain untouched.

## Artifact inventory

`inventory.json`: sanitized Docker/image/volume/health/source/version evidence. `compose-runtime-comparison.json`: resolved-config equality, with no credential values. `patch-test-validation.json`: exact hashes, dry-run and sealed JUnit counts. `DEPLOYMENT_ROLLBACK.md`: exact future app-only procedure. Existing sealed package paths are in the inventory. `FILES_SHA256.json` seals this new report. No rebuild/tag/container recreation, DB query or inference occurred.
