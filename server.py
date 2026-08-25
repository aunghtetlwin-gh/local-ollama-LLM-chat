import json
import urllib.request

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel


my_api = FastAPI()


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


@my_api.get("/")
def home():
    return FileResponse("index.html")


@my_api.get("/health")
def health():
    return {
        "message": "FastAPI is running on lai512"
    }


@my_api.post("/chat")
def chat(request: ChatRequest):

    ollama_url = "http://127.0.0.1:11434/api/chat"

    messages = [
        {
            "role": message.role,
            "content": message.content
        }
        for message in request.messages
    ]

    data = {
        "model": "qwen3:1.7b",
        "messages": messages,
        "stream": False
    }

    ollama_request = urllib.request.Request(
        ollama_url,
        data=json.dumps(data).encode("utf-8"),
        headers={
            "Content-Type": "application/json"
        },
    )

    with urllib.request.urlopen(ollama_request) as response:
        result = json.loads(
            response.read().decode("utf-8")
        )

    return {
        "answer": result["message"]["content"]
    }
