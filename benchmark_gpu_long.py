import csv
import json
import subprocess
import threading
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

PROMPT = (
    "Write a detailed technical explanation of Kubernetes architecture. "
    "Cover the control plane, worker nodes, Pods, Deployments, Services, "
    "scheduling, scaling, networking, and self-healing. "
    "Continue with detailed explanations and examples for at least 1500 words."
)

RUNS_PER_MODEL = 3

RESULTS_FILE = Path("benchmark_gpu_long.csv")

KEEP_ALIVE = "10m"

NUM_CTX = 4096
TEMPERATURE = 0
SEED = 42


# ==================================================
# Ollama helpers
# ==================================================

def stop_model(model):
    subprocess.run(
        ["ollama", "stop", model],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


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
# Build Ollama request
# ==================================================

def build_request(model):

    payload = {
        "model": model,

        "messages": [
            {
                "role": "user",
                "content": PROMPT,
            }
        ],

        "stream": False,

        "keep_alive": KEEP_ALIVE,

        "options": {
            "num_ctx": NUM_CTX,
            "temperature": TEMPERATURE,
            "seed": SEED,
            "num_predict": 1024,
        },
    }

    return urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
        },
    )


# ==================================================
# Warm-up model
# ==================================================

def warm_up_model(model):

    print(f"Warming up {model}...")

    request = build_request(model)

    with urllib.request.urlopen(
        request,
        timeout=300,
    ) as response:

        response.read()

    if not is_model_loaded(model):
        raise RuntimeError(
            f"{model} did not remain loaded "
            "after warm-up."
        )

    print(f"{model} is loaded and ready.")


# ==================================================
# GPU monitor
# ==================================================

class GPUMonitor:

    def __init__(self):
        self.samples = []
        self.process = None
        self.thread = None
        self.running = False


    def start(self):

        command = [
            "nvidia-smi",

            "--query-gpu="
            "utilization.gpu,"
            "memory.used,"
            "power.draw,"
            "temperature.gpu",

            "--format=csv,noheader,nounits",

            "-lms",
            "100",
        ]

        self.process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )

        self.running = True

        self.thread = threading.Thread(
            target=self._read_samples,
            daemon=True,
        )

        self.thread.start()


    def _read_samples(self):

        if self.process.stdout is None:
            return

        while self.running:

            line = self.process.stdout.readline()

            if not line:
                break

            parts = [
                item.strip()
                for item in line.split(",")
            ]

            if len(parts) != 4:
                continue

            try:
                gpu_util = float(parts[0])
                memory_used = float(parts[1])
                power_draw = float(parts[2])
                temperature = float(parts[3])

                self.samples.append(
                    {
                        "gpu_util": gpu_util,
                        "memory_used": memory_used,
                        "power_draw": power_draw,
                        "temperature": temperature,
                    }
                )

            except ValueError:
                continue


    def stop(self):

        self.running = False

        if self.process is not None:
            self.process.terminate()

            try:
                self.process.wait(timeout=2)

            except subprocess.TimeoutExpired:
                self.process.kill()

        if self.thread is not None:
            self.thread.join(timeout=2)


    def summarize(self):

        if not self.samples:
            return {
                "gpu_samples": 0,
                "avg_gpu_util_percent": 0,
                "peak_gpu_util_percent": 0,
                "avg_vram_mib": 0,
                "peak_vram_mib": 0,
                "avg_power_w": 0,
                "peak_power_w": 0,
                "max_temperature_c": 0,
            }

        gpu_values = [
            sample["gpu_util"]
            for sample in self.samples
        ]

        memory_values = [
            sample["memory_used"]
            for sample in self.samples
        ]

        power_values = [
            sample["power_draw"]
            for sample in self.samples
        ]

        temperature_values = [
            sample["temperature"]
            for sample in self.samples
        ]

        return {
            "gpu_samples": len(self.samples),

            "avg_gpu_util_percent": round(
                sum(gpu_values) / len(gpu_values),
                2,
            ),

            "peak_gpu_util_percent": round(
                max(gpu_values),
                2,
            ),

            "avg_vram_mib": round(
                sum(memory_values) / len(memory_values),
                2,
            ),

            "peak_vram_mib": round(
                max(memory_values),
                2,
            ),

            "avg_power_w": round(
                sum(power_values) / len(power_values),
                2,
            ),

            "peak_power_w": round(
                max(power_values),
                2,
            ),

            "max_temperature_c": round(
                max(temperature_values),
                2,
            ),
        }


# ==================================================
# Run one monitored inference
# ==================================================

def run_monitored_request(
    model,
    run_number,
):

    print()
    print("--------------------------------------")
    print(
        f"{model} | GPU RUN {run_number}"
    )
    print("--------------------------------------")

    request = build_request(model)

    monitor = GPUMonitor()

    monitor.start()

    # Allow monitor to capture initial warm state
    time.sleep(0.1)

    wall_start = time.perf_counter()

    try:

        with urllib.request.urlopen(
            request,
            timeout=300,
        ) as response:

            result = json.loads(
                response.read().decode("utf-8")
            )

    finally:

        wall_time_s = (
            time.perf_counter() - wall_start
        )

        monitor.stop()


    gpu_summary = monitor.summarize()


    # --------------------------------------------------
    # Ollama metrics
    # --------------------------------------------------

    total_duration_s = (
        result["total_duration"] / 1e9
    )

    load_duration_s = (
        result["load_duration"] / 1e9
    )

    eval_duration_s = (
        result["eval_duration"] / 1e9
    )

    eval_count = (
        result["eval_count"]
    )

    if eval_duration_s > 0:
        generation_tokens_per_second = (
            eval_count / eval_duration_s
        )
    else:
        generation_tokens_per_second = 0


    assistant_content = (
        result
        .get("message", {})
        .get("content", "")
    )


    # --------------------------------------------------
    # Display
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
        f"Eval tokens:         "
        f"{eval_count}"
    )

    print(
        f"Generation speed:    "
        f"{generation_tokens_per_second:.2f} tok/s"
    )

    print(
        f"GPU samples:         "
        f"{gpu_summary['gpu_samples']}"
    )

    print(
        f"Average GPU util:    "
        f"{gpu_summary['avg_gpu_util_percent']:.2f}%"
    )

    print(
        f"Peak GPU util:       "
        f"{gpu_summary['peak_gpu_util_percent']:.2f}%"
    )

    print(
        f"Average VRAM:        "
        f"{gpu_summary['avg_vram_mib']:.2f} MiB"
    )

    print(
        f"Peak VRAM:           "
        f"{gpu_summary['peak_vram_mib']:.2f} MiB"
    )

    print(
        f"Average power:       "
        f"{gpu_summary['avg_power_w']:.2f} W"
    )

    print(
        f"Peak power:          "
        f"{gpu_summary['peak_power_w']:.2f} W"
    )

    print(
        f"Max temperature:     "
        f"{gpu_summary['max_temperature_c']:.2f} °C"
    )


    return {
        "timestamp": datetime.now().isoformat(),

        "model": model,

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

        "eval_tokens": eval_count,

        "eval_duration_s": round(
            eval_duration_s,
            3,
        ),

        "generation_tokens_per_second": round(
            generation_tokens_per_second,
            2,
        ),

        **gpu_summary,

        "response": assistant_content,
    }


# ==================================================
# CSV fields
# ==================================================

fieldnames = [
    "timestamp",
    "model",
    "run_number",
    "prompt",

    "client_wall_time_s",
    "total_latency_s",
    "load_duration_s",

    "eval_tokens",
    "eval_duration_s",
    "generation_tokens_per_second",

    "gpu_samples",

    "avg_gpu_util_percent",
    "peak_gpu_util_percent",

    "avg_vram_mib",
    "peak_vram_mib",

    "avg_power_w",
    "peak_power_w",

    "max_temperature_c",

    "response",
]


# ==================================================
# Main benchmark
# ==================================================

results = []


print("======================================")
print("GPU Resource Benchmark")
print("======================================")

print()
print("Models:")

for model in MODELS:
    print(" -", model)

print()
print("Runs per model:", RUNS_PER_MODEL)

print()
print("Fixed settings:")
print("  num_ctx     =", NUM_CTX)
print("  temperature =", TEMPERATURE)
print("  seed        =", SEED)
print("  GPU sample  = 100 ms")
print("  prompt      =", PROMPT)


print()
print("Unloading benchmark models...")

unload_all_models()

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


    for model in MODELS:

        print()
        print()
        print("======================================")
        print("MODEL:", model)
        print("======================================")

        unload_all_models()

        warm_up_model(model)


        for run_number in range(
            1,
            RUNS_PER_MODEL + 1,
        ):

            result = run_monitored_request(
                model=model,
                run_number=run_number,
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
# Final summary
# ==================================================

print()
print()
print("======================================")
print("GPU BENCHMARK COMPLETED")
print("======================================")

print()

print(
    f"{'MODEL':<15}"
    f"{'RUN':<6}"
    f"{'GPU AVG':<10}"
    f"{'GPU MAX':<10}"
    f"{'VRAM MAX':<12}"
    f"{'PWR AVG':<10}"
    f"{'TEMP':<8}"
)

print("-" * 75)


for row in results:

    print(
        f"{row['model']:<15}"
        f"{row['run_number']:<6}"
        f"{row['avg_gpu_util_percent']:<10}"
        f"{row['peak_gpu_util_percent']:<10}"
        f"{row['peak_vram_mib']:<12}"
        f"{row['avg_power_w']:<10}"
        f"{row['max_temperature_c']:<8}"
    )


print()
print(
    f"Total monitored runs: {len(results)}"
)

print(
    f"Results saved to: {RESULTS_FILE}"
)