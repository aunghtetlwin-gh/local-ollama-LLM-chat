# Project 2 — tested Origin/Referer candidate image

**CONDITIONAL GO for a separately approved, drained app-only deployment. Candidate preparation and tests PASSED; production NOT changed.**

Confirmed browser URL: **http://127.0.0.1:18000**. This closes the earlier URL uncertainty. No Project 1/Slurm/portal/GPU work occurred.

## Image and code

- Candidate tag: `local-ollama-chat:origin-20261109T060037Z-4f0fba1d`
- Candidate Docker image ID: **`sha256:7f6a70da03c092c12a2fa2b3c50e1765efd95f44cb99aba6cb839bdc77eb006d`**
- Retained rollback tag: `local-ollama-chat:pre-origin-20261109T060037Z-4f0fba1d`
- Rollback/base Docker image ID: `sha256:fb589d346de905895e8b3746a98735fd0001958899684a2223692977e866ddae`
- Patched `/app/server.py` SHA-256: **`3e8993bbbc0c0fea98224d568f5a4bd27704e5908b9e04723948484f0502bccc`**

The live prepatch image/source/Python/packages matched the sealed readiness report before work. Dockerfile uses the retained local base and **only COPY server.py /app/server.py**, with no RUN or dependency installation. The isolated context contains only the Dockerfile and reviewed patch. Build used `--pull=false --network=none`; base layers remain identical plus one COPY layer. Environment, command, entrypoint, user, working directory, exposed-port metadata, volume/healthcheck metadata and stop signal remain unchanged. All inventoried unmodified code/UI/migration/requirements hashes match; Python 3.10.21 and every recorded runtime package version remain equal. The Docker image ID is recorded as returned by this engine; build output also records separate manifest/config digests.

The expected middleware patch is the only server source change; model names, Ollama URL/timeout, existing authentication, frontend and PostgreSQL integration are preserved. Original `local-ollama-chat:1.0` still resolves to the base image; it was not overwritten. Adding the rollback/candidate tags and building a local image does not activate either image.

## Tests

**77 chat regression + 2 forwarding cases = 79 passed**, zero failed/errors/skipped, process exit 0. Two existing dependency deprecation warnings (TestClient/httpx and AnyIO BlockingPortal alias) are retained in the log.

Tests run in a NEW disposable container from the actual candidate image ID, with network=none, read-only rootfs, no production credentials/data/DB/GPU mounts, no added capabilities, no-new-privileges, and a nonroot test user. Test-only pytest/httpx support is mounted read-only rather than installed into the image. SQLite is in-memory; PostgreSQL and Ollama calls are blocked/mocked. Query-capture migration tests do not apply migrations. Assertions pin all baseline runtime versions/files and explicitly confirm `server`, `auth`, `database`, `migrate` import from **candidate `/app`**, with no source bind mount shadowing them.

The 79 cases cover authentication, sessions, cross-user conversation ownership, blocked hostile/missing/duplicate Origin, Referer fallback, origin scheme/host/port differences, safe owned operations, mocked streaming and both forwarded browser-host forms. The actual confirmed 127.0.0.1:18000 origin passed alongside localhost:18000. These are in-memory HTTP compatibility tests, not a newly run real browser SSH login or real inference.

## Activity and client impact

Three samples at approximately 2026-11-09T06:08:29.254226+00:00 through 2026-11-09T06:08:31.276722+00:00 found **one established TCP connection** represented at both loopback endpoints (not two independent streams). The recent bounded log window contained successful GET `/auth/session` polling. It showed no POST/chat events in that collected slice, but access-log entries and idle sockets cannot conclusively identify streaming completion or all clients. A browser appears connected; **do not recreate app until its users confirm requests/streams are drained**.

Origin/Referer are not recorded in the access log, so active headerless mutation clients cannot be enumerated reliably from these records. A concrete compatibility issue exists in the current README example near line 262: its authenticated curl POST/chat has no Origin/Referer and will return403 after deployment. The old unadapted host test clients likewise omit required headers; the copied regression adapters send legitimate origins. No currently active headerless client was proven, and no README or client code was modified. Communicate before cutover: scripts must send an Origin matching the actual request scheme/Host/port; Origin does not replace authentication. Direct backend curl at 127.0.0.1:8000 uses that origin, while browser-forward requests use 127.0.0.1:18000. Keep the existing SSH Host/scheme behavior and cookie settings unchanged.

## Production preservation

Final check: 2026-11-09T06:10:40.027021+00:00. Production container ID/image/start time unchanged; HTTP /health200. DB container ID/image/start time and volume `ollama-test_postgres_data` unchanged; DB healthy. No database queries, conversation content access, login/session writes or production restarts occurred. The named volume was neither mounted into tests nor modified by this work. This is identity/action preservation evidence, not a byte-for-byte audit of a live database that users may independently access. Temporary candidate test containers were removed (zero remaining under the candidate label).

`config/compose.security.yml` and `config/compose.rollback.yml` were validated by resolved Compose comparison, without applying them. They change only app image and pull_policy=never; DB service, volumes and all other resolved service settings are identical. The inherited base build stanza remains but is disabled by `--no-build` in the prepared activation command.

## Deployment conditions and acceptance

Ready image; remaining operational gates: coordinate the connected browser/users; confirm no active/uncertain stream; notify/update any legitimate headerless clients; preserve private current launch configuration/environment; and obtain separate 8000 app-recreation authorization. Do not change Secure cookies, authentication, migration state, volume, project name, port/network, model configuration or dependency versions in this change.

After activation, verify exact image/source/runtime hashes, unchanged DB identity/volume, health and all 13 API operations; missing/hostile Origin denial; matching-origin no-cookie logout and no-cookie chat denial without inference. Operator confirms existing browser login/session/logout at 127.0.0.1:18000. Deletion tests require separately designated synthetic data, never existing research conversations. Persisted session continuity is expected but remains an operator check, not proven by these tests. No new LLM inference is needed.

See `DEPLOYMENT_ROLLBACK.md` for exact future commands. A rollback restores the retained old app image and known Origin/CSRF weakness; it must not restore a stale database snapshot. No activation command was executed here.

## Evidence

`candidate_manifest.json`, `source_hashes.csv`, `context/`, `config/`, `raw/build.log`, build/test command records, full pytest output and JUnit XML; `evidence/` contains preflight, activity, image/runtime validation and final preservation results. `tools/` retains exact script provenance using the temporary run pointer; these are not a general deployment automation framework. `FILES_SHA256.json` seals the package. Existing source/evaluation/Slurm evidence packages remain unmodified.
