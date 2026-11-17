"""Versioned, offline-only validation of saved development thinking evidence."""
import argparse
from pathlib import Path

from .common import BASE, digest, read_json, sha256, write_new
from .scoring import strict_json, typed_equal

VERSION = 'empirical-thinking-v1'
PROMPT = 'Compute 17 × 19. Return only {"answer":323}.'


def require(condition, message):
    if not condition:
        raise ValueError('Thinking evidence: ' + message)


def validator_hashes():
    return {name: sha256((BASE / name).read_bytes())
            for name in ('thinking_evidence.py', 'common.py', 'scoring.py')}


def inventory(root):
    require(root.is_dir() and not root.is_symlink(), 'missing or symlink evidence root')
    paths = list(root.rglob('*'))
    require(not any(p.is_symlink() for p in paths), 'symlinks forbidden')
    return {p.relative_to(root).as_posix(): sha256(p.read_bytes())
            for p in sorted(paths) if p.is_file()}


def evidence_root(index):
    root = Path(index['root'])
    return root if root.is_absolute() else BASE.parent / root


def build_index(root):
    """Index original bytes; this is neither reviewer approval nor capacity evidence."""
    root = Path(root).absolute()
    files = inventory(root)
    try:
        location = root.relative_to(BASE.parent).as_posix()
    except ValueError:
        location = str(root)
    manifest = read_json(root / 'manifest.json')
    index = {'version': VERSION, 'root': location, 'files': files,
             'validator_sha256': validator_hashes(),
             'options': manifest['config']['options'],
             'system_message': manifest['config']['system_message']}
    validate_index(manifest['config'], read_json(root / 'metadata.json'), index)
    return index


def validate_index(config, snapshot, index):
    """Recompute facts, never trust saved pass flags alone. Returns format diagnostics."""
    require(index.get('version') == VERSION, 'unsupported validator version')
    require(index.get('validator_sha256') == validator_hashes(), 'validator source changed')
    require(typed_equal(index.get('options'), config['options']), 'generation options mismatch')
    require(index.get('system_message') == config['system_message'], 'system prompt mismatch')
    root = evidence_root(index)
    require(inventory(root) == index.get('files'), 'file inventory/hash mismatch')
    manifest = read_json(root / 'manifest.json')
    original = manifest['config']
    require(digest(original) == manifest.get('config_sha256'), 'manifest config hash mismatch')
    require(original['models'] == config['models'], 'model list mismatch')
    require(typed_equal(original['options'], config['options']) and
            original['system_message'] == config['system_message'], 'manifest configuration mismatch')
    require(original.get('stream') is False and config.get('stream') is False,
            'non-streaming configuration required')
    require(read_json(root / 'metadata.json') == snapshot, 'model/runtime metadata mismatch')
    require(bool(snapshot.get('ollama_version', {}).get('version')), 'missing Ollama version')
    require(read_json(root / 'initial_ps.json') == {'models': []}, 'initial residency not empty')
    require(not (root / 'stopped.json').exists(), 'development run stopped')
    complete = read_json(root / 'complete.json')
    require(complete.get('requests') == 9, 'incomplete development sequence')
    failures = 0
    diagnostics = {}
    expected_attempts = {model.replace(':', '_') + '-' + case
                         for model in config['models'] for case in 'ABC'}
    require({p.parent.name for p in root.glob('*/request.json')} == expected_attempts,
            'unexpected or missing probes')
    for model in config['models']:
        metadata = snapshot['models'][model]
        require(bool(metadata.get('digest')) and isinstance(metadata.get('show'), dict),
                'model digest/metadata missing')
        require(isinstance(metadata['show'].get('template'), str), 'template missing')
        advertised = metadata['show'].get('thinking', {}).get('values', [])
        if advertised:
            require(all(any(type(v) is bool and v == mode for v in advertised)
                        for mode in (False, True)), 'advertised modes contradict paired evidence')
        require(read_json(root / (model.replace(':', '_') + '-expired.json')) == {'models': []},
                'model expiration not confirmed')
        for case in 'ABC':
            attempt = root / (model.replace(':', '_') + '-' + case)
            req, raw = read_json(attempt / 'request.json'), read_json(attempt / 'response.json')
            mode = case == 'B'
            options = dict(config['options'], num_predict=1 if case == 'C' else config['options']['num_predict'])
            prompt = ('Write the integers from 1 through 1000, separated by spaces.'
                      if case == 'C' else PROMPT)
            expected = {'model': model, 'messages': [
                {'role': 'system', 'content': config['system_message']},
                {'role': 'user', 'content': prompt}], 'think': mode, 'stream': False,
                'keep_alive': '30s', 'options': options}
            require(typed_equal(req, expected), model + ' ' + case + ' request mismatch')
            require(isinstance(raw, dict) and not raw.get('_collector_error') and not raw.get('error'),
                    'HTTP/model error envelope')
            require(raw.get('model') == model and raw.get('done') is True and
                    raw.get('done_reason') == ('length' if case == 'C' else 'stop'),
                    'request completion unconfirmed')
            message = raw.get('message')
            require(isinstance(message, dict) and message.get('role') == 'assistant' and
                    isinstance(message.get('content'), str) and not message.get('tool_calls'),
                    'malformed assistant message')
            thinking = message.get('thinking', '')
            require(isinstance(thinking, str) and bool(thinking.strip()) == mode,
                    model + ' ' + case + ' contradictory thinking behavior')
            samples = sorted((attempt / 'monitoring').glob('sample-*.json'))
            require(len(samples) >= 2, 'missing monitoring evidence')
            resident = False
            for path in samples:
                sample = read_json(path)
                require(not any(key.endswith('_error') for key in sample), 'monitoring failure')
                require(isinstance(sample.get('gpu', {}).get('csv'), str), 'missing GPU observation')
                models = sample.get('ollama_ps', {}).get('models')
                require(isinstance(models, list), 'malformed residency evidence')
                for item in models:
                    require(item.get('name') == model and item.get('digest') == metadata['digest'],
                            'unexpected resident model/digest')
                    require(item.get('context_length') == config['options']['num_ctx'],
                            'resident context mismatch')
                    resident = True
            require(resident, 'no matching residency observation')
            summary = read_json(attempt / 'summary.json')
            require(summary.get('done') is True and summary.get('done_reason') == raw['done_reason'] and
                    summary.get('status') == ('truncated' if case == 'C' else 'completed') and
                    summary.get('thinking') == message.get('thinking'), 'contradictory summary')
            format_status = 'not_applicable'
            if case != 'C':
                try:
                    answer = strict_json(message['content'])
                except ValueError:
                    format_status = 'failed'
                else:
                    # Wrong answers are a separate contract failure, not thinking evidence approval.
                    require(typed_equal(answer, {'answer': 323}), 'unexpected probe answer')
                    format_status = 'passed'
            failed = format_status == 'failed'
            failures += int(failed)
            require(read_json(attempt / 'output_format.json') == {
                'status': format_status, 'code': 'invalid_final_json' if failed else None},
                'contradictory output-format result')
            require(read_json(attempt / 'result.json') == {
                'request_status': 'completed', 'probe_status': 'failed' if failed else 'passed',
                'failure_category': 'output_format' if failed else None}, 'contradictory probe result')
            error_path = attempt / 'error.json'
            if failed:
                error = read_json(error_path)
                require(error.get('type') == 'ResponseValidationError' and
                        error.get('code') == 'invalid_final_json' and
                        error.get('phase') == 'response_validation' and
                        error.get('response_received') is True and
                        error.get('server_completion_unconfirmed') is False,
                        'unconfirmed or non-format failure')
            else:
                require(not error_path.exists(), 'unexpected error artifact')
            diagnostics[attempt.name] = {'thinking_compatible': True, 'output_format': format_status}
    require(complete.get('output_format_failures') == failures and
            complete.get('all_probes_passed') is (failures == 0), 'contradictory experiment result')
    return diagnostics


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    # Never add artifacts to the source evidence tree.
    if args.output.resolve().is_relative_to(args.run_dir.resolve()):
        parser.error('Evidence index must be outside the preserved experiment')
    index = build_index(args.run_dir)
    write_new(args.output, index)
    print('Indexed saved evidence only; capacity and protocol remain unverified:', args.output)


if __name__ == '__main__':
    main()
