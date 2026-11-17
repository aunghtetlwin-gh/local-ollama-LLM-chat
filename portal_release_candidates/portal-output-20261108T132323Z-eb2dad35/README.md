# Reviewed portal output release candidate

**Prepared and tested; NOT DEPLOYED.**

- [Candidate review](reports/CANDIDATE_REVIEW.md)
- [Exact deployment/rollback checklist](reports/DEPLOYMENT_ROLLBACK.md)
- `candidate_manifest.json`: full source/base/configuration hashes and paths.
- `config/output-roots.json`: nine explicit MPS job directories, jobs 123–131.
- `portal-release/`: four read-only, tested source files; unchanged frontend dependency is explicitly pinned.
- `raw/`: complete new 190-test run; `evidence/`: permissions, ACLs, groups, source/runtime/policy checks.

Verification (no service changes):

```bash
PYTHONDONTWRITEBYTECODE=1 python3 '/home/lailai/ollama-test/portal_release_candidates/portal-output-20261108T132323Z-eb2dad35/tools/verify_candidate.py'
```

Reproduce the isolated suite using `PYTHONDONTWRITEBYTECODE=1 python3 '/home/lailai/ollama-test/portal_release_candidates/portal-output-20261108T132323Z-eb2dad35/run_tests.py'`; new results go to a unique `raw/rerun-*` directory without overwriting the original run. Sandbox TestClient may need separate host execution approval. Tests block live scheduler/network operations and use disposable synthetic data.

Source is read-only and hash-sealed, not kernel immutable. Neither running portal was deployed/restarted. No real output contents, production DB/account changes, GPU work or Slurm mutations occurred. Actual deployment requires separate approval.
