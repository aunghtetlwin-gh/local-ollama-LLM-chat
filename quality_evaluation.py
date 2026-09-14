import ast
import csv
import re
from pathlib import Path


INPUT_FILE = Path("multi_prompt_results.csv")
OUTPUT_FILE = Path("quality_objective_checks.csv")
REPORT_FILE = Path("quality_objective_checks.md")


# ==================================================
# Read results
# ==================================================

with INPUT_FILE.open(
    newline="",
    encoding="utf-8",
) as file:

    rows = list(
        csv.DictReader(file)
    )


# ==================================================
# Helpers
# ==================================================

def normalize_lines(text):

    return [
        line.strip()
        for line in text.strip().splitlines()
        if line.strip()
    ]


def count_sentences(text):

    # Sufficient for our controlled benchmark text.
    sentences = re.split(
        r"(?<=[.!?])\s+",
        text.strip(),
    )

    return len(
        [
            sentence
            for sentence in sentences
            if sentence.strip()
        ]
    )


# ==================================================
# Knowledge check
# ==================================================

def check_knowledge(response):

    lines = normalize_lines(response)

    bullet_lines = [
        line
        for line in lines
        if (
            line.startswith("-")
            or line.startswith("*")
        )
    ]

    exactly_four_bullets = (
        len(bullet_lines) == 4
    )

    text = response.lower()

    identity_covered = (
        "identity" in text
        or "identities" in text
    )

    storage_covered = (
        "storage" in text
        or "persistent" in text
    )

    scaling_update_covered = (
        "scal" in text
        and "update" in text
    )

    use_case_covered = (
        "use case" in text
        or "stateless" in text
        or "database" in text
    )

    passed = all(
        [
            exactly_four_bullets,
            identity_covered,
            storage_covered,
            scaling_update_covered,
            use_case_covered,
        ]
    )

    details = (
        f"four_bullets={exactly_four_bullets}; "
        f"identity={identity_covered}; "
        f"storage={storage_covered}; "
        f"scaling_update={scaling_update_covered}; "
        f"use_case={use_case_covered}"
    )

    return passed, details


# ==================================================
# Reasoning check
# ==================================================

def check_reasoning(response):

    text = response.lower()

    has_16 = (
        "16" in text
    )

    mentions_a = (
        "model a" in text
        or re.search(r"\ba\b", text)
    )

    mentions_b = (
        "model b" in text
        or re.search(r"\bb\b", text)
    )

    mentions_c = (
        "model c" in text
        or re.search(r"\bc\b", text)
    )

    correct_combination = bool(
        has_16
        and mentions_a
        and mentions_b
        and mentions_c
    )

    lines = normalize_lines(response)

    within_four_lines = (
        len(lines) <= 4
    )

    passed = (
        correct_combination
        and within_four_lines
    )

    details = (
        f"correct_combination={correct_combination}; "
        f"nonempty_lines={len(lines)}; "
        f"within_four_lines={within_four_lines}"
    )

    return passed, details


# ==================================================
# Coding check
# ==================================================

def check_coding(response):

    no_counter = (
        "Counter" not in response
        and "collections.counter"
        not in response.lower()
    )

    no_markdown_fence = (
        "```" not in response
    )

    parses = False
    function_exists = False
    tests_pass = False

    try:

        tree = ast.parse(response)

        parses = True

        function_exists = any(
            isinstance(node, ast.FunctionDef)
            and node.name == "first_unique"
            for node in tree.body
        )

        namespace = {}

        exec(
            compile(
                tree,
                filename="<benchmark>",
                mode="exec",
            ),
            namespace,
        )

        function = namespace.get(
            "first_unique"
        )

        if callable(function):

            test_cases = [
                (
                    [4, 5, 4, 6, 5],
                    6,
                ),

                (
                    [1, 1, 2, 2],
                    None,
                ),

                (
                    [7],
                    7,
                ),

                (
                    ["a", "b", "a", "c"],
                    "b",
                ),

                (
                    [],
                    None,
                ),
            ]

            tests_pass = all(
                function(items) == expected
                for items, expected
                in test_cases
            )

    except Exception:
        pass


    passed = all(
        [
            no_counter,
            no_markdown_fence,
            parses,
            function_exists,
            tests_pass,
        ]
    )

    details = (
        f"no_counter={no_counter}; "
        f"no_markdown_fence={no_markdown_fence}; "
        f"parses={parses}; "
        f"function_exists={function_exists}; "
        f"tests_pass={tests_pass}"
    )

    return passed, details


# ==================================================
# Summarization check
# ==================================================

def check_summarization(response):

    sentence_count = count_sentences(
        response
    )

    exactly_two = (
        sentence_count == 2
    )

    details = (
        f"sentence_count={sentence_count}; "
        f"exactly_two={exactly_two}"
    )

    return exactly_two, details


# ==================================================
# Instruction check
# ==================================================

def check_instruction(response):

    # Remove trailing Markdown whitespace.
    cleaned_lines = [
        line.rstrip().strip()
        for line in response.strip().splitlines()
        if line.strip()
    ]

    expected = [
        "COUNT=3",
        "SUM=19",
        "MAX=9",
    ]

    exact_match = (
        cleaned_lines == expected
    )

    details = (
        f"lines={cleaned_lines}; "
        f"exact_match={exact_match}"
    )

    return exact_match, details


# ==================================================
# Run checks
# ==================================================

evaluated = []


for row in rows:

    task_id = row["task_id"]
    response = row["response"]

    if task_id == "knowledge":
        passed, details = (
            check_knowledge(response)
        )

    elif task_id == "reasoning":
        passed, details = (
            check_reasoning(response)
        )

    elif task_id == "coding":
        passed, details = (
            check_coding(response)
        )

    elif task_id == "summarization":
        passed, details = (
            check_summarization(response)
        )

    elif task_id == "instruction":
        passed, details = (
            check_instruction(response)
        )

    else:
        passed = False
        details = "unknown_task"


    evaluated.append(
        {
            "model": row["model"],
            "task_id": task_id,
            "category": row["category"],
            "objective_pass": passed,
            "details": details,
        }
    )


# ==================================================
# Write CSV
# ==================================================

fieldnames = [
    "model",
    "task_id",
    "category",
    "objective_pass",
    "details",
]


with OUTPUT_FILE.open(
    "w",
    newline="",
    encoding="utf-8",
) as file:

    writer = csv.DictWriter(
        file,
        fieldnames=fieldnames,
    )

    writer.writeheader()
    writer.writerows(evaluated)


# ==================================================
# Markdown report
# ==================================================

with REPORT_FILE.open(
    "w",
    encoding="utf-8",
) as report:

    report.write(
        "# Objective Quality Checks\n\n"
    )

    report.write(
        "| Model | Task | Result | Details |\n"
    )

    report.write(
        "|---|---|---|---|\n"
    )

    for row in evaluated:

        status = (
            "PASS"
            if row["objective_pass"]
            else "FAIL"
        )

        details = (
            row["details"]
            .replace("|", "\\|")
        )

        report.write(
            f"| {row['model']} "
            f"| {row['task_id']} "
            f"| {status} "
            f"| {details} |\n"
        )


# ==================================================
# Terminal summary
# ==================================================

print(
    "======================================"
)

print(
    "OBJECTIVE QUALITY CHECKS"
)

print(
    "======================================"
)

print()


for model in [
    "qwen3:1.7b",
    "qwen3:8b",
    "gemma4:12b",
]:

    model_rows = [
        row
        for row in evaluated
        if row["model"] == model
    ]

    passed = sum(
        1
        for row in model_rows
        if row["objective_pass"]
    )

    print(
        f"{model}: "
        f"{passed}/{len(model_rows)} "
        "objective checks passed"
    )


print()

print(
    "Detailed CSV:",
    OUTPUT_FILE,
)

print(
    "Readable report:",
    REPORT_FILE,
)