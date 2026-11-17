"""Local credentials and opaque, PostgreSQL-backed browser sessions."""
import hashlib
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, SecretStr

from database import get_db_connection

BASE_DIR = Path(__file__).resolve().parent
COOKIE_NAME = "ollama_session"
COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "86400"))
if SESSION_TTL_SECONDS <= 0:
    raise ValueError("SESSION_TTL_SECONDS must be positive")

password_hasher = PasswordHasher()  # Argon2id, random salt per password.
router = APIRouter()


class Credentials(BaseModel):
    email: str
    password: SecretStr


class Registration(Credentials):
    password_confirmation: SecretStr


def normalize_email(email: str) -> str:
    email = email.strip().lower()
    if len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise HTTPException(400, "Enter a valid email address.")
    return email


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(cur, user_id: int, previous_token: str | None = None) -> str:
    """Use the caller's transaction so registration and login are atomic."""
    if previous_token:
        cur.execute("DELETE FROM sessions WHERE token_hash = %s", (token_digest(previous_token),))
    token = secrets.token_urlsafe(32)
    cur.execute(
        "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (%s, %s, %s)",
        (token_digest(token), user_id, datetime.now(timezone.utc) + timedelta(seconds=SESSION_TTL_SECONDS)),
    )
    return token


def set_session_cookie(response: Response, token: str):
    response.set_cookie(
        COOKIE_NAME, token, max_age=SESSION_TTL_SECONDS,
        httponly=True, secure=COOKIE_SECURE, samesite="lax", path="/",
    )
    response.headers["Cache-Control"] = "no-store"


def optional_user(request: Request):
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    try:
        with get_db_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """SELECT u.id, u.email FROM sessions s
                   JOIN users u ON u.id = s.user_id
                   WHERE s.token_hash = %s AND s.expires_at > NOW()""",
                (token_digest(token),),
            )
            row = cur.fetchone()
    except psycopg.Error:
        raise HTTPException(503, "Authentication database unavailable.") from None
    return {"id": row[0], "email": row[1]} if row else None


def require_user(request: Request):
    user = optional_user(request)
    if user is None:
        raise HTTPException(401, "Please log in.")
    return user


def require_chat_user(user=Depends(require_user)):
    """Allow registration before history ownership is migrated; deny all chat access."""
    try:
        with get_db_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT EXISTS (SELECT 1 FROM schema_migrations WHERE version = 2)")
            ready = cur.fetchone()[0]
    except psycopg.Error:
        raise HTTPException(503, "Database setup is incomplete.") from None
    if not ready:
        raise HTTPException(503, "Register first, then run the conversation ownership migration.")
    return user


@router.get("/register")
def register_page():
    return FileResponse(BASE_DIR / "register.html", headers={"Cache-Control": "no-store"})


@router.get("/login")
def login_page():
    return FileResponse(BASE_DIR / "login.html", headers={"Cache-Control": "no-store"})


@router.post("/register", status_code=201)
def register(body: Registration, request: Request, response: Response):
    email = normalize_email(body.email)
    password = body.password.get_secret_value()
    if password != body.password_confirmation.get_secret_value():
        raise HTTPException(400, "Passwords do not match.")
    if not 8 <= len(password) <= 1024:
        raise HTTPException(400, "Password must contain between 8 and 1024 characters.")
    password_hash = password_hasher.hash(password)
    try:
        with get_db_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (email, password_hash) VALUES (%s, %s) RETURNING id",
                (email, password_hash),
            )
            user_id = cur.fetchone()[0]
            token = create_session(cur, user_id, request.cookies.get(COOKIE_NAME))
    except psycopg.errors.UniqueViolation:
        raise HTTPException(409, "An account with this email already exists.") from None
    except psycopg.Error:
        # Database errors can include SQL parameters; never log credential operations.
        raise HTTPException(503, "Could not create account. Check database setup.") from None
    set_session_cookie(response, token)
    return {"user": {"id": user_id, "email": email}}


@router.post("/login")
def login(body: Credentials, request: Request, response: Response):
    email = normalize_email(body.email)
    password = body.password.get_secret_value()
    if len(password) > 1024:
        raise HTTPException(401, "Invalid email or password.")
    try:
        with get_db_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT id, password_hash FROM users WHERE email = %s", (email,))
            row = cur.fetchone()
            if row is None:
                raise HTTPException(401, "Invalid email or password.")
            try:
                password_hasher.verify(row[1], password)
            except (VerificationError, InvalidHashError):
                raise HTTPException(401, "Invalid email or password.") from None
            token = create_session(cur, row[0], request.cookies.get(COOKIE_NAME))
    except psycopg.Error:
        raise HTTPException(503, "Authentication database unavailable.") from None
    set_session_cookie(response, token)
    return {"user": {"id": row[0], "email": email}}


@router.post("/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get(COOKIE_NAME)
    if token:
        try:
            with get_db_connection() as conn, conn.cursor() as cur:
                cur.execute("DELETE FROM sessions WHERE token_hash = %s", (token_digest(token),))
        except psycopg.Error:
            raise HTTPException(503, "Could not log out. Please try again.") from None
    response.delete_cookie(COOKIE_NAME, path="/", httponly=True, secure=COOKIE_SECURE, samesite="lax")
    response.headers["Cache-Control"] = "no-store"
    return {"logged_out": True}


@router.get("/auth/session")
def session_status(user=Depends(require_user)):
    return {"user": user}
