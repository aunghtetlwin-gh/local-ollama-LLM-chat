# Code Guide

## Authentication and ownership

`auth.py` implements registration/login/logout, email normalization, Argon2id hashing,
and PostgreSQL session lookup. `database.py` shares connection configuration without
connecting on import. `register.html` and `login.html` submit JSON and navigate to chat
after the server sets an HttpOnly session cookie. No password or session token is stored
in localStorage. The server stores the password hash and session-token digest only.

`server.py` uses `require_chat_user` on model, conversation, and chat APIs. It checks
that migration 2 has completed, then scopes each conversation operation to the current
user. Message queries use the parent conversation's owner; writes use an ownership-filtered
`INSERT ... SELECT`. This includes assistant persistence after streaming. Ollama still
receives only the selected model, role/content history, and `stream: true`.

`index.html` wraps API fetches to handle expired sessions, clears displayed chats before
redirecting to login, and provides logout. A session expires after the configured fixed
lifetime. The app does not reauthenticate each stream chunk.

The database now also has `users`, `sessions`, and `schema_migrations`.
`conversations.user_id` references `users.id`; `messages` keeps its existing schema.
`migrate.py` runs the two SQL migrations only when explicitly invoked. The ownership
migration selects the sole registered user, rejects zero users, and requires `--owner-id`
when multiple users exist. It does not delete historical data. See README for the exact
backup and deployment sequence; no migration runs during startup.

Tests in `tests/` use isolated in-memory data and block external service connections.
They do not validate migration DDL against a live PostgreSQL server.

You do **not** need to understand every line in this project. Start by understanding how the pieces connect, where configuration lives, and how one chat message moves through the system. You can learn the implementation details when you need to change them.

## What you should understand first

Focus on these five ideas:

1. **The browser displays the interface.** `index.html` contains the page layout, styling, and browser-side JavaScript.
2. **FastAPI is the middle layer.** `server.py` receives browser requests, reads and writes conversations, and contacts Ollama.
3. **Ollama generates answers.** It runs separately at `127.0.0.1:11434`.
4. **PostgreSQL remembers chats.** It stores conversations and messages after the page or server closes.
5. **The `.env` file holds database settings.** It should remain private because it contains a password.

The overall system looks like this:

```text
Browser (index.html)
        |
        | HTTP requests
        v
FastAPI (server.py) --------> PostgreSQL
        |                      conversations + messages
        |
        | Ollama API request
        v
Ollama (local language model)
```

## What you do not need to understand yet

You can safely postpone learning:

- Every CSS rule in `index.html`
- Every DOM operation used to build message elements
- The internal implementation of FastAPI, Psycopg, or Ollama
- Docker image layers and networking details
- Old `*.before-*`, `*.backup`, and database dump files
- Every error handler and HTTP header

Those details matter only when you modify or debug that particular area.

## The files that matter

### `server.py`

This is the main backend application and the most important file to understand.

#### Configuration

Near the top of the file you will find:

- `DEFAULT_MODEL_NAME`: the model selected by default
- `AVAILABLE_MODELS`: models the user may select
- `OLLAMA_CHAT_URL`: where the Ollama API is running
- `OLLAMA_TIMEOUT`: how long the server waits for Ollama
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`: database settings loaded from `.env`

If you want to support another Ollama model, pull it with Ollama and add its exact name to `AVAILABLE_MODELS`.

#### Request model

`ChatRequest` defines the JSON accepted by `POST /chat`:

```json
{
  "conversation_id": 1,
  "message": "Hello",
  "model": "qwen3:8b"
}
```

`conversation_id` may be omitted for a new conversation. `message` is the user's text, and `model` selects the Ollama model.

#### Database helpers

These functions keep SQL operations separate from the route logic:

- `get_db_connection()` connects to PostgreSQL.
- `make_conversation_title()` turns the first message into a short title.
- `create_conversation()` inserts a new conversation.
- `conversation_exists()` validates an existing conversation ID.
- `save_message()` stores a user or assistant message.
- `get_conversation_messages()` loads the complete chat history.

You do not need to memorize the SQL. Understand that `conversations` contains one row per chat and `messages` contains many rows linked to a conversation.

#### API routes

Routes are functions marked with decorators such as `@my_api.get(...)`:

- `GET /` serves `index.html`.
- `GET /health` confirms the backend is running.
- `GET /models` tells the UI which models are available.
- `GET /conversations` lists saved chats.
- `GET /conversations/{id}` loads one saved chat.
- `DELETE /conversations/{id}` deletes a chat.
- `POST /chat` processes a message and streams the answer.

The `/chat` route is the core of the application. Read it in sections rather than line by line.

### `index.html`

This file contains three technologies together:

- **HTML** defines buttons, text areas, sidebars, and other elements.
- **CSS** controls colors, spacing, sizing, and responsive layout.
- **JavaScript** calls the backend and updates the page.

The main JavaScript state variables are:

- `currentConversationId`: the open chat, or `null` for a new chat
- `messages`: messages displayed in the current chat
- `isSending`: prevents two requests from being sent simultaneously
- `conversations`: saved conversation summaries
- `availableModels`: models returned by the backend

The most useful functions to recognize are:

- `loadModels()` fills the model selector.
- `refreshConversations()` reloads the sidebar.
- `loadConversation()` opens a saved conversation.
- `startNewChat()` clears the current chat.
- `deleteConversation()` asks the backend to remove a chat.
- `sendMessage()` sends the user's message and reads the streamed response.
- `renderMessages()` and `renderConversationList()` redraw information on screen.

If you only want to change colors or layout, work in the CSS and avoid changing these functions. If you want to change chat behavior, begin with `sendMessage()` and the matching `/chat` route in `server.py`.

### `.env`

This file provides database configuration without placing passwords in Python code:

```dotenv
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=ollama_chat
DB_USER=ollama_user
DB_PASSWORD=your-password
```

Never commit `.env` to Git or paste its password into documentation. The existing `.gitignore` excludes it.

### `requirements.txt`

This lists the Python packages that must be installed:

- `fastapi`: web API framework
- `uvicorn`: server that runs the FastAPI application
- `psycopg[binary]`: PostgreSQL driver
- `python-dotenv`: loads values from `.env`

You normally edit this file only when adding or removing a Python dependency.

### `Dockerfile`

This describes how to build the application container. It:

1. Starts with Python 3.10.
2. Installs packages from `requirements.txt`.
3. copies `server.py` and `index.html`.
4. Runs the application with Uvicorn on port 8000.

You usually change it only when the application needs another file, system package, or startup command.

### `docker-compose.yml`

This starts two services:

- `db`: PostgreSQL, with persistent data in the `postgres_data` volume
- `app`: the FastAPI application

The app uses host networking so it can reach the host's Ollama server at `127.0.0.1:11434`. PostgreSQL is published on host port `5433` for the containerized app.

### Test and backup files

- `db_test.py` checks the database connection and prints stored rows.
- `ollama_api_test.py` sends a test request directly to Ollama.
- `*.before-*`, `*.backup`, and files in `backups/` are recovery snapshots. They are not part of the running application.

## What happens when you send a message

Understanding this flow is more valuable than memorizing individual lines:

1. The user clicks Send in the browser.
2. `sendMessage()` in `index.html` sends JSON to `POST /chat`.
3. FastAPI validates the JSON using `ChatRequest`.
4. The backend creates a conversation if this is the first message.
5. The user's message is saved in PostgreSQL.
6. All messages in that conversation are loaded to give Ollama context.
7. The backend sends that history and selected model to Ollama.
8. Ollama generates its response in small chunks.
9. FastAPI immediately streams each chunk to the browser.
10. The browser appends the chunks so the answer appears progressively.
11. After Ollama finishes, the complete assistant response and model name are saved in PostgreSQL.

One consequence of this design is that an interrupted Ollama response may appear partly in the browser but will not be saved unless the response finishes successfully.

## The database relationships

There are two tables:

```text
conversations
  id
  title
  created_at
  updated_at
       |
       | one conversation has many messages
       v
messages
  id
  conversation_id
  role
  content
  created_at
  model
```

`messages.conversation_id` points to `conversations.id`. Deleting a conversation also deletes its messages because the foreign key uses `ON DELETE CASCADE`.

The `role` identifies who wrote a message:

- `user`: the person using the chat
- `assistant`: the Ollama model
- `system`: special instructions for a model, although the current UI does not create these

## Common changes and where to make them

| Goal | Start here |
| --- | --- |
| Add or remove a selectable model | `AVAILABLE_MODELS` in `server.py` |
| Change the default model | `DEFAULT_MODEL_NAME` in `server.py` |
| Change colors or spacing | CSS in `index.html` |
| Change how messages look | Rendering functions in `index.html` |
| Change chat request behavior | `sendMessage()` and `POST /chat` |
| Add a new API endpoint | Route section in `server.py` |
| Store more message information | Database schema, SQL helpers, and API output |
| Change database credentials | `.env` |
| Change ports or containers | `docker-compose.yml` and possibly `Dockerfile` |

When changing the database structure, update all three places that depend on it: the database schema, SQL queries in `server.py`, and any UI code that consumes the new field.

## A simple debugging order

When something does not work, test the layers from the bottom up:

1. Run `ollama list` and confirm the selected model exists.
2. Run `python ollama_api_test.py` to test Ollama without the application.
3. Run `python db_test.py` to test PostgreSQL without the application.
4. Open `http://127.0.0.1:8000/health` to test FastAPI.
5. Open `http://127.0.0.1:8000/models` to check model configuration.
6. Check the application terminal or `docker compose logs -f app` for errors.
7. Use the browser developer console and Network tab if only the interface fails.

This order helps identify whether a problem belongs to Ollama, PostgreSQL, FastAPI, or the browser.

## Suggested learning order

Learn only enough for the next change you want to make:

1. Read this guide and the main README.
2. Learn basic HTTP concepts: request, response, JSON, method, endpoint, and status code.
3. Read the configuration and route names in `server.py`.
4. Trace the message flow above through `sendMessage()` and `/chat`.
5. Learn basic SQL: `SELECT`, `INSERT`, `UPDATE`, and `DELETE`.
6. Learn JavaScript DOM and `fetch()` only when changing the interface.
7. Learn Docker details only when changing deployment.

You should aim to explain the system in your own words and know where to look—not memorize the code.
