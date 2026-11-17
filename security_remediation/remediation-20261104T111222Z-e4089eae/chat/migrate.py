"""Explicit, transactional migrations. Never invoked by application startup."""
import argparse
from pathlib import Path

import psycopg

from database import get_db_connection

MIGRATIONS = {
    "auth": (1, "001_users_sessions.sql"),
    "ownership": (2, "002_conversation_ownership.sql"),
}


def run_migration(stage: str, owner_id: int | None = None):
    version, filename = MIGRATIONS[stage]
    if owner_id is not None and (stage != "ownership" or owner_id <= 0):
        raise ValueError("--owner-id must be a positive user ID and is only valid for ownership.")
    sql = (Path(__file__).resolve().parent / "migrations" / filename).read_text()
    with get_db_connection() as conn, conn.cursor() as cur:
        # Serialize migration runners. Any failure rolls back DDL and data together.
        cur.execute("SELECT pg_advisory_xact_lock(734902184)")
        cur.execute("SELECT to_regclass('public.schema_migrations')")
        if cur.fetchone()[0] is not None:
            cur.execute("SELECT version FROM schema_migrations")
            applied = {row[0] for row in cur.fetchall()}
        else:
            applied = set()
        if version in applied:
            print(f"Migration {version} is already applied; no changes made.")
            return
        if version == 2 and 1 not in applied:
            raise ValueError("Run the auth migration and register first.")
        if stage == "ownership":
            cur.execute(
                "SELECT set_config('app.migration_owner_id', %s, true)",
                (str(owner_id) if owner_id is not None else "",),
            )
        cur.execute(sql)
    print(f"Applied migration {version}: {filename}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=MIGRATIONS)
    parser.add_argument("--owner-id", type=int)
    args = parser.parse_args()
    try:
        run_migration(args.stage, args.owner_id)
    except (psycopg.Error, ValueError) as error:
        # Migration errors contain no submitted credentials or conversation content.
        parser.exit(1, f"Migration aborted (transaction rolled back): {error}\n")


if __name__ == "__main__":
    main()
