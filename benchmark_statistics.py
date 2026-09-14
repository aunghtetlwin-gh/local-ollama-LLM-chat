import csv
import statistics
from collections import defaultdict
from pathlib import Path


# ==================================================
# Input / output files
# ==================================================

CONTROLLED_FILE = Path(
    "benchmark_controlled_seed42.csv"
)

GPU_FILE = Path(
    "benchmark_gpu_long.csv"
)

MULTI_PROMPT_FILE = Path(
    "multi_prompt_results.csv"
)

SUMMARY_FILE = Path(
    "statistical_summary.csv"
)

REPORT_FILE = Path(
    "statistical_summary.md"
)


# ==================================================
# Helpers
# ==================================================

def read_csv(path):
    with path.open(
        newline="",
        encoding="utf-8",
    ) as file:

        return list(
            csv.DictReader(file)
        )


def calculate_stats(values):

    values = [
        float(value)
        for value in values
    ]

    return {
        "n": len(values),

        "mean": round(
            statistics.mean(values),
            3,
        ),

        "min": round(
            min(values),
            3,
        ),

        "max": round(
            max(values),
            3,
        ),

        "std_dev": round(
            statistics.stdev(values),
            3,
        )
        if len(values) > 1
        else 0,
    }


# ==================================================
# Load data
# ==================================================

controlled_rows = read_csv(
    CONTROLLED_FILE
)

gpu_rows = read_csv(
    GPU_FILE
)

multi_prompt_rows = read_csv(
    MULTI_PROMPT_FILE
)


summary_rows = []


# ==================================================
# 1. Controlled cold/warm statistics
# ==================================================

controlled_groups = defaultdict(list)

for row in controlled_rows:

    key = (
        row["model"],
        row["run_type"],
    )

    controlled_groups[key].append(row)


controlled_metrics = [
    "client_wall_time_s",
    "total_latency_s",
    "load_duration_s",
    "generation_tokens_per_second",
]


for (
    model,
    run_type,
), rows in controlled_groups.items():

    for metric in controlled_metrics:

        stats = calculate_stats(
            [
                row[metric]
                for row in rows
            ]
        )

        summary_rows.append(
            {
                "dataset":
                    "controlled_performance",

                "model":
                    model,

                "condition":
                    run_type,

                "metric":
                    metric,

                **stats,
            }
        )


# ==================================================
# 2. Sustained GPU statistics
# ==================================================

gpu_groups = defaultdict(list)

for row in gpu_rows:

    gpu_groups[
        row["model"]
    ].append(row)


gpu_metrics = [
    "total_latency_s",
    "generation_tokens_per_second",

    "avg_gpu_util_percent",
    "peak_gpu_util_percent",

    "avg_vram_mib",
    "peak_vram_mib",

    "avg_power_w",
    "peak_power_w",

    "max_temperature_c",
]


for model, rows in gpu_groups.items():

    for metric in gpu_metrics:

        stats = calculate_stats(
            [
                row[metric]
                for row in rows
            ]
        )

        summary_rows.append(
            {
                "dataset":
                    "gpu_sustained",

                "model":
                    model,

                "condition":
                    "warm_sustained",

                "metric":
                    metric,

                **stats,
            }
        )


# ==================================================
# 3. Multi-prompt cross-task statistics
# ==================================================

multi_groups = defaultdict(list)

for row in multi_prompt_rows:

    multi_groups[
        row["model"]
    ].append(row)


multi_metrics = [
    "total_latency_s",
    "eval_tokens",
    "generation_tokens_per_second",
    "thinking_characters",
    "response_characters",
]


for model, rows in multi_groups.items():

    for metric in multi_metrics:

        stats = calculate_stats(
            [
                row[metric]
                for row in rows
            ]
        )

        summary_rows.append(
            {
                "dataset":
                    "multi_prompt_cross_task",

                "model":
                    model,

                "condition":
                    "five_task_categories",

                "metric":
                    metric,

                **stats,
            }
        )


# ==================================================
# Save CSV
# ==================================================

fieldnames = [
    "dataset",
    "model",
    "condition",
    "metric",
    "n",
    "mean",
    "min",
    "max",
    "std_dev",
]


with SUMMARY_FILE.open(
    "w",
    newline="",
    encoding="utf-8",
) as file:

    writer = csv.DictWriter(
        file,
        fieldnames=fieldnames,
    )

    writer.writeheader()

    writer.writerows(
        summary_rows
    )


# ==================================================
# Markdown report helpers
# ==================================================

def find_summary(
    dataset,
    model,
    condition,
    metric,
):

    for row in summary_rows:

        if (
            row["dataset"] == dataset
            and row["model"] == model
            and row["condition"] == condition
            and row["metric"] == metric
        ):
            return row

    return None


models = [
    "qwen3:1.7b",
    "qwen3:8b",
    "gemma4:12b",
]


# ==================================================
# Write readable Markdown report
# ==================================================

with REPORT_FILE.open(
    "w",
    encoding="utf-8",
) as report:

    report.write(
        "# Statistical Benchmark Summary\n\n"
    )

    report.write(
        "Mean, minimum, maximum, and sample "
        "standard deviation are reported below.\n\n"
    )


    # ----------------------------------------------
    # Controlled performance
    # ----------------------------------------------

    report.write(
        "## Controlled Performance\n\n"
    )

    report.write(
        "| Model | State | Mean Latency (s) | "
        "Min | Max | Std Dev | "
        "Mean Load (s) | "
        "Mean Generation (tok/s) |\n"
    )

    report.write(
        "|---|---|---:|---:|---:|---:|---:|---:|\n"
    )


    for model in models:

        for condition in [
            "cold",
            "warm",
        ]:

            latency = find_summary(
                "controlled_performance",
                model,
                condition,
                "total_latency_s",
            )

            load = find_summary(
                "controlled_performance",
                model,
                condition,
                "load_duration_s",
            )

            speed = find_summary(
                "controlled_performance",
                model,
                condition,
                "generation_tokens_per_second",
            )

            report.write(
                f"| {model} "
                f"| {condition} "
                f"| {latency['mean']} "
                f"| {latency['min']} "
                f"| {latency['max']} "
                f"| {latency['std_dev']} "
                f"| {load['mean']} "
                f"| {speed['mean']} |\n"
            )


    # ----------------------------------------------
    # GPU resource statistics
    # ----------------------------------------------

    report.write(
        "\n## Sustained GPU Resource Use\n\n"
    )

    report.write(
        "| Model | Mean GPU (%) | GPU Std Dev | "
        "Mean VRAM (MiB) | "
        "Mean Power (W) | "
        "Max Observed Temp (C) | "
        "Mean Generation (tok/s) |\n"
    )

    report.write(
        "|---|---:|---:|---:|---:|---:|---:|\n"
    )


    for model in models:

        gpu_util = find_summary(
            "gpu_sustained",
            model,
            "warm_sustained",
            "avg_gpu_util_percent",
        )

        vram = find_summary(
            "gpu_sustained",
            model,
            "warm_sustained",
            "avg_vram_mib",
        )

        power = find_summary(
            "gpu_sustained",
            model,
            "warm_sustained",
            "avg_power_w",
        )

        temperature = find_summary(
            "gpu_sustained",
            model,
            "warm_sustained",
            "max_temperature_c",
        )

        speed = find_summary(
            "gpu_sustained",
            model,
            "warm_sustained",
            "generation_tokens_per_second",
        )

        report.write(
            f"| {model} "
            f"| {gpu_util['mean']} "
            f"| {gpu_util['std_dev']} "
            f"| {vram['mean']} "
            f"| {power['mean']} "
            f"| {temperature['max']} "
            f"| {speed['mean']} |\n"
        )


    # ----------------------------------------------
    # Multi-prompt descriptive statistics
    # ----------------------------------------------

    report.write(
        "\n## Multi-Prompt Cross-Task Summary\n\n"
    )

    report.write(
        "> These statistics summarize variation "
        "across five different task categories. "
        "They should not be interpreted as repeated "
        "trials of the same workload.\n\n"
    )

    report.write(
        "| Model | Mean Latency (s) | "
        "Min | Max | Std Dev | "
        "Mean Eval Tokens | "
        "Mean Generation (tok/s) |\n"
    )

    report.write(
        "|---|---:|---:|---:|---:|---:|---:|\n"
    )


    for model in models:

        latency = find_summary(
            "multi_prompt_cross_task",
            model,
            "five_task_categories",
            "total_latency_s",
        )

        tokens = find_summary(
            "multi_prompt_cross_task",
            model,
            "five_task_categories",
            "eval_tokens",
        )

        speed = find_summary(
            "multi_prompt_cross_task",
            model,
            "five_task_categories",
            "generation_tokens_per_second",
        )

        report.write(
            f"| {model} "
            f"| {latency['mean']} "
            f"| {latency['min']} "
            f"| {latency['max']} "
            f"| {latency['std_dev']} "
            f"| {tokens['mean']} "
            f"| {speed['mean']} |\n"
        )


# ==================================================
# Terminal output
# ==================================================

print(
    "======================================"
)

print(
    "STATISTICAL SUMMARY"
)

print(
    "======================================"
)

print()

print(
    "Controlled benchmark rows:",
    len(controlled_rows),
)

print(
    "GPU benchmark rows:",
    len(gpu_rows),
)

print(
    "Multi-prompt rows:",
    len(multi_prompt_rows),
)

print()

print(
    "Summary rows:",
    len(summary_rows),
)

print()

print(
    "CSV summary:",
    SUMMARY_FILE,
)

print(
    "Markdown report:",
    REPORT_FILE,
)