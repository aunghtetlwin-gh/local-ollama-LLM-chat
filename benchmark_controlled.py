import csv
import json
import subprocess
import time
import urllib.request
from datetime import datetime
from pathlib import Path


# ==================================================
# Benchmark configuration
# ==================================================

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"

MODELS = [
    "qwen3:1.7b",
    "qwen3:8b",
    "gemma4:12b",
]

PROMPT = "Explain Kubernetes in exactly three short sentences."

COLD_RUNS = 3
WARM_RUNS = 3

KEEP_ALIVE = "10m"

RESULTS_FILE = Path("benchmark_controlled_seed42.csv")



# ==================================================
# Ollama model-state helpers
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


def wait_until_unloaded(model, timeout=15):
    start = time.time()

    while time.time() - start < timeout:
        if not is_model_loaded(model):
            return True

        time.sleep(1)

    return False


def unload_benchmark_models():
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
# Run one Ollama request
# ==================================================

def run_request(model, run_type, run_number):

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": PROMPT,
            }
        ],
        "stream": False,

        # Keep model loaded after request
        # so warm tests can reuse it.
        "keep_alive": KEEP_ALIVE,

        "options": {
            "num_ctx": 4096,
            "temperature": 0,
            "seed": 42,
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
    print("--------------------------------------")
    print(
        f"{model} | {run_type.upper()} "
        f"| Run {run_number}"
    )
    print("--------------------------------------")

    wall_start = time.perf_counter()

    with urllib.request.urlopen(
        request,
        timeout=300,
    ) as response:

        result = json.loads(
            response.read().decode("utf-8")
        )

    wall_time_s = (
        time.perf_counter() - wall_start
    )


    # ----------------------------------------------
    # Convert Ollama nanoseconds → seconds
    # ----------------------------------------------

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


    # ----------------------------------------------
    # Token counts
    # ----------------------------------------------

    prompt_eval_count = (
        result["prompt_eval_count"]
    )

    eval_count = (
        result["eval_count"]
    )


    # ----------------------------------------------
    # Throughput
    # ----------------------------------------------

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


    # ----------------------------------------------
    # Terminal output
    # ----------------------------------------------

    print(
        f"Client wall time:    "
        f"{wall_time_s:.3f} s"
    )

    print(
        f"Ollama total:        "
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


    return {
        "timestamp": datetime.now().isoformat(),
        "model": model,
        "run_type": run_type,
        "run_number": run_number,
        "prompt": PROMPT,

        "client_wall_time_s": round(
            wall_time_s,
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


# ==================================================
# CSV configuration
# ==================================================

fieldnames = [
    "timestamp",
    "model",
    "run_type",
    "run_number",
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

    "response",
]


# ==================================================
# Run controlled benchmark
# ==================================================

results = []


print("======================================")
print("Controlled Local LLM Benchmark")
print("======================================")
print()
print("Models:")
for model in MODELS:
    print(" -", model)

print()
print("Cold runs per model:", COLD_RUNS)
print("Warm runs per model:", WARM_RUNS)

print()
print("Fixed settings:")
print("  num_ctx     = 4096")
print("  temperature = 0")
print("  seed        = 42")
print("  prompt      =", PROMPT)


# Start from a clean benchmark state
print()
print("Unloading benchmark models...")

unload_benchmark_models()

print("Benchmark models unloaded.")


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


    # ==============================================
    # Benchmark each model
    # ==============================================

    for model in MODELS:

        print()
        print()
        print("======================================")
        print("MODEL:", model)
        print("======================================")


        # ------------------------------------------
        # COLD RUNS
        # ------------------------------------------

        for run_number in range(
            1,
            COLD_RUNS + 1,
        ):

            print()
            print(
                f"Preparing cold run "
                f"{run_number}..."
            )

            # Make sure all benchmark models
            # are unloaded before every cold run.
            unload_benchmark_models()

            if is_model_loaded(model):
                raise RuntimeError(
                    f"{model} is still loaded "
                    "before cold run."
                )

            result = run_request(
                model=model,
                run_type="cold",
                run_number=run_number,
            )

            results.append(result)

            writer.writerow(result)
            csv_file.flush()

            time.sleep(1)


        # ------------------------------------------
        # WARM RUNS
        # ------------------------------------------

        # The final cold request leaves this model
        # loaded because keep_alive = 10m.
        #
        # Therefore the next requests are warm.

        if not is_model_loaded(model):
            raise RuntimeError(
                f"{model} was expected to be "
                "loaded before warm tests."
            )

        print()
        print(
            f"{model} is loaded. "
            "Starting warm runs..."
        )


        for run_number in range(
            1,
            WARM_RUNS + 1,
        ):

            result = run_request(
                model=model,
                run_type="warm",
                run_number=run_number,
            )

            results.append(result)

            writer.writerow(result)
            csv_file.flush()

            time.sleep(1)


        # Clean up before next model
        stop_model(model)

        if not wait_until_unloaded(model):
            raise RuntimeError(
                f"Could not unload {model} "
                "after benchmark."
            )


# ==================================================
# Compact terminal summary
# ==================================================

print()
print()
print("======================================")
print("CONTROLLED BENCHMARK COMPLETED")
print("======================================")
print()

print(
    f"{'MODEL':<15}"
    f"{'TYPE':<8}"
    f"{'RUN':<6}"
    f"{'TOTAL(s)':<11}"
    f"{'LOAD(s)':<10}"
    f"{'EVAL TOK':<10}"
    f"{'TOK/s':<10}"
)

print("-" * 70)


for row in results:

    print(
        f"{row['model']:<15}"
        f"{row['run_type']:<8}"
        f"{row['run_number']:<6}"
        f"{row['total_latency_s']:<11}"
        f"{row['load_duration_s']:<10}"
        f"{row['eval_tokens']:<10}"
        f"{row['generation_tokens_per_second']:<10}"
    )


print()
print(
    f"Total benchmark runs: {len(results)}"
)

print(
    f"Results saved to: {RESULTS_FILE}"
)