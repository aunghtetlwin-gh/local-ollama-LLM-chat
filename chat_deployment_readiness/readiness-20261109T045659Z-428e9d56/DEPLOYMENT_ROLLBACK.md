# Future app-only deployment / rollback — NOT EXECUTED

Requires separate approval for preparation/build/isolated validation and then production app recreation, with a current drained maintenance window. Confirm actual browser forward URL and notify users about headerless-client compatibility. Stop on any source/image/environment/volume mismatch or uncertain in-flight completion. The database and portals must remain untouched.

## 1. Preserve base and build a one-file overlay (after approval only)

Commands below do not upgrade dependencies and do not replace the existing `local-ollama-chat:1.0` tag. Keep the same Compose file/project and privately preserve current Compose/environment operational files (never publish `.env`, full inspect or resolved Compose secrets). Confirm the existing database backup/recovery policy with the operator; do not restore or migrate data for this patch.

```bash
set -eu
umask 077
project_dir='/home/lailai/ollama-test'
change_dir='/home/lailai/nectec-changes/chat-origin-20261109-428e9d56'
base_id='sha256:fb589d346de905895e8b3746a98735fd0001958899684a2223692977e866ddae'
rollback_image='local-ollama-chat:pre-origin-20261109-428e9d56'
candidate_image='local-ollama-chat:origin-security-20261109-428e9d56'
# Verify current image/source/config/environment and sealed evidence again before proceeding.
test "$(docker inspect --format '{{.Image}}' local-ollama-chat)" = "$base_id"
mkdir -m 0700 -- "$change_dir"
mkdir -m 0700 -- "$change_dir/context"
docker tag "$base_id" "$rollback_image"
test "$(docker image inspect --format '{{.Id}}' "$rollback_image")" = "$base_id"
cp -- '/home/lailai/ollama-test/security_remediation/remediation-20261104T111222Z-e4089eae/chat/server.py' "$change_dir/context/server.py"
printf '%s  %s\n' '3e8993bbbc0c0fea98224d568f5a4bd27704e5908b9e04723948484f0502bccc' "$change_dir/context/server.py" | sha256sum -c -
cat > "$change_dir/context/Dockerfile" <<'DOCKERFILE'
FROM local-ollama-chat:pre-origin-20261109-428e9d56
COPY server.py /app/server.py
DOCKERFILE
docker build --pull=false --network=none -t "$candidate_image" "$change_dir/context"
docker image inspect --format '{{.Id}}' "$candidate_image" > "$change_dir/candidate-image-id.txt"
cat > "$change_dir/compose.security.yml" <<'COMPOSE'
services:
  app:
    image: local-ollama-chat:origin-security-20261109-428e9d56
    pull_policy: never
COMPOSE
cat > "$change_dir/compose.rollback.yml" <<'COMPOSE'
services:
  app:
    image: local-ollama-chat:pre-origin-20261109-428e9d56
    pull_policy: never
COMPOSE
```

Before tagging, check that the chosen unique tags do not already designate another image; stop rather than overwrite a conflicting tag. Use the local Docker engine/image store. No registry pull or pip/network install is intended; stop if the builder cannot use the retained local base. The isolated context contains only server.py and Dockerfile, excluding `.env`, databases, unrelated source changes and evidence trees. No RUN line or database initialization is included. Build restrictions mean **none of these commands was executed during readiness review**.

## 2. Candidate image verification gate

Record candidate image ID. In a disposable networkless/read-only inspection container, use only Python stdlib/importlib.metadata to hash files and list package/Python versions, with `python -B`, no application import, production environment, DB mounts or GPU devices. A future authorized invocation shape is:

```bash
docker run --rm --network=none --read-only --cap-drop=ALL \
  --security-opt=no-new-privileges --entrypoint python "$candidate_image" -B -c \
  'import sys,json,hashlib,importlib.metadata; from pathlib import Path; print(json.dumps({"python":sys.version,"server_sha256":hashlib.sha256(Path("/app/server.py").read_bytes()).hexdigest(),"packages":{d.metadata["Name"].lower().replace("_","-"):d.version for d in importlib.metadata.distributions()}}))'
```

Require server SHA `3e8993bbbc0c0fea98224d568f5a4bd27704e5908b9e04723948484f0502bccc`, exact Python and every baseline package version from `inventory.json`, unchanged remaining `/app` code/UI/SQL hashes, original command/working-directory/environment configuration and no added mounts. Extend the same read-only hash listing to every baseline file; do not infer unchanged code from tag names. Retain new inspection output separately. The existing 79 exact-image regression cases and one-file hash equivalence support compatibility; if further candidate tests are run, reuse the isolated profiles with mocked Ollama/disposable SQL, and ensure imports target candidate `/app`, not a shadow staging tree. Any mismatch blocks activation.

## 3. Activate app only in the approved drained window

Recheck app/DB identities, DB healthy state, same named volume, resolved environment equality and client URL. Preserve private launch metadata and recovery configuration. Record DB container ID `3568ff1916f8eec35c6d6290b0d5471e12a5c5771a418ec07841004cf523d9cd` and volume `ollama-test_postgres_data` for post-check. Then:

```bash
docker compose -p ollama-test \
  -f "$project_dir/docker-compose.yml" -f "$change_dir/compose.security.yml" \
  up -d --no-deps --no-build --pull never --force-recreate app
```

This interrupts only chat app streams; it must not recreate DB, portal, Ollama or Slurm services. No `compose down`, `down -v`, `up db`, image pruning or migration command. The base Compose build stanza may remain, but `--no-build` prevents its use. Keep the override path in the operational runbook for future app management, rather than accidentally returning to the base image on the next bare Compose up.

## 4. Acceptance without inference

- Running image ID equals recorded candidate ID; patched/unmodified source and package hashes match; localhost8000 command/networking and selected cookie/DB settings unchanged. Health200 and 13 API operations. There is no app Docker healthcheck, so Compose returning is not sufficient acceptance.
- DB container ID, image and `ollama-test_postgres_data` attachment unchanged; DB still healthy. Do not query conversation contents to establish this.
- With no Cookie header/jar, POST/logout missing Origin →403; hostile Origin →403; matching Origin `http://127.0.0.1:8000` →200. Referer-only matching source may also pass; invalid Origin must not fall back to good Referer. No-cookie matching-origin POST/chat →401 before inference. Do not send authenticated chat or inference requests.
- Malformed login sentinel with matching Origin remains redacted422. Anonymous protected reads denied. Review logs privately for startup/errors without exposing cookies or credentials.
- Actual browser SSH URL: existing authorized user confirms login/session/logout and same-origin requests. These ordinary session writes require the deployment acceptance authorization. No production account creation/password change. Existing conversation owner access may be confirmed by its owner; deletion tests require separately approved synthetic data only. Never delete existing research data.

Stop and preserve evidence on failure. Record expected effects of no Origin on scripts; do not weaken same-origin policy as an ad hoc workaround.

## 5. Rollback app only

In the coordinated window, verify retained rollback tag resolves to `sha256:fb589d346de905895e8b3746a98735fd0001958899684a2223692977e866ddae`, then:

```bash
docker compose -p ollama-test \
  -f "$project_dir/docker-compose.yml" -f "$change_dir/compose.rollback.yml" \
  up -d --no-deps --no-build --pull never --force-recreate app
```

Verify old server SHA `19f4c324aeea22333412dc3c58b4d158881e70859dfca159498ad3777a203967`, original Python/packages/settings, health/API and unchanged DB ID/volume. Retain candidate image/logs; do not restore old database snapshots or remove volumes. Rollback returns the known prepatch app and therefore reintroduces its Origin/CSRF weakness. Image retention prevents a dependency rebuild; it does not preserve an in-flight stream, which must be drained before either cutover.
