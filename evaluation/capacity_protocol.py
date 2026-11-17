"""Pure synthetic prompt construction and response checks; no service access."""
from .common import digest, sha256
from .scoring import strict_json

VERSION = 'synthetic-capacity-v1'
PROFILE = 'ollama-0.32.15-no-truncate-no-shift-v1'
TARGETS = {'S': None, 'I': 7936, 'IO': 3840}
TOLERANCE = 32


def require(value, message):
    if not value:
        raise ValueError('Capacity: ' + message)


def capacity_config(config):
    require(config.get('think') in (None, False), 'capacity evidence covers only think=false')
    return {key: config[key] for key in ('models', 'system_message', 'options', 'stream', 'timeout_seconds')}


def markers(model, case):
    return {key: sha256(f'{VERSION}:{model}:{case}:{key}'.encode())[:16]
            for key in ('begin', 'middle', 'end')}


def synthetic_text(model, case, padding):
    require(case in TARGETS and type(padding) is int and 0 <= padding <= 2048, 'invalid generator input')
    codes = markers(model, case)
    lines = [f'BEGIN_CODE={codes["begin"]}']
    for i in range(padding + 1):
        if i == padding // 2:
            lines.append(f'MIDDLE_CODE={codes["middle"]}')
        if i < padding:
            word = ('cedar', 'amber', 'river', 'stone')[i % 4]
            lines.append(f'Record {i:06d}: the {word} sample remains neutral.')
    lines.append(f'END_CODE={codes["end"]}')
    if case == 'IO':
        lines.append('First write one compact JSON object with keys begin, middle, end containing '
                     'the three codes above. Then write a newline and continuously generate numbered '
                     'lines of neutral words: cedar amber river stone. Continue until the output '
                     'limit stops you. Do not conclude, summarize, or use Markdown fences.')
    else:
        lines.append('Return only one JSON object with exactly the keys begin, middle, end containing '
                     'the corresponding codes above. Do not explain or use Markdown fences.')
    return '\n'.join(lines)


def payload(config, model, case, padding):
    return {'model': model, 'messages': [
        {'role': 'system', 'content': config['system_message']},
        {'role': 'user', 'content': synthetic_text(model, case, padding)}],
        'think': False, 'stream': False, 'keep_alive': '30s',
        'truncate': False, 'shift': False, 'options': dict(config['options'])}


def prepare(config, snapshot, counter):
    require(snapshot.get('ollama_version') == {'version': '0.32.15'}, 'unsupported server version')
    require(config['options']['num_ctx'] == 8192 and config['options']['num_predict'] == 4096,
            'v1 covers only the proposed 8192/4096 configuration')
    require(config.get('think') in (None, False), 'baseline must be thinking disabled')
    rows = []
    for model in config['models']:
        for case, target in TARGETS.items():
            best = None
            low, high = 0, 2048 if target else 0
            while low <= high:
                n = (low + high) // 2
                req = payload(config, model, case, n)
                measured = counter.measure(model, req['messages'], False)
                require(measured['identity']['status'] == 'calibrated_cpu' and
                        measured['identity']['cpu_only'] is True and
                        measured['identity']['vocab_only'] is True, 'uncalibrated tokenization')
                count = measured['count']
                require(type(count) is int and count > 0 and
                        isinstance(measured.get('token_ids'), list) and len(measured['token_ids']) == count and
                        all(type(t) is int and t >= 0 for t in measured['token_ids']) and
                        measured.get('messages_sha256') == digest(req['messages']) and
                        measured.get('rendered_sha256') == sha256(measured['rendered'].encode()) and
                        measured['identity'].get('model_digest') == snapshot['models'][model]['digest'],
                        'invalid tokenization evidence')
                best = (n, req, measured) if best is None or abs(count - (target or count)) < abs(best[2]['count'] - (target or count)) else best
                if target is None or abs(count - target) <= TOLERANCE:
                    best = n, req, measured
                    break
                if count < target:
                    low = n + 1
                else:
                    high = n - 1
            n, req, measured = best
            require(target is None or abs(measured['count'] - target) <= TOLERANCE,
                    'cannot achieve token target without inference; preparation stopped')
            require(measured['count'] + (4096 if case == 'IO' else 128) <= 8192,
                    'synthetic request exceeds non-shifting context budget')
            rows.append({'model': model, 'case': case, 'padding': n, 'target': target,
                         'request': req, 'request_sha256': digest(req), 'tokenization': measured})
    return {'version': VERSION, 'profile': PROFILE, 'config': config,
            'config_sha256': digest(config), 'snapshot': snapshot,
            'snapshot_sha256': digest(snapshot), 'probes': rows,
            'capacity_verified': False}


def separate_findings(probe, raw):
    result = {'thinking_disabled_observed': None, 'output_format': 'not_evaluated',
              'markers_preserved': None, 'capacity_probe': 'insufficient'}
    if not isinstance(raw, dict) or not isinstance(raw.get('message'), dict):
        return result
    message = raw['message']
    thinking = message.get('thinking', '')
    result['thinking_disabled_observed'] = isinstance(thinking, str) and not thinking.strip()
    text = message.get('content')
    if not isinstance(text, str):
        return result
    text = text.split('\n', 1)[0] if probe['case'] == 'IO' else text
    try:
        answer = strict_json(text)
    except ValueError:
        result['output_format'] = 'failed'
    else:
        result['output_format'] = 'passed'
        result['markers_preserved'] = answer == markers(probe['model'], probe['case'])
    return result


def check_response(probe, raw):
    require(isinstance(raw, dict) and not raw.get('_collector_error') and not raw.get('error'),
            'malformed HTTP/model error response')
    require(raw.get('model') == probe['model'], 'response model mismatch')
    require(raw.get('done') is True, 'request completion unconfirmed')
    case = probe['case']
    require(raw.get('done_reason') == ('length' if case == 'IO' else 'stop'), 'unexpected completion reason')
    message = raw.get('message')
    require(isinstance(message, dict) and message.get('role') == 'assistant' and
            isinstance(message.get('content'), str) and not message.get('tool_calls'), 'malformed message')
    thinking = message.get('thinking', '')
    require(isinstance(thinking, str) and not thinking.strip(), 'unexpected thinking behavior')
    require(type(raw.get('prompt_eval_count')) is int and
            raw['prompt_eval_count'] == probe['tokenization']['count'],
            'input truncation/rendering mismatch')
    generated = raw.get('eval_count')
    require(type(generated) is int and generated > 0, 'missing generated-token count')
    text = message['content']
    first = text.split('\n', 1)[0] if case == 'IO' else text
    try:
        answer = strict_json(first)
    except ValueError as error:
        raise ValueError('Capacity: output format failure; no JSON extraction') from error
    require(answer == markers(probe['model'], case), 'marker retrieval failed')
    if case == 'IO':
        require(generated == 4096, 'insufficient output capacity evidence')
        require('\n' in text and len(text.split('\n', 1)[1].strip()) > 0, 'missing sustained output')
    else:
        require(generated <= 128, 'control answer exceeded reserved output space')
    require(raw['prompt_eval_count'] + generated <= 8192, 'context shifting/overflow')
    for key in ('load_duration', 'total_duration', 'eval_duration'):
        require(type(raw.get(key)) is int and raw[key] >= 0, 'missing duration statistics')
    return {'thinking_disabled_observed': True, 'output_format': 'passed',
            'markers_preserved': True, 'capacity_probe': 'passed'}
