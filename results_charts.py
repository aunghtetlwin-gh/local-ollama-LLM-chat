import csv
import statistics
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt


# ==================================================
# Files
# ==================================================

CONTROLLED_FILE = Path(
    "benchmark_controlled_seed42.csv"
)

GPU_FILE = Path(
    "benchmark_gpu_long.csv"
)

QUALITY_FILE = Path(
    "quality_manual_scores.csv"
)

OBJECTIVE_FILE = Path(
    "quality_objective_checks.csv"
)

OUTPUT_DIR = Path("charts")

SUMMARY_CSV = Path(
    "final_model_summary.csv"
)

SUMMARY_MD = Path(
    "final_results_summary.md"
)


# ==================================================
# Models
# ==================================================

MODELS = [
    "qwen3:1.7b",
    "qwen3:8b",
    "gemma4:12b",
]

LABELS = {
    "qwen3:1.7b": "Qwen3 1.7B",
    "qwen3:8b": "Qwen3 8B",
    "gemma4:12b": "Gemma4 12B",
}


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


def mean(values):

    return statistics.mean(
        float(value)
        for value in values
    )


def save_bar_chart(
    labels,
    values,
    title,
    ylabel,
    filename,
    value_format="{:.2f}",
):

    plt.figure(
        figsize=(8, 5)
    )

    bars = plt.bar(
        labels,
        values,
    )

    plt.title(title)

    plt.ylabel(ylabel)

    plt.xlabel("Model")

    plt.grid(
        axis="y",
        alpha=0.25,
    )

    for bar, value in zip(
        bars,
        values,
    ):

        plt.text(
            bar.get_x()
            + bar.get_width() / 2,

            bar.get_height(),

            value_format.format(value),

            ha="center",
            va="bottom",
        )

    plt.tight_layout()

    plt.savefig(
        OUTPUT_DIR / filename,
        dpi=200,
    )

    plt.close()


# ==================================================
# Load files
# ==================================================

controlled_rows = read_csv(
    CONTROLLED_FILE
)

gpu_rows = read_csv(
    GPU_FILE
)

quality_rows = read_csv(
    QUALITY_FILE
)

objective_rows = read_csv(
    OBJECTIVE_FILE
)


OUTPUT_DIR.mkdir(
    exist_ok=True
)


# ==================================================
# Controlled warm performance
# ==================================================

warm_groups = defaultdict(list)

for row in controlled_rows:

    if row["run_type"] == "warm":

        warm_groups[
            row["model"]
        ].append(row)


# ==================================================
# GPU sustained results
# ==================================================

gpu_groups = defaultdict(list)

for row in gpu_rows:

    gpu_groups[
        row["model"]
    ].append(row)


# ==================================================
# Quality results
# ==================================================

quality_groups = defaultdict(list)

for row in quality_rows:

    quality_groups[
        row["model"]
    ].append(row)


objective_groups = defaultdict(list)

for row in objective_rows:

    objective_groups[
        row["model"]
    ].append(row)


# ==================================================
# Build final model summary
# ==================================================

summary = []


for model in MODELS:

    warm = warm_groups[model]

    gpu = gpu_groups[model]

    quality = quality_groups[model]

    objective = objective_groups[model]


    # ----------------------------------------------
    # Performance
    # ----------------------------------------------

    warm_latency = mean(
        row["total_latency_s"]
        for row in warm
    )


    # Use sustained 1024-token GPU workload
    # for stable generation-speed comparison.

    generation_speed = mean(
        row["generation_tokens_per_second"]
        for row in gpu
    )


    # ----------------------------------------------
    # Hardware
    # ----------------------------------------------

    gpu_util = mean(
        row["avg_gpu_util_percent"]
        for row in gpu
    )

    vram_mib = mean(
        row["peak_vram_mib"]
        for row in gpu
    )

    power_w = mean(
        row["avg_power_w"]
        for row in gpu
    )

    max_temperature = max(
        float(row["max_temperature_c"])
        for row in gpu
    )


    # ----------------------------------------------
    # Human quality score
    # ----------------------------------------------

    quality_total = sum(
        int(row["total"])
        for row in quality
    )

    # 5 tasks × 25 points = 125 maximum

    quality_percent = (
        quality_total / 125
    ) * 100

    # 25 individual rubric criteria total.
    quality_average_5 = (
        quality_total / 25
    )


    # ----------------------------------------------
    # Objective quality checks
    # ----------------------------------------------

    objective_passes = sum(
        1
        for row in objective
        if (
            row["objective_pass"]
            .strip()
            .lower()
            == "true"
        )
    )


    summary.append(
        {
            "model": model,

            "display_name":
                LABELS[model],

            "warm_latency_s":
                round(
                    warm_latency,
                    3,
                ),

            "generation_speed_tok_s":
                round(
                    generation_speed,
                    2,
                ),

            "avg_gpu_util_percent":
                round(
                    gpu_util,
                    2,
                ),

            "vram_mib":
                round(
                    vram_mib,
                    2,
                ),

            "vram_gib":
                round(
                    vram_mib / 1024,
                    2,
                ),

            "avg_power_w":
                round(
                    power_w,
                    2,
                ),

            "max_temperature_c":
                round(
                    max_temperature,
                    2,
                ),

            "quality_total_125":
                quality_total,

            "quality_average_5":
                round(
                    quality_average_5,
                    2,
                ),

            "quality_percent":
                round(
                    quality_percent,
                    2,
                ),

            "objective_passes":
                objective_passes,

            "objective_total":
                len(objective),
        }
    )


# ==================================================
# Write final CSV
# ==================================================

fieldnames = [
    "model",
    "display_name",

    "warm_latency_s",
    "generation_speed_tok_s",

    "avg_gpu_util_percent",

    "vram_mib",
    "vram_gib",

    "avg_power_w",
    "max_temperature_c",

    "quality_total_125",
    "quality_average_5",
    "quality_percent",

    "objective_passes",
    "objective_total",
]


with SUMMARY_CSV.open(
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
        summary
    )


# ==================================================
# Chart data
# ==================================================

labels = [
    row["display_name"]
    for row in summary
]


# ==================================================
# 1. Warm latency
# ==================================================

save_bar_chart(
    labels,

    [
        row["warm_latency_s"]
        for row in summary
    ],

    "Warm Inference Latency",

    "Latency (seconds)",

    "warm_latency.png",

    "{:.2f}",
)


# ==================================================
# 2. Generation throughput
# ==================================================

save_bar_chart(
    labels,

    [
        row["generation_speed_tok_s"]
        for row in summary
    ],

    "Sustained Generation Speed",

    "Tokens per second",

    "generation_speed.png",

    "{:.1f}",
)


# ==================================================
# 3. VRAM usage
# ==================================================

save_bar_chart(
    labels,

    [
        row["vram_gib"]
        for row in summary
    ],

    "GPU Memory Usage During Inference",

    "VRAM (GiB)",

    "vram_usage.png",

    "{:.2f}",
)


# ==================================================
# 4. Average power
# ==================================================

save_bar_chart(
    labels,

    [
        row["avg_power_w"]
        for row in summary
    ],

    "Average GPU Power During Sustained Inference",

    "Power (W)",

    "power_usage.png",

    "{:.1f}",
)


# ==================================================
# 5. GPU utilization
# ==================================================

save_bar_chart(
    labels,

    [
        row["avg_gpu_util_percent"]
        for row in summary
    ],

    "Average GPU Utilization",

    "GPU utilization (%)",

    "gpu_utilization.png",

    "{:.1f}%",
)


# ==================================================
# 6. Quality score
# ==================================================

save_bar_chart(
    labels,

    [
        row["quality_average_5"]
        for row in summary
    ],

    "Response Quality Score",

    "Average score (1–5)",

    "quality_score.png",

    "{:.2f}",
)


# ==================================================
# Markdown final report
# ==================================================

with SUMMARY_MD.open(
    "w",
    encoding="utf-8",
) as report:

    report.write(
        "# Final Model Comparison\n\n"
    )

    report.write(
        "| Model | Warm Latency (s) | "
        "Generation (tok/s) | "
        "VRAM (GiB) | GPU Util (%) | "
        "Power (W) | Max Temp (C) | "
        "Quality (/5) | Objective |\n"
    )

    report.write(
        "|---|---:|---:|---:|---:|---:|"
        "---:|---:|---:|\n"
    )


    for row in summary:

        report.write(
            f"| {row['display_name']} "
            f"| {row['warm_latency_s']} "
            f"| {row['generation_speed_tok_s']} "
            f"| {row['vram_gib']} "
            f"| {row['avg_gpu_util_percent']} "
            f"| {row['avg_power_w']} "
            f"| {row['max_temperature_c']} "
            f"| {row['quality_average_5']} "
            f"| {row['objective_passes']}/"
            f"{row['objective_total']} |\n"
        )


    report.write(
        "\n## Interpretation\n\n"
    )

    report.write(
        "- **Qwen3 1.7B:** lowest resource usage "
        "and highest generation throughput, "
        "but lower overall quality than the "
        "larger models in this benchmark.\n"
    )

    report.write(
        "- **Qwen3 8B:** strongest overall "
        "quality result while retaining "
        "substantially lower latency and VRAM "
        "use than Gemma4 12B.\n"
    )

    report.write(
        "- **Gemma4 12B:** strong response "
        "quality but highest VRAM requirement "
        "and slowest generation speed.\n"
    )

    report.write(
        "\nThese results demonstrate a trade-off "
        "between inference performance, hardware "
        "resource consumption, and response quality.\n"
    )


# ==================================================
# Terminal summary
# ==================================================

print(
    "======================================"
)

print(
    "FINAL RESULTS"
)

print(
    "======================================"
)

print()

print(
    f"{'MODEL':<15}"
    f"{'LATENCY':<10}"
    f"{'TOK/S':<10}"
    f"{'VRAM':<10}"
    f"{'GPU%':<10}"
    f"{'POWER':<10}"
    f"{'QUALITY':<10}"
)

print("-" * 75)


for row in summary:

    print(
        f"{row['display_name']:<15}"
        f"{row['warm_latency_s']:<10}"
        f"{row['generation_speed_tok_s']:<10}"
        f"{row['vram_gib']:<10}"
        f"{row['avg_gpu_util_percent']:<10}"
        f"{row['avg_power_w']:<10}"
        f"{row['quality_average_5']:<10}"
    )


print()

print(
    "Summary CSV:",
    SUMMARY_CSV,
)

print(
    "Summary report:",
    SUMMARY_MD,
)

print()

print(
    "Charts:"
)

for path in sorted(
    OUTPUT_DIR.glob("*.png")
):

    print(
        " -",
        path,
    )