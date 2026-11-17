# P4 security evidence: concise assessment

**Application authorization is supported by passing isolated tests; production and host isolation are not certified.** No production remediation was performed.

| Completed suite | Passed | Environment |
|---|---:|---|
| Portal behavior | 96 | Synthetic SQLite users, in-process HTTP, mocked Slurm/Linux/token calls |
| Chat regressions | 35 | In-memory SQLite adapter; PostgreSQL/Ollama calls blocked |
| Chat PostgreSQL integration | 11 | Newly created private PostgreSQL cluster; mocked inference |
| Portal limitation characterization | 2 | Synthetic credentials and simulated DB outage |
| Chat limitation characterization | 2 | In-memory conversations; supplied valid cookie and untrusted Origin |
| **Total** | **146** | **0 completed-suite failures/errors/skips; all exit 0** |

Two initial sandbox TestClient attempts timed out and are not counted as passing assertions. Five cases deliberately reproduce limitations: four dedicated characterizations plus the onboarding/allowlist mismatch. Test counts do not represent independent security guarantees.

Verified scoped claims:

- Portal rejects unauthenticated, invalid, expired, revoked and disabled sessions; logout prevents replay of that session.
- Implemented portal mutations require a CSRF token belonging to the authenticated session.
- Researchers see their own jobs; administrators may monitor metadata. Neither researchers nor administrators may mutate or read output belonging to another user through the tested API paths.
- Output handling rejects symlinks, directories, wrong ownership, missing files and over-limit files.
- Only administrators can onboard/disable researchers; duplicate creation does not overwrite an account, and disabling revokes existing sessions.
- Chat application ownership was verified using two accounts and actual SQL in a disposable PostgreSQL database, including forged IDs and unchanged state after denial.

Reproduced issues and minimum next actions:

1. **Credential handling:** a portal login request missing username echoes its submitted password in HTTP 422. Add sanitized validation responses and an explicit no-secret-echo regression. A simulated auth DB outage denies access but returns unhandled 500; provide a controlled availability response.
2. **Identity policy:** eligible onboarding is broader than the Slurm token allowlist. Align the two using one approved policy while preserving default deny. Real sudo/JWT/backend permissions still need operator review.
3. **Chat CSRF:** authenticated delete/logout lack backend Origin/token checks. This is not proof of browser exploitability. Establish a policy and test it with actual browser/cookie/transport behavior.
4. **Deployment:** source defaults permit non-Secure cookies. Loopback listeners do not establish the public TLS/tunnel path; selected process environment inspection is inconclusive. Confirm the deployment's actual access path and cookie configuration before claiming transport security.
5. **Host isolation:** sampled job outputs are 0644 under /tmp; NVIDIA nodes are 0666; ConstrainDevices is absent; MPS directory/control socket are 0777/0666. Review private output locations, GPU constraints and MPS namespace access under separate operator approval. Do not change active host settings as part of this report.
6. **Unverified controls:** production DB least privilege/RLS/backups, upstream rate limiting, real-browser XSS/CSRF, session races and live Slurm negative access remain outside this study. Do not run broad stress/penetration tests merely to enlarge the test count.

No live Slurm jobs, model inference, GPU workloads, production-account mutations or existing-service restarts occurred. The only database process started/stopped was the explicitly isolated temporary PostgreSQL test cluster. Detailed sources, cases, commands and limits are in the accompanying matrix, academic draft and raw evidence.
