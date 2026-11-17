# Deployment and rollback plan — review only; NOT executed

## Approval prerequisites

Approve the two-file patch, candidate hashes, and exact dedicated output-root policy. Confirm that `/home/lailai/slurm_contention_runs/mps-20261104T082034Z-cee9c5d4/jobs` is an acceptable output-only tree (no application secrets); other roots need their own review. Arrange a maintenance window and researcher communication. Preserve port 8002 unchanged. Confirm current 8001 revision and dependency versions still match the recorded base; stop if they drift. No production database migration or account edits are necessary.

## Prepare privately (only after separate deployment approval)

1. Set umask 077. Create a unique private backup under `/home/lailai/nectec-changes/` containing the current 8001 release, effective unit metadata and `/etc/systemd/system/slurm-portal.service.d/90-nectec-security-30beac16.conf`. Save a SHA-256 inventory and selected PID/start configuration. Record `/home/lailai/slurm-portal/portal_users.db` explicitly; do not copy a live SQLite database using an unsafe ordinary file copy and do not roll session data back during code rollback.
2. Create new release `/home/lailai/nectec-changes/output-fix-20261108T064131Z-f623c77b/portal-release`. Copy the current known authenticated release into it, then replace only `app.py` and add `job_output.py` from this package's `portal/`. Keep unchanged authentication and identity modules. Verify all candidate hashes against `release_manifest.json`. The original source tree and original release stay unchanged.
3. Review `patches/90-nectec-security-30beac16.conf.proposed`. It preserves the localhost binding, 8001, original interpreter and DB path; it points to the new release and explicitly configures only the approved MPS output root. Use it to replace only the current targeted drop-in, preserving all other unit/drop-in settings. Never install it before release files and policy have been reviewed.
4. Authorized operator commands for the reviewed file, then managed service only:

```bash
sudo install -m 0644 '/home/lailai/ollama-test/portal_output_remediation/output-fix-20261108T064131Z-f623c77b/patches/90-nectec-security-30beac16.conf.proposed' /etc/systemd/system/slurm-portal.service.d/90-nectec-security-30beac16.conf
sudo systemctl daemon-reload
sudo systemctl restart slurm-portal.service
```

These privileged commands are a future reviewed step, not authorization to execute them now. Port 8002, Slurm, Cloudflare and Ollama must remain untouched.

## Acceptance and stop conditions

- Check active service, new working directory, unchanged DB path, new hashes, 16 API operations and startup logs (no credentials printed).
- Authenticate using existing authorized accounts in the browser. Owner `lailai` may inspect jobs 127/129; expect HTTP 200 with empty output if accounting/files still match their saved state. Never read another researcher's raw output. Check an authorized existing standard-output job if available; do not submit a job for this check.
- Repeat password redaction, unauthenticated denial, role controls and session checks without mutating real jobs. Fixture tests supply cross-user boundary evidence; any live negative authorization check needs designated authorized resources/accounts. Confirm 8002 remains healthy.
- If a custom path is denied, inspect only approved path/accounting/file metadata; do not widen roots automatically, disable owner checks or chmod private files.
- Stop on unexpected file disclosure, ownership violation, service failure, changed base or unsafe researcher activity. Preserve logs privately and use fallback 8002 as documented.

## Exact functional rollback

Restore the privately backed-up `90-nectec-security-30beac16.conf` to the same path, run `sudo systemctl daemon-reload`, then `sudo systemctl restart slurm-portal.service`. This returns to the **known authenticated release** `/home/lailai/nectec-changes/portal-security-20261106T125653Z-30beac16/portal-release`, not the unknown pre-authentication legacy runtime. Verify hashes, original working directory/DB path, 16 operations and 8002 health. No database rollback is required or permitted by this code-only plan. The prior custom-output limitation returns after rollback; no historical files are deleted. Retain new release and logs for diagnosis rather than deleting evidence.
