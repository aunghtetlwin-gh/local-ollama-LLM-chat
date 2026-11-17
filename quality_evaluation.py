import argparse
import ast
import csv
import re
from pathlib import Path


INPUT_FILE = Path("multi_prompt_results.csv")
MAX_CODE_CHARACTERS = 100_000

# Importing this module performs no evaluation or file I/O.


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
    """Check source structure only. Never execute or certify generated code.

    Counter detection is deliberately conservative, not alias/data-flow analysis.
    A passing result establishes neither functional correctness nor code safety.
    The size limit bounds parser input; it is not a general resource sandbox.
    """
    no_markdown_fence = "```" not in response
    within_size_limit = len(response) <= MAX_CODE_CHARACTERS
    parses = False
    function_exists = False
    signature_matches = False
    no_counter = False

    if within_size_limit:
        try:
            tree = ast.parse(response)
            parses = True
            functions = [node for node in tree.body
                         if isinstance(node, ast.FunctionDef)
                         and node.name == "first_unique"]
            function_exists = len(functions) == 1
            if function_exists:
                function = functions[0]
                args = function.args
                positional = args.posonlyargs + args.args
                signature_matches = (
                    len(positional) == 1 and positional[0].arg == "items"
                    and not args.defaults and not args.kwonlyargs
                    and args.vararg is None and args.kwarg is None
                    and not function.decorator_list
                )
            no_counter = not any(
                (isinstance(node, ast.Name) and node.id == "Counter")
                or (isinstance(node, ast.Attribute) and node.attr == "Counter")
                or (isinstance(node, ast.ImportFrom)
                    and node.module == "collections"
                    and any(alias.name in {"Counter", "*"} for alias in node.names))
                for node in ast.walk(tree)
            )
        except (SyntaxError, ValueError, RecursionError):
            # Syntax errors, NUL bytes, or excessive parser nesting are failures.
            pass

    static_pass = all((within_size_limit, no_markdown_fence, parses,
                       function_exists, signature_matches, no_counter))
    details = (
        f"within_size_limit={within_size_limit}; "
        f"no_counter={no_counter}; no_markdown_fence={no_markdown_fence}; "
        f"parses={parses}; function_exists={function_exists}; "
        f"signature_matches={signature_matches}; "
        "coding_correctness=not evaluated; execution=disabled"
    )
    return static_pass, details


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
# Explicit evaluation and reporting (no import-time work)
# ==================================================

def evaluate_rows(rows):
    checks = {
        "knowledge": check_knowledge,
        "reasoning": check_reasoning,
        "coding": check_coding,
        "summarization": check_summarization,
        "instruction": check_instruction,
    }
    evaluated = []
    for row in rows:
        task = row["task_id"]
        check = checks.get(task)
        passed, details = check(row["response"]) if check else (False, "unknown_task")
        coding = task == "coding"
        evaluated.append({
            "model": row["model"],
            "task_id": task,
            "category": row["category"],
            # None becomes an empty CSV cell, never a correctness PASS/FAIL.
            "objective_pass": None if coding else passed,
            "static_checks_pass": passed if coding else None,
            "coding_correctness": "not evaluated" if coding else "not applicable",
            "details": details,
        })
    return evaluated


def write_reports(evaluated, output_dir):
    """Write only into a new directory; refuse reuse of any existing path."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    csv_path = output_dir / "quality_static_checks.csv"
    report_path = output_dir / "quality_static_checks.md"
    fields = ["model", "task_id", "category", "objective_pass",
              "static_checks_pass", "coding_correctness", "details"]
    with csv_path.open("x", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(evaluated)
    with report_path.open("x", encoding="utf-8") as report:
        report.write(
            "# Static Quality Checks\n\n"
            "Generated Python is never executed. Coding correctness is **not evaluated**. "
            "Static PASS means only the listed source checks passed; it does not "
            "establish correctness or safety. Other task checks retain their existing heuristics.\n\n"
            "| Model | Task | Objective result | Static checks | Coding correctness | Details |\n"
            "|---|---|---|---|---|---|\n"
        )
        for row in evaluated:
            objective = row["objective_pass"]
            static = row["static_checks_pass"]
            values = [row["model"], row["task_id"],
                      "not evaluated" if objective is None else ("PASS" if objective else "FAIL"),
                      "not applicable" if static is None else ("PASS" if static else "FAIL"),
                      row["coding_correctness"], row["details"]]
            report.write("| " + " | ".join(
                str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")
                for value in values
            ) + " |\n")
    return csv_path, report_path


def main(argv=None):
    parser = argparse.ArgumentParser(description="Non-executing quality checks for saved responses.")
    parser.add_argument("--input", type=Path, default=INPUT_FILE)
    parser.add_argument("--output-dir", type=Path, required=True,
                        help="New directory that must not already exist; historical reports are never overwritten.")
    args = parser.parse_args(argv)
    try:
        with args.input.open(newline="", encoding="utf-8") as file:
            evaluated = evaluate_rows(csv.DictReader(file))
        csv_path, report_path = write_reports(evaluated, args.output_dir)
    except (OSError, csv.Error, KeyError) as error:
        parser.exit(1, f"Evaluation stopped: {error}\n")
    print("Coding correctness: not evaluated (execution disabled).")
    print(f"Static-check CSV: {csv_path}")
    print(f"Static-check report: {report_path}")


if __name__ == "__main__":
    main()
