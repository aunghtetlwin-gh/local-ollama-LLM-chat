# Separate controlled chat deployment / rollback — NOT EXECUTED

Candidate image: `local-ollama-chat:origin-20261109T060037Z-4f0fba1d` → `sha256:7f6a70da03c092c12a2fa2b3c50e1765efd95f44cb99aba6cb839bdc77eb006d`.
Rollback image: `local-ollama-chat:pre-origin-20261109T060037Z-4f0fba1d` → `sha256:fb589d346de905895e8b3746a98735fd0001958899684a2223692977e866ddae`.

## Before approval / activation

Confirm current running container still equals base `a6526b0cbd1401c78416747f93a1f4e174e5e790b319a38cf1bb1653113aead6` and image `sha256:fb589d346de905895e8b3746a98735fd0001958899684a2223692977e866ddae`; DB ID `3568ff1916f8eec35c6d6290b0d5471e12a5c5771a418ec07841004cf523d9cd` and volume `ollama-test_postgres_data`; environment/configuration match the recorded readiness snapshot. Stop on drift. Coordinate maintenance, notify clients and confirm the observed browser/polling user has no active stream. Do not infer a drain from an empty socket sample alone. Preserve private Compose/.env/launch metadata according to operator policy without publishing credentials. Keep both immutable image IDs/tags; do not prune. No DB schema migration or restore is needed.

After **separate production deployment authorization**, use only the validated override and app service:

```bash
set -eu
project_dir='/home/lailai/ollama-test'
candidate_dir='/home/lailai/ollama-test/chat_image_candidates/origin-20261109T060037Z-4f0fba1d'
test "$(docker inspect --format '{{.Id}}' local-ollama-chat)" = 'a6526b0cbd1401c78416747f93a1f4e174e5e790b319a38cf1bb1653113aead6'
test "$(docker inspect --format '{{.Image}}' local-ollama-chat)" = 'sha256:fb589d346de905895e8b3746a98735fd0001958899684a2223692977e866ddae'
test "$(docker image inspect --format '{{.Id}}' 'local-ollama-chat:origin-20261109T060037Z-4f0fba1d')" = 'sha256:7f6a70da03c092c12a2fa2b3c50e1765efd95f44cb99aba6cb839bdc77eb006d'
test "$(docker image inspect --format '{{.Id}}' 'local-ollama-chat:pre-origin-20261109T060037Z-4f0fba1d')" = 'sha256:fb589d346de905895e8b3746a98735fd0001958899684a2223692977e866ddae'
docker compose -p ollama-test \
  -f "$project_dir/docker-compose.yml" -f "$candidate_dir/config/compose.security.yml" \
  up -d --no-deps --no-build --pull never --force-recreate app
```

This briefly interrupts app8000. Never run whole-project up/down, down -v, volume removal, migrations or a fresh requirements build. Do not touch Ollama/Slurm/portal services. Record private pre/post metadata, hashes and timestamps in a NEW deployment directory. Use the override in future operational commands; bare base Compose could reactivate the old tag.

## Acceptance (no inference or production conversation mutation)

- App image ID/server hash and unchanged remaining file/package hashes match manifest; localhost8000 and original DB/cookie configuration unchanged; health200 and expected13 operations. DB ID/image/start/volume unchanged and healthy.
- Send no Cookie header/jar: POST/logout missing Origin403; hostile Origin403; matching backend Origin `http://127.0.0.1:8000`200; matching Referer-only fallback permitted. Matching-origin POST/chat with valid body but no cookie401 before inference. Invalid Origin cannot be rescued by a good Referer.
- Matching-origin malformed login sentinel422 redacted. Protected anonymous reads denied. Review startup logs privately; no credentials or real cookies saved in research reports.
- Existing authorized user confirms browser login/session/logout at **http://127.0.0.1:18000** and owner-scoped history. This requires ordinary session-write acceptance authorization. Do not run actual chat inference or delete existing conversation records. Authenticated delete testing is confined to separately approved synthetic data.
- Any failure: stop, preserve logs and use reviewed rollback; never disable middleware or broaden origins ad hoc.

## Rollback (separate authorized operation)

```bash
set -eu
project_dir='/home/lailai/ollama-test'
candidate_dir='/home/lailai/ollama-test/chat_image_candidates/origin-20261109T060037Z-4f0fba1d'
test "$(docker image inspect --format '{{.Id}}' 'local-ollama-chat:pre-origin-20261109T060037Z-4f0fba1d')" = 'sha256:fb589d346de905895e8b3746a98735fd0001958899684a2223692977e866ddae'
docker compose -p ollama-test \
  -f "$project_dir/docker-compose.yml" -f "$candidate_dir/config/compose.rollback.yml" \
  up -d --no-deps --no-build --pull never --force-recreate app
```

Verify restored image ID `sha256:fb589d346de905895e8b3746a98735fd0001958899684a2223692977e866ddae`, prepatch server hash `19f4c324aeea22333412dc3c58b4d158881e70859dfca159498ad3777a203967`, old package/configuration values, health and unchanged DB volume/container. Keep candidate image/evidence for diagnosis. Do NOT roll the DB/sessions/conversations back. Old app restores the known CSRF weakness, so rollback is temporary risk containment with a follow-up fix window. Drain streams before rollback too.
