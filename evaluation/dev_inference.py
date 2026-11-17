"""Separately approved development probes; never freezes or scores a benchmark."""
import argparse
import json
from pathlib import Path
import secrets
import subprocess
import threading
import time

from .execution_guard import execution_guard
from .common import BASE, digest, read_json, utcnow, write_new
from .runner import OllamaTransport, inspect_models, response_status, validate_config, run_lock


class DevTransport(OllamaTransport):
    def request(self, endpoint, body=None):
        if endpoint == '/api/ps':
            # Reuse the bounded, proxy-free metadata reader without broadening benchmark endpoints.
            import urllib.request
            with self.opener.open(urllib.request.Request('http://127.0.0.1:11434/api/ps'),
                                  timeout=min(self.timeout, 5)) as response:
                data = response.read(2_000_001)
            if len(data) > 2_000_000:
                raise ValueError('Oversized ps response')
            return json.loads(data)
        return super().request(endpoint, body)


def gpu_sample():
    result = subprocess.run(['nvidia-smi',
        '--query-gpu=index,name,memory.total,memory.used,memory.free,driver_version',
        '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=5)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or 'nvidia-smi failed')
    return {'csv': result.stdout, 'columns': ['index', 'name', 'total_mib', 'used_mib',
                                             'free_mib', 'driver_version']}


def payloads(config, model):
    for case, thinking, limit, prompt in [
        ('A', False, 4096, 'Compute 17 × 19. Return only {"answer":323}.'),
        ('B', True, 4096, 'Compute 17 × 19. Return only {"answer":323}.'),
        ('C', False, 1, 'Write the integers from 1 through 1000, separated by spaces.')]:
        options = dict(config['options'], num_predict=limit)
        yield case, {'model': model, 'messages': [
            {'role': 'system', 'content': config['system_message']},
            {'role': 'user', 'content': prompt}], 'think': thinking,
            'stream': False, 'keep_alive': '30s', 'options': options}


class Monitor:
    def __init__(self, transport, gpu, path, interval=0.5, model=None):
        self.transport, self.gpu, self.path = transport, gpu, path
        self.interval = interval
        self.model = model
        self.stop = threading.Event()
        self.thread = None
        self.error = None
        self.count = 0

    def sample(self):
        record = {'at': utcnow()}
        for key, action in [('gpu', self.gpu), ('ollama_ps', lambda: self.transport.request('/api/ps'))]:
            try:
                record[key] = action()
                if key == 'ollama_ps':
                    status = record[key]
                    if not isinstance(status, dict) or not isinstance(status.get('models'), list):
                        raise ValueError('Malformed ps response')
                    if any(not isinstance(item, dict) or
                           item.get('name', item.get('model')) != self.model
                           for item in status['models']):
                        raise RuntimeError('Unsafe concurrent model residency')
            except Exception as error:
                record[key + '_error'] = {'type': type(error).__name__, 'message': str(error)}
                self.error = record[key + '_error']
        write_new(self.path / f'sample-{self.count:06d}.json', record)
        self.count += 1

    def loop(self):
        try:
            while not self.stop.wait(self.interval):
                self.sample()
        except Exception as error:
            self.error = {'type': type(error).__name__, 'message': str(error)}

    def __enter__(self):
        self.sample()
        if self.error:
            raise RuntimeError('Monitoring unavailable: ' + str(self.error))
        self.thread = threading.Thread(target=self.loop, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.stop.set()
        self.thread.join()
        self.sample()


class ResponseValidationError(ValueError):
    """A completed model response failed a development probe's output contract."""
    code = 'invalid_final_json'


def check_response(case, model, raw):
    if not isinstance(raw, dict):
        raise ValueError('Malformed response envelope')
    status = response_status(raw)
    if raw.get('model') != model:
        raise ValueError('Unexpected response model')
    if raw.get('error'):
        raise ValueError('Ollama reported an error: ' + str(raw['error']))
    message = raw.get('message')
    if (not isinstance(message, dict) or message.get('role', 'assistant') != 'assistant'
            or not isinstance(message.get('content'), str)):
        raise ValueError('Malformed response message')
    if message.get('tool_calls'):
        raise ValueError('Unexpected tool calls')
    if case == 'C':
        if status != 'truncated':
            raise ValueError('Output-limit probe did not report length truncation')
        return
    if status != 'completed':
        raise ValueError('Request did not complete: ' + status)
    thinking = message.get('thinking', '')
    if not isinstance(thinking, str) or (case == 'A' and thinking.strip()):
        raise ValueError('Unexpected thinking field')
    if case == 'B' and not thinking.strip():
        raise ValueError('Thinking-enabled probe returned no thinking evidence')
    try:
        answer = json.loads(message['content'])
    except json.JSONDecodeError as error:
        raise ResponseValidationError(
            'Final content must be one JSON object with no surrounding prose; '
            f'{error.msg} at line {error.lineno}, column {error.colno} '
            f'(character {error.pos})') from error
    if answer != {'answer': 323}:
        raise ValueError('Unexpected final answer')


def wait_empty(transport, timeout=120, sleep=time.sleep, model=None):
    deadline = time.monotonic() + timeout
    while True:
        status = transport.request('/api/ps')
        if not isinstance(status, dict) or not isinstance(status.get('models'), list):
            raise ValueError('Malformed ps response')
        if model is not None and any(not isinstance(item, dict) or
                item.get('name', item.get('model')) != model for item in status['models']):
            raise RuntimeError('Unsafe concurrent model residency')
        if not status['models']:
            return status
        if time.monotonic() >= deadline:
            raise TimeoutError('Models remain resident; stop without unloading anything')
        sleep(1)


def run(config, root, transport, gpu=gpu_sample, coordination_root=None):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    with execution_guard(coordination_root), run_lock(root):
        return _run(config, root, transport, gpu)


def _run(config, root, transport, gpu):
    validate_config(config)
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    directory = root / ('dev-' + utcnow().replace(':', '') + '-' + secrets.token_hex(6))
    directory.mkdir(exist_ok=False)
    write_new(directory / 'manifest.json', {'purpose': 'development only; not capacity certification',
        'created_at': utcnow(), 'config': config, 'config_sha256': digest(config),
        'keep_alive': '30s', 'maximum_requests': 9, 'resume_supported': False})
    format_failures = 0
    requests = 0
    try:
        initial = transport.request('/api/ps')
        write_new(directory / 'initial_ps.json', initial)
        if initial.get('models') != []:
            raise ValueError('Require no loaded models before development test')
        write_new(directory / 'metadata.json', inspect_models(transport, config['models']))
        for model in config['models']:
            for case, payload in payloads(config, model):
                attempt = directory / (model.replace(':', '_') + '-' + case)
                attempt.mkdir(exist_ok=False)
                samples = attempt / 'monitoring'
                samples.mkdir()
                write_new(attempt / 'request.json', payload)
                started = utcnow()
                timer = time.monotonic()
                phase = 'monitoring_preflight'
                raw = None
                response_received = False
                try:
                    with Monitor(transport, gpu, samples, model=model) as monitor:
                        phase = 'request'
                        requests += 1
                        raw = transport.request('/api/chat', payload)
                        response_received = True
                        phase = 'response_capture'
                        write_new(attempt / 'response.json', raw)
                        phase = 'monitoring_finalization'
                    envelope = raw if isinstance(raw, dict) else {}
                    message = envelope.get('message', {})
                    if not isinstance(message, dict):
                        message = {}
                    write_new(attempt / 'summary.json', {'started_at': started, 'finished_at': utcnow(),
                        'wall_time_s': time.monotonic() - timer, 'status': response_status(raw),
                        'thinking': message.get('thinking'), 'done': envelope.get('done'),
                        'done_reason': envelope.get('done_reason'),
                        'statistics': {k: v for k, v in envelope.items() if k.endswith(('_duration', '_count'))}})
                    if monitor.error:
                        raise RuntimeError('Monitoring failed: ' + str(monitor.error))
                    phase = 'response_validation'
                    check_response(case, model, raw)
                    write_new(attempt / 'output_format.json', {
                        'status': 'not_applicable' if case == 'C' else 'passed',
                        'code': None})
                    write_new(attempt / 'result.json', {'request_status': 'completed',
                        'probe_status': 'passed', 'failure_category': None})
                except BaseException as error:
                    format_only = isinstance(error, ResponseValidationError) and phase == 'response_validation'
                    write_new(attempt / 'output_format.json', {
                        'status': 'failed' if format_only else 'not_evaluated',
                        'code': error.code if format_only else None})
                    write_new(attempt / 'result.json', {
                        'request_status': 'completed' if format_only else 'failed_or_unconfirmed',
                        'probe_status': 'failed',
                        'failure_category': 'output_format' if format_only else 'request_or_infrastructure'})
                    write_new(attempt / 'error.json', {'type': type(error).__name__, 'message': str(error),
                        'finished_at': utcnow(), 'wall_time_s': time.monotonic() - timer,
                        'phase': phase, 'code': getattr(error, 'code', None),
                        'response_received': response_received,
                        'server_completion_unconfirmed': not (
                            response_received and isinstance(raw, dict) and raw.get('done') is True)})
                    if not format_only:
                        raise
                    format_failures += 1
            write_new(directory / (model.replace(':', '_') + '-expired.json'), wait_empty(transport, model=model))
        write_new(directory / 'complete.json', {'finished_at': utcnow(), 'requests': requests,
            'output_format_failures': format_failures, 'all_probes_passed': format_failures == 0})
    except BaseException as error:
        write_new(directory / 'stopped.json', {'at': utcnow(), 'type': type(error).__name__,
            'message': str(error), 'no_automatic_retry': True})
        raise
    return directory


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=BASE / 'configs/quality_v2.draft.json')
    parser.add_argument('--output-root', type=Path, default=BASE.parent / 'evaluation_dev_runs')
    parser.add_argument('--allow-inference', action='store_true')
    parser.add_argument('--development-only', action='store_true')
    args = parser.parse_args(argv)
    if not (args.allow_inference and args.development_only):
        parser.error('Both --allow-inference and --development-only required; no service access performed')
    config = read_json(args.config)
    validate_config(config)
    try:
        result = run(config, args.output_root, DevTransport(config['timeout_seconds']))
    except (Exception, KeyboardInterrupt) as error:
        parser.exit(1, f'Development test stopped: {type(error).__name__}: {error}\n')
    print(result)


if __name__ == '__main__':
    main()
