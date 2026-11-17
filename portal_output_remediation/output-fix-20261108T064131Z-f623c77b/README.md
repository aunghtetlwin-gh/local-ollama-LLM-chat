# Isolated Slurm historical-output patch

Status: tested, not deployed. Read [remediation report](reports/REMEDIATION_REPORT.md) and [deployment/rollback plan](reports/DEPLOYMENT_ROLLBACK.md).

Changed application files: `portal/app.py`, new `portal/job_output.py`. New tests: `tests/test_job_output_paths.py`; copied old security-test file has mock-boundary adaptation. Auth/identity modules are unchanged support files. No current service/configuration/database was modified.

Tests: 190 passed (108 existing + 82 new). Exact original command and raw output are under `raw/`. Reproduce in the recorded deployed-version isolated environment, without production data:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 '/home/lailai/ollama-test/portal_output_remediation/output-fix-20261108T064131Z-f623c77b/run_tests.py'
```

Each rerun writes a new unique directory under `raw/`, exits nonzero on any failure/timeout, and leaves original results unchanged. A restricted sandbox may require explicit host execution approval for TestClient; all scheduler and account data remain mocked/disposable. No GPU/Slurm workload is run.

Manifest: `release_manifest.json`; patch: `patches/historical-output.patch`; prospective (not installed) systemd configuration: `patches/90-nectec-security-30beac16.conf.proposed`. Additional roots, deployment and authenticated live acceptance require separate review.
