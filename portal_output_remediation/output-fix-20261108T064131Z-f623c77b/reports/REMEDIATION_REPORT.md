# Secure historical stdout fix — isolated implementation

Status: **implemented and tested in an isolated copy; NOT deployed**. Candidate `portal-output-v1`, based on `portal-security-v1-b893d3a5f7c1`. Only application changes are `portal/app.py` and new `portal/job_output.py`. Original and deployed source hashes are unchanged. Managed PID 1565020 remains active/running with NRestarts=0 and the original release directory; fallback PID 2019096 and start ticks match prior evidence.

## Investigation and bounded scope

The previous endpoint checked Slurm job identity and username (no administrator output bypass), then always opened `/tmp/slurm-<jobid>.out`. Saved accounting metadata for jobs 127 and 129 instead identifies custom stdout paths in the preserved MPS jobs tree. No real output contents were opened in this task. Their prior zero-byte existence observations are historical metadata, not a newly read output result.

The installed Slurm executable reports 26.05.4. An offline `slurmrestd --generate-openapi-spec -d v0.0.45 -s slurmctld,slurmdbd` invocation generated the installed API schema without querying jobs or starting a service. It confirms controller `job_id`, `user_name`, `stdout_expanded`, `current_working_directory`, and accounting `job_id`, `user`, `stdout`, `stdout_expanded`, `working_directory`. Full schema and exact invocation/exit status are retained. Saved accounting records provide `StdOut`, `WorkDir`, job identity and owner; no new live accounting query was needed.

[Slurm filename-pattern documentation](https://slurm.schedmd.com/sbatch.html#SECTION_FILENAME-PATTERN) and the installed manpage describe additional array, step, node, task and name substitutions. This deliberately narrow implementation supports raw `%%`, `%j`, and `%1j` through `%10j`; it rejects all other raw substitutions, unsupported widths and backslash disable-expansion syntax. `stdout_expanded` is already literal and is never expanded a second time, including literal percent sequences. This avoids guessing array or step identities.

## Security policy and implementation

1. The existing scheduler-first ownership check and 90-day accounting fallback are preserved. The function now returns the exact ownership-checked record, avoiding an independent lookup with a potentially different identity. Unauthorized users and administrators cannot reach path resolution, UID lookup or file access for a foreign job.
2. Prefer accounting raw `stdout`, expanding only the supported tokens once. Otherwise use literal `stdout_expanded`. Relative paths require an absolute, lexically safe WorkDir from that same record. Client query fields cannot select a path.
3. Exact `/tmp/slurm-<authorized-jobid>.out` remains supported. When output metadata is absent/empty, only that legacy fixed path is used. Explicit invalid, missing-on-disk, unsupported or out-of-policy metadata NEVER triggers fallback to an unrelated file.
4. Custom paths require operator-controlled `PORTAL_OUTPUT_ROOTS`, a JSON list of dedicated output-only directories. Default `[]` denies all custom paths. The proposed narrow root is `/home/lailai/slurm_contention_runs/mps-20261104T082034Z-cee9c5d4/jobs`. No directory is enabled in production by this package. Broad roots such as `/`, `/tmp`, home-directory roots, and sensitive system trees are rejected. Prefix checks include a directory separator.
5. Reject traversal components, redundant separators, backslashes, controls, relative/invalid roots and malformed policies before opening any output file. A malformed policy yields generic 503; unavailable/unsafe outputs yield concealed 404.
6. Walk from `/` using directory descriptors, `O_DIRECTORY` and `O_NOFOLLOW` on EVERY parent, then `O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC` for the final file. This removes the old parent-symlink weakness and avoids a realpath-then-open race. No recursive search, shell expansion or arbitrary pathname parameter is introduced.
7. Preserve regular-file, exact Linux UID, 1 MiB stat limit and bounded-read/growth checks. Additionally reject hard-linked files (`st_nlink != 1`). An authorized empty regular file returns HTTP 200 with `output: ""`.

Scheduler metadata can include a filename originally chosen by its submitting user. It is therefore NOT sufficient authorization for arbitrary filesystem access: the root allowlist and UID checks are both essential. Operators must approve only directories dedicated to output, containing no credentials, databases or other private application files. An allowlist is not OS isolation and cannot make a badly chosen output root safe. Do not allow entire home/project trees to avoid selecting this boundary.

## Regression validation

**190 passed, zero failed, zero skipped, exit code 0**: 108 existing portal regression cases and 82 new output/path cases. Runtime assertions match the recorded production Python and all recorded production package versions, including Python 3.10.12, FastAPI 0.141.1, Starlette 1.7.0 and Pydantic 2.13.5. Extra test-only dependencies are permitted. One existing TestClient/httpx deprecation warning remains.

Coverage includes standard/legacy paths; absolute, relative and expanded custom paths; empty files; completed-accounting fallback; `%j` padding and one-pass literals; unsupported tokens; traversal and forbidden roots; malformed metadata/policy; missing files; leaf/parent/root symlinks; directories, FIFOs, hard links; wrong UID; oversize and growth; scheduler failures; owner/admin boundaries; query override rejection; and pure path resolution of saved job 127/129 patterns without disk access. Denial cases assert no content read, and foreign-owner cases assert no path/UID resolution or file open.

The initial sandbox run timed out after 120 seconds with no completed test result and no retained partial stdout; its failed attempt record is preserved separately. It is not counted as a pass or attributed definitively to an application defect. The same isolated suite completed outside the sandbox in 30.92 seconds. Exact command/environment assertions, raw output and JUnit results are in `raw/`. The two old output-file test mocks were adapted only in the isolated copy to mock the new open-helper boundary; new tests exercise the real descriptor traversal.

## Compatibility and residual limitations

- New helper has no additional dependency; Linux descriptor-relative open support is required and tested here. Authentication, roles, job mutation rules, database schema, API count and response schema do not change.
- Custom paths remain denied unless the operator approves roots. Files outside approved roots, arrays/steps requiring unsupported raw patterns, symlinked directory trees, hard-linked outputs, oversized files and inaccessible owner-only files remain intentionally unsupported. No chmod, impersonation or administrator bypass is proposed.
- The existing 90-day accounting lookup window remains unchanged. Missing archived accounting or actual retention deletion still yields 404. Files available only on remote compute nodes cannot be read locally.
- Application file UID checks do not provide Slurm/cgroup or OS-level isolation. The single service UID may legitimately lack access to another researcher's private filesystem. No permissions should be weakened to bypass that condition.
- Live owner-authenticated output retrieval was not tested. Post-deployment browser checks are required; pure fixture success is not production acceptance. Existing job files and records are never rewritten.

## Artifacts and preservation

`patches/historical-output.patch` contains only the app change and new helper. `release_manifest.json` contains full candidate/base SHA-256 values. `evidence/source-preservation.json` verifies all captured original and deployed Python/frontend files remain unchanged. `evidence/service-preservation.json` records unchanged service PID/directory and fallback start ticks. `FILES_SHA256.json` seals this package after validation. No production DB/accounts, output files, services, Slurm/GPU settings or existing evidence packages were changed. This is targeted source/service preservation verification, not a new full rehash of every historical LLM/MPS artifact.
