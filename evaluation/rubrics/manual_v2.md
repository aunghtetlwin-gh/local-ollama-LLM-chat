# Manual rubric v2

Use final assistant content only. Reference criteria are in evaluator-only references.jsonl.
Score independently before discussion. Review repetition 1 as primary; repeated identical
response hashes may reuse a rating, while changed responses need separate assessment.
Keep independent ratings and adjudicated scores in separate new files. Do not overwrite
an export with completed ratings; copy it to a rater-specific new filename.

| Dimension | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| Correctness/fidelity | Fundamentally wrong or contradictory | Major error changes answer | Partly correct; material error remains | Correct core with minor imprecision | All material claims/calculations correct |
| Instruction following | Main instructions ignored | Several major violations | One major or several minor violations | One minor violation | All explicit constraints satisfied |
| Relevance | Off topic | Mostly irrelevant | Relevant answer with substantial diversion | Almost entirely relevant | Entirely focused |
| Completeness | Essential answer absent | Most required elements absent | Some required elements absent | All major elements, minor omission | Every required element covered |
| Conciseness/clarity | Unusable/confusing | Major repetition/ambiguity | Understandable but inefficient | Clear with minor excess | Clear, economical, sufficient |

For empty, interrupted, truncated, transport-error, or malformed responses, preserve the
failure status. Do not mark them successful. Zero aggregate credit is distinct from a
1–5 rating; leave unavailable dimensions blank. A valid but incorrect answer receives
ordinary dimension ratings. Do not penalize an answer's mathematics because it exceeds
a line limit; record the line violation under instruction following.

Knowledge: check each stated proposition and reject unsupported absolutes. Summaries:
check every required source fact, numbers, chronology, and preservation of uncertainty;
no invented causal claims. Coding: manually trace the documented examples and inspect
edge cases without running the source. Label any correctness rating "manual algorithm
assessment". Runtime correctness remains NOT EVALUATED regardless of static success.

Record reviewer ID, each dimension, and a short rationale citing response text for material
deductions. Two reviewers should calibrate on separate development examples, then score
blindly. Share manual_review.csv, not private_blind_mapping.json. Model self-identification
in answer text may compromise blinding; record it without altering the raw response.
Report pre-adjudication exact agreement, agreement within one point, and optionally
weighted kappa (with small-sample caveats). Preserve disagreements and resolution reasons.

Report per-dimension and per-category means. A /25 total is secondary. Macro-average the
five equally sized internal categories; never combine it with GSM8K accuracy as one score.
