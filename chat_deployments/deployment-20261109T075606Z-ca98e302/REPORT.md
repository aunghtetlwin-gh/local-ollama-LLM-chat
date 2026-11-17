# Controlled Project 2 chat deployment — BLOCKED before activation

**No production deployment performed.** Mandatory technical preflight passed **14/14** checks at 2026-11-09T07:56:09.361595+00:00. The candidate package seal, expected image ID and patched server hash match. Current app/base image identity, PostgreSQL identity/health/volume, Compose hash and resolved environment settings match the reviewed baseline. The rollback image remains available.

Three connection samples found no established chat connections. The bounded recent log review found no HTTP events. These observations cannot confirm that all users finished work, all automated/headerless clients were coordinated or an agreed maintenance window is currently active. An explicit current-window/end-time and user/client-drain confirmation was requested; none was received before stopping. This is the sole known blocker, not a Docker permission or image/test failure.

As mandated, stopped before app recreation, private configuration backup, Compose update or any PostgreSQL action. The running app remains container `a6526b0cbd1401c78416747f93a1f4e174e5e790b319a38cf1bb1653113aead6` using prepatch image `sha256:fb589d346de905895e8b3746a98735fd0001958899684a2223692977e866ddae`. PostgreSQL remains `3568ff1916f8eec35c6d6290b0d5471e12a5c5771a418ec07841004cf523d9cd` with volume `ollama-test_postgres_data`. Original and rollback image remain present. Only a networkless temporary candidate image-hash inspection container was run and removed; no candidate app service was started.

Expected candidate image: `sha256:7f6a70da03c092c12a2fa2b3c50e1765efd95f44cb99aba6cb839bdc77eb006d`. Patched server SHA-256: `3e8993bbbc0c0fea98224d568f5a4bd27704e5908b9e04723948484f0502bccc`. These are prepared-image checks, not assertions that the production app has been patched.

To resume, establish a current coordinated window (including its end time in Asia/Bangkok), confirm affected users have finished and automated mutation clients are accounted for, then repeat live preflight. Use only the candidate's existing `DEPLOYMENT_ROLLBACK.md` app-only override command. No alternative Compose deployment is prepared or attempted here. Private operational backups and production activation remain future steps after the mandatory gate passes.

Post-deployment image/source/health/Origin checks and authenticated browser login/session/logout acceptance remain unperformed because deployment did not occur. Do not interpret the prior 79 isolated candidate tests as live production acceptance. No existing conversations, accounts, session records, schemas or volumes were read or modified, and no inference/GPU or Project 1 action occurred.

Evidence: `preflight.json`, `result.json`, `preflight_readonly.py`. Raw logs, credential values and database contents were not retained. Prior candidate/evidence files remain unchanged.
