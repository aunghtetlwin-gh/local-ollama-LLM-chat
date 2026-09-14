import csv
import json
import urllib.request
from datetime import datetime
from pathlib import Path


# --------------------------------------------------
# Benchmark configuration
# --------------------------------------------------

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"

MODELS = [
    "qwen3:1.7b",
    "qwen3:8b",
    "gemma4:12b",
]

PROMPT = "Explain Kubernetes in exactly three short sentences."

RESULTS_FILE = Path("benchmark_baseline.csv")


# --------------------------------------------------
# Run one model
# --------------------------------------------------

def run_benchmark(model):
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": PROMPT,
            }
        ],
        "stream": False,
        "options": {
            "num_ctx": 4096,
            "temperature": 0,
        },
    }

    request = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
        },
    )

    print()
    print("======================================")
    print("Model:", model)
    print("======================================")

    with urllib.request.urlopen(
        request,
        timeout=300,
    ) as response:
        result = json.loads(
            response.read().decode("utf-8")
        )

    # Ollama durations are returned in nanoseconds
    total_duration_s = result["total_duration"] / 1e9
    load_duration_s = result["load_duration"] / 1e9

    prompt_eval_duration_s = (
        result["prompt_eval_duration"] / 1e9
    )

    eval_duration_s = (
        result["eval_duration"] / 1e9
    )

    prompt_eval_count = result["prompt_eval_count"]
    eval_count = result["eval_count"]

    if prompt_eval_duration_s > 0:
        prompt_tokens_per_second = (
            prompt_eval_count
            / prompt_eval_duration_s
        )
    else:
        prompt_tokens_per_second = 0

    if eval_duration_s > 0:
        generation_tokens_per_second = (
            eval_count
            / eval_duration_s
        )
    else:
        generation_tokens_per_second = 0

    assistant_content = (
        result
        .get("message", {})
        .get("content", "")
    )

    print(
        f"Total latency:       "
        f"{total_duration_s:.3f} s"
    )

    print(
        f"Load duration:       "
        f"{load_duration_s:.3f} s"
    )

    print(
        f"Prompt tokens:       "
        f"{prompt_eval_count}"
    )

    print(
        f"Prompt speed:        "
        f"{prompt_tokens_per_second:.2f} tok/s"
    )

    print(
        f"Eval tokens:         "
        f"{eval_count}"
    )

    print(
        f"Generation duration: "
        f"{eval_duration_s:.3f} s"
    )

    print(
        f"Generation speed:    "
        f"{generation_tokens_per_second:.2f} tok/s"
    )

    print()
    print("Response:")
    print("--------------------------------------")
    print(assistant_content)
    print("--------------------------------------")

    return {
        "timestamp": datetime.now().isoformat(),
        "model": model,
        "prompt": PROMPT,
        "total_latency_s": round(
            total_duration_s,
            3,
        ),
        "load_duration_s": round(
            load_duration_s,
            3,
        ),
        "prompt_tokens": prompt_eval_count,
        "prompt_eval_duration_s": round(
            prompt_eval_duration_s,
            3,
        ),
        "prompt_tokens_per_second": round(
            prompt_tokens_per_second,
            2,
        ),
        "eval_tokens": eval_count,
        "eval_duration_s": round(
            eval_duration_s,
            3,
        ),
        "generation_tokens_per_second": round(
            generation_tokens_per_second,
            2,
        ),
        "response": assistant_content,
    }


# --------------------------------------------------
# Run all models
# --------------------------------------------------

results = []

print("======================================")
print("Local LLM Baseline Benchmark")
print("======================================")
print("Prompt:", PROMPT)
print("Models:", ", ".join(MODELS))

for model in MODELS:
    try:
        result = run_benchmark(model)
        results.append(result)

    except Exception as error:
        print()
        print(f"ERROR benchmarking {model}:")
        print(error)


# --------------------------------------------------
# Save all results
# --------------------------------------------------

fieldnames = [
    "timestamp",
    "model",
    "prompt",
    "total_latency_s",
    "load_duration_s",
    "prompt_tokens",
    "prompt_eval_duration_s",
    "prompt_tokens_per_second",
    "eval_tokens",
    "eval_duration_s",
    "generation_tokens_per_second",
    "response",
]


with RESULTS_FILE.open(
    "w",
    newline="",
    encoding="utf-8",
) as csv_file:

    writer = csv.DictWriter(
        csv_file,
        fieldnames=fieldnames,
    )

    writer.writeheader()
    writer.writerows(results)


print()
print("======================================")
print("Benchmark completed")
print("======================================")
print(
    f"Models completed: {len(results)}/{len(MODELS)}"
)
print(
    f"Results saved to: {RESULTS_FILE}"
)