"""All capacity requests are mocks; token counts here are explicitly synthetic fixtures."""
from copy import deepcopy
import json
import math
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from evaluation import capacity_inference as harness, capacity_protocol as protocol
from evaluation import capacity_evidence as evidence, token_accounting as accounting
from evaluation import execution_guard as guard
from evaluation.common import BASE, digest, read_json, sha256
from evaluation.thinking_evidence import inventory
from evaluation.tests.test_dev_inference import Fake as DevFake
from evaluation import dev_inference


def config():
    return read_json(BASE / 'configs/quality_v2.draft.json')


def snapshot():
    return read_json(accounting.PHASE2 / 'metadata.json')


class FixtureCounter:
    """Fake CPU counts for control-flow testing; never used by production CLIs."""
    def __init__(self, metadata):
        self.snapshot = metadata

    def measure(self, model, messages, think=False):
        rendered = accounting.render(model, messages, think)
        count = max(1, len(rendered) // 4)
        return {'identity': {'status': 'calibrated_cpu', 'cpu_only': True, 'vocab_only': True,
                'tokenizer': 'OFFLINE TEST FIXTURE', 'tokenizer_version': 'synthetic-1',
                'model_digest': self.snapshot['models'][model]['digest']},
                'rendered': rendered, 'rendered_sha256': sha256(rendered.encode()),
                'token_ids': list(range(count)), 'count': count,
                'messages_sha256': digest(messages), 'think': think}

    def close(self):
        pass


class FixtureTransport:
    def __init__(self, metadata):
        self.metadata, self.calls, self.resident, self.expire = metadata, [], None, False

    def request(self, endpoint, body=None):
        self.calls.append((endpoint, deepcopy(body)))
        if endpoint == '/api/ps':
            if self.expire:
                self.resident, self.expire = None, False
            if self.resident is None:
                return {'models': []}
            return {'models': [{'name': self.resident,
                'digest': self.metadata['models'][self.resident]['digest'], 'size': 1000,
                'size_vram': 1000, 'context_length': 8192}]}
        if endpoint == '/api/version': return self.metadata['ollama_version']
        if endpoint == '/api/tags':
            return {'models': [{'name': name, 'digest': item['digest']}
                               for name, item in self.metadata['models'].items()]}
        if endpoint == '/api/show': return self.metadata['models'][body['model']]['show']
        raise AssertionError('Unexpected real request route: ' + endpoint)


class SleepingTransport:
    def request(self, endpoint, body=None):
        time.sleep(2)
        return {}


def gpu():
    return {'gpus': [{'index': 0, 'uuid': 'fixture-gpu', 'name': 'NVIDIA GeForce RTX 5060 Ti',
                     'total_mib': 16311, 'used_mib': 9000, 'free_mib': 6000, 'driver': '580.178.04'}],
            'processes': []}


class CapacityTests(unittest.TestCase):
    def setUp(self):
        for name in ('socket.create_connection', 'socket.socket.connect',
                     'urllib.request.OpenerDirector.open', 'subprocess.run'):
            p = patch(name, side_effect=AssertionError('Real service/GPU access forbidden'))
            p.start(); self.addCleanup(p.stop)
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.metadata = snapshot()
        self.counter = FixtureCounter(self.metadata)
        self.config = config()
        self.plan = protocol.prepare(self.config, self.metadata, self.counter)
        self.fake = FixtureTransport(self.metadata)
        self.sent = []
        self.failure = None

    def fake_request(self, transport, request, timeout, monitor, on_sent):
        on_sent()
        transport.calls.append(('/api/chat', deepcopy(request)))
        probe = next(p for p in self.plan['probes'] if p['request'] == request)
        self.sent.append(probe)
        if isinstance(self.failure, Exception): raise self.failure
        transport.resident = probe['model']
        monitor.sample('inflight')
        content = json.dumps(protocol.markers(probe['model'], probe['case']))
        if probe['case'] == 'IO': content += '\n1 cedar amber river stone\n2 cedar amber river stone'
        raw = {'model': probe['model'], 'done': True,
               'done_reason': 'length' if probe['case'] == 'IO' else 'stop',
               'message': {'role': 'assistant', 'content': content},
               'prompt_eval_count': probe['tokenization']['count'],
               'eval_count': 4096 if probe['case'] == 'IO' else 64,
               'load_duration': 1000, 'total_duration': 1000000, 'eval_duration': 10000}
        if callable(self.failure): self.failure(raw, monitor)
        return raw, 0.1

    def collect(self, gpu_action=gpu):
        # Expire only when wait_empty is invoked after the IO final sample.
        original = harness.wait_empty
        def expire(transport, **kwargs):
            transport.expire = True
            return original(transport, **kwargs)
        with patch.object(harness, 'wait_empty', side_effect=expire):
            return harness.run(self.plan, self.root / 'runs', self.fake, self.counter,
                gpu=gpu_action, coordination_root=self.root / 'coord', request_call=self.fake_request)

    def report(self):
        run = self.collect()
        return run, evidence.build_report(run, self.counter)

    def test_exact_payloads_targets_and_reproducibility(self):
        original = deepcopy(self.config)
        self.assertEqual(self.plan, protocol.prepare(self.config, self.metadata, self.counter))
        self.assertEqual(len(self.plan['probes']), 9)
        for probe in self.plan['probes']:
            req = probe['request']
            self.assertFalse(req['think']); self.assertFalse(req['truncate']); self.assertFalse(req['shift'])
            self.assertEqual(req['keep_alive'], '30s')
            self.assertEqual(req['options'], self.config['options'])
            if probe['target']:
                self.assertLessEqual(abs(probe['target'] - probe['tokenization']['count']), 32)
        self.assertEqual(self.config, original)

    def test_missing_flags_refuse_before_any_backend_or_transport(self):
        for flags in ([], ['--allow-inference'], ['--allow-inference', '--development-only']):
            with patch.object(harness, 'CpuCounter') as counter, patch.object(harness, 'DevTransport') as transport:
                with self.assertRaises(SystemExit):harness.main(['run', '--plan', 'missing.json', *flags])
                counter.assert_not_called();transport.assert_not_called()

    def test_successful_run_report_and_named_review(self):
        run, report = self.report()
        self.assertEqual(len(self.sent), 9)
        self.assertTrue((run / 'complete.json').exists())
        self.assertFalse(report['capacity_verified'])
        result = evidence.validate_report(report, self.config, self.metadata, 'Offline test reviewer', self.counter)
        self.assertTrue(result['capacity_criteria_met']);self.assertFalse(result['capacity_verified'])
        with self.assertRaisesRegex(ValueError, 'named capacity reviewer'):
            evidence.validate_report(report, self.config, self.metadata, '', self.counter)

    def test_successful_unique_runs_preserve_previous_artifacts(self):
        a = self.collect(); before = inventory(a)
        b = self.collect()
        self.assertNotEqual(a, b);self.assertEqual(inventory(a), before)

    def test_failed_marker_retrieval_stops_without_retry(self):
        self.failure = lambda raw, monitor: raw['message'].update(content='{"begin":"wrong"}')
        with self.assertRaisesRegex(ValueError, 'marker retrieval'):self.collect()
        self.assertEqual(len(self.sent), 1)
        self.assertFalse((self.root / 'coord/BLOCKED.json').exists())
        self.assertEqual(len(list((self.root / 'runs').glob('*/qwen3_1.7b-S/response.json'))), 1)

    def test_input_truncation_stops(self):
        self.failure = lambda raw, monitor: raw.update(prompt_eval_count=1)
        with self.assertRaisesRegex(ValueError, 'input truncation'):self.collect()
        self.assertEqual(len(self.sent), 1)

    def test_insufficient_output_does_not_certify_capacity(self):
        def short(raw, monitor):
            if raw['done_reason'] == 'length':raw['eval_count'] = 100
        self.failure = short
        with self.assertRaisesRegex(ValueError, 'insufficient output'):self.collect()
        self.assertEqual(len(self.sent), 3)
        run = next(p for p in (self.root / 'runs').iterdir() if p.is_dir())
        with self.assertRaises(FileNotFoundError):evidence.build_report(run, self.counter)

    def test_mismatched_model_oom_malformed_and_incomplete_latch_uncertainty(self):
        for label, mutation in (
            ('model', lambda raw: raw.update(model='other')),
            ('oom', lambda raw: raw.update(error='CUDA out of memory')),
            ('http', lambda raw: raw.update(_collector_error='invalid_json')),
            ('done', lambda raw: raw.update(done=False))):
            with self.subTest(label=label):
                self.root = Path(self.temp.name) / label
                self.fake = FixtureTransport(self.metadata)
                self.failure = lambda raw, monitor: mutation(raw)
                with self.assertRaises(ValueError):self.collect()
                self.assertTrue((self.root / 'coord/BLOCKED.json').exists())
                calls = len(self.fake.calls)
                with self.assertRaisesRegex(ValueError, 'unresolved'):self.collect()
                self.assertEqual(len(self.fake.calls), calls)

    def test_monitoring_and_gpu_residency_failures_stop(self):
        for label in ('gpu', 'memory', 'process', 'digest', 'offload', 'context', 'missing'):
            with self.subTest(label=label):
                def broken():
                    data = gpu()
                    if label == 'gpu':raise RuntimeError('nvidia-smi unavailable')
                    if label == 'memory':data['gpus'][0]['free_mib'] = 100
                    if label == 'process':data['processes'] = [{'pid': 1}]
                    return data
                if label in ('digest', 'offload', 'context', 'missing'):
                    from evaluation.capacity_monitor import check_sample
                    sample = {'telemetry': gpu(), 'ollama_ps': {'models': [
                        {'name': 'qwen3:1.7b', 'digest': self.metadata['models']['qwen3:1.7b']['digest'],
                         'size': 100, 'size_vram': 100, 'context_length': 8192}]}}
                    item = sample['ollama_ps']['models'][0]
                    if label == 'digest':item['digest'] = 'wrong'
                    if label == 'offload':item['size_vram'] = 50
                    if label == 'context':item['context_length'] = 4096
                    if label == 'missing':sample['ollama_ps']['models'] = []
                    with self.assertRaises(ValueError):
                        check_sample(sample, 'qwen3:1.7b', self.metadata['models']['qwen3:1.7b']['digest'], True)
                else:
                    self.root = Path(self.temp.name) / label
                    with self.assertRaises(RuntimeError):self.collect(broken)

    def test_transport_timeout_persists_latch_and_blocks_development(self):
        self.failure = TimeoutError('mock completion unknown')
        with self.assertRaises(TimeoutError):self.collect()
        self.assertTrue((self.root / 'coord/BLOCKED.json').exists())
        fake = DevFake()
        with self.assertRaisesRegex(ValueError, 'unresolved'):
            dev_inference.run(self.config, self.root / 'dev', fake, gpu=lambda: {},
                              coordination_root=self.root / 'coord')
        self.assertEqual(fake.calls, [])

    def test_independent_deadline_terminates_local_worker(self):
        monitor = type('Monitor', (), {'failed': threading.Event()})()
        started = time.monotonic()
        with self.assertRaises((TimeoutError, RuntimeError)):
            harness.bounded_request(SleepingTransport(), {}, 0.05, monitor)
        self.assertLess(time.monotonic() - started, 1.5)

    def test_shared_execution_lock_blocks_capacity_and_development(self):
        with guard.execution_guard(self.root / 'coord'):
            with self.assertRaisesRegex(ValueError, 'execution lock'):self.collect()
            with self.assertRaisesRegex(ValueError, 'execution lock'):
                dev_inference.run(self.config, self.root / 'dev', DevFake(), gpu=lambda: {},
                                  coordination_root=self.root / 'coord')
        self.assertEqual(self.fake.calls, [])

    def test_tokenization_unavailable_blocks_before_service_access(self):
        with patch.object(accounting.importlib.util, 'find_spec', return_value=None):
            counter = accounting.CpuCounter(self.metadata)
        with self.assertRaisesRegex(ValueError, 'unavailable'):
            harness.run(self.plan, self.root / 'runs', self.fake, counter, coordination_root=self.root / 'coord')
        self.assertEqual(self.fake.calls, [])

    def test_token_census_has_210_rows_without_invented_counts(self):
        with patch.object(accounting.importlib.util, 'find_spec', return_value=None):
            counter = accounting.CpuCounter(self.metadata)
        report = accounting.census(self.config, self.metadata, counter)
        self.assertEqual(len(report['rows']), 210)
        self.assertTrue(all(r['count'] is None for r in report['rows']))
        self.assertFalse(report['exact_counts_available'])

    def test_gemma_profile_includes_system_generation_prefix_and_thinking_control(self):
        messages = [{'role': 'system', 'content': ' system '}, {'role': 'user', 'content': ' user '}]
        off = accounting.render('gemma4:12b', messages, False)
        on = accounting.render('gemma4:12b', messages, True)
        self.assertIn('<|turn>system\nsystem<turn|>', off)
        self.assertIn('<|turn>model\n<|channel>thought\n<channel|>', off)
        self.assertIn('<|think|>', on)
        self.assertNotEqual(off, on)
        with self.assertRaises(ValueError):accounting.render('gemma4:12b', messages, None)

    def test_tampered_plan_rejected_before_service(self):
        self.plan['probes'][0]['tokenization']['count'] += 1
        with self.assertRaisesRegex(ValueError, 'plan/tokenization'):self.collect()
        self.assertEqual(self.fake.calls, [])

    def test_evidence_hash_tampering_is_rejected(self):
        run, report = self.report()
        path = run / 'qwen3_1.7b-S/response.json'
        path.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'inventory/hash'):
            evidence.validate_report(report, self.config, self.metadata, 'reviewer', self.counter)

    def test_rehashed_substantively_wrong_evidence_is_rejected(self):
        run, report = self.report()
        path = run / 'qwen3_1.7b-I/response.json'
        raw = read_json(path);raw['prompt_eval_count'] -= 100;path.write_text(json.dumps(raw))
        report['files'] = inventory(run)
        with self.assertRaisesRegex(ValueError, 'input truncation'):
            evidence.validate_report(report, self.config, self.metadata, 'reviewer', self.counter)

    def test_report_binds_config_metadata_and_validator(self):
        run, report = self.report()
        for change in ('options', 'metadata', 'source', 'findings'):
            with self.subTest(change=change):
                cfg, snap, candidate = deepcopy(self.config), deepcopy(self.metadata), deepcopy(report)
                if change == 'options':cfg['options']['num_ctx'] = 4096
                if change == 'metadata':snap['models']['qwen3:1.7b']['digest'] = 'wrong'
                if change == 'source':candidate['validator_sha256'] = {}
                if change == 'findings':candidate['findings']['capacity'] = 'approved'
                with self.assertRaises(ValueError):
                    evidence.validate_report(candidate, cfg, snap, 'reviewer', self.counter)

    def test_missing_monitoring_and_nonfinite_timing_rejected(self):
        run, report = self.report()
        path = run / 'qwen3_1.7b-S/timing.json'
        timing = read_json(path);timing['request_wall_time_s'] = math.inf
        path.write_text(json.dumps(timing));report['files'] = inventory(run)
        with self.assertRaisesRegex(ValueError, 'timing evidence'):
            evidence.validate_report(report, self.config, self.metadata, 'reviewer', self.counter)

    def test_raw_format_failure_is_separate_from_thinking(self):
        self.failure = lambda raw, monitor: raw['message'].update(content='prose {"begin":"x"}')
        with self.assertRaisesRegex(ValueError, 'output format'):self.collect()
        path = next((self.root / 'runs').glob('*/qwen3_1.7b-S/error.json'))
        findings = read_json(path)['findings']
        self.assertTrue(findings['thinking_disabled_observed'])
        self.assertEqual(findings['output_format'], 'failed')
        self.assertEqual(findings['capacity_probe'], 'insufficient')

    def test_monitor_failure_after_send_is_latched(self):
        def fail(raw, monitor):
            monitor.failed.set()
            monitor.error = {'message': 'fixture monitoring failure'}
        self.failure = fail
        with self.assertRaises(RuntimeError):self.collect()
        self.assertEqual(len(self.sent), 1)
        self.assertTrue((self.root / 'coord/BLOCKED.json').exists())
        self.assertTrue(list((self.root / 'runs').glob('*/qwen3_1.7b-S/response.json')))

    def test_metadata_mismatch_stops_before_chat(self):
        original = self.fake.request
        def changed(endpoint, body=None):
            response = original(endpoint, body)
            if endpoint == '/api/version':return {'version': 'other'}
            return response
        self.fake.request = changed
        with self.assertRaisesRegex(ValueError, 'metadata or digest mismatch'):self.collect()
        self.assertEqual(self.sent, [])

    def test_inflight_worker_aborts_on_monitor_signal(self):
        event = threading.Event();event.set()
        monitor = type('Monitor', (), {'failed': event})()
        with self.assertRaisesRegex(RuntimeError, 'Unsafe activity'):
            harness.bounded_request(SleepingTransport(), {}, 10, monitor)

    def test_source_changed_and_missing_samples_fail_even_if_rehashed(self):
        run, report = self.report()
        path = run / 'qwen3_1.7b-I/monitoring/sample-000000.json'
        path.unlink();report['files'] = inventory(run)
        with self.assertRaisesRegex(ValueError, 'monitoring coverage'):
            evidence.validate_report(report, self.config, self.metadata, 'reviewer', self.counter)

    def test_residency_tampering_fails_even_if_rehashed(self):
        run, report = self.report()
        path = run / 'qwen3_1.7b-I/monitoring/sample-000001.json'
        sample = read_json(path);sample['ollama_ps']['models'][0]['size_vram'] = 1
        path.write_text(json.dumps(sample));report['files'] = inventory(run)
        with self.assertRaisesRegex(ValueError, 'GPU residency'):
            evidence.validate_report(report, self.config, self.metadata, 'reviewer', self.counter)

    def test_capacity_evidence_cannot_approve_thinking_enabled_configuration(self):
        run, report = self.report()
        with self.assertRaisesRegex(ValueError, 'only think=false'):
            evidence.validate_report(report, dict(self.config, think=True), self.metadata, 'reviewer', self.counter)

    def test_new_substantive_gate_rejects_hash_only_capacity_files(self):
        from evaluation import runner
        path = self.root / 'empty-report.json';path.write_text('{}')
        # Valid Phase 2 thinking evidence plus a hashed but substantively empty report.
        index = read_json(BASE / 'evidence/phase2-thinking-v1.json')
        verification = {'reviewer': 'offline fixture',
            'thinking_verification': {'method': 'empirical-thinking-v1', 'evidence': index,
                                      'evidence_sha256': digest(index)},
            'models': {name: {'digest': data['digest'], 'capacity_verified': True,
                'verified_options': self.config['options'], 'evidence_note': 'offline fixture',
                'capacity_evidence': [{'path': str(path), 'sha256': sha256(path.read_bytes())}]}
                for name, data in self.metadata['models'].items()}}
        with self.assertRaisesRegex(ValueError, 'unsupported capacity report'):
            runner.validate_verification(self.config, self.metadata, verification, False)

    def test_benchmark_collector_also_obeys_shared_lock(self):
        from evaluation import runner
        fake = DevFake()
        run = self.root / 'benchmark';run.mkdir()
        with patch.object(guard, 'DEFAULT_ROOT', self.root / 'coord'):
            with guard.execution_guard():
                with self.assertRaisesRegex(ValueError, 'execution lock'):
                    runner.collect(run, fake)
        self.assertEqual(fake.calls, [])

    def test_durable_pending_record_survives_interrupted_collector(self):
        coord = self.root / 'coord'
        with guard.execution_guard(coord):
            guard.mark_pending(coord, 'synthetic-run', 'synthetic-attempt')
        with self.assertRaisesRegex(ValueError, 'unresolved'):
            with guard.execution_guard(coord):pass
        with self.assertRaisesRegex(ValueError, 'ownership mismatch'):
            guard.complete_pending(coord, 'other-run', 'synthetic-attempt')
        self.assertTrue((coord / 'PENDING.json').exists())

    def test_claimed_counts_without_token_ids_are_rejected(self):
        original = self.counter.measure
        def missing(*args):
            result = original(*args);result['token_ids'] = [];return result
        self.counter.measure = missing
        with self.assertRaisesRegex(ValueError, 'invalid tokenization'):self.collect()
        self.assertEqual(self.fake.calls, [])
