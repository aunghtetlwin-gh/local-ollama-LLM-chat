# Local Ollama LLM Chat

A lightweight local chat application built with FastAPI, Ollama, PostgreSQL, and a single-page web interface. Conversations are persisted in PostgreSQL, responses stream to the browser, and each assistant message records the model that generated it.

New to the codebase? Read [CODE_GUIDE.md](CODE_GUIDE.md) for an explanation of the architecture, important files, message flow, and recommended learning order.

## Features

- Streaming responses from a local Ollama server
- Persistent conversation history
- Create, reopen, and delete conversations
- Per-message model tracking
- Self-service email/password registration and login with Argon2id password hashes
- PostgreSQL-backed browser sessions and private per-user conversations
- Selectable Ollama models
- Docker support for the application and PostgreSQL
- FastAPI health and model endpoints

## Requirements

- [Ollama](https://ollama.com/) running locally
- Python 3.10 or newer for a native installation
- PostgreSQL 14 or newer, or Docker with Docker Compose

The application currently supports these models:

- `qwen3:1.7b`
- `qwen3:8b` (default)
- `gemma4:12b`

Pull them before starting the application:

```bash
ollama pull qwen3:1.7b
ollama pull qwen3:8b
ollama pull gemma4:12b
```

## Configuration

Create a `.env` file in the project root:

```dotenv
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=ollama_chat
DB_USER=ollama_user
DB_PASSWORD=change-me
SESSION_COOKIE_SECURE=false
SESSION_TTL_SECONDS=86400
```

When using `docker compose`, the application overrides `DB_HOST` and `DB_PORT` with `127.0.0.1:5433` to reach the containerized database through its published host port.

Session cookies use `HttpOnly`, `SameSite=Lax`, and `Path=/`. `SESSION_COOKIE_SECURE=false`
supports the current local HTTP deployment. Session lifetime defaults to 24 hours and
is enforced in PostgreSQL; it does not slide with activity. Set the lifetime to a positive
number of seconds. No email service or external identity provider is used.

## Authentication deployment and existing-history migration

The application never runs migrations automatically. The following commands are for
an explicitly approved future deployment; editing these files does not apply them.
Do not run the old application after ownership migration: it cannot create owned chats.

1. Stop application writes, keeping PostgreSQL running:

   ```bash
   docker compose stop app
   ```

2. Take a new PostgreSQL custom-format backup without overwriting existing backups.
   Run this block from the project directory. Proceed only if both commands succeed:

   ```bash
   mkdir -p backups
   backup_file=$(mktemp backups/ollama-chat-before-auth.XXXXXX.dump)
   if docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' > "$backup_file"; then
       docker compose exec -T db pg_restore --list < "$backup_file"
   else
       echo "Backup failed. Do not migrate." >&2
   fi
   ```

   `pg_restore --list` checks that the archive can be read; it does not restore or
   alter any database. A full restore rehearsal should use a separate database.

3. Build the updated image and apply only the authentication migration:

   ```bash
   docker compose build app
   docker compose run --rm --no-deps app python migrate.py auth
   ```

4. Start the updated application, then open `http://127.0.0.1:8000/register` and
   register your account first:

   ```bash
   docker compose up -d --no-deps app
   ```

   Registration automatically logs you in. Chat APIs return `503` with a setup
   message until ownership migration completes; historical chats are never public.

5. Assign historical conversations and enforce ownership:

   ```bash
   docker compose run --rm --no-deps app python migrate.py ownership
   ```

   - Exactly one registered user: all existing conversations are assigned to that user.
   - Zero users: the transaction aborts and asks you to register first.
   - Multiple users: the transaction aborts; select an owner explicitly:

     ```bash
     docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT id, email FROM users ORDER BY id"'
     docker compose run --rm --no-deps app python migrate.py ownership --owner-id 1
     ```

     Replace `1` with the intended user's actual ID. A nonexistent owner aborts.

6. Refresh the chat page. Existing history should appear under its assigned owner.
   A second account must see only its own chats. No restart is needed after step 5.

Migrations are transactional and recorded in `schema_migrations`; rerunning an applied
migration makes no changes. The ownership migration locks users and conversations so
registration cannot race owner selection. It adds `conversations.user_id`, backfills it,
then enforces its user foreign key and `NOT NULL`. It preserves conversation IDs,
titles, timestamps, message contents, and models. Messages inherit their conversation's
ownership. No tables or history are deleted.

For native execution, use `python migrate.py auth` and `python migrate.py ownership`
from the configured environment instead of the Compose one-off commands. Do not assume
the native `.env` port is the container database port; Compose explicitly uses `5433`.

## Registration and sessions

`GET /register` serves an email/password/confirmation form. `POST /register` accepts
JSON with `email`, `password`, and `password_confirmation`. Email is trimmed and
lowercased for both registration and login and has a database uniqueness constraint.
Passwords must match and contain 8–1024 characters. Argon2id hashes include a random
salt; passwords are never written to logs or stored as plaintext. Duplicate email
registration returns `409`. User and session creation commit together.

`GET /login` serves the existing-user form; `POST /login` accepts JSON with `email`
and `password`. Successful registration/login sets an opaque session cookie and the
browser navigates to `/`. PostgreSQL stores only a SHA-256 digest of the random session
token. Login replaces the browser's previous session. `POST /logout` revokes that
session and clears the cookie. `GET /auth/session` returns the current user's ID/email.

Unauthenticated page access redirects to `/login`; protected APIs return `401`.
The UI redirects and clears displayed chats on expiry, checks sessions on focus and
once per minute, and provides a logout button. An already authorized stream may finish
server-side after session expiry/logout; new requests require a valid session, and
assistant persistence still checks conversation ownership.

Email verification, password-reset email, MFA, CSRF framework, throttling, and HTTPS
setup are outside this stage. `/health` and FastAPI documentation retain their existing
behavior. There is no public account-management or password-reset endpoint.

## Database setup

Create the database and user, then run the following schema in the configured database:

```sql
CREATE TABLE conversations (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL DEFAULT 'New Chat',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE messages (
    id BIGSERIAL PRIMARY KEY,
    conversation_id BIGINT NOT NULL
        REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL
        CHECK (role IN ('system', 'user', 'assistant')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    model TEXT
);
```

For an existing database created before model tracking was added, run:

```sql
ALTER TABLE messages ADD COLUMN IF NOT EXISTS model TEXT;
```

## Run with Docker Compose

Keep Ollama running on the host, then start the application and database:

```bash
docker compose up --build -d
```

On the first run, initialize the schema from the previous section:

```bash
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

Paste the schema into the PostgreSQL prompt, then open <http://127.0.0.1:8000>.

For a new database, also apply `migrate.py auth`, register, and apply `migrate.py ownership`
as described above. The schema block is the original chat schema used as the migration base.

Useful commands:

```bash
docker compose logs -f app
docker compose ps
docker compose down
```

Conversation data is retained in the `postgres_data` Docker volume when the containers stop.

## Run locally

Create and activate a virtual environment, then install the dependencies:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Make sure Ollama and PostgreSQL are running and the database schema has been created. Start the web server with:

```bash
uvicorn server:my_api --host 127.0.0.1 --port 8000 --reload
```

Open <http://127.0.0.1:8000> in a browser.

## API

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/` | Serve the chat interface |
| `GET`, `POST` | `/register` | Registration page / create account and session |
| `GET`, `POST` | `/login` | Login page / create session |
| `POST` | `/logout` | Revoke session and clear cookie |
| `GET` | `/auth/session` | Current authenticated user |
| `GET` | `/health` | Return application and configuration status |
| `GET` | `/models` | List supported models and the default model |
| `GET` | `/conversations` | List conversations, newest first |
| `GET` | `/conversations/{id}` | Return a conversation and its messages |
| `DELETE` | `/conversations/{id}` | Delete a conversation and its messages |
| `POST` | `/chat` | Send a message and stream the assistant response |

`/models`, conversation routes, and `/chat` require a session. Conversations are scoped
to the authenticated user; another user's ID returns `404`. Messages are also checked
through the parent conversation in SQL before reads/writes. The browser cannot select
an owner by submitting a user ID.

Example chat request (with a cookie jar from an authenticated API client):

```bash
curl --no-buffer http://127.0.0.1:8000/chat \
  --cookie cookies.txt \
  -H 'Content-Type: application/json' \
  -d '{"message":"Hello!","model":"qwen3:8b"}'
```

To continue a conversation, include its ID:

```json
{
  "conversation_id": 1,
  "message": "Tell me more.",
  "model": "qwen3:8b"
}
```

The `/chat` response includes the conversation ID in the `X-Conversation-ID` header and the selected model in `X-Ollama-Model`.

## Troubleshooting

- **Ollama connection error:** confirm Ollama is running and available at `http://127.0.0.1:11434`.
- **Unsupported model:** use one of the models returned by `GET /models`. To add another model, update `AVAILABLE_MODELS` in `server.py` and pull it with Ollama.
- **Database connection error:** verify the `.env` values and confirm PostgreSQL is listening on the configured port.
- **Missing table or column:** apply the schema in the database setup section, including the `model` column migration for older databases.

## Project structure

```text
.
├── server.py            # FastAPI application and Ollama/PostgreSQL integration
├── index.html           # Browser chat interface
├── requirements.txt     # Python dependencies
├── Dockerfile           # Application image
├── docker-compose.yml   # Application and PostgreSQL services
├── db_test.py           # PostgreSQL connectivity check
└── ollama_api_test.py   # Direct Ollama API test
```

## Isolated tests

```bash
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
```

Tests block real Psycopg and Ollama connections. They use an in-memory SQLite adapter
for application SQL and stub Ollama's streamed response. Migration-runner tests use
fakes: they do not execute migration SQL. PostgreSQL DDL, locking, and rollback behavior
still need a separate approved migration rehearsal before deployment.
