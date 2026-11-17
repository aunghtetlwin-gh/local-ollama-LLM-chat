# Controlled 8001-only deployment and rollback — NOT EXECUTED

Approval gate: approve candidate `portal-output-20261108T132323Z-eb2dad35`, exact nine-leaf directory policy, maintenance window and 8001 restart. Do not deploy if researchers/requests would be disrupted. Recheck service PID/source/dependencies, group membership/ACLs and frontend hash first. Both ports remain untouched during preparation. Actual 8001 restart has a brief interruption; this is not a zero-downtime procedure. Port 8002 remains the functional fallback, and SSH forwarding can be pointed there without terminating it.

## Before approval: verification only

```bash
PYTHONDONTWRITEBYTECODE=1 python3 '/home/lailai/ollama-test/portal_release_candidates/portal-output-20261108T132323Z-eb2dad35/tools/verify_candidate.py'
```

Review `evidence/host-preflight.json`, `config/output-roots.json`, `candidate_manifest.json`, and the proposed drop-in. Never broaden the roots automatically. Current DB path stays `/home/lailai/slurm-portal/portal_users.db`; do not restore or rewrite it for this code update.

## After separate deployment authorization only

Run as application owner with approved sudo access. Do not type passwords into an agent/tool; authenticate sudo in the operator's own terminal. Execute as one error-stopping block; any failure stops before subsequent actions. These commands prepare private code/config backups and a new release, then update only the reviewed drop-in:

```bash
set -eu
umask 077
candidate_dir='/home/lailai/ollama-test/portal_release_candidates/portal-output-20261108T132323Z-eb2dad35'
release_parent='/home/lailai/nectec-changes/portal-output-20261108T132323Z-eb2dad35'
release_dir="$release_parent/portal-release"
backup_dir='/home/lailai/nectec-changes/portal-output-20261108T132323Z-eb2dad35-before-deploy'
dropin_path='/etc/systemd/system/slurm-portal.service.d/90-nectec-security-30beac16.conf'
PYTHONDONTWRITEBYTECODE=1 python3 "$candidate_dir/tools/verify_candidate.py"
sudo -n true
mkdir -m 0700 -- "$backup_dir"
cp -a -- '/home/lailai/nectec-changes/portal-security-20261106T125653Z-30beac16/portal-release' "$backup_dir/previous-release"
sudo cp -a -- "$dropin_path" "$backup_dir/previous-dropin.conf"
sudo cp -a -- /etc/systemd/system/slurm-portal.service "$backup_dir/base-unit.conf"
systemctl cat slurm-portal.service > "$backup_dir/effective-unit.txt"
systemctl show slurm-portal.service --property=MainPID,WorkingDirectory,ActiveState,SubState > "$backup_dir/service-before.txt"
mkdir -m 0700 -- "$release_parent"
cp -a -- "$candidate_dir/portal-release" "$release_dir"
PYTHONDONTWRITEBYTECODE=1 python3 "$candidate_dir/tools/verify_release_copy.py" "$release_dir"
sudo install -m 0644 -- "$candidate_dir/config/90-nectec-security-30beac16.conf.candidate" "$dropin_path"
sudo systemctl daemon-reload
sudo systemctl restart slurm-portal.service
systemctl is-active --quiet slurm-portal.service
systemctl show slurm-portal.service --property=MainPID,WorkingDirectory,ActiveState,SubState,Result,NRestarts
```

`mkdir` deliberately fails if either unique backup/release parent already exists; stop and review rather than overwrite. Do not edit the sealed candidate or copy bytecode. Do not create/migrate/replace the authentication database. No command targets 8002, Slurm, GPU, Ollama or Cloudflare. Keep backups private; do not print complete environments, cookies or logs containing tokens.

## Acceptance criteria

1. 8001 active, expected new working directory and source hashes, original DB path, localhost binding, 16 API operations and clean startup. Inspect only selected settings; keep any raw logs private/redacted.
2. Existing administrator/researcher login and role controls work. Password redaction and unauthenticated denial remain. Verify normal session/logout and approved authenticated CSRF checks without sending a valid Slurm mutation.
3. Owner `lailai` checks existing jobs 127/129: if current accounting and files still match, HTTP 200 with empty output. Check an authorized existing standard-output job if available. No new jobs, no reading foreign private output. Negative ownership/path guarantees are covered by isolated tests; any live check needs designated authorized resources.
4. 8002 still healthy, same process/start identity and unchanged source/configuration. No missing-data, unknown source drift or access broadening is acceptable.
5. Record timestamps, selected service metadata, release/config hashes and test results in a NEW post-deployment directory. Do not overwrite this candidate or previous evidence.

On failed acceptance, unexpected disclosure, unhealthy service or uncertainty: stop, preserve private logs and use 8002 fallback. Do not widen roots or change file permissions.

## Rollback (operator authorization only)

Restore the backup of the same drop-in and restart only 8001:

```bash
set -eu
backup_dir='/home/lailai/nectec-changes/portal-output-20261108T132323Z-eb2dad35-before-deploy'
sudo install -m 0644 -- "$backup_dir/previous-dropin.conf" '/etc/systemd/system/slurm-portal.service.d/90-nectec-security-30beac16.conf'
sudo systemctl daemon-reload
sudo systemctl restart slurm-portal.service
systemctl is-active --quiet slurm-portal.service
systemctl show slurm-portal.service --property=MainPID,WorkingDirectory,ActiveState,SubState,Result
```

Expected rollback directory: `/home/lailai/nectec-changes/portal-security-20261106T125653Z-30beac16/portal-release`, version `portal-security-v1-b893d3a5f7c1`. It remains in place and its hashes were captured. Verify the original DB path and 16 operations; retain the candidate/new release and logs. No DB rollback or 8002 change. This restores known authenticated functionality with its previous custom-output limitation; it does not recreate the unknown old legacy runtime.
