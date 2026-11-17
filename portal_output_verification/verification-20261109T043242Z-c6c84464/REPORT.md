# Historical-output final post-deployment verification

**SUCCESS — read-only automated verification. Final authenticated browser acceptance remains pending.**

Live verification timestamp: 2026-11-09T04:32:42.764642+00:00 (9 November 2026, approximately 11:32 Asia/Bangkok). Supplemental checks completed at 2026-11-09T04:34:23.600517+00:00.

## Active release and health

- Managed PID **2610502**, active/running with Result=success and stable PID; startup completed with no reviewed error markers.
- Release **portal-output-20261108T132323Z-eb2dad35**, working directory `/home/lailai/nectec-changes/portal-output-20261108T132323Z-eb2dad35/portal-release`. Actual process cwd agrees with effective systemd configuration; localhost 8001, no development reload, daemon-reload state clean.
- All four deployed source SHA-256 values exactly match the sealed reviewed candidate. The candidate seal itself verifies. The systemd drop-in also matches exact reviewed bytes.
- Running authentication DB path remains `/home/lailai/slurm-portal/portal_users.db`; no DB migration, login/session creation, account update or service change was performed by verification.
- All **16 exact expected API operations** remain advertised, not merely an equal route count.

| Source | Deployed SHA-256 |
|---|---|
| app.py | `fed3c86942a9164fbaef3d284045a8c3ec97a9f6a62a4695d506c274bd2d4ea3` |
| auth.py | `cae1cf4875fe66d7f2bb23d75ddf61613954d56157e69c0e11bd6f12dfc945d4` |
| job_output.py | `9a50e06b181ba40b8bc8eedc4beb5c6d8aa736938ec990a785e5b9f29b8b588b` |
| slurm_identity.py | `37f24fc6d04162493bb6caa7e8d639c614dfc1b1c0519a937bb7ab2125870744` |

Drop-in SHA-256: `976ff72fa2a4efd37c400d0c82a6e06bdcef549f429311bfa88d29fafa424d18`.

## Active output policy

The running process has exactly the nine approved MPS leaf directories for jobs 123–131, in the reviewed order. No entire home or experiment-parent grant was added. Active canonical JSON SHA-256 is `fea107903acdb8d08cd0172f5582754b12b7c54997b39b2ea2390c80da521b66`, equal to the candidate's canonical policy. The original formatted candidate policy file SHA-256 is `a002a4655b1c29ac1a9e5e519d132d0c8dc3e66ac43bde03f0c33eef6996f653`; these use different serialization formats and should not be compared as raw bytes. Exact drop-in hash additionally binds the installed environment setting.

Nine retained stdout paths were checked by metadata only; their path patterns resolve under the deployed helper with zero real file opens. For jobs **127/129**, the preserved trusted accounting `StdOut`/`WorkDir` records were separately passed to the actual deployed helper and resolve to the expected custom paths. These accounting records are saved evidence, not a fresh Slurm query or a live authenticated output response. The nine-file check uses saved approved path metadata; it is not a claim that all nine raw accounting records were recollected. Metadata at verification still reports the retained stdout files as zero bytes.

Fresh synthetic checks against the deployed helper: **6/6 passed** — custom output, empty output, final symlink rejection, parent symlink rejection, outside-policy denial before open, and legacy fixed-path resolution without output access. Only synthetic temporary contents were read. No real/private job-output contents were opened.

The sealed candidate's **190 passing tests** were revalidated as existing evidence; they were not rerun here. Because deployed source hashes match, those tests provide the isolated owner-first/admin-no-bypass, UID, hardlink, size/growth, authorization and CSRF regression evidence. Metadata and synthetic tests do not replace live authenticated browser acceptance. Legacy `/tmp/slurm-<authorized-jobid>.out` remains the intentional safe exception outside the nine custom roots. Unsupported substitutions and other previously documented limitations remain.

## Authentication, authorization and logs

**37/37 read-only automated checks passed**, with zero failed checks, plus the six fresh helper fixtures and two saved accounting-pattern checks reported separately.

- Anonymous auth/admin/job-list/history/detail/output/node requests return 401. Invalid synthetic session cookie rejected.
- Two malformed-login cases return 422 with generic redacted validation response; synthetic password sentinel is absent from responses and reviewed logs. No real credentials were used, no valid login attempted, and no job mutation request was sent.
- Session and CSRF parameters remain present in API metadata on all six mutation routes. This is not a live authenticated CSRF exercise; actual authenticated role/ownership protections use sealed fixture evidence until browser acceptance.
- Current PID journal records reviewed: **32**. Startup-complete marker observed; no error/traceback/critical/failed-start markers found. Raw journal messages and cookies were not retained. This is bounded marker-based log review, not proof that every possible operational fault has been excluded.

## Rollback and independent fallback

Previous known-good authenticated release `portal-security-v1-b893d3a5f7c1` remains intact. Its original source hashes and fallback source/frontend hashes match. Private backup at `/home/lailai/nectec-changes/portal-output-20261108T132323Z-eb2dad35-before-deploy` exists, mode 0o700; three backed-up Python files match that previous release, and `previous-dropin.conf` matches the exact predeployment override hash. Base unit backup is present. Rollback was verified by metadata/hash evidence, **not executed**. The reviewed rollback checklist restores the prior override and restarts only 8001; no database rollback is needed.

Port **8002** remains HTTP 200 with 16 operations and unchanged API. Its PID **2019096**, start ticks, cwd and command arguments match the baseline; its original source tree is unchanged. It remains a separately launched process using `/home/lailai/slurm-portal`, rather than the new managed release. No restart or change to it occurred.

## Remaining operator acceptance

1. Through the normal SSH-forwarded browser, authenticate with existing administrator/researcher accounts; confirm role controls and history, then session/logout behavior.
2. Owner `lailai` checks jobs **127 and 129**: expect HTTP 200 with empty output if accounting and retained files remain unchanged. Empty output is a valid result, not a missing-file error. Do not access another researcher's private output.
3. Complete approved authenticated missing/invalid-CSRF denial and direct researcher denial of administrator routes, without a valid job mutation or changing accounts. Use designated authorized resources/test procedures only.
4. Check an existing authorized standard-output job if available; do not submit a new job just for acceptance.

No further deployment or remediation is indicated by these automated results. Unqualified final portal acceptance awaits those browser checks. Source, service, account, database records, permissions, Slurm/GPU configuration, Cloudflare and Ollama chat were not changed by this verification. HTTP checks naturally append service access logs; new evidence and synthetic tempfiles are the only files created by verification.

## Evidence inventory

`result.json` and `acceptance.csv`: outcome/checks. `evidence/`: selected systemd/process metadata, OpenAPI, full source/policy hashes, rollback checks, historical file metadata, deployed-helper resolution, sealed fixture provenance, fresh synthetic cases and redacted startup-log summary. `verify_readonly.py` and `synthetic_readonly.py` retain the verification source; copied temporary-path pointers are run provenance, not a generic deployment framework. Prior failed verification attempts remain unchanged. `FILES_SHA256.json` seals this new package.
