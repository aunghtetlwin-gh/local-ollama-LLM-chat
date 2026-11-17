"""Offline rating import; preserves automatic results and never evaluates model code."""
import argparse
import csv
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics

DIMENSIONS = ('correctness', 'instruction_following', 'relevance', 'completeness', 'conciseness')
FIELDS = ('blind_id', 'question_id', 'category', 'reviewer_id', 'human_verdict', *DIMENSIONS,
          'rationale', 'blinding_note')
VERDICTS = {'correct', 'partly_correct', 'incorrect', 'uncertain'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def dump_new(path, value):
    with Path(path).open('x', encoding='utf-8') as file:
        json.dump(value, file, ensure_ascii=False, indent=2, allow_nan=False)
        file.write('\n')


def csv_new(path, rows):
    with Path(path).open('x', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)


def validate_rows(path, expected):
    with Path(path).open(newline='', encoding='utf-8-sig') as file:
        reader = csv.DictReader(file)
        require(reader.fieldnames is not None and len(reader.fieldnames) == len(set(reader.fieldnames))
                and set(reader.fieldnames) == set(FIELDS), 'Unexpected or duplicate CSV columns')
        rows = list(reader)
    require(len(rows) == len(expected), 'Expected exactly one row per selected blind ID')
    result, seen, reviewers = [], set(), set()
    for row in rows:
        require(None not in row and all(value is not None for value in row.values()), 'Malformed CSV row')
        bid = row['blind_id']
        require(bid in expected and bid not in seen, 'Unknown or duplicate blind ID')
        seen.add(bid)
        require(row['question_id'] == expected[bid]['question_id'] and
                row['category'] == expected[bid]['category'], 'Question/category identifier changed')
        reviewer = row['reviewer_id'].strip()
        require(bool(reviewer), 'Reviewer ID missing; blank templates cannot be imported')
        reviewers.add(reviewer)
        verdict = row['human_verdict'].strip()
        require(verdict in VERDICTS, 'Missing/invalid human verdict')
        require(bool(row['rationale'].strip()), 'Rationale required for every decision')
        ratings = {}
        for dimension in DIMENSIONS:
            value = row[dimension].strip()
            if not value:
                require(verdict == 'uncertain' or dimension != 'correctness',
                        'Correctness rating required for a decided response')
                ratings[dimension] = None
            else:
                require(value in {'1','2','3','4','5'}, 'Rubric ratings must be integers 1–5')
                ratings[dimension] = int(value)
        result.append({'blind_id': bid, 'question_id': row['question_id'], 'category': row['category'],
                       'reviewer_id': reviewer, 'human_verdict': verdict, **ratings,
                       'rationale': row['rationale'], 'blinding_note': row['blinding_note']})
    require(seen == set(expected), 'Missing blind IDs')
    require(len(reviewers) == 1, 'Import one independent reviewer/adjudication file at a time')
    return result


def review_summary(rows):
    counts = Counter(row['human_verdict'] for row in rows)
    n = len(rows);decided = n - counts['uncertain']
    result = {'human_reviewed': n, 'human_correct': counts['correct'],
        'human_partly_correct': counts['partly_correct'], 'human_incorrect': counts['incorrect'],
        'human_uncertain': counts['uncertain'], 'human_decided': decided,
        'human_fully_correct_fraction_all_reviewed': counts['correct']/n if n else None,
        'human_fully_correct_fraction_decided_only': counts['correct']/decided if decided else None}
    for dimension in DIMENSIONS:
        values = [row[dimension] for row in rows if row[dimension] is not None]
        result[dimension+'_n'] = len(values)
        result[dimension+'_mean_1_to_5'] = statistics.mean(values) if values else None
    return result


def import_ratings(package, ratings, output):
    package, ratings, output = Path(package).resolve(), Path(ratings).resolve(), Path(output).resolve()
    private = package / 'private'
    require(output.is_relative_to(private / 'results') and output != private / 'results',
            'Model-labelled output must be in a NEW directory below private/results/')
    manifest = load(private / 'manifest.json')
    require(manifest['version'] == 'human-review-packet-v1', 'Unsupported packet version')
    for relative, checksum in manifest['packet_files_sha256'].items():
        path = (package / relative).resolve()
        require(path.is_relative_to(package) and sha(path) == checksum, 'Packet file missing/changed: '+relative)
    for name, checksum in manifest['source_files_sha256'].items():
        require(sha(name) == checksum, 'Preserved source missing/changed: '+name)
    expected = manifest['responses']
    require(len(expected) == 36, 'This packet must contain exactly the 36 required responses')
    raw_records = [json.loads(line) for line in (package/'reviewer/responses.jsonl').read_text(encoding='utf-8').splitlines()]
    require(len(raw_records) == 36 and len({r['blind_id'] for r in raw_records}) == 36, 'Response packet incomplete')
    for record in raw_records:
        meta = expected[record['blind_id']]
        raw = load(meta['raw_response_file'])['message']['content']
        require(record['response'] == raw and hashlib.sha256(raw.encode()).hexdigest() == meta['response_text_sha256'],
                'Exact model response changed')
    normalized = validate_rows(ratings, expected)
    automatic = load(manifest['scores_json'])
    require(len(automatic) == 210, 'Automatic score input incomplete')
    merged = [{**row, 'model': expected[row['blind_id']]['model'],
               'request_id': expected[row['blind_id']]['request_id']} for row in normalized]
    models = sorted({row['model'] for row in automatic})
    model_tables, categories = [], []
    for model in models:
        auto = [r for r in automatic if r['model'] == model and r['answer_correct'] is not None]
        human = [r for r in merged if r['model'] == model]
        require(len(auto) == 58 and len(human) == 12, 'Unexpected automatic/human denominator')
        correct = sum(r['answer_correct'] is True for r in auto)
        model_tables.append({'model': model, 'automatic_correct': correct, 'automatic_n': len(auto),
                             'automatic_accuracy': correct/len(auto), **review_summary(human)})
        for category in ('coding', 'knowledge', 'summarization'):
            group = [r for r in human if r['category'] == category]
            require(len(group) == 4, 'Unexpected human category count')
            categories.append({'model': model, 'category': category, **review_summary(group)})
        for category in ('reasoning', 'instruction', 'gsm8k'):
            group = [r for r in auto if manifest['categories'][r['question_id']] == category]
            categories.append({'model': model, 'category': category, 'automatic_n':len(group),
                               'automatic_correct':sum(r['answer_correct'] is True for r in group),
                               'automatic_accuracy':sum(r['answer_correct'] is True for r in group)/len(group)})
    # All validation happens before creating output. Nothing is written to original analysis.
    output.mkdir(parents=True, exist_ok=False)
    with (output/'completed_ratings.csv').open('xb') as file:file.write(ratings.read_bytes())
    dump_new(output/'human_ratings.json', merged)
    csv_new(output/'model_metrics.csv', model_tables)
    dump_new(output/'category_metrics.json', categories)
    for name, subset in (('human_category_metrics.csv',[x for x in categories if 'human_reviewed' in x]),
                         ('automatic_category_metrics.csv',[x for x in categories if 'automatic_n' in x])):
        csv_new(output/name, subset)
    dump_new(output/'import_manifest.json', {'version':'human-review-import-v1',
        'packet_manifest_sha256':sha(private/'manifest.json'), 'ratings_file_sha256':sha(ratings),
        'reviewer_id': normalized[0]['reviewer_id'], 'rating_rows':len(normalized),
        'automatic_results_modified':False, 'model_code_executed':False,
        'notes':['Human verdicts are explicit reviewer judgements, never inferred from numeric ratings.',
                 'Partly correct is not counted as fully correct; uncertainty counts and both denominators are retained.',
                 'Do not combine automatic accuracy and human verdict proportions into an overall /70 accuracy.',
                 'Coding correctness is manual algorithm assessment; runtime correctness remains NOT EVALUATED.']})
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ratings',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    try:
        result = import_ratings(Path(__file__).resolve().parents[1], args.ratings, args.output)
    except (ValueError, OSError, KeyError) as error:
        parser.exit(1, 'Ratings NOT imported: '+str(error)+'\n')
    print('Imported reviewer decisions into private results only:',result)


if __name__ == '__main__':main()
