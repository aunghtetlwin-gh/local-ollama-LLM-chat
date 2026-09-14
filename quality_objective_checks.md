# Objective Quality Checks

| Model | Task | Result | Details |
|---|---|---|---|
| qwen3:1.7b | knowledge | PASS | four_bullets=True; identity=True; storage=True; scaling_update=True; use_case=True |
| qwen3:1.7b | reasoning | FAIL | correct_combination=True; nonempty_lines=11; within_four_lines=False |
| qwen3:1.7b | coding | PASS | no_counter=True; no_markdown_fence=True; parses=True; function_exists=True; tests_pass=True |
| qwen3:1.7b | summarization | PASS | sentence_count=2; exactly_two=True |
| qwen3:1.7b | instruction | PASS | lines=['COUNT=3', 'SUM=19', 'MAX=9']; exact_match=True |
| qwen3:8b | knowledge | PASS | four_bullets=True; identity=True; storage=True; scaling_update=True; use_case=True |
| qwen3:8b | reasoning | PASS | correct_combination=True; nonempty_lines=3; within_four_lines=True |
| qwen3:8b | coding | PASS | no_counter=True; no_markdown_fence=True; parses=True; function_exists=True; tests_pass=True |
| qwen3:8b | summarization | PASS | sentence_count=2; exactly_two=True |
| qwen3:8b | instruction | PASS | lines=['COUNT=3', 'SUM=19', 'MAX=9']; exact_match=True |
| gemma4:12b | knowledge | PASS | four_bullets=True; identity=True; storage=True; scaling_update=True; use_case=True |
| gemma4:12b | reasoning | FAIL | correct_combination=True; nonempty_lines=5; within_four_lines=False |
| gemma4:12b | coding | PASS | no_counter=True; no_markdown_fence=True; parses=True; function_exists=True; tests_pass=True |
| gemma4:12b | summarization | PASS | sentence_count=2; exactly_two=True |
| gemma4:12b | instruction | PASS | lines=['COUNT=3', 'SUM=19', 'MAX=9']; exact_match=True |
