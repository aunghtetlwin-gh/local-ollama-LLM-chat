"""Offline dataset, sampling, and historical-integrity validation."""
import argparse
from collections import Counter
from pathlib import Path

from .common import BASE, DATASETS, digest, load_questions, read_json, read_jsonl, sha256


def require(condition, message):
    if not condition: raise ValueError(message)


def validate():
    sizes = {}
    for suite, directory in DATASETS.items():
        manifest = read_json(directory / 'manifest.json')
        questions = load_questions(suite)
        refs = read_jsonl(directory / 'references.jsonl')
        require(sha256((directory / 'references.jsonl').read_bytes()) == manifest['references_sha256'], 'Reference checksum')
        require(len(refs) == len(questions), 'Reference count')
        require([r['id'] for r in refs] == [q['id'] for q in questions], 'Reference alignment')
        for r in refs:
            require(r['kind'] in {'manual','exact','json','json_alternatives','code','numeric'}, 'Scorer kind')
            require(bool(r['acceptance_criteria']) and bool(r['scoring_rules']), 'Missing scoring specification')
        sizes[suite] = len(questions)
        if suite == 'internal_v2':
            require(Counter(q['category'] for q in questions) == dict.fromkeys(['knowledge','reasoning','coding','summarization','instruction'],4), 'Category balance')
            require(all(q['difficulty'] != 'unrated' for q in questions), 'Missing internal difficulty')
        else:
            for name, key in [('upstream_test.jsonl','upstream_sha256'),('LICENSE','license_sha256'),('UPSTREAM_README.md','readme_sha256'),('selection.json','selection_sha256')]:
                require(sha256((directory/name).read_bytes()) == manifest[key], 'Upstream provenance checksum')
            source = read_jsonl(directory/'upstream_test.jsonl')
            require(len(source) == manifest['upstream_count'] == 1319, 'Upstream count')
            require('MIT License' in (directory/'LICENSE').read_text(), 'License')
            selection = read_json(directory/'selection.json')
            require(len(selection['selected']) == len(questions) == len(refs) == 50, 'Fixed subset size')
            rank = lambda i: sha256(f"{selection['seed']}:{i}".encode('ascii'))
            indices = sorted(range(len(source)), key=lambda i:(rank(i),i))[:50]
            require(indices == [r['source_row_zero_based'] for r in selection['selected']], 'Deterministic selection mismatch')
            for q, ref, item, i in zip(questions,refs,selection['selected'],indices):
                original = source[i]
                require(q['id'] == item['id'] == f'gsm8k-test-{i:04d}', 'Source ID')
                require(item['record_sha256'] == digest(original), 'Source record hash')
                require(item['question_sha256'] == sha256(original['question'].encode()), 'Source question hash')
                require(item['rank_sha256'] == rank(i), 'Selection rank')
                require(q['prompt'].endswith('\n\n'+original['question']), 'Question altered')
                require(ref['expected'] == original['answer'].rsplit('####',1)[1].strip(), 'Reference extraction')
    historical = BASE/'datasets/pilot_v1'
    require(sha256((historical/'manifest.json').read_bytes()) == (historical/'manifest.sha256').read_text().split()[0], 'Historical manifest changed')
    pilot = read_json(historical/'manifest.json')
    require(sha256((historical/'prompts.jsonl').read_bytes()) == pilot['prompts_sha256'], 'Pilot prompts changed')
    for item in pilot['files']:
        require(sha256((BASE.parent/item['path']).read_bytes()) == item['sha256'], 'Historical file changed: '+item['path'])
    prompts = read_jsonl(historical/'prompts.jsonl')
    require(len(prompts) == 5, 'Pilot task count')
    require(not {q['prompt'] for q in load_questions('internal_v2')} & {q['prompt'] for q in prompts}, 'Pilot question reused')
    sizes['pilot_v1'] = len(prompts)
    return sizes


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    for name, count in validate().items(): print(f'{name}: {count} questions validated')
    print('Hashes, references, official subset selection, license, and historical artifacts verified')


if __name__ == '__main__': main()
