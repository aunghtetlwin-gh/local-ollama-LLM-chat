from datetime import datetime, timedelta, timezone

import psycopg
import pytest

import auth


def test_registration_hash_and_auto_login(client, db, register_user):
    response = register_user(client, "  OWNER@Example.COM  ")
    assert response.status_code == 201
    assert response.json()["user"]["email"] == "owner@example.com"
    email, password_hash = db.raw.execute("SELECT email, password_hash FROM users").fetchone()
    assert password_hash.startswith("$argon2id$")
    assert auth.password_hasher.verify(password_hash, "correct horse battery")
    token = client.cookies.get(auth.COOKIE_NAME)
    stored = db.raw.execute("SELECT token_hash FROM sessions").fetchone()[0]
    assert stored == auth.token_digest(token) and stored != token
    assert "correct horse battery" not in repr(db.queries)
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=lax" in response.headers["set-cookie"]
    assert client.get("/").status_code == 200
    assert client.get("/auth/session").json()["user"]["email"] == email


@pytest.mark.parametrize("payload", [
    {"email": "owner@example.com", "password": "abcdefgh", "password_confirmation": "different"},
    {"email": "invalid", "password": "abcdefgh", "password_confirmation": "abcdefgh"},
    {"email": "owner@example.com", "password": "short", "password_confirmation": "short"},
])
def test_invalid_registration_creates_nothing(client, db, payload):
    assert client.post("/register", json=payload).status_code == 400
    assert db.raw.execute("SELECT count(*) FROM users").fetchone()[0] == 0
    assert db.raw.execute("SELECT count(*) FROM sessions").fetchone()[0] == 0


def test_duplicate_normalized_email(client, db, register_user):
    assert register_user(client).status_code == 201
    original = client.cookies.get(auth.COOKIE_NAME)
    assert register_user(client, " OWNER@EXAMPLE.COM ").status_code == 409
    assert client.cookies.get(auth.COOKIE_NAME) == original
    assert db.raw.execute("SELECT count(*) FROM users").fetchone()[0] == 1


def test_session_failure_rolls_back_registration(client, db, monkeypatch, register_user):
    def fail(*args):
        raise psycopg.OperationalError("Do not expose query parameters")
    monkeypatch.setattr(auth, "create_session", fail)
    response = register_user(client)
    assert response.status_code == 503
    assert "query parameters" not in response.text
    assert db.raw.execute("SELECT count(*) FROM users").fetchone()[0] == 0
    assert not client.cookies.get(auth.COOKIE_NAME)


def test_login_rotation_logout_and_replay(client, db, register_user):
    register_user(client)
    old = client.cookies.get(auth.COOKIE_NAME)
    response = client.post("/login", json={"email": " OWNER@EXAMPLE.COM ", "password": "correct horse battery"})
    assert response.status_code == 200
    token = client.cookies.get(auth.COOKIE_NAME)
    assert token != old
    assert db.raw.execute("SELECT count(*) FROM sessions WHERE token_hash = ?", (auth.token_digest(old),)).fetchone()[0] == 0
    assert client.post("/logout").status_code == 200
    assert not client.cookies.get(auth.COOKIE_NAME)
    assert db.raw.execute("SELECT count(*) FROM sessions").fetchone()[0] == 0
    client.cookies.set(auth.COOKIE_NAME, token)
    assert client.get("/auth/session").status_code == 401
    assert client.get("/").headers["location"] == "/login"


@pytest.mark.parametrize("email,password", [("owner@example.com", "wrong"), ("missing@example.com", "wrong")])
def test_invalid_login(client, register_user, email, password):
    register_user(client)
    client.post("/logout")
    response = client.post("/login", json={"email": email, "password": password})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password."
    assert not client.cookies.get(auth.COOKIE_NAME)


def test_expired_session(client, db, register_user):
    register_user(client)
    db.raw.execute("UPDATE sessions SET expires_at = ?", (str(datetime.now(timezone.utc) - timedelta(seconds=1)),))
    db.raw.commit()
    assert client.get("/conversations").status_code == 401
    assert client.get("/auth/session").status_code == 401
    assert client.get("/").status_code == 303


@pytest.mark.parametrize("secure", [True, False])
def test_cookie_secure_configuration(client, monkeypatch, register_user, secure):
    monkeypatch.setattr(auth, "COOKIE_SECURE", secure)
    cookie = register_user(client).headers["set-cookie"]
    assert ("; Secure" in cookie) is secure
    assert "Path=/" in cookie and "Domain=" not in cookie


def test_validation_does_not_echo_credentials(client):
    secret = "never-echo-this-password"
    response = client.post("/register", json={"email": [], "password": secret})
    assert response.status_code == 422 and secret not in response.text


def test_setup_blocks_chat_but_allows_registration(client, db, register_user):
    db.raw.execute("DELETE FROM schema_migrations WHERE version = 2")
    db.raw.commit()
    assert register_user(client).status_code == 201
    assert client.get("/auth/session").status_code == 200
    for method, path in [("get", "/models"), ("get", "/conversations"),
                         ("get", "/conversations/1"), ("delete", "/conversations/1")]:
        assert getattr(client, method)(path).status_code == 503
    assert client.post("/chat", json={"message": "Hello"}).status_code == 503


def test_database_failure_denies_access(client, monkeypatch, register_user):
    register_user(client)
    def fail():
        raise psycopg.OperationalError()
    monkeypatch.setattr(auth, "get_db_connection", fail)
    assert client.get("/conversations").status_code == 503


def test_distinct_users_get_distinct_hashes_for_same_password(client, db, register_user):
    register_user(client)
    register_user(client, "second@example.com")
    hashes = [row[0] for row in db.raw.execute("SELECT password_hash FROM users")]
    assert hashes[0] != hashes[1]


def test_session_pages_and_logout_without_cookie(client):
    assert client.get("/register").status_code == 200
    assert client.get("/login").status_code == 200
    response = client.post("/logout")
    assert response.status_code == 200
    assert "Max-Age=0" in response.headers["set-cookie"]
