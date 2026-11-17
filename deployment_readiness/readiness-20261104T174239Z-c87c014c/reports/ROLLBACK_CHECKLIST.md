# Rollback checklist — proposed, not executed

- Retain original hashes, current source-file backups, launch arguments, image ID and environment/volume references before the approved change. Backups containing operational configuration must be private and excluded from research/public artifacts.
- Roll back portal patches by restoring the backed-up prepatch files and restarting only approved processes. This restores the prepatch ON-DISK multi-user application; it cannot promise recovery of8001's unknown legacy in-memory code. Explicitly approve that limitation before the broader upgrade.
- Roll back chat by recreating service app with the retained immutable previous image and unchanged environment/database volume, using --no-deps --no-build. Keep the DB service running.
- Do not restore a stale database/session snapshot for these schema-free application fixes; that can discard legitimate intervening work. Any database recovery is a separate operator procedure.
- If client SSH forwards or service routing were deliberately changed, restore only the recorded approved mapping; no Cloudflare/DNS/Zero Trust change is implied by these patches.
- Drain requests, verify code/image/API metadata, verify the authorized user access path and preserve logs after rollback. A rollback reintroduces the known application weaknesses; require operator risk acceptance and a follow-up window.
- No rollback, restart, live account mutation or deployment has occurred during this assessment.
