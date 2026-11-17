# NECTEC application security fixes — isolated, not deployed

Read reports/REMEDIATION_SUMMARY.md first. Four runtime files were minimally remediated in portal/ and chat/ copies. Originals, deployed data/services, and sealed LLM/MPS/P4 audit evidence are unchanged. No branch switch or deployment was performed.

- portal/: isolated portal implementation and frontend snapshot; do not start it against a real DB.
- chat/: isolated chat implementation, HTML, migrations and copied test fixtures; no .env/database copied.
- tests/: adapted audit security regressions and focused remediation tests.
- patches/: reviewable application patches plus separate test-adapter changes. Never apply patches to the sealed audit.
- raw/: full pytest output, JUnit, exact command/environment/source hashes, exit codes and read-only patch checks.
- reports/: summary, final test cases/totals, changed-file and source inventories, environment and preservation checks.
- harness_check/: deliberately failing self-check, excluded from application suites.

## Safe reproduction

Use a COPY of this package for reproduction. From the original project directory:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 PACKAGE/run_tests.py portal --attempt repeat1
PYTHONDONTWRITEBYTECODE=1 python3 PACKAGE/run_tests.py chat --attempt repeat1
PYTHONDONTWRITEBYTECODE=1 python3 PACKAGE/run_tests.py postgres --attempt repeat1
```

The wrapper runs /tmp/conversation-isolation-tools/bin/python against copied source, suppresses dotenv loading, disables bytecode/cache/plugin writes, uses synthetic data and propagates pytest exit codes. Existing output records are refused. Portal host/network operations are mocked; chat external DB/Ollama calls are blocked. PostgreSQL starts/stops only a new private temporary cluster. Running these tests does not authorize live job submission or production deployment. TestClient may require execution outside the restrictive sandbox, as in the prior audit.

A separately selected `canary` suite deliberately returns exit 1 to confirm assertion failure propagation. Do not include it in application pass/fail totals.

## Compatibility and deployment

No DB migration, session token or new credential is introduced. Approved Slurm identity policy remains the existing three names; bootstrap CLI restrictions remain narrower as before. Chat unsafe methods now require a matching Origin or Referer. Non-browser clients and trusted proxy Host/scheme handling need operator review. Generic portal 422 responses no longer expose detailed validation inputs.

The patch checks are read-only and are recorded in raw/*patch-check.json. Do not deploy or restart services without separate approval. Review actual dependency, TLS and cookie settings, integration branch and staging checks first. The application fixes do not alter the unresolved host security findings in the original audit.

## Final validation and evidence seal

Fifteen independent package checks passed, including tested-source bindings, exact test totals, expected failure propagation, patch applicability and all 1,666 protected original hashes. Prior LLM, MPS and P4 package seals were verified. No original file was changed. `reports/output_validation.json` records the checks. The copied integration_tests/ISOLATION_REPORT.md is a historical report; current remediation results are in this package’s reports/ and raw/ directories.

FILES_SHA256.json seals every other package file. Verify hashes read-only; use a copy when re-running the validator or tests because they write new evidence. Production deployment is still pending separate review/approval.
