# Human-review coordinator instructions

Prepared packet: `evaluation_human_review/human-review-20261104-cd80448ab4a3`.
Share ONLY `reviewer/` with raters. Keep `private/` and original analysis/model summaries
away from raters until independent judgements are complete. `private/` has owner-only
permissions. Existing blinding IDs are preserved; no new model assignments were exposed.
Response wording can sometimes identify a source; this packet's selected texts contain
no detected model-name disclosures. Prior familiarity can still compromise blinding and
should be recorded in blinding_note without altering responses.

## Exactly what is included

36 responses: three existing blind IDs for each of C01–C04, K01–K04 and S01–S04.
That is 12 coding, 12 knowledge, and 12 summarization answers. `reviewer/selection.csv`
lists every selected blind ID. The 24 automatically scored internal answers from the old
60-row sheet are deliberately excluded. The original 210 automatic results remain unchanged.

Reviewer-facing files:
- booklet.html: static, escaped, locally readable exact questions/responses and criteria.
- guide.md: review steps, original rubric anchors, question-specific criteria/examples.
- rubric.md: byte-for-byte copy of the original manual_v2 rubric.
- ratings_template.csv: 36 rows, all judgements/ratings/rationales blank.
- selection.csv: preserved IDs, question IDs and categories only.
- responses.jsonl: authoritative exact response strings, preserved from raw responses.

The old spreadsheet export prefixes certain unsafe leading cells with an apostrophe.
Those spreadsheet presentation escapes are not part of model output: the new booklet
and response JSON use the hash-verified original text, not repaired or rewritten answers.

## 1. Conduct the review without identities

From the project root:

```sh
packet=evaluation_human_review/human-review-20261104-cd80448ab4a3
cp --no-clobber "$packet/reviewer/ratings_template.csv" "$packet/reviewer/ratings_R1.csv"
```

Open `reviewer/booklet.html` in a browser and `reviewer/guide.md` alongside it. Open the
ratings_R1.csv copy in a spreadsheet or CSV editor. Fill a real, stable reviewer ID, an
explicit human_verdict, correctness (1–5) and rationale for each blind ID. The other four
rubric ratings are optional for this minimal correctness workflow; leave them blank when
not assessed. For uncertain verdicts, unassessable correctness can remain blank too.
There are no model columns, timings, automatic scores, or automatic pass recommendations.

Allowed verdicts: correct, partly_correct, incorrect, uncertain. A verdict is the human's
explicit semantic assessment against existing material acceptance criteria; it is not
computed from an ordinal rating. Formatting is separate from semantic correctness. For
coding, trace by inspection and call the result manual algorithm assessment. Never run
or import generated source. Runtime correctness remains NOT EVALUATED.

Judge answers against the stated criteria, not relative to other answers. Save UTF-8 CSV
with the original header and unchanged identifier columns. Never fill a second person's
ratings. If only one reviewer is available, disclose that limitation. If two reviewers
are available, give each a separate copy and keep their reviews independent until done.

## 2. Validate/import only after a real reviewer completes the file

The following command has NOT been run on actual ratings. The template is still blank.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 "$packet/private/import_ratings.py" \
  --ratings "$packet/reviewer/ratings_R1.csv" \
  --output "$packet/private/results/reviewer_R1_01"
```

The command validates all 36 rows, unique known blind IDs, fixed question/category fields,
one nonblank reviewer ID, verdicts, rationale and integer 1–5 ratings. It rejects blank
or incomplete decided reviews. It also rechecks packet/source hashes and exact raw response
strings. It validates before writing anything, refuses an existing output directory,
and permits model-labelled results only below private/results. It makes no network/model
calls and does not overwrite original scores, evidence, or completed rating files.

For a second real reviewer, use their separate input and a NEW reviewer_R2_01 output.
Keep independent imports. Resolve disagreements as a human process in a separate copied
sheet, with an adjudication reviewer ID and rationale identifying disagreements and their
resolution; import it to another new output directory. Do not silently average, replace,
or choose a favourable reviewer. Preserve pre-adjudication agreement information.

## 3. Final tables and interpretation

Each valid import produces privately:
- completed_ratings.csv: exact archived bytes of the submitted file.
- human_ratings.json: normalized ratings, explicit verdicts and private identity linkage.
- model_metrics.csv: original automatic accuracy (58 items/model), plus separate human
  verdict counts/fractions and available 1–5 rubric means (12 human items/model).
- automatic_category_metrics.csv and human_category_metrics.csv: separate category tables.
- category_metrics.json and import_manifest.json: coverage and provenance.

There is no combined /70 accuracy and no automatic threshold mapping from correctness
ratings to a binary verdict. Human partly-correct counts are retained without half credit.
The fully-correct fraction over all reviewed answers means explicitly judged correct /12;
it does NOT label uncertain answers incorrect. The decided-only fraction excludes uncertainty
and must be accompanied by its denominator and uncertainty count. Optional dimension means
report their own n; absent ratings are not zeros. With only 36 responses, the full five-
category internal rubric aggregate cannot be calculated: do not invent the missing ratings.
Automatic exact/JSON/numeric correctness remains governed by the original scoring rules.
Human findings are separate subjective results, especially manual coding assessment.

Keep the private mapping and model-labelled results away from reviewers until judgements
are locked. Share only the reviewer folder, not this coordinator file or the parent project.

## Offline checks

```sh
PYTHONDONTWRITEBYTECODE=1 python3 "$packet/private/checks.py"
```

The checks use clearly synthetic temporary fixtures for successful import tests. They do
not submit ratings for any real response. All actual decision and rating cells remain blank.
Original benchmark/analysis/dataset files are hash-checked separately in PREPARATION.json.
