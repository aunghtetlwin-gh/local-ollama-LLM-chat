"""Isolated SQL/API tests: no PostgreSQL, migration execution, or Ollama access.

SQLite executes the application's data queries with placeholder/error adaptation.
These tests do not replace a future PostgreSQL migration rehearsal.
"""
import sqlite3
import threading
from datetime import datetime, timezone

import psycopg
import pytest
from fastapi.testclient import TestClient as BaseTestClient

def TestClient(*args, **kwargs):
    kwargs.setdefault("headers", {"Origin": "http://testserver"})
    return BaseTestClient(*args, **kwargs)

import auth
import server


class Cursor:
    def __init__(self, db):
        self.db = db
        self.cursor = db.raw.cursor()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.cursor.close()

    def execute(self, sql, params=()):
        self.db.queries.append((sql, params))
        try:
            self.cursor.execute(sql.replace("%s", "?"), params)
        except sqlite3.IntegrityError as error:
            if "UNIQUE" in str(error):
                raise psycopg.errors.UniqueViolation() from None
            raise
        return self

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()


class MemoryDatabase:
    def __init__(self):
        self.raw = sqlite3.connect(":memory:", check_same_thread=False)
        self.raw.create_function("NOW", 0, lambda: str(datetime.now(timezone.utc)))
        self.raw.execute("PRAGMA foreign_keys = ON")
        self.raw.executescript("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY, email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL, CHECK(email = lower(trim(email)))
            );
            CREATE TABLE sessions (
                token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
                expires_at TEXT NOT NULL
            );
            CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY);
            INSERT INTO schema_migrations VALUES (1), (2);
            CREATE TABLE conversations (
                id INTEGER PRIMARY KEY, title TEXT NOT NULL,
                user_id INTEGER NOT NULL REFERENCES users(id),
                created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY,
                conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                role TEXT, content TEXT, model TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        self.lock = threading.RLock()
        self.queries = []

    def __enter__(self):
        self.lock.acquire()
        return self

    def __exit__(self, kind, value, traceback):
        try:
            self.raw.rollback() if kind else self.raw.commit()
        finally:
            self.lock.release()

    def cursor(self):
        return Cursor(self)


@pytest.fixture(autouse=True)
def block_external_services(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Tests must not connect to PostgreSQL or Ollama")
    monkeypatch.setattr(psycopg, "connect", blocked)
    monkeypatch.setattr(server.urllib.request, "urlopen", blocked)


@pytest.fixture
def db(monkeypatch):
    db = MemoryDatabase()
    monkeypatch.setattr(auth, "get_db_connection", lambda: db)
    monkeypatch.setattr(server, "get_db_connection", lambda: db)
    yield db
    db.raw.close()


@pytest.fixture
def client(db):
    with TestClient(server.my_api, follow_redirects=False) as client:
        yield client


@pytest.fixture
def register_user():
    def register(client, email="owner@example.com", password="correct horse battery"):
        return client.post("/register", json={
            "email": email, "password": password, "password_confirmation": password,
        })
    return register
