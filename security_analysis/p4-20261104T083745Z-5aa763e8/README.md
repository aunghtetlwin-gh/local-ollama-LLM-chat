# NECTEC P4 security evidence package

Start with reports/SECURITY_EVALUATION.md and reports/SECURITY_CONTROL_MATRIX.md. The package distinguishes executed assertions, reproduced limitations, historical reports, source inspection and untested deployment behavior. It does not certify comprehensive security.

## Contents

- reports/test_cases.csv: all 146 completed test cases and outcomes.
- reports/test_summary.csv/json: five suite totals and evidence references.
- raw/*host.log, *host.xml, *host-command.json: full output, JUnit results, exact argv/cwd/environment and exit status.
- raw/sandbox_attempts.json: two initial 240-second sandbox stalls, separate from successful assertions.
- tests/: new isolated portal tests and explicit limitation characterizations, without production source changes.
- run_tests.py: test wrapper; outputs refuse existing command records.
- evidence/source_snapshot/: nonsecret source/test/configuration and historical-report/log snapshots. No .env, real password records, database dumps or live tokens were copied.
- evidence/deployment_metadata.json: read-only listeners, selected runtime cookie environment, permissions and Slurm configuration. No application endpoint/database/GPU API was called.
- source_inventory.csv/json: paths, snapshot hashes, roles and byte counts.
- evidence/preservation_before.json and reports/preservation.json: protected originals and unchanged-file validation.
- reports/validation.json and FILES_SHA256.json: output validation and package integrity.

## Reproduce tests

From /home/lailai/ollama-test, use the existing /tmp/conversation-isolation-tools environment. It is a test environment, not a verified copy of deployed dependencies. Full executed commands are in raw/*host-command.json. To create NEW output records, choose a unique --attempt label:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 PACKAGE/run_tests.py portal --attempt repeat1
PYTHONDONTWRITEBYTECODE=1 python3 PACKAGE/run_tests.py chat --attempt repeat1
PYTHONDONTWRITEBYTECODE=1 python3 PACKAGE/run_tests.py postgres --attempt repeat1
PYTHONDONTWRITEBYTECODE=1 python3 PACKAGE/run_tests.py portal-characterization --attempt repeat1
PYTHONDONTWRITEBYTECODE=1 python3 PACKAGE/run_tests.py chat-characterization --attempt repeat1
```

Use a copy of the sealed package for reproduction. The PostgreSQL suite starts/stops only a newly generated private temporary cluster; no production URL is accepted. Network/host-operation guards and synthetic data are defined in the tests. Run outside the restrictive sandbox if TestClient cannot start there; do not weaken application safeguards. No live Slurm test or workload is authorized by this reproduction command.

## Interpretation and confidentiality

146 passing tests include deliberate reproductions of limitations. Do not translate the count into 146 independent guarantees. Portal Slurm/Linux responses are mocked; PostgreSQL semantics are real only in the disposable cluster. Host permissions are metadata, not an exploitation test. Browser CSRF exploitability, public TLS and production DB least privilege remain unverified.

The package is internal evidence: source snapshots, synthetic test credentials, usernames, listener/session metadata and historical access logs should be reviewed/redacted before public release. Real passwords, session tokens and .env contents were not collected. The original projects, LLM results, human review and MPS experiment are protected by the preservation inventory.

## Completion and package validation

`reports/AUDIT_SUMMARY.md` is the concise committee-facing assessment. All 146 completed cases passed with exit 0; five cases reproduce limitations rather than protective controls. Fourteen independent package checks passed, including original/snapshot hashes, 27 evidence-bound matrix rows and verification of the prior LLM/MPS package seals. All 1,584 protected originals remained unchanged.

The final FILES_SHA256.json excludes itself and binds all other package files. Verify it read-only with Python hashlib, rather than regenerating sealed outputs. `validate_package.py` checks the recorded suites and source preservation but rewrites its own validation record; use a copy if rerunning it after sealing. The package reports scoped P4 evidence and pending deployment requirements, not comprehensive security certification.
