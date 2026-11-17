"""Development harness tests: all network access blocked, GPU calls injected."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evaluation import dev_inference as dev
from evaluation.common import BASE, read_json


class Fake:
    def __init__(self, failure=None):
        self.calls = []
        self.failure = failure

    def request(self, endpoint, body=None):
        self.calls.append((endpoint, deepcopy(body)))
        if endpoint == '/api/ps': return {'models': []}
        if endpoint == '/api/version': return {'version': 'fixture'}
        if endpoint == '/api/tags':
            return {'models': [{'name': m, 'digest': 'fixture-' + m} for m in dev_config()['models']]}
        if endpoint == '/api/show': return {'capabilities': ['thinking'], 'template': 'fixture'}
        if endpoint != '/api/chat': raise AssertionError(endpoint)
        if self.failure: raise self.failure
        return {'model': body['model'], 'done': True,
                'done_reason': 'length' if body['options']['num_predict'] == 1 else 'stop',
                'message': {'content': '{"answer":323}',
                            'thinking': 'fixture reasoning' if body['think'] else ''},
                'eval_count': 1, 'total_duration': 1000}


def dev_config():
    return read_json(BASE / 'configs/quality_v2.draft.json')


class DevelopmentTests(unittest.TestCase):
    def setUp(self):
        coordination = tempfile.TemporaryDirectory()
        self.addCleanup(coordination.cleanup)
        patcher = patch('evaluation.execution_guard.DEFAULT_ROOT', Path(coordination.name))
        patcher.start()
        self.addCleanup(patcher.stop)
        for target in ('socket.socket.connect', 'socket.create_connection',
                       'urllib.request.OpenerDirector.open', 'subprocess.run'):
            p = patch(target, side_effect=AssertionError('Real service/GPU access forbidden'))
            p.start()
            self.addCleanup(p.stop)

    def test_flags_block_before_transport(self):
        with patch.object(dev, 'DevTransport') as transport:
            for args in ([], ['--allow-inference'], ['--development-only']):
                with self.assertRaises(SystemExit): dev.main(args)
            transport.assert_not_called()

    def test_exact_payloads_and_config_preservation(self):
        config = dev_config()
        original = deepcopy(config)
        probes = list(dev.payloads(config, config['models'][0]))
        self.assertEqual([p[1]['think'] for p in probes], [False, True, False])
        self.assertEqual([p[1]['options']['num_predict'] for p in probes], [4096, 4096, 1])
        self.assertEqual(probes[0][1]['messages'][1]['content'],
                         'Compute 17 × 19. Return only {"answer":323}.')
        self.assertEqual(probes[2][1]['messages'][1]['content'],
                         'Write the integers from 1 through 1000, separated by spaces.')
        self.assertEqual(config, original)

    def test_nine_sequential_requests_unique_results_and_monitoring(self):
        with tempfile.TemporaryDirectory() as temp:
            fake = Fake()
            first = dev.run(dev_config(), temp, fake, gpu=lambda: {'used_mib': 123})
            before = {p.relative_to(first): p.read_bytes() for p in first.rglob('*') if p.is_file()}
            second = dev.run(dev_config(), temp, Fake(), gpu=lambda: {'used_mib': 123})
            self.assertNotEqual(first, second)
            self.assertEqual(before, {p.relative_to(first): p.read_bytes() for p in first.rglob('*') if p.is_file()})
            requests = [b for e, b in fake.calls if e == '/api/chat']
            self.assertEqual([r['model'] for r in requests],
                             [m for m in dev_config()['models'] for _ in range(3)])
            self.assertEqual(len(list(first.glob('*/response.json'))), 9)
            self.assertEqual(len(list(first.glob('*/summary.json'))), 9)
            self.assertEqual(len(list(first.glob('*/monitoring/sample-*.json'))), 18)
            self.assertTrue((first / 'metadata.json').exists())
            self.assertTrue((first / 'complete.json').exists())

    def test_errors_and_interruptions_stop_without_retry(self):
        for failure in (OSError('timeout fixture'), KeyboardInterrupt()):
            with tempfile.TemporaryDirectory() as temp:
                fake = Fake(failure)
                with self.assertRaises(type(failure)):
                    dev.run(dev_config(), temp, fake, gpu=lambda: {})
                self.assertEqual(sum(e == '/api/chat' for e, _ in fake.calls), 1)
                directory = next(p for p in Path(temp).iterdir() if p.is_dir())
                self.assertTrue((directory / 'stopped.json').exists())
                self.assertEqual(len(list(directory.glob('*/error.json'))), 1)
                self.assertFalse((directory / 'complete.json').exists())

    def test_monitor_failure_prevents_inference(self):
        with tempfile.TemporaryDirectory() as temp:
            fake = Fake()
            def broken(): raise RuntimeError('GPU unavailable')
            with self.assertRaises(RuntimeError): dev.run(dev_config(), temp, fake, gpu=broken)
            self.assertFalse(any(e == '/api/chat' for e, _ in fake.calls))

    def test_initial_residency_refused(self):
        fake = Fake()
        original = fake.request
        fake.request = lambda endpoint, body=None: {'models': [{}]} if endpoint == '/api/ps' else original(endpoint, body)
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError): dev.run(dev_config(), temp, fake, gpu=lambda: {})
            self.assertFalse(any(e == '/api/chat' for e, _ in fake.calls))

    def test_response_contracts(self):
        good = {'model': 'fixture', 'done': True, 'done_reason': 'stop',
                'message': {'content': '{"answer":323}', 'thinking': ''}}
        dev.check_response('A', 'fixture', good)
        with self.assertRaises(ValueError): dev.check_response('B', 'fixture', good)
        with self.assertRaises(ValueError): dev.check_response('C', 'fixture', good)
        bad = deepcopy(good)
        bad['message']['thinking'] = 'unexpected'
        with self.assertRaises(ValueError): dev.check_response('A', 'fixture', bad)
        bad = deepcopy(good)
        bad['done'] = False
        with self.assertRaises(ValueError): dev.check_response('A', 'fixture', bad)

    def test_residency_timeout(self):
        fake = Fake()
        fake.request = lambda *args: {'models': [{}]}
        with self.assertRaises(TimeoutError): dev.wait_empty(fake, timeout=0)

    def test_prose_before_json_is_validation_failure_after_completed_request(self):
        # Exact content from the failed development run, not an HTTP/ps JSON failure.
        content = '17 × 19 = 323\n\n{"answer": 323}'
        with self.assertRaises(json.JSONDecodeError) as original:
            json.loads(content)
        self.assertEqual(original.exception.pos, 3)
        fake = Fake()
        original_request = fake.request

        def request(endpoint, body=None):
            raw = original_request(endpoint, body)
            if endpoint == '/api/chat':
                raw['message']['content'] = content
            return raw

        fake.request = request
        with tempfile.TemporaryDirectory() as temp:
            dev.run(dev_config(), temp, fake, gpu=lambda: {})
            directory = next(p for p in Path(temp).iterdir() if p.is_dir())
            attempt = directory / 'qwen3_1.7b-A'
            self.assertEqual(read_json(attempt / 'response.json')['message']['content'], content)
            summary = read_json(attempt / 'summary.json')
            self.assertEqual(summary['status'], 'completed')
            self.assertTrue(summary['done'])
            error = read_json(attempt / 'error.json')
            self.assertEqual(error['type'], 'ResponseValidationError')
            self.assertEqual(error['code'], 'invalid_final_json')
            self.assertEqual(error['phase'], 'response_validation')
            self.assertTrue(error['response_received'])
            self.assertFalse(error['server_completion_unconfirmed'])
            self.assertFalse((directory / 'stopped.json').exists())
            self.assertEqual(sum(e == '/api/chat' for e, _ in fake.calls), 9)
            self.assertEqual(read_json(directory / 'complete.json')['output_format_failures'], 6)
            self.assertFalse(read_json(directory / 'complete.json')['all_probes_passed'])
            self.assertEqual(read_json(attempt / 'output_format.json')['status'], 'failed')
            self.assertEqual(read_json(attempt / 'result.json')['failure_category'], 'output_format')
            self.assertEqual(len(list(directory.glob('*/request.json'))), 9)
            self.assertEqual(len(list(directory.glob('*/response.json'))), 9)

    def test_non_json_answers_remain_rejected(self):
        raw = {'model': 'fixture', 'done': True, 'done_reason': 'stop',
               'message': {'content': ''}}
        for content in ('323', '{"answer":324}', '{"answer":323} trailing',
                        '```json\n{"answer":323}\n```', '17 × 19 = 323\n\n{"answer": 323}'):
            raw['message']['content'] = content
            with self.assertRaises(ValueError):
                dev.check_response('A', 'fixture', raw)

    def test_infrastructure_responses_stop_without_retry(self):
        for replacement in (
            {'_collector_error': 'invalid_json', 'body_base64': 'bm90IGpzb24='},
            {'_collector_error': 'http_error', 'http_status': 500},
            {'error': 'CUDA out of memory'},
            {'model': 'qwen3:1.7b', 'done': True, 'done_reason': 'stop',
             'error': 'CUDA out of memory', 'message': {'content': 'prose'}}, [],
            {'model': 'qwen3:1.7b', 'done': False},
        ):
            with self.subTest(raw=replacement), tempfile.TemporaryDirectory() as temp:
                fake = Fake()
                original = fake.request
                def request(endpoint, body=None):
                    raw = original(endpoint, body)
                    return replacement if endpoint == '/api/chat' else raw
                fake.request = request
                with self.assertRaises(ValueError):
                    dev.run(dev_config(), temp, fake, gpu=lambda: {})
                directory = next(p for p in Path(temp).iterdir() if p.is_dir())
                self.assertEqual(sum(e == '/api/chat' for e, _ in fake.calls), 1)
                self.assertEqual(read_json(next(directory.glob('*/response.json'))), replacement)
                self.assertTrue((directory / 'stopped.json').exists())
                self.assertEqual(read_json(next(directory.glob('*/output_format.json')))['status'],
                                 'not_evaluated')

    def test_format_error_does_not_mask_other_contract_or_monitor_failure(self):
        for fault in ('thinking', 'monitor', 'concurrent', 'malformed_ps'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as temp:
                fake = Fake()
                original = fake.request
                def request(endpoint, body=None):
                    raw = original(endpoint, body)
                    if endpoint == '/api/chat':
                        raw['message']['content'] = 'prose {"answer":323}'
                        if fault == 'thinking': raw['message']['thinking'] = 'unexpected'
                    if endpoint == '/api/ps' and any(e == '/api/chat' for e, _ in fake.calls):
                        if fault == 'monitor': raise OSError('monitor unavailable')
                        if fault == 'concurrent': return {'models': [{'name': 'other:model'}]}
                        if fault == 'malformed_ps': return {'models': None}
                    return raw
                fake.request = request
                with self.assertRaises((ValueError, RuntimeError)):
                    dev.run(dev_config(), temp, fake, gpu=lambda: {})
                self.assertEqual(sum(e == '/api/chat' for e, _ in fake.calls), 1)
                directory = next(p for p in Path(temp).iterdir() if p.is_dir())
                self.assertTrue((directory / 'stopped.json').exists())

    def test_format_failure_then_timeout_stops_at_second_request(self):
        fake = Fake()
        original = fake.request
        def request(endpoint, body=None):
            if endpoint == '/api/chat' and any(e == '/api/chat' for e, _ in fake.calls):
                fake.calls.append((endpoint, deepcopy(body)))
                raise TimeoutError('completion unknown')
            raw = original(endpoint, body)
            if endpoint == '/api/chat': raw['message']['content'] = 'prose {"answer":323}'
            return raw
        fake.request = request
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(TimeoutError):
                dev.run(dev_config(), temp, fake, gpu=lambda: {})
            self.assertEqual(sum(e == '/api/chat' for e, _ in fake.calls), 2)
            directory = next(p for p in Path(temp).iterdir() if p.is_dir())
            self.assertTrue((directory / 'stopped.json').exists())
            self.assertFalse((directory / 'complete.json').exists())

    def test_single_format_failure_followed_by_passing_probes(self):
        fake = Fake()
        original = fake.request
        def request(endpoint, body=None):
            raw = original(endpoint, body)
            if endpoint == '/api/chat' and sum(e == '/api/chat' for e, _ in fake.calls) == 1:
                raw['message']['content'] = '17 × 19 = 323\n\n{"answer": 323}'
            return raw
        fake.request = request
        with tempfile.TemporaryDirectory() as temp:
            directory = dev.run(dev_config(), temp, fake, gpu=lambda: {})
            self.assertEqual(read_json(directory / 'complete.json')['output_format_failures'], 1)
            results = [read_json(p) for p in directory.glob('*/result.json')]
            self.assertEqual(sum(r['probe_status'] == 'passed' for r in results), 8)
            self.assertEqual(sum(e == '/api/chat' for e, _ in fake.calls), 9)

    def test_same_root_lock_prevents_requests(self):
        fake = Fake()
        with tempfile.TemporaryDirectory() as temp:
            with dev.run_lock(Path(temp)):
                with self.assertRaisesRegex(ValueError, 'Another collector'):
                    dev.run(dev_config(), temp, fake, gpu=lambda: {})
            self.assertEqual(fake.calls, [])
