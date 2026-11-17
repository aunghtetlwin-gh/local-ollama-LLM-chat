# Reviewed manual deployment steps — NOT executed

Only proceed in the coordinated maintenance window after confirming researcher availability and current preflight. This attempt stopped at `sudo -n true`: `sudo: a password is required`.

If deploying manually, authenticate sudo ONLY in your own authorized SSH terminal (`sudo -v`), never through an agent. Sudo timestamps may be terminal-specific; authentication in another terminal does not guarantee availability to the agent session. Alternatively perform the entire reviewed block below in the authorized terminal. No password should be copied, logged or sent to an agent.

The following block is copied verbatim from the sealed candidate deployment plan. Stop on any failed command; do not overwrite an existing backup/release destination. Candidate source, policy and maintenance authorization must be rechecked if execution is delayed.

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

After the block, complete the acceptance criteria in the original candidate deployment plan. In particular, check 8001 release/policy hashes, original DB path and 16 operations; safe unauthenticated denial; owner-authorized browser checks for 127/129; and unchanged 8002. Do not read foreign private output or mutate live Slurm jobs.

Rollback commands and acceptance criteria remain in `/home/lailai/ollama-test/portal_release_candidates/portal-output-20261108T132323Z-eb2dad35/reports/DEPLOYMENT_ROLLBACK.md`.
