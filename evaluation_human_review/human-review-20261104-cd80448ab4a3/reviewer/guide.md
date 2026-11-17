# Blinded human correctness review — 36 responses

Review only the contents of this reviewer folder. Do not consult model identities,
automatic score summaries, timings, or private mappings. Keep the existing blind IDs.
There are 12 questions with three independently labelled answers each: four coding,
four knowledge, four summarization questions. No model assignments are supplied.

## Conducting the review

1. Open booklet.html in a browser. It is a static local document: no scripts, network
   requests, submit button, executable responses, or embedded model identities.
2. Copy ratings_template.csv to ratings_R1.csv (use a different filename/ID for each
   independent reviewer). Open the copy in a spreadsheet or UTF-8 CSV editor. One row
   corresponds to one blind ID. Do not edit blind_id, question_id, or category.
3. Read the complete question, its reference criteria below, and the exact response.
   Enter a stable reviewer_id, an explicit human_verdict, a 1–5 correctness rating,
   and a rationale. The other four original rubric dimensions are optional in this
   minimal correctness review; fill them only if you assess them. Cite response text for material deductions. Add blinding_note if
   you recognize an identity or already know this particular response.
4. Review independently before discussion. For code, trace the existing examples and
   specified edge cases on paper; never run, import or evaluate the answer as code.
   Code correctness is a MANUAL ALGORITHM ASSESSMENT; runtime correctness stays untested.
5. Save the completed copy as UTF-8 CSV, preserving the header. Keep original template,
   response packet, guide and rubric unchanged. Return only your completed ratings copy
   to the coordinator. Do not send or request any private mapping.

## Decisions and ratings

The original rubric in rubric.md is unchanged: correctness/fidelity, instruction following,
relevance, completeness, and conciseness/clarity, each 1–5. Record formatting violations
under instruction following; do not mark a semantically correct answer wrong solely for
line/bullet count or fences. Do not rewrite or repair responses. Do not assume code is
correct merely because it parses or uses the expected signature.

human_verdict is an additional explicitly HUMAN descriptive judgement, separate from both
the original automatic results and the original ordinal ratings:

- correct: all material question-specific correctness/fidelity requirements are satisfied;
  no substantive error or omission is identified. Pure output-format violations are separate.
- partly_correct: some required material is correct, but a substantive error or omission remains.
- incorrect: the central answer/algorithm is wrong, contradictory, or fails essential requirements.
- uncertain: you cannot confidently assess correctness; explain why. Never invent a rating.

No correctness threshold is calculated from a 1–5 rating. The coordinator reports the
human verdict proportions under their own label, not as automatic benchmark accuracy.
Partly correct remains a separate count and is not assigned invented half credit.
A correctness rating and rationale are required for a decided response. For uncertain,
leave unassessable correctness blank. The other four dimensions are optional; retain
blanks if you do not assess them. Their coverage will be reported explicitly. Missing
ratings are not zeros. All 36 rows need an explicit verdict and reviewer ID before import.
Numeric ratings must be integers 1–5. The rationale is required even for correct/uncertain.

Use the provided criteria consistently across the three answers to a question. Apply
only the question/reference requirements; do not add personal style preferences or new
facts/requirements. Knowledge answers should not add unsupported absolutes. Summaries
must preserve the original facts and uncertainty without invented causal conclusions.

## Original rubric anchors

| Dimension | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| Correctness/fidelity | Fundamentally wrong or contradictory | Major error changes answer | Partly correct; material error remains | Correct core with minor imprecision | All material claims/calculations correct |
| Instruction following | Main instructions ignored | Several major violations | One major or several minor violations | One minor violation | All explicit constraints satisfied |
| Relevance | Off topic | Mostly irrelevant | Relevant answer with substantial diversion | Almost entirely relevant | Entirely focused |
| Completeness | Essential answer absent | Most required elements absent | Some required elements absent | All major elements, minor omission | Every required element covered |
| Conciseness/clarity | Unusable/confusing | Major repetition/ambiguity | Understandable but inefficient | Clear with minor excess | Clear, economical, sufficient |


## Question-specific correctness criteria

### C01 — coding

Question:

> Write a Python function stable_unique(items). Input is a list of strings. Return a new list with duplicate strings removed, preserving first-occurrence order. An empty input returns []. Do not mutate the input. Do not import modules. Return only the function definition, with no Markdown fences, decorators, type annotations, or explanation.

Existing acceptance criteria:

- Use string equality to identify duplicates.
- Preserve first occurrence order and the input.
- Empty list returns []; all duplicates collapse to one.

Existing reference examples to trace manually (JSON null means Python None):

```json
[
  {
    "input": [],
    "output": []
  },
  {
    "input": [
      "b",
      "a",
      "b",
      "c",
      "a"
    ],
    "output": [
      "b",
      "a",
      "c"
    ]
  }
]
```

### C02 — coding

Question:

> Write a Python function second_largest(items). Input is a list of integers (not booleans). Return the second-largest distinct value, or None when fewer than two distinct values exist. Do not mutate the input. Do not import modules. Return only the function definition, with no Markdown fences, decorators, type annotations, or explanation.

Existing acceptance criteria:

- Ignore repeated equal values.
- Handle negative integers and empty lists.
- Return None for fewer than two distinct values.

Existing reference examples to trace manually (JSON null means Python None):

```json
[
  {
    "input": [
      5,
      5,
      2,
      1
    ],
    "output": 2
  },
  {
    "input": [
      -3,
      -1,
      -2
    ],
    "output": -2
  },
  {
    "input": [],
    "output": null
  }
]
```

### C03 — coding

Question:

> Write a Python function chunks(items, size). Input items is a list and size is an integer (not a boolean). Return a new list of consecutive sublists of at most size elements, preserving order. Keep a final short chunk. Empty items returns []. Raise ValueError if size <= 0, including for empty items. Do not mutate items or import modules. Return only the function definition, with no Markdown fences, decorators, type annotations, or explanation.

Existing acceptance criteria:

- Reject nonpositive size before returning for empty input.
- Keep every element exactly once in order.
- Final short chunk is retained; size larger than input is valid.

Existing reference examples to trace manually (JSON null means Python None):

```json
[
  {
    "input": [
      [
        1,
        2,
        3,
        4,
        5
      ],
      2
    ],
    "output": [
      [
        1,
        2
      ],
      [
        3,
        4
      ],
      [
        5
      ]
    ]
  },
  {
    "input": [
      [],
      0
    ],
    "raises": "ValueError"
  }
]
```

### C04 — coding

Question:

> Write a Python function group_values(pairs). Input is a list of (key, value) tuples; keys are strings and values are integers. Return a dictionary mapping each key to a list of its values in input order. Empty input returns {}. Do not mutate the input or import modules. Return only the function definition, with no Markdown fences, decorators, type annotations, or explanation.

Existing acceptance criteria:

- Accumulate repeated keys without losing values.
- Preserve per-key order.
- Empty input returns an empty dictionary.

Existing reference examples to trace manually (JSON null means Python None):

```json
[
  {
    "input": [
      [
        "a",
        1
      ],
      [
        "b",
        2
      ],
      [
        "a",
        3
      ]
    ],
    "output": {
      "a": [
        1,
        3
      ],
      "b": [
        2
      ]
    }
  }
]
```

### K01 — knowledge

Question:

> Explain authentication and authorization in exactly two bullet lines beginning with "- ". In the first bullet define authentication and give an example. In the second define authorization and give an example.

Existing acceptance criteria:

- Authentication establishes identity, e.g. validating a login session.
- Authorization decides permitted actions/resources, e.g. checking conversation ownership.
- Do not conflate the two.

### K02 — knowledge

Question:

> In exactly three bullet lines beginning with "- ", explain how parameterized SQL handles values, why it helps prevent SQL injection, and why it does not by itself prevent one authenticated user reading another user's records.

Existing acceptance criteria:

- Values are bound separately from SQL syntax.
- Bound values are treated as data, not executable SQL fragments.
- An ownership/authorization condition is still required.

### K03 — knowledge

Question:

> A service must debit account A and credit account B as one operation. The second update fails. In exactly two sentences, explain the required transaction outcome and why. Assume a transaction-capable database and no commit before both updates succeed.

Existing acceptance criteria:

- Both updates must roll back so the debit is not retained alone.
- Atomicity requires all-or-nothing commit.

### K04 — knowledge

Question:

> A messages.conversation_id foreign key references conversations.id with ON DELETE CASCADE. In exactly two bullet lines beginning with "- ", explain what happens when a message references a nonexistent conversation and when an existing conversation is deleted.

Existing acceptance criteria:

- Insertion/update with nonexistent referenced parent is rejected.
- Deleting the parent deletes its referencing messages, not unrelated conversations.

### S01 — summarization

Question:

> Summarize this synthetic incident in exactly two sentences, preserving cause, impact, and recovery. Do not add facts.

At 09:00 a configuration change routed API traffic to an unavailable backend. Requests failed for twelve minutes. At 09:12 the team rolled back the change and requests recovered. No stored records were lost.

Existing acceptance criteria:

- Configuration change routed traffic to unavailable backend.
- Requests failed for twelve minutes.
- Rollback restored service at 09:12.
- No stored records were lost.

### S02 — summarization

Question:

> Summarize this synthetic experiment in exactly two sentences. Preserve both latency values and their units, the sample size, and the limitation.

On one workstation, configuration A had mean latency 800 milliseconds and configuration B had mean latency 600 milliseconds. Each configuration processed ten requests. Output quality was not measured, so these results alone cannot identify the better overall configuration.

Existing acceptance criteria:

- A: 800 milliseconds; B: 600 milliseconds.
- Ten requests per configuration, on one workstation.
- Quality was not measured; no overall superiority claim.

### S03 — summarization

Question:

> Summarize this synthetic status note in exactly three bullet lines beginning with "- ", one each for completed, ongoing, and planned work.

The team completed the database schema review. Documentation drafting is still in progress. A load test is planned for next week, but no load-test results exist yet.

Existing acceptance criteria:

- Schema review completed.
- Documentation drafting ongoing.
- Load test planned for next week; no results yet.

### S04 — summarization

Question:

> Summarize this synthetic investigation in exactly two sentences. Preserve the conflicting observations and uncertainty.

One monitor recorded increased response times during the evening. A second monitor showed no change during the same period. Engineers have not determined whether the difference came from monitoring configuration or service behavior. No cause has been confirmed.

Existing acceptance criteria:

- One monitor saw evening latency increase; the other did not.
- Monitoring configuration versus service behavior remains unresolved.
- No confirmed cause or invented resolution.

