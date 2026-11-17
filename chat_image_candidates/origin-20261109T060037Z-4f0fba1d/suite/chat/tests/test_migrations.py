"""Runner tests capture SQL; they never execute migrations against a database."""
from pathlib import Path
from unittest.mock import MagicMock

import psycopg
import pytest

import migrate


def fake_connection(monkeypatch, applied):
    conn = MagicMock()
    cur = MagicMock()
    conn.__enter__.return_value = conn
    conn.cursor.return_value.__enter__.return_value = cur
    cur.fetchone.return_value = ("schema_migrations" if applied is not None else None,)
    cur.fetchall.return_value = [(v,) for v in (applied or [])]
    monkeypatch.setattr(migrate, "get_db_connection", lambda: conn)
    return conn, cur


def test_auth_runner_sends_one_transactional_script(monkeypatch):
    conn, cur = fake_connection(monkeypatch, None)
    migrate.run_migration("auth")
    script = cur.execute.call_args.args[0]
    assert "CREATE TABLE users" in script
    assert "CREATE TABLE sessions" in script
    assert "conversations" not in script
    conn.__exit__.assert_called_once_with(None, None, None)


def test_ownership_requires_auth_migration(monkeypatch):
    conn, cur = fake_connection(monkeypatch, None)
    with pytest.raises(ValueError, match="register first"):
        migrate.run_migration("ownership")
    assert not any("ALTER TABLE" in c.args[0] for c in cur.execute.call_args_list)
    assert conn.__exit__.call_args.args[0] is ValueError


@pytest.mark.parametrize("owner,expected", [(None, ""), (9, "9")])
def test_owner_selection_passed_as_parameter(monkeypatch, owner, expected):
    conn, cur = fake_connection(monkeypatch, [1])
    migrate.run_migration("ownership", owner)
    cur.execute.assert_any_call("SELECT set_config('app.migration_owner_id', %s, true)", (expected,))
    assert "LOCK TABLE users IN SHARE MODE" in cur.execute.call_args.args[0]
    conn.__exit__.assert_called_once_with(None, None, None)


def test_applied_migration_is_noop(monkeypatch):
    _, cur = fake_connection(monkeypatch, [1, 2])
    migrate.run_migration("ownership", 99)
    assert not any("ALTER TABLE" in c.args[0] for c in cur.execute.call_args_list)


def test_migration_failure_exits_transaction_with_error(monkeypatch):
    conn, cur = fake_connection(monkeypatch, [1])
    def execute(sql, *args):
        if "ALTER TABLE" in sql:
            raise psycopg.errors.RaiseException("No registered users. Register first.")
    cur.execute.side_effect = execute
    with pytest.raises(psycopg.errors.RaiseException, match="Register first"):
        migrate.run_migration("ownership")
    assert conn.__exit__.call_args.args[0] is psycopg.errors.RaiseException


def test_ownership_script_has_explicit_cardinality_guards():
    sql = (Path(__file__).resolve().parents[1] / "migrations/002_conversation_ownership.sql").read_text()
    # Static safeguards only; PostgreSQL execution remains intentionally untested.
    assert "IF user_count = 0 THEN" in sql and "ELSIF user_count > 1 THEN" in sql
    assert "--owner-id ID" in sql and "Selected owner does not exist" in sql
    assert sql.index("LOCK TABLE users") < sql.index("COUNT(*)") < sql.index("UPDATE conversations")
    assert "FOREIGN KEY (user_id) REFERENCES users(id)" in sql
    assert "ALTER COLUMN user_id SET NOT NULL" in sql
    assert "DELETE FROM" not in sql and "DROP TABLE" not in sql


@pytest.mark.parametrize("stage,owner", [("auth", 1), ("ownership", 0), ("ownership", -1)])
def test_invalid_owner_option_never_connects(stage, owner):
    with pytest.raises(ValueError):
        migrate.run_migration(stage, owner)
