"""Isolated stdlib tests; never import the application or execute responses."""
import ast
import csv
import importlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import quality_evaluation as evaluator


FUNCTION = "def first_unique(items):\n    return None\n"


def coding_row(response=FUNCTION):
    return {"model": "synthetic", "task_id": "coding",
            "category": "coding", "response": response}


class StaticCodingTests(unittest.TestCase):
    def test_structurally_valid_code_does_not_claim_correctness(self):
        row = evaluator.evaluate_rows([coding_row()])[0]
        self.assertTrue(row["static_checks_pass"])
        self.assertIsNone(row["objective_pass"])
        self.assertEqual(row["coding_correctness"], "not evaluated")
        self.assertIn("execution=disabled", row["details"])

    def test_invalid_structure(self):
        sources = ["", "def broken(:", "x = 1", "\x00",
                   "async " + FUNCTION, FUNCTION + FUNCTION,
                   "@decorator\n" + FUNCTION,
                   FUNCTION.replace("items", "other"),
                   FUNCTION.replace("items", "items=None"),
                   FUNCTION.replace("items", "items, extra"),
                   FUNCTION.replace("items", "*items"),
                   FUNCTION.replace("items", "items, **kwargs"),
                   FUNCTION.replace("items", "*, items"),
                   "```python\n" + FUNCTION + "```"]
        for source in sources:
            with self.subTest(source=source):
                passed, details = evaluator.check_coding(source)
                self.assertFalse(passed)
                self.assertIn("coding_correctness=not evaluated", details)

    def test_counter_ast_checks(self):
        sources = ["from collections import Counter as C\n",
                   "from collections import *\n",
                   "import collections as c\nc.Counter([])\n",
                   "Counter([])\n"]
        for prefix in sources:
            with self.subTest(prefix=prefix):
                self.assertFalse(evaluator.check_coding(prefix + FUNCTION)[0])
        self.assertTrue(evaluator.check_coding(
            '# Counter in a comment\n"Counter in a string"\n' + FUNCTION)[0])

    def test_top_level_and_function_bodies_are_never_executed(self):
        with tempfile.TemporaryDirectory() as directory:
            sentinel = Path(directory) / "must-not-exist"
            source = (
                "import nonexistent_generated_module\n"
                f"open({str(sentinel)!r}, 'w').write('executed')\n"
                "raise RuntimeError('must not execute')\n"
                "def first_unique(items):\n"
                "    raise RuntimeError('must not call')\n"
            )
            self.assertTrue(evaluator.check_coding(source)[0])
            self.assertFalse(sentinel.exists())

    def test_default_expression_is_not_executed(self):
        source = "def first_unique(items=1/0):\n    return items\n"
        self.assertFalse(evaluator.check_coding(source)[0])

    def test_large_input_is_not_parsed(self):
        with patch.object(evaluator.ast, "parse") as parse:
            self.assertFalse(evaluator.check_coding(
                " " * (evaluator.MAX_CODE_CHARACTERS + 1))[0])
            parse.assert_not_called()

    def test_parser_recursion_error_is_a_static_failure(self):
        with patch.object(evaluator.ast, "parse", side_effect=RecursionError):
            self.assertFalse(evaluator.check_coding(FUNCTION)[0])

    def test_no_execution_primitives_in_evaluator(self):
        tree = ast.parse(Path(evaluator.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = (node.func.id if isinstance(node.func, ast.Name)
                        else node.func.attr if isinstance(node.func, ast.Attribute)
                        else None)
                self.assertNotIn(name, {"exec", "eval", "compile", "system",
                                        "Popen", "run", "check_output", "check_call"})


class ReportTests(unittest.TestCase):
    def test_import_has_no_report_or_input_io(self):
        with patch.object(Path, "open") as opened, \
                patch.object(Path, "mkdir") as mkdir:
            importlib.reload(evaluator)
            opened.assert_not_called()
            mkdir.assert_not_called()

    def test_report_separates_static_checks_from_correctness(self):
        with tempfile.TemporaryDirectory() as directory:
            rows = evaluator.evaluate_rows([coding_row()])
            csv_path, md_path = evaluator.write_reports(rows, Path(directory) / "new")
            with csv_path.open(newline="", encoding="utf-8") as file:
                row = next(csv.DictReader(file))
            self.assertEqual(row["objective_pass"], "")
            self.assertEqual(row["static_checks_pass"], "True")
            self.assertEqual(row["coding_correctness"], "not evaluated")
            self.assertIn("| not evaluated | PASS | not evaluated |",
                          md_path.read_text(encoding="utf-8"))

    def test_existing_directory_and_reports_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            historical = Path(directory) / "quality_objective_checks.csv"
            historical.write_bytes(b"historical results\n")
            with self.assertRaises(FileExistsError):
                evaluator.write_reports([], directory)
            self.assertEqual(historical.read_bytes(), b"historical results\n")
            destination = Path(directory) / "new"
            csv_path, _ = evaluator.write_reports([], destination)
            before = csv_path.read_bytes()
            with self.assertRaises(FileExistsError):
                evaluator.write_reports([], destination)
            self.assertEqual(csv_path.read_bytes(), before)

    def test_cli_requires_explicit_output_directory(self):
        with patch.object(Path, "open") as opened, \
                patch("sys.stderr"), self.assertRaises(SystemExit) as raised:
            evaluator.main([])
        self.assertEqual(raised.exception.code, 2)
        opened.assert_not_called()

    def test_other_task_checks_keep_objective_results(self):
        row = coding_row("COUNT=3\nSUM=19\nMAX=9")
        row["task_id"] = "instruction"
        result = evaluator.evaluate_rows([row])[0]
        self.assertTrue(result["objective_pass"])
        self.assertIsNone(result["static_checks_pass"])
        self.assertEqual(result["coding_correctness"], "not applicable")


if __name__ == "__main__":
    unittest.main()
