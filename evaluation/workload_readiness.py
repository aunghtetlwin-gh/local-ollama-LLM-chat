"""Scoped human review for the fixed 70-question workload; no capacity certification."""
import argparse
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from .common import BASE, DATASETS, digest, load_questions, read_json, sha256, write_new
from .scoring import typed_equal

VERSION = 'fixed-workload-readiness-v1'
LIMITATIONS = [
    '8192 context and 4096 output are configured limits, not certified occupied-context or sustained-output capacity.',
    'Readiness is limited to the pinned 20 internal and 50 GSM8K questions, one repetition, and their selected subsets.',
    'Exact offline tokenization is not required; runtime token counts, failures and truncations must be retained without success credit or automatic quality retries.',
    'Exclusive GPU/Ollama access is an operator prerequisite; locks and residency observations cannot exclude every external client.',
    'Smoke answers must not be used to tune a confirmatory condition; disclose evaluation exposure and any exploratory changes.',
]


def require(condition, message):
    if not condition:
        raise ValueError('Workload readiness: ' + message)


def datasets():
    """Public requests/manifest identities only; reference contents remain scorer-only."""
    result = {}
    for suite, count in (('internal_v2', 20), ('gsm8k_50_v1', 50)):
        directory = DATASETS[suite]
        questions = load_questions(suite)
        require(len(questions) == count, 'fixed question counts changed')
        result[suite] = {
            'manifest_sha256': sha256((directory / 'manifest.json').read_bytes()),
            'manifest': read_json(directory / 'manifest.json'),
            'questions_sha256': sha256((directory / 'questions.jsonl').read_bytes()),
            'questions': [{'id': q['id'], 'prompt_sha256': q['prompt_sha256']} for q in questions],
        }
    return result


def binding(config, snapshot, thinking):
    from .runner import code_hashes, MODELS
    require(thinking is False and config.get('think') in (None, False),
            'v1 supports only explicit think=false')
    require(config['models'] == MODELS and type(config.get('repetitions')) is int and
            config['repetitions'] == 1 and type(config.get('timeout_seconds')) is int and
            config.get('keep_alive') == '30s' and config.get('timeout_seconds') == 600 and
            config.get('stream') is False, 'v1 requires the one-repetition 30s/600s profile')
    options = {'num_ctx': 8192, 'num_predict': 4096, 'temperature': 0, 'seed': 42,
               'top_k': 40, 'top_p': 0.9, 'repeat_last_n': 64, 'repeat_penalty': 1.0}
    require(typed_equal(config['options'], options), 'unsupported generation options')
    # Only freeze bookkeeping is excluded; every candidate setting, including notes and
    # ordering seed, is otherwise pinned. The CLI-selected thinking mode is explicit.
    candidate = {k: v for k, v in config.items()
                 if k not in {'protocol_status', 'model_snapshot', 'verification', 'frozen_at'}}
    candidate['think'] = thinking
    candidate = deepcopy(candidate)
    return {'config': candidate, 'snapshot': deepcopy(snapshot), 'snapshot_sha256': digest(snapshot),
            'datasets': datasets(), 'runner_version': 'quality-runner-scoped-v1',
            'source_sha256': code_hashes(), 'limitations': list(LIMITATIONS)}


def prepare(config, snapshot, thinking_index):
    from .runner import validate_config
    from .thinking_evidence import validate_index
    from .validate import validate
    validate_config(config)
    validate()  # Offline preparation verifies reference/historical integrity too.
    validate_index(config, snapshot, thinking_index)
    bound = binding(config, snapshot, False)
    return {'reviewer': '', 'verified_at': '',
            'thinking_verification': {'method': 'empirical-thinking-v1',
                'evidence': thinking_index, 'evidence_sha256': digest(thinking_index)},
            'workload_readiness': {'method': VERSION, 'decision': 'pending',
                'limitations_acknowledged': False, 'binding': bound, 'binding_sha256': digest(bound)},
            'models': {name: {'digest': snapshot['models'][name]['digest'],
                'capacity_verified': False, 'verified_options': deepcopy(config['options']),
                'evidence_note': 'Phase 2 compatibility only; fixed-workload review pending. Full capacity not certified.'}
                for name in config['models']}}


def validate_scope(config, snapshot, verification, thinking):
    require(isinstance(verification.get('reviewer'), str) and bool(verification['reviewer'].strip()),
            'named human reviewer required')
    scope = verification['workload_readiness']
    require(isinstance(scope, dict), 'missing scoped evidence')
    require(isinstance(verification.get('models'), dict) and
            all(name in verification['models'] and isinstance(verification['models'][name], dict)
                for name in config['models']), 'missing model review evidence')
    require(scope.get('method') == VERSION, 'unsupported scope version')
    require(scope.get('decision') == 'approved' and scope.get('limitations_acknowledged') is True,
            'affirmative review decision and limitations acknowledgement required')
    date = verification.get('verified_at')
    try:
        parsed = datetime.fromisoformat(date)
    except (TypeError, ValueError):
        raise ValueError('Workload readiness: timezone-aware review timestamp required') from None
    require(parsed.tzinfo is not None and parsed.utcoffset() is not None, 'review timestamp requires timezone')
    require(verification.get('thinking_verification', {}).get('method') == 'empirical-thinking-v1',
            'scoped path requires empirical thinking evidence')
    expected = binding(config, snapshot, thinking)
    require(scope.get('binding_sha256') == digest(scope.get('binding')),
            'scope binding hash mismatch')
    require(typed_equal(scope.get('binding'), expected), 'scope settings/datasets/model/source binding changed')
    for name in config['models']:
        require(verification['models'][name].get('capacity_verified') is False,
                'scoped approval must retain capacity_verified=false')


def validate_selection(config, suites, question_ids=None):
    """Constrain collection to reviewed public questions and ordinary smoke subsets."""
    scope = config.get('verification', {}).get('workload_readiness')
    if scope is None:
        return
    require(set(suites) <= {'internal_v2', 'gsm8k_50_v1'}, 'unapproved suite')
    approved = scope['binding']['datasets']
    for suite in suites:
        require(suite in approved, 'suite absent from approved scope')
        actual = [{'id': q['id'], 'prompt_sha256': q['prompt_sha256']} for q in load_questions(suite)]
        require(actual == approved[suite]['questions'], 'question scope changed')
    # Existing make_plan additionally rejects unknown/duplicate selected IDs.


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--inspection', type=Path, required=True)
    parser.add_argument('--thinking-index', type=Path, default=BASE / 'evidence/phase2-thinking-v1.json')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    write_new(args.output, prepare(read_json(args.config), read_json(args.inspection),
                                   read_json(args.thinking_index)))
    print('Prepared PENDING human review; no approval, capacity certification, or freeze:', args.output)


if __name__ == '__main__':
    main()
