import io
import json

import pytest
from fastapi import HTTPException
from conftest import TestClient

import server


@pytest.mark.parametrize("method,path", [
    ("get", "/models"), ("get", "/conversations"),
    ("get", "/conversations/1"), ("delete", "/conversations/1"),
])
def test_anonymous_api_denied(client, method, path):
    assert getattr(client, method)(path).status_code == 401


def test_anonymous_chat_denied(client):
    assert client.post("/chat", json={"message": "Hello"}).status_code == 401
    assert client.get("/").status_code == 303


def test_two_user_isolation_and_message_helpers(client, db, register_user):
    owner_id = register_user(client).json()["user"]["id"]
    conversation_id = server.create_conversation("Private title", owner_id)
    server.save_message(conversation_id, owner_id, "user", "Private content")
    with TestClient(server.my_api) as other:
        other_id = register_user(other, "other@example.com").json()["user"]["id"]
        assert other.get("/conversations").json() == {"conversations": []}
        for response in [other.get(f"/conversations/{conversation_id}"),
                         other.delete(f"/conversations/{conversation_id}"),
                         other.post("/chat", json={"conversation_id": conversation_id, "message": "Attack"})]:
            assert response.status_code == 404
            assert "Private" not in response.text
        assert server.get_conversation_messages(conversation_id, other_id) == []
        with pytest.raises(HTTPException) as error:
            server.save_message(conversation_id, other_id, "assistant", "Attack")
        assert error.value.status_code == 404
    assert len(client.get("/conversations").json()["conversations"]) == 1
    assert client.get(f"/conversations/{conversation_id}").json()["messages"][0]["content"] == "Private content"
    assert db.raw.execute("SELECT count(*) FROM messages").fetchone()[0] == 1
    assert client.delete(f"/conversations/{conversation_id}").status_code == 200
    assert db.raw.execute("SELECT count(*) FROM messages").fetchone()[0] == 0


def test_streaming_history_and_model_tracking(client, db, register_user, monkeypatch):
    user_id = register_user(client).json()["user"]["id"]
    requests = []
    def ollama(request, timeout):
        requests.append(json.loads(request.data))
        assert request.full_url == server.OLLAMA_CHAT_URL and timeout == server.OLLAMA_TIMEOUT
        return io.BytesIO(b'{"message":{"content":"Hello "}}\n{"message":{"content":"there"},"done":true}\n')
    monkeypatch.setattr(server.urllib.request, "urlopen", ollama)
    response = client.post("/chat", json={"message": "Hi", "model": "qwen3:1.7b", "user_id": 999})
    assert response.status_code == 200 and response.text == "Hello there"
    assert response.headers["x-ollama-model"] == "qwen3:1.7b"
    conversation_id = int(response.headers["x-conversation-id"])
    assert db.raw.execute("SELECT user_id FROM conversations").fetchone()[0] == user_id
    messages = client.get(f"/conversations/{conversation_id}").json()["messages"]
    assert [(m["role"], m["content"], m["model"]) for m in messages] == [
        ("user", "Hi", None), ("assistant", "Hello there", "qwen3:1.7b")]
    assert requests[0] == {"model": "qwen3:1.7b", "messages": [{"role": "user", "content": "Hi"}], "stream": True}
    response = client.post("/chat", json={"conversation_id": conversation_id, "message": "Again"})
    assert response.status_code == 200
    assert requests[1]["messages"] == [
        {"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello there"},
        {"role": "user", "content": "Again"}]
    assert requests[1]["model"] == "qwen3:8b"


def test_incomplete_stream_not_persisted(client, db, register_user, monkeypatch):
    register_user(client)
    monkeypatch.setattr(server.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(b'{"message":{"content":"Partial"}}\n'))
    response = client.post("/chat", json={"message": "Hi"})
    assert response.text == "Partial"
    assert db.raw.execute("SELECT role FROM messages").fetchall() == [("user",)]
