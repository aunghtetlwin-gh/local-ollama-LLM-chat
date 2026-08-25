import json
import urllib.request

url = "http://localhost:11434/api/chat"

data = {
    "model": "qwen3:1.7b",
    "messages": [
        {
            "role": "user",
            "content": "Explain Kubernetes in two simple sentences."
        }
    ],
    "stream": False
}

request = urllib.request.Request(
    url,
    data=json.dumps(data).encode("utf-8"),
    headers={"Content-Type": "application/json"},
)

with urllib.request.urlopen(request) as response:
    result = json.loads(response.read().decode("utf-8"))

print("===== QWEN ANSWER =====")
print(result["message"]["content"])
