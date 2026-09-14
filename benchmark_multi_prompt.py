import csv
import json
import subprocess
import time
import urllib.request
from datetime import datetime
from pathlib import Path


# ==================================================
# Configuration
# ==================================================

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"

MODELS = [
    "qwen3:1.7b",
    "qwen3:8b",
    "gemma4:12b",
]

NUM_CTX = 4096
TEMPERATURE = 0
SEED = 42
KEEP_ALIVE = "10m"

RESULTS_FILE = Path("multi_prompt_results.csv")
RESPONSES_FILE = Path("multi_prompt_responses.md")


# ==================================================
# Benchmark prompts
# ==================================================

PROMPTS = [
    {
        "task_id": "knowledge",
        "category": "Knowledge / Explanation",
        "prompt": (
            "Explain the difference between a Kubernetes Deployment "
            "and a StatefulSet in exactly four bullet points. "
            "Mention identity, storage, scaling/update behavior, "
            "and one typical use case."
        ),
    },

    {
        "task_id": "reasoning",
        "category": "Reasoning",
        "prompt": (
            "A GPU server has 16 GB of free VRAM. "
            "Model A needs 3 GB, Model B needs 5 GB, "
            "and Model C needs 8 GB. "
            "You must run exactly three model instances and maximize "
            "total VRAM usage without exceeding 16 GB. "
            "Instances may be repeated. "
            "Which three instances should you run? "
            "Show the calculation in at most four lines."
        ),
    },

    {
        "task_id": "coding",
        "category": "Coding",
        "prompt": (
            "Write a Python function named first_unique(items) "
            "that returns the first element that appears exactly once "
            "in the input list. Return None if no unique element exists. "
            "Preserve the original input order. "
            "Do not use collections.Counter. "
            "Return only Python code with no Markdown code fences "
            "and no explanation."
        ),
    },

    {
        "task_id": "summarization",
        "category": "Summarization",
        "prompt": (
            "Summarize the following text in exactly two sentences:\n\n"
            "NECTEC's local AI test environment uses an NVIDIA GPU "
            "to run several large language models through Ollama. "
            "A FastAPI service sends chat requests to Ollama, "
            "PostgreSQL stores conversations, and Docker Compose "
            "manages the application and database. "
            "The environment also includes Slurm, which was previously "
            "configured for CPU and GPU workload scheduling. "
            "The current evaluation compares models using latency, "
            "generation speed, GPU memory, GPU utilization, power usage, "
            "and response quality."
        ),
    },

    {
        "task_id": "instruction",
        "category": "Instruction Following",
        "prompt": (
            "Read these values: alpha=7, beta=3, gamma=9. "
            "Return exactly three lines and nothing else. "
            "Line 1 must be: COUNT=3 "
            "Line 2 must be: SUM=19 "
            "Line 3 must be: MAX=9"
        ),
    },
]


# ==================================================
# Ollama model helpers
# ==================================================

def get_ollama_ps():
    result = subprocess.run(
        ["ollama", "ps"],
        capture_output=True,
        text=True,
        check=False,
    )

    return result.stdout


def is_model_loaded(model):
    return model in get_ollama_ps()


def stop_model(model):
    subprocess.run(
        ["ollama", "stop", model],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def wait_until_unloaded(model, timeout=20):
    start = time.time()

    while time.time() - start < timeout:

        if not is_model_loaded(model):
            return True

        time.sleep(1)

    return False


def unload_all_models():

    for model in MODELS:
        stop_model(model)

    time.sleep(1)

    for model in MODELS:

        if is_model_loaded(model):

            if not wait_until_unloaded(model):
                raise RuntimeError(
                    f"Could not unload {model}"
                )


# ==================================================
# Warm model
# ==================================================

def warm_up_model(model):

    print(f"Warming up {model}...")

    payload = {
        "model": model,

        "messages": [
            {
                "role": "user",
                "content": "Reply with OK.",
            }
        ],

        "stream": False,

        "keep_alive": KEEP_ALIVE,

        "options": {
            "num_ctx": NUM_CTX,
            "temperature": TEMPERATURE,
            "seed": SEED,

            # We only need to load the model.
            "num_predict": 1,
        },
    }

    request = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=300,
    ) as response:

        response.read()

    if not is_model_loaded(model):
        raise RuntimeError(
            f"{model} did not remain loaded."
        )

    print(f"{model} is loaded and ready.")


# ==================================================
# Run one benchmark task
# ==================================================

def run_task(model, task):

    task_id = task["task_id"]
    category = task["category"]
    prompt = task["prompt"]

    print()
    print("--------------------------------------")
    print(f"Model:    {model}")
    print(f"Task:     {task_id}")
    print(f"Category: {category}")
    print("--------------------------------------")

    payload = {
        "model": model,

        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],

        "stream": False,

        "keep_alive": KEEP_ALIVE,

        "options": {
            "num_ctx": NUM_CTX,
            "temperature": TEMPERATURE,
            "seed": SEED,
        },
    }

    request = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
        },
    )

    wall_start = time.perf_counter()

    with urllib.request.urlopen(
        request,
        timeout=600,
    ) as response:

        result = json.loads(
            response.read().decode("utf-8")
        )

    client_wall_time_s = (
        time.perf_counter() - wall_start
    )


    # --------------------------------------------------
    # Ollama metrics
    # --------------------------------------------------

    total_duration_s = (
        result["total_duration"] / 1e9
    )

    load_duration_s = (
        result["load_duration"] / 1e9
    )

    prompt_eval_duration_s = (
        result["prompt_eval_duration"] / 1e9
    )

    eval_duration_s = (
        result["eval_duration"] / 1e9
    )

    prompt_tokens = (
        result["prompt_eval_count"]
    )

    eval_tokens = (
        result["eval_count"]
    )


    if prompt_eval_duration_s > 0:
        prompt_tokens_per_second = (
            prompt_tokens /
            prompt_eval_duration_s
        )
    else:
        prompt_tokens_per_second = 0


    if eval_duration_s > 0:
        generation_tokens_per_second = (
            eval_tokens /
            eval_duration_s
        )
    else:
        generation_tokens_per_second = 0


    # --------------------------------------------------
    # Response
    # --------------------------------------------------

    message = result.get(
        "message",
        {},
    )

    assistant_content = message.get(
        "content",
        "",
    )

    thinking_content = message.get(
        "thinking",
        "",
    )

    done_reason = result.get(
        "done_reason",
        "",
    )


    # --------------------------------------------------
    # Terminal output
    # --------------------------------------------------

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
        f"{prompt_tokens}"
    )

    print(
        f"Eval tokens:         "
        f"{eval_tokens}"
    )

    print(
        f"Generation speed:    "
        f"{generation_tokens_per_second:.2f} tok/s"
    )

    print(
        f"Response characters: "
        f"{len(assistant_content)}"
    )

    print(
        f"Thinking characters: "
        f"{len(thinking_content)}"
    )

    print(
        f"Done reason:         "
        f"{done_reason}"
    )

    print()
    print("Response:")
    print("--------------------------------------")
    print(assistant_content)
    print("--------------------------------------")


    return {
        "timestamp": datetime.now().isoformat(),

        "model": model,

        "task_id": task_id,

        "category": category,

        "prompt": prompt,

        "client_wall_time_s": round(
            client_wall_time_s,
            3,
        ),

        "total_latency_s": round(
            total_duration_s,
            3,
        ),

        "load_duration_s": round(
            load_duration_s,
            3,
        ),

        "prompt_tokens": prompt_tokens,

        "prompt_eval_duration_s": round(
            prompt_eval_duration_s,
            3,
        ),

        "prompt_tokens_per_second": round(
            prompt_tokens_per_second,
            2,
        ),

        "eval_tokens": eval_tokens,

        "eval_duration_s": round(
            eval_duration_s,
            3,
        ),

        "generation_tokens_per_second": round(
            generation_tokens_per_second,
            2,
        ),

        "thinking_characters": len(
            thinking_content
        ),

        "response_characters": len(
            assistant_content
        ),

        "done_reason": done_reason,

        "response": assistant_content,
    }


# ==================================================
# CSV fields
# ==================================================

fieldnames = [
    "timestamp",
    "model",
    "task_id",
    "category",
    "prompt",

    "client_wall_time_s",
    "total_latency_s",
    "load_duration_s",

    "prompt_tokens",
    "prompt_eval_duration_s",
    "prompt_tokens_per_second",

    "eval_tokens",
    "eval_duration_s",
    "generation_tokens_per_second",

    "thinking_characters",
    "response_characters",

    "done_reason",

    "response",
]


# ==================================================
# Main
# ==================================================

results = []


print("======================================")
print("Multi-Prompt LLM Evaluation")
print("======================================")

print()
print("Models:")

for model in MODELS:
    print(" -", model)

print()
print("Tasks:")

for task in PROMPTS:
    print(
        f" - {task['task_id']}: "
        f"{task['category']}"
    )

print()
print("Fixed settings:")
print("  num_ctx     =", NUM_CTX)
print("  temperature =", TEMPERATURE)
print("  seed        =", SEED)

print()
print(
    "Total evaluations:",
    len(MODELS) * len(PROMPTS),
)


# ==================================================
# Run benchmark
# ==================================================

unload_all_models()


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


    for model in MODELS:

        print()
        print()
        print("======================================")
        print("MODEL:", model)
        print("======================================")

        unload_all_models()

        warm_up_model(model)


        for task in PROMPTS:

            result = run_task(
                model=model,
                task=task,
            )

            results.append(result)

            writer.writerow(result)

            csv_file.flush()

            time.sleep(1)


        stop_model(model)

        if not wait_until_unloaded(model):

            raise RuntimeError(
                f"Could not unload {model}"
            )


# ==================================================
# Human-readable response file
# ==================================================

with RESPONSES_FILE.open(
    "w",
    encoding="utf-8",
) as markdown_file:

    markdown_file.write(
        "# Multi-Prompt LLM Responses\n\n"
    )

    for row in results:

        markdown_file.write(
            f"## {row['model']} — "
            f"{row['category']}\n\n"
        )

        markdown_file.write(
            f"**Task ID:** "
            f"`{row['task_id']}`\n\n"
        )

        markdown_file.write(
            "**Prompt:**\n\n"
        )

        markdown_file.write(
            row["prompt"] + "\n\n"
        )

        markdown_file.write(
            "**Response:**\n\n"
        )

        if row["response"]:
            markdown_file.write(
                row["response"] + "\n\n"
            )
        else:
            markdown_file.write(
                "*No final response content.*\n\n"
            )

        markdown_file.write(
            f"**Latency:** "
            f"{row['total_latency_s']} s  \n"
        )

        markdown_file.write(
            f"**Generation speed:** "
            f"{row['generation_tokens_per_second']} "
            f"tok/s  \n"
        )

        markdown_file.write(
            f"**Eval tokens:** "
            f"{row['eval_tokens']}  \n"
        )

        markdown_file.write(
            f"**Done reason:** "
            f"{row['done_reason']}  \n\n"
        )

        markdown_file.write(
            "---\n\n"
        )


# ==================================================
# Final terminal summary
# ==================================================

print()
print()
print("======================================")
print("MULTI-PROMPT EVALUATION COMPLETED")
print("======================================")

print()

print(
    f"{'MODEL':<15}"
    f"{'TASK':<16}"
    f"{'TOTAL(s)':<11}"
    f"{'EVAL':<8}"
    f"{'TOK/s':<10}"
    f"{'CHARS':<8}"
    f"{'DONE':<10}"
)

print("-" * 78)


for row in results:

    print(
        f"{row['model']:<15}"
        f"{row['task_id']:<16}"
        f"{row['total_latency_s']:<11}"
        f"{row['eval_tokens']:<8}"
        f"{row['generation_tokens_per_second']:<10}"
        f"{row['response_characters']:<8}"
        f"{row['done_reason']:<10}"
    )


print()
print(
    f"Total evaluations completed: "
    f"{len(results)}"
)

print(
    f"CSV results: {RESULTS_FILE}"
)

print(
    f"Readable responses: {RESPONSES_FILE}"
)