# Local Ollama LLM Chat

A lightweight local chat application built with FastAPI, Ollama, PostgreSQL, and a single-page web interface. Conversations are persisted in PostgreSQL, responses stream to the browser, and each assistant message records the model that generated it.

New to the codebase? Read [CODE_GUIDE.md](CODE_GUIDE.md) for an explanation of the architecture, important files, message flow, and recommended learning order.

## Features

- Streaming responses from a local Ollama server
- Persistent conversation history
- Create, reopen, and delete conversations
- Per-message model tracking
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
```

When using `docker compose`, the application overrides `DB_HOST` and `DB_PORT` with `127.0.0.1:5433` to reach the containerized database through its published host port.

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
| `GET` | `/health` | Return application and configuration status |
| `GET` | `/models` | List supported models and the default model |
| `GET` | `/conversations` | List conversations, newest first |
| `GET` | `/conversations/{id}` | Return a conversation and its messages |
| `DELETE` | `/conversations/{id}` | Delete a conversation and its messages |
| `POST` | `/chat` | Send a message and stream the assistant response |

Example chat request:

```bash
curl --no-buffer http://127.0.0.1:8000/chat \
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
