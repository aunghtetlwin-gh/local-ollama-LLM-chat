# NECTEC final deployment-readiness assessment

Start with reports/FINAL_DEPLOYMENT_READINESS.md. **Reviewed fixes are staged and tested, NOT deployed.**

The current cloudflared connector publishes SSH only, not a portal/chat HTTP route. The two portal runtimes advertise different authentication APIs despite sharing current on-disk source.198 isolated compatibility cases passed with zero failed/error/skipped cases; deployed runtime package versions were preserved.

## Evidence

- raw/openapi-8000/8001/8002.json: public route metadata only; no private operations were invoked.
- evidence/runtime.json, portal-use-records.json, portal-historical-log-summary.json, portal-git-history.json: source/runtime/process intent and historical use evidence.
- evidence/cloudflare-current-routing.json: sanitized loaded/config and/diag/tunnel metadata, version, SSH service and nonsecret UUIDs. No token/credential content was read. Earlier unsuccessful journal/metrics attempts remain as evidence.
- evidence/*runtime-packages.json, *staging-packages.json and test-only-extras.json: exact version inventories and additive test-only packages. No production pip upgrade or image rebuild occurred.
- raw/staging-patch-application.json: reviewed patches applied only to staging; resulting hashes match the sealed remediation.
- raw/*-command.json, *.log, *.xml: exact commands, source hashes, environment assertions, exit codes and complete test output.
- reports/compatibility_results.csv and test_cases.csv:198 completed passing cases, with PostgreSQL interpreter limitation explicit.
- reports/portal_route_comparison.csv and portal_route_summary.json: exact operations/parameters/schema differences; not authorization-exploit results.
- reports/dependency_comparison.csv: earlier tests versus deployed and current staged packages.
- reports/DEPLOYMENT_CHECKLIST.md and ROLLBACK_CHECKLIST.md: operator approval, change, smoke and rollback procedures.
- reports/preservation.json, evidence/post-validation-deployment.json, validation.json: unchanged originals/services/container and output consistency.

## Staging isolation and reproduction

The staging/ tree contains isolated copies and one additional test of localhost-forward Origin/session behavior. envs/ and exports/ contain OFFLINE copies of installed packages, and test_extras/ contains only missing test support. They are local execution artifacts, not production installations. Chat tests used a new disposable container from the existing image, network=none, read-only sources/root, no GPU devices and no production secrets or DB mounts. PostgreSQL used only its own private temporary cluster and host Python 3.10.12 with deployed client packages; the main chat79 cases used exact image Python3.10.21.

Exact commands and mount constraints are recorded in raw/. Helper scripts capture this assessment root through /tmp/nectec-readiness-path.txt; do not rerun capture/preparation against the sealed assessment. For reproduction use a NEW copy/root, update that pointer deliberately, choose unused --attempt labels and recheck mounted writable output paths. Test commands refuse existing command records. No helper authorizes deployment.

Capture scripts and version/source inventories provide provenance; no private.env/database/tunnel-token contents were copied. Metadata includes internal hostnames/UUIDs and process/listener information and should be reviewed before public release. Historical copied reports are context, not current runtime results.

FILES_SHA256.json seals publication/evidence/staging-source files; copied envs/, exports/ and test_extras/ are excluded from that output seal and identified separately by version inventories and origins. Prior sealed packages and original files remain unchanged. No remote Cloudflare management API, route/DNS/policy update, GPU workload or model inference occurred.

## Preservation detail

One live portal access log appended the normal GET /openapi.json audit request. Its original byte prefix matches the starting hash; 1,727 other protected files are byte-identical. This expected access logging is distinguished from editing original source/evidence. No production service, image or account was changed. The UTC directory timestamp is 4 November; the assessment began on 5 November in Asia/Bangkok.

Final output validation: 14 checks passed, including the 198 recorded cases, runtime package/interpreter matching, reviewed patch hashes, all four prior evidence seals, route inventory, SSH-only loaded ingress and production container preservation. One access-log append is explicitly accounted for. No deployment occurred.
