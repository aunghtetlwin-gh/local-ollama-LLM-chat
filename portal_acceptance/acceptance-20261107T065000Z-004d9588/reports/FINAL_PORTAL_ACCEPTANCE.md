# Final Slurm Portal acceptance review

**Decision: PARTIAL — core authenticated portal accepted; unrestricted historical-output retrieval is not ready for unqualified final acceptance.** No evidence warrants rolling back the healthy deployment. Resolve the output-path defect, or explicitly approve and disclose a narrower supported-output scope before closing engineering acceptance.

## Current deployment and acceptance evidence

The final read-only snapshot (timestamp in `evidence/final-runtime-snapshot.json`) confirms `slurm-portal.service` active/running, PID 1565020, Result=success and NRestarts=0. Its working directory is the prepared `portal-release`; version `portal-security-v1-b893d3a5f7c1`. All three deployed Python source hashes match the prepared manifest. The authentication database path remains `/home/lailai/slurm-portal/portal_users.db`. Port 8001 returns OpenAPI successfully with 16 API operations. Port 8002 also returns 16 operations; fallback PID 2019096 remains present. Original portal sources, frontend and base systemd unit match the recorded hashes. This review did not change either process or configuration.

The prior verification package `portal_deployment_verification/verification-20261106T164500Z-e0f8b1c9/` recorded **31/31 automated live checks passing**, including password-redaction, unauthenticated denial and deployment identity. Those are prior results, not newly repeated authenticated tests.

The operator now reports successful browser login as administrator `lailai` and researcher `mangkud`, correct role-specific controls, node statistics and researcher history through SSH forwarding at `http://127.0.0.1:18003/ui`. These observations are attributed to the operator, not independently captured browser traces. They close the basic login/display acceptance gaps.

Fresh isolated tests: **36 passed, 0 failed, 0 skipped; 61 deselected**, exit code 0. Of these, 35 exercise existing ownership/role/filesystem behavior; one characterizes the custom-stdout limitation. A passing characterization test does not mean that defect is fixed. Raw log, JUnit XML, command, synthetic source and fixture configuration are retained. Tests use disposable SQLite users and synthetic files with mocked Slurm; no live job mutations or production account/session writes occur. The current fixture environment differs from production dependency versions; the earlier sealed readiness package supplies the separate deployed-version compatibility evidence. One TestClient dependency deprecation warning occurred.

## Historical output finding

The service journal records Output HTTP 404s for **jobs 127 and 129**, both from the current service PID. Accounting identifies both as completed jobs owned by `lailai` and records custom stdout paths:

- 127: `/home/lailai/slurm_contention_runs/mps-20261104T082034Z-cee9c5d4/jobs/r2-concurrent-job1/slurm-%j.out`
- 129: `/home/lailai/slurm_contention_runs/mps-20261104T082034Z-cee9c5d4/jobs/r3-baseline-job1/slurm-%j.out`

The corresponding expanded files `slurm-127.out` and `slurm-129.out` still exist, are regular files owned by UID 1000, readable by the audit user, and **zero bytes long**. Their contents were not opened. These are empty stdout files, not evidence that primary experiment result artifacts were lost. The portal's assumed `/tmp/slurm-127.out` and `/tmp/slurm-129.out` do not exist.

Deployed `app.py` verifies job ownership, then hardcodes `/tmp/slurm-{job_id}.out`; it does not resolve the authoritative Slurm stdout path. The synthetic custom-path test reproduces the 404 even when the retained custom file exists. This is a genuine output-path handling limitation for externally submitted/custom-output jobs, rather than proof of deletion. Exact attribution of the operator's single reported error remains unconfirmed because its job ID and logged-in account were not supplied; the journal contains no authenticated identity attribution used in this audit.

## Distinguishing outcomes and authorization

- **Existing supported-path output:** synthetic owner request returns HTTP 200 and exact synthetic content. Completed-job accounting fallback also passes. A fresh live owner-authenticated output success was not attempted: no production cookies or credentials were used and no real output contents were retrieved.
- **Missing output:** supported-path absence produces 404 `Job output not found`. Current custom-path behavior produces the same result despite an existing retained file elsewhere.
- **Filesystem denial:** wrong file UID, symlink, nonregular file or open/read failure produces a concealed 404; oversized output produces 413. A response body alone cannot distinguish missing files from access problems.
- **Foreign job ownership:** denied before opening any file, with 404 `Job not found`; fixtures verify this for researchers and administrators. No another researcher's private output was retrieved.
- **Roles:** backend `admin` and `user` correspond to administrator and researcher UI roles. Administrators can view broader job metadata, but have no general bypass for another user's raw output/cancel/requeue. This intentional distinction is consistently covered by fixture tests. Browser controls alone do not prove API enforcement; isolated API tests supply that evidence.

## Remaining acceptance checks and minimum remediation

1. Confirm which job/account produced the browser error. Do not send credentials or output contents.
2. Using an existing authorized own job whose *supported* stdout file exists, check Output in the browser. Empty stdout should be distinguished from an error. If no such authorized job is available, retain this as untested; do not submit a new job for this review.
3. Confirm normal logout/session handling and authenticated missing/invalid-CSRF denial, plus direct researcher denial of administrator routes, using approved acceptance procedures. These have isolated/prior evidence but were not newly demonstrated in an authenticated production browser here. Never use a valid job mutation as a CSRF test.
4. For generic history Output support, separately approve a narrow patch resolving authoritative stdout paths with controlled expansion, allowed-path policy, unchanged job ownership checks, no-follow/UID/type/size protections and regression cases for empty/custom/missing/foreign/unsafe paths. Do not blindly follow arbitrary scheduler paths, weaken ownership, make private files public, or rewrite historical records. Alternatively formally limit the portal to managed default output paths and make unsupported historical output explicit in the UI/documentation; merely leaving a generic failing Output control is not a complete resolution.

## Scope and preservation

This is an application acceptance review, not penetration testing or proof of OS isolation. File modes are metadata observations, not proof the service can read every researcher-owned file. The portal's single service identity and per-user filesystem permissions remain a deployment limitation. No services restarted; no accounts, database records, output files, Slurm jobs, GPU resources, Cloudflare or port 8002 were modified. All new material is confined to this acceptance directory. Existing evidence packages were read, not regenerated or edited. Source-hash checks cover the listed deployment/original files; this review does not claim a fresh full rehash of all LLM/MPS artifacts.

## Source inventory

- Deployed release: `/home/lailai/nectec-changes/portal-security-20261106T125653Z-30beac16/portal-release/{app.py,auth.py,slurm_identity.py}`; ownership/output implementation in app.py near lines 1390–1540.
- Prepared release manifest and prior verification result/acceptance records.
- Sealed security remediation tests, copied only into this package's fixtures.
- Read-only Slurm accounting for jobs 127/129; journal output-request status metadata; file `stat` metadata only.
- `evidence/`: browser provenance, runtime snapshot, source hashes, request events and file metadata.
- `raw/`: exact fixture invocation, test log and JUnit XML. `fixtures/`: reproducible isolated test copy.
