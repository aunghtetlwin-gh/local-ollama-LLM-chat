# Historical-output deployment attempt — BLOCKED

Preflight timestamp: 2026-11-09T03:40:34.863512+00:00. No deployment or service changes performed.

## Verified

- Sealed candidate integrity, expected current 8001/base source hashes, external frontend hash and current override hash all match.
- Candidate's recorded JUnit and command evidence confirms 190 passing tests, zero failures/skips, exit 0. Tests were validated, not rerun in this deployment attempt.
- All nine approved leaf directories and captured file metadata, ACLs, ownership, link counts and group membership match the reviewed snapshot. No real output contents were opened. The policy remains limited to jobs 123–131's nine leaves, with the exact standard-path exception documented in the candidate.
- 8001 active on `portal-security-v1-b893d3a5f7c1` at `/home/lailai/nectec-changes/portal-security-20261106T125653Z-30beac16/portal-release`, PID 1565020, original authentication DB path. Both 8001 and 8002 OpenAPI return HTTP 200 with 16 operations. Fallback PID/start identity unchanged.
- Slurm queue empty; only `lailai` is reported by `who`; no relevant established connections were observed. Recent recorded HTTP activity is the audit's own OpenAPI GET. These observations cannot prove absence of idle browser users, unreported sessions or a coordinated maintenance agreement.

## Blocking prerequisites and stop

`sudo -n true` exited 1: **sudo: a password is required**. As explicitly required, execution stopped before backup creation, release installation, systemd modification/reload or restart. No credentials were requested or read. Current maintenance-window end time/coordination was also not established from evidence; the operator question remains unresolved.

Use `MANUAL_DEPLOYMENT.md` for the exact reviewed block, copied from the sealed candidate plan. Sudo authentication, if needed, must occur only in the operator's own SSH terminal; credentials must never be shared. A sudo timestamp in a different TTY may not authorize this agent session. If proceeding manually, perform all backup/release steps, not just restart commands.

## Rollback readiness and limitations

The immediately previous known-good authenticated release and override remain unchanged and hash verified. No rollback is necessary because nothing was applied. Private backups have NOT yet been created; the reviewed deployment block creates them before activation. Rollback after deployment restores that saved override and the known authenticated release, never the unknown legacy runtime. Port 8002 remains available and untouched.

## Remaining acceptance

After deployment under an explicitly coordinated window: verify new release/policy hashes, original DB path, 16 operations, health/redaction/unauthenticated denial, ownership evidence and unchanged fallback. Authorized owner browser checks for jobs 127/129 should return empty output if current accounting/files still match. Login/logout and approved authenticated CSRF/role checks remain operator tasks. No production account/database changes, Slurm mutations, GPU work, chat deployment or Cloudflare changes are authorized by this attempt.

Source evidence: `preflight.json`, `test-evidence-validation.json`, `DEPLOYMENT_STATUS.json`; sealed candidate remains unchanged. No new post-deployment claims are made.
