# Approval and verification checklist — no deployment executed

## Before any change

- [ ] Operator selects the canonical portal endpoint and acknowledges that restarting legacy port 8001 loads broader authentication/ownership behavior.
- [ ] Confirm consumers of8001/8002 and documented SSH18002→8002; coordinate any forwarding change.
- [ ] Confirm this tunnel's SSH-only rule in dashboard if required; identify any separate browser gateway before applying HTTPS assumptions.
- [ ] Approve maintenance/drain window, exact restart scope and production test-account/session writes separately.
- [ ] Verify four original source hashes against the remediation package and dry-run both reviewed application patches.
- [ ] Securely back up those source files and launch metadata; retain immutable chat image/rollback tag and unchanged DB volume/environment.
- [ ] Record in-flight portal submissions and chat streams; do not retry uncertain submissions automatically.

## Change after separate authorization

- [ ] Apply only the four reviewed runtime-file changes; preserve unrelated Git edits.
- [ ] Restart only the approved portal instances; do not blindly restart/retire either port.
- [ ] Build a separate candidate image from the retained runtime image plus patched server.py, without resolving new dependencies.
- [ ] Recreate only chat service app with --no-deps --no-build using the approved image override.
- [ ] Preserve existing production databases, accounts, secrets, scheduler, GPU and tunnel settings.

## Focused post-deployment checks

- [ ] Verify expected PIDs/image/code hashes and current API metadata on the chosen endpoints.
- [ ] Portal malformed login with a fresh synthetic password sentinel, missing username:422 and no sentinel in response or reviewed logs. No real credential is needed.
- [ ] Use an explicitly authorized existing researcher/test account to verify login and owner-scoped metadata; do not submit a Slurm job. Account/session writes require approval.
- [ ] Verify deployed common identity policy. If admin live negative onboarding is authorized, an unapproved synthetic name must be rejected before record creation. Do not create real researchers as a smoke test.
- [ ] Chat hostile/missing Origin with no valid fallback:403. Matching-origin POST/logout without cookie:200 and no DB mutation. Matching-origin POST/chat without cookie:401 and no inference.
- [ ] Through the actual SSH-forward/browser path, verify legitimate login/session/logout, then a denied hostile-origin request. Authenticated synthetic conversation deletion requires separate permission for its data writes; delete only that explicitly created test record.
- [ ] Do not send a valid inference request as part of these checks.
- [ ] Check session continuity and errors; do not infer browser behavior solely from TestClient.

Any failed control or unexpected routing/identity result stops progression. Keep staging and production evidence clearly separated.
