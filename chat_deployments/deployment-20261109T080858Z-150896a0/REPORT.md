# Project 2 controlled Origin/Referer security deployment

**SUCCESS — app-only deployment and automated verification completed. Authenticated browser acceptance remains pending.**

## Time and authorization

Explicit operator authorization covered 9 November 2026 **15:00–15:30 Asia/Bangkok**, with affected users/automated clients confirmed finished. The window was live at preflight and checked again immediately before activation. Activation began **15:11:34 Asia/Bangkok** (2026-11-09T08:11:34.140377+00:00); final automated verification completed **15:14:00 Asia/Bangkok** (2026-11-09T08:14:00.819848+00:00). No activity resumed in the pre-activation connection/log checks. Sixteen technical preflight checks passed, including current runtime/files/dependencies and matching resolved environment.

## Exact deployed change

Only Compose service **app** in project **ollama-test** was recreated, using the existing reviewed candidate override and `up -d --no-deps --no-build --pull never --force-recreate app`. Exact argv/output are in `activation-command.json`/`activation.log`; exit code 0. No alternate Compose procedure, image rebuild, dependency install, migration, database operation or Ollama/model action occurred.

- Old app container: `a6526b0cbd1401c78416747f93a1f4e174e5e790b319a38cf1bb1653113aead6`.
- New app container: `dbbb685f46aa0161f63023409b390421e50137d4cfa8292c7b4904528e6b8bd1`.
- Old/rollback image: `sha256:fb589d346de905895e8b3746a98735fd0001958899684a2223692977e866ddae`.
- Active candidate image: **`sha256:7f6a70da03c092c12a2fa2b3c50e1765efd95f44cb99aba6cb839bdc77eb006d`**.
- Active tag: `local-ollama-chat:origin-20261109T060037Z-4f0fba1d`.
- Patched `/app/server.py` SHA-256: **`3e8993bbbc0c0fea98224d568f5a4bd27704e5908b9e04723948484f0502bccc`**.

All candidate code/UI/SQL hashes and exact Python/package versions match the tested manifest. The original model settings, frontend, authentication implementation, network mode and all app environment values remain identical to the prior running app. Session/cookie settings were not changed. Persisted session continuity is supported by unchanged DB/environment/cookie implementation but still needs an existing-user browser check.

## Post-deployment acceptance

**29/29 automated checks passed**, zero failed final checks. Health200, no-store responses, exact13 expected API operations and stable running container with no unexpected restarts. Startup complete; no error/traceback/critical markers found in the bounded new-container log review. Raw logs and real tokens were not retained.

No-cookie live checks verified missing/hostile/null/mismatched-port Origin403, matching Origin200, matching Referer fallback200, invalid Origin not rescued by good Referer403, hostile Referer403, anonymous protected reads401 and matching-origin anonymous chat401 **before inference**. Matching-origin malformed-login validation returned422 with no password sentinel disclosure. No real credentials or session cookies were used; matching logout without cookie does not delete stored sessions. No conversation content was read, created, deleted or changed by these checks.

The real deployed app accepted Host `127.0.0.1:18000` with matching Origin `http://127.0.0.1:18000`. This validates the SSH-forwarded HTTP shape; it is not a real SSH/browser interaction. Browser acceptance must still use the confirmed URL exactly. Headerless mutation scripts now receive403 unless they supply a matching source header; this was the reviewed compatibility change.

The first verifier run incorrectly used case-sensitive lookup after converting HTTP headers into a plain dict; this falsely flagged cache-header assertions despite correct HTTP statuses. All initial artifacts are retained in `verification-attempt-1/`. The verifier alone was corrected to normalize header names and the same checks passed. No runtime code change or rollback was needed for that instrumentation issue. See `verification-correction.json`; the initial results are not hidden or counted as passing checks.

## Preservation and rollback readiness

PostgreSQL container **3568ff1916f8eec35c6d6290b0d5471e12a5c5771a418ec07841004cf523d9cd**, its image, original start time and exact mounts remained unchanged; DB healthy. Named volume **ollama-test_postgres_data** remains attached. No DB queries/migration/schema/volume action was performed by deployment or smoke tests. This is identity/action preservation evidence, not an independent content audit of live data.

Existing portal process IDs **2610502 (8001)** and **2019096 (8002)** retained identical start ticks before/after. No portal API call, source/configuration change, restart or Slurm command was issued. GPU/MPS/Cloudflare were not touched. No LLM inference ran.

The retained rollback tag `local-ollama-chat:pre-origin-20261109T060037Z-4f0fba1d` still resolves to the prior image ID. **Private exact operational backups** were created before activation under `private/`: app/DB inspect metadata, resolved Compose configuration, original Compose file, environment file and both reviewed overrides. This directory contains secrets, is excluded from the public evidence seal, and MUST NOT be published or copied into research/public reports. No production environment file was edited. The public report exposes only selected non-secret metadata and booleans.

Use only the candidate's reviewed app-only rollback command if separately authorized. It recreates app with the old image and does not restore a stale DB snapshot or alter volumes. Rollback reintroduces the known Origin/CSRF weakness; it was not executed here. The prepared override must remain part of future operational commands, because a bare base Compose up could select the old base tag.

## Remaining manual browser acceptance

1. At **http://127.0.0.1:18000**, confirm an existing authorized user's session continuity or normal login, page loading and owner-scoped conversation list/view. No existing conversation deletion is needed.
2. Confirm normal logout and subsequent login. These are ordinary session writes to be performed by the operator; none were performed automatically.
3. If required, verify an authenticated bad-Origin logout request is denied without revoking the session, using an approved owner-controlled browser/API procedure. Do not test by mutating or deleting research conversations.
4. Confirm legitimate automated clients have adopted matching Origin/Referer headers. No inference is required to close security acceptance.

## Evidence

`preflight.json`/`live-runtime.json`; `deployment-state.json`; exact activation command/log; `activation-preservation.json`; deployed source/package hashes; final `result.json`, `smoke-checks.json`/CSV and startup-log summary; initial verifier-attempt records and correction. Script copies retain exact execution provenance and use temporary run pointers; they are not generic redeployment automation. **Do not rerun deployment scripts blindly.** Public files are SHA-256 sealed; private backups are deliberately excluded. Existing candidate, evaluations and prior deployment evidence remain unchanged.
