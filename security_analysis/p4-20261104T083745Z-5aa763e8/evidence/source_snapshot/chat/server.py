import json
import urllib.error
import urllib.request
from pathlib import Path

import psycopg
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel

from database import DB_NAME, get_db_connection
from auth import optional_user, require_chat_user, router as auth_router


# --------------------------------------------------
# Application setup
# --------------------------------------------------

my_api = FastAPI()

BASE_DIR = Path(__file__).resolve().parent
INDEX_FILE = BASE_DIR / "index.html"

my_api.include_router(auth_router)


@my_api.exception_handler(RequestValidationError)
async def validation_error(request: Request, error: RequestValidationError):
    # FastAPI's default validation output can echo submitted passwords.
    if request.url.path in {"/register", "/login"}:
        return JSONResponse(status_code=422, content={"detail": "Invalid request fields."})
    return await request_validation_exception_handler(request, error)


@my_api.middleware("http")
async def private_responses(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


# --------------------------------------------------
# Ollama configuration
# --------------------------------------------------

DEFAULT_MODEL_NAME = "qwen3:8b"

AVAILABLE_MODELS = [
    "qwen3:1.7b",
    "qwen3:8b",
    "gemma4:12b",
]

OLLAMA_CHAT_URL = "http://127.0.0.1:11434/api/chat"

OLLAMA_TIMEOUT = 120


# --------------------------------------------------
# Request models
# --------------------------------------------------

class ChatRequest(BaseModel):
    conversation_id: int | None = None
    message: str
    model: str = DEFAULT_MODEL_NAME


# --------------------------------------------------
# Database helpers
# --------------------------------------------------

def make_conversation_title(message: str) -> str:
    """
    Use the first user message as the conversation title.
    """

    cleaned = " ".join(message.split())

    if not cleaned:
        return "New Chat"

    if len(cleaned) <= 60:
        return cleaned

    return cleaned[:57] + "..."


def create_conversation(first_message: str, user_id: int) -> int:
    """
    Create a new conversation and return its ID.
    """

    title = make_conversation_title(first_message)

    with get_db_connection() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                INSERT INTO conversations (title, user_id)
                VALUES (%s, %s)
                RETURNING id;
                """,
                (title, user_id),
            )

            row = cur.fetchone()

            return row[0]


def conversation_exists(conversation_id: int, user_id: int) -> bool:
    """
    Check that a conversation exists.
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT id
                FROM conversations
                WHERE id = %s AND user_id = %s;
                """,
                (conversation_id, user_id),
            )

            return cur.fetchone() is not None


def save_message(
    conversation_id: int,
    user_id: int,
    role: str,
    content: str,
    model: str | None = None,
):
    """
    Save one message and update the conversation timestamp.

    User messages normally have model=NULL.
    Assistant messages store the Ollama model that generated them.
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                INSERT INTO messages (
                    conversation_id,
                    role,
                    content,
                    model
                )
                SELECT id, %s, %s, %s FROM conversations
                WHERE id = %s AND user_id = %s
                RETURNING id;
                """,
                (
                    role,
                    content,
                    model,
                    conversation_id,
                    user_id,
                ),
            )

            if cur.fetchone() is None:
                raise HTTPException(404, "Conversation not found.")

            cur.execute(
                """
                UPDATE conversations
                SET updated_at = NOW()
                WHERE id = %s AND user_id = %s;
                """,
                (conversation_id, user_id),
            )


def get_conversation_messages(
    conversation_id: int,
    user_id: int,
):
    """
    Load every message belonging to a conversation.

    Model information is returned for the browser,
    but Ollama itself only needs role + content.
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    id,
                    role,
                    content,
                    created_at,
                    model
                FROM messages
                WHERE conversation_id = %s
                  AND EXISTS (SELECT 1 FROM conversations c
                              WHERE c.id = messages.conversation_id AND c.user_id = %s)
                ORDER BY id;
                """,
                (conversation_id, user_id),
            )

            rows = cur.fetchall()

    return [
        {
            "id": row[0],
            "role": row[1],
            "content": row[2],
            "created_at": row[3],
            "model": row[4],
        }
        for row in rows
    ]


# --------------------------------------------------
# Basic routes
# --------------------------------------------------

@my_api.get("/")
def home(request: Request):
    if optional_user(request) is None:
        return RedirectResponse("/login", status_code=303)
    return FileResponse(INDEX_FILE)


@my_api.get("/health")
def health():
    return {
        "status": "ok",
        "message": "FastAPI is running on lai512",
        "default_model": DEFAULT_MODEL_NAME,
        "available_models": AVAILABLE_MODELS,
        "streaming": True,
        "database": DB_NAME,
        "persistence": True,
        "model_tracking": True,
    }


@my_api.get("/models")
def list_models(user=Depends(require_chat_user)):
    """
    Return selectable Ollama models.
    """

    return {
        "default_model": DEFAULT_MODEL_NAME,
        "models": AVAILABLE_MODELS,
    }


# --------------------------------------------------
# Conversation API
# --------------------------------------------------

@my_api.get("/conversations")
def list_conversations(user=Depends(require_chat_user)):
    """
    Return the current user's conversations.

    Most recently updated conversations appear first.
    """
    user_id = user["id"]

    try:

        with get_db_connection() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                        id,
                        title,
                        created_at,
                        updated_at
                    FROM conversations
                    WHERE user_id = %s
                    ORDER BY updated_at DESC;
                    """,
                    (user_id,),
                )

                rows = cur.fetchall()

    except psycopg.Error as error:

        print(
            "PostgreSQL error while listing conversations:",
            error,
        )

        raise HTTPException(
            status_code=500,
            detail="Could not load conversations.",
        )

    conversations = [
        {
            "id": row[0],
            "title": row[1],
            "created_at": row[2],
            "updated_at": row[3],
        }
        for row in rows
    ]

    return {
        "conversations": conversations
    }


@my_api.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: int, user=Depends(require_chat_user)):
    """Return an owned conversation and all of its messages."""
    user_id = user["id"]

    try:

        with get_db_connection() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                        id,
                        title,
                        created_at,
                        updated_at
                    FROM conversations
                    WHERE id = %s AND user_id = %s;
                    """,
                    (conversation_id, user_id),
                )

                conversation = cur.fetchone()

                if conversation is None:

                    raise HTTPException(
                        status_code=404,
                        detail="Conversation not found.",
                    )

                cur.execute(
                    """
                    SELECT
                        id,
                        role,
                        content,
                        created_at,
                        model
                    FROM messages
                    WHERE conversation_id = %s
                      AND EXISTS (SELECT 1 FROM conversations c
                                  WHERE c.id = messages.conversation_id AND c.user_id = %s)
                    ORDER BY id;
                    """,
                    (conversation_id, user_id),
                )

                message_rows = cur.fetchall()

    except HTTPException:
        raise

    except psycopg.Error as error:

        print(
            "PostgreSQL error while loading conversation:",
            error,
        )

        raise HTTPException(
            status_code=500,
            detail="Could not load conversation.",
        )

    messages = [
        {
            "id": row[0],
            "role": row[1],
            "content": row[2],
            "created_at": row[3],
            "model": row[4],
        }
        for row in message_rows
    ]

    return {
        "conversation": {
            "id": conversation[0],
            "title": conversation[1],
            "created_at": conversation[2],
            "updated_at": conversation[3],
        },
        "messages": messages,
    }


@my_api.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: int, user=Depends(require_chat_user)):
    """
    Delete an owned conversation.

    PostgreSQL ON DELETE CASCADE automatically
    deletes all messages belonging to it.
    """
    user_id = user["id"]

    try:

        with get_db_connection() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    DELETE FROM conversations
                    WHERE id = %s AND user_id = %s
                    RETURNING id;
                    """,
                    (conversation_id, user_id),
                )

                deleted = cur.fetchone()

                if deleted is None:

                    raise HTTPException(
                        status_code=404,
                        detail="Conversation not found.",
                    )

    except HTTPException:
        raise

    except psycopg.Error as error:

        print(
            "PostgreSQL error while deleting conversation:",
            error,
        )

        raise HTTPException(
            status_code=500,
            detail="Could not delete conversation.",
        )

    return {
        "deleted": True,
        "conversation_id": conversation_id,
    }


# --------------------------------------------------
# Chat API
# --------------------------------------------------

@my_api.post("/chat")
def chat(request: ChatRequest, user=Depends(require_chat_user)):
    user_id = user["id"]

    user_message = request.message.strip()
    selected_model = request.model.strip()

    if not user_message:

        raise HTTPException(
            status_code=400,
            detail="Message cannot be empty.",
        )

    if selected_model not in AVAILABLE_MODELS:

        raise HTTPException(
            status_code=400,
            detail={
                "message": "Unsupported model.",
                "selected_model": selected_model,
                "available_models": AVAILABLE_MODELS,
            },
        )


    # --------------------------------------------------
    # Determine conversation
    # --------------------------------------------------

    try:

        if request.conversation_id is None:

            conversation_id = create_conversation(
                user_message, user_id
            )

        else:

            conversation_id = request.conversation_id

            if not conversation_exists(
                conversation_id, user_id
            ):

                raise HTTPException(
                    status_code=404,
                    detail="Conversation not found.",
                )


        # User messages do not have a generating model.
        save_message(
            conversation_id=conversation_id,
            user_id=user_id,
            role="user",
            content=user_message,
            model=None,
        )


        # Load complete persistent history.
        database_messages = (
            get_conversation_messages(
                conversation_id, user_id
            )
        )

    except HTTPException:
        raise

    except psycopg.Error as error:

        print(
            "PostgreSQL error before Ollama request:",
            error,
        )

        raise HTTPException(
            status_code=500,
            detail="Could not save or load conversation.",
        )


    # --------------------------------------------------
    # Build Ollama conversation history
    # --------------------------------------------------

    ollama_messages = [
        {
            "role": message["role"],
            "content": message["content"],
        }
        for message in database_messages
    ]


    data = {
        "model": selected_model,
        "messages": ollama_messages,
        "stream": True,
    }


    ollama_request = urllib.request.Request(
        OLLAMA_CHAT_URL,
        data=json.dumps(data).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
        },
    )


    # --------------------------------------------------
    # Connect to Ollama
    # --------------------------------------------------

    try:

        ollama_response = urllib.request.urlopen(
            ollama_request,
            timeout=OLLAMA_TIMEOUT,
        )

    except urllib.error.HTTPError as error:

        raise HTTPException(
            status_code=502,
            detail=f"Ollama returned HTTP {error.code}",
        )

    except urllib.error.URLError as error:

        raise HTTPException(
            status_code=502,
            detail=f"Could not connect to Ollama: {error.reason}",
        )


    # --------------------------------------------------
    # Stream Ollama response
    # --------------------------------------------------

    def stream_ollama_response():

        assistant_parts = []

        completed = False


        with ollama_response as response:

            for raw_line in response:

                if not raw_line.strip():
                    continue

                try:

                    chunk = json.loads(
                        raw_line.decode("utf-8")
                    )

                except json.JSONDecodeError:
                    continue


                content = (
                    chunk
                    .get("message", {})
                    .get("content", "")
                )


                if content:

                    assistant_parts.append(
                        content
                    )

                    yield content


                if chunk.get("done"):

                    completed = True

                    break


        assistant_content = "".join(
            assistant_parts
        ).strip()


        if completed and assistant_content:

            try:

                # Store exactly which model generated
                # this assistant response.
                save_message(
                    conversation_id=conversation_id,
                    user_id=user_id,
                    role="assistant",
                    content=assistant_content,
                    model=selected_model,
                )

            except HTTPException:
                # Conversation was deleted while inference was in flight.
                pass

            except psycopg.Error as error:

                print(
                    "PostgreSQL error while saving "
                    "assistant message:",
                    error,
                )


    return StreamingResponse(
        stream_ollama_response(),
        media_type="text/plain; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "X-Content-Type-Options": "nosniff",
            "X-Conversation-ID": str(
                conversation_id
            ),
            "X-Ollama-Model": selected_model,
        },
    )
