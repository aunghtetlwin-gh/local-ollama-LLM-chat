"""Saved-evidence regression tests; edits are confined to disposable copies."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from evaluation import runner
from evaluation.common import BASE, digest, read_json
from evaluation import thinking_evidence as evidence

PHASE2 = BASE.parent / 'evaluation_dev_runs/dev-2026-11-03T071419.213574+0000-db8509361d9e'


class EmpiricalThinkingTests(unittest.TestCase):
    def setUp(self):
        for target in ('socket.create_connection', 'socket.socket.connect',
                       'urllib.request.OpenerDirector.open', 'subprocess.run'):
            p = patch(target, side_effect=AssertionError('Real service/GPU access forbidden'))
            p.start()
            self.addCleanup(p.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'saved'
        shutil.copytree(PHASE2, self.root)
        self.config = read_json(self.root / 'manifest.json')['config']
        self.snapshot = read_json(self.root / 'metadata.json')
        self.index = evidence.build_index(self.root)

    def mutate(self, relative, action, rehash=False):
        path = self.root / relative
        obj = read_json(path)
        action(obj)
        path.write_text(json.dumps(obj))
        if rehash:
            self.index['files'] = evidence.inventory(self.root)

    def verify(self):
        return evidence.validate_index(self.config, self.snapshot, self.index)

    def verification(self):
        return {'reviewer': 'offline regression fixture',
                'thinking_verification': {'method': evidence.VERSION, 'evidence': self.index,
                                          'evidence_sha256': digest(self.index)},
                'models': {name: {'digest': data['digest'], 'capacity_verified': False,
                                  'evidence_note': 'Thinking only; no capacity evidence',
                                  'verified_options': deepcopy(self.config['options'])}
                           for name, data in self.snapshot['models'].items()}}

    def test_real_saved_pairs_validate_without_relaxing_format(self):
        before = deepcopy(self.snapshot)
        result = self.verify()
        self.assertEqual(len(result), 9)
        self.assertEqual(result['qwen3_1.7b-A'],
                         {'thinking_compatible': True, 'output_format': 'failed'})
        self.assertEqual(self.snapshot, before)
        self.assertTrue(all('thinking' not in data['show'] for data in self.snapshot['models'].values()))

    def test_committed_phase2_index_matches_original_evidence(self):
        index = read_json(BASE / 'evidence/phase2-thinking-v1.json')
        self.assertEqual(len(evidence.validate_index(self.config, self.snapshot, index)), 9)

    def test_missing_corrupted_and_added_files_fail_closed(self):
        path = self.root / 'qwen3_1.7b-A/response.json'
        original = path.read_bytes()
        for action in ('missing', 'corrupt', 'added'):
            with self.subTest(action=action):
                if action == 'missing':path.unlink()
                elif action == 'corrupt':path.write_text('{}')
                else:(self.root / 'extra.json').write_text('{}')
                with self.assertRaisesRegex(ValueError, 'inventory/hash'):self.verify()
                path.write_bytes(original)

    def test_configuration_metadata_and_validator_mismatch(self):
        for field in ('options', 'system', 'digest', 'template', 'version', 'validator', 'schema'):
            with self.subTest(field=field):
                config, snapshot, index = deepcopy(self.config), deepcopy(self.snapshot), deepcopy(self.index)
                name = config['models'][0]
                if field == 'options':config['options']['num_ctx'] = 4096
                if field == 'system':config['system_message'] = 'different'
                if field == 'digest':snapshot['models'][name]['digest'] = 'different'
                if field == 'template':snapshot['models'][name]['show']['template'] = 'different'
                if field == 'version':snapshot['ollama_version']['version'] = 'different'
                if field == 'validator':index['validator_sha256'] = {}
                if field == 'schema':index['version'] = 'unknown'
                with self.assertRaises(ValueError):evidence.validate_index(config, snapshot, index)

    def test_rehashed_contradictory_or_incomplete_response_rejected(self):
        path = 'qwen3_1.7b-B/response.json'
        original = (self.root / path).read_bytes()
        for change in ('thinking', 'done', 'reason', 'model', 'http', 'oom', 'tool', 'role'):
            with self.subTest(change=change):
                def alter(raw):
                    if change == 'thinking':raw['message']['thinking'] = ''
                    if change == 'done':raw['done'] = False
                    if change == 'reason':raw['done_reason'] = 'length'
                    if change == 'model':raw['model'] = 'wrong'
                    if change == 'http':raw['_collector_error'] = 'invalid_json'
                    if change == 'oom':raw['error'] = 'out of memory'
                    if change == 'tool':raw['message']['tool_calls'] = [{}]
                    if change == 'role':raw['message']['role'] = 'tool'
                self.mutate(path, alter, rehash=True)
                with self.assertRaises(ValueError):self.verify()
                (self.root / path).write_bytes(original)
                self.index['files'] = evidence.inventory(self.root)

    def test_thinking_disabled_must_have_no_thinking(self):
        self.mutate('qwen3_1.7b-A/response.json',
                    lambda raw: raw['message'].update(thinking='unexpected'), rehash=True)
        with self.assertRaisesRegex(ValueError, 'thinking behavior'):self.verify()

    def test_request_options_and_boolean_mode_must_match(self):
        path = 'qwen3_8b-B/request.json'
        original = (self.root / path).read_bytes()
        for mutate in (lambda req: req.update(think=1),
                       lambda req: req['options'].update(seed=43),
                       lambda req: req['messages'][0].update(content='other')):
            self.mutate(path, mutate, rehash=True)
            with self.assertRaisesRegex(ValueError, 'request mismatch'):self.verify()
            (self.root / path).write_bytes(original)

    def test_saved_pass_flags_do_not_override_recomputed_outcomes(self):
        self.mutate('qwen3_1.7b-A/output_format.json',
                    lambda obj: obj.update(status='passed', code=None), rehash=True)
        with self.assertRaisesRegex(ValueError, 'output-format'):self.verify()

    def test_monitoring_and_residency_are_required(self):
        sample = next((self.root / 'qwen3_8b-B/monitoring').glob('sample-*.json'))
        self.mutate(str(sample.relative_to(self.root)),
                    lambda obj: obj.update(gpu_error={'message': 'failed'}), rehash=True)
        with self.assertRaisesRegex(ValueError, 'monitoring failure'):self.verify()

    def test_rehashed_summary_and_completion_contradictions(self):
        self.mutate('complete.json', lambda obj: obj.update(output_format_failures=0), rehash=True)
        with self.assertRaisesRegex(ValueError, 'experiment result'):self.verify()

    def test_reviewer_index_hash_and_capacity_gates_remain(self):
        ver = self.verification()
        with self.assertRaisesRegex(ValueError, 'capacity'):
            runner.validate_verification(self.config, self.snapshot, ver, False)
        ver['reviewer'] = ''
        with self.assertRaisesRegex(ValueError, 'reviewer'):
            runner.validate_verification(self.config, self.snapshot, ver, False)
        ver['reviewer'] = 'offline regression fixture'
        ver['thinking_verification']['evidence_sha256'] = 'wrong'
        with self.assertRaisesRegex(ValueError, 'index hash'):
            runner.validate_verification(self.config, self.snapshot, ver, False)

    def test_advertised_path_is_preserved_and_unknown_method_rejected(self):
        ver = self.verification()
        ver.pop('thinking_verification')
        with self.assertRaisesRegex(ValueError, 'not advertised'):
            runner.validate_verification(self.config, self.snapshot, ver, False)
        ver['thinking_verification'] = {'method': 'skip-verification'}
        with self.assertRaisesRegex(ValueError, 'Unknown'):
            runner.validate_verification(self.config, self.snapshot, ver, False)

    def test_empirical_gate_accepts_only_with_separate_capacity_attestation(self):
        # Synthetic capacity attestation tests wiring only; it makes no real capacity claim.
        report = Path(self.temp.name) / 'synthetic-capacity.txt'
        report.write_text('{"fixture":"OFFLINE TEST ONLY; not real capacity evidence"}')
        ver = self.verification()
        for item in ver['models'].values():
            item['capacity_verified'] = True
        with self.assertRaisesRegex(ValueError, 'Separate capacity'):
            runner.validate_verification(self.config, self.snapshot, ver, False)
        for item in ver['models'].values():
            item['capacity_evidence'] = [{'path': str(report),
                                         'sha256': evidence.sha256(report.read_bytes())}]
        # This legacy test exercises attachment wiring; substantive synthetic reports
        # are covered in test_capacity.py. Plain text is not real capacity evidence.
        with patch('evaluation.capacity_evidence.validate_report') as validator:
            for mode in (False, True):
                runner.validate_verification(self.config, self.snapshot, ver, mode)
            self.assertEqual(validator.call_count, 6)
        report.write_text('changed')
        with self.assertRaisesRegex(ValueError, 'Capacity evidence file hash'):
            runner.validate_verification(self.config, self.snapshot, ver, False)

    def test_thinking_artifact_cannot_be_used_as_capacity_evidence(self):
        ver = self.verification()
        path = self.root / 'metadata.json'
        for item in ver['models'].values():
            item.update(capacity_verified=True, capacity_evidence=[
                {'path': str(path), 'sha256': evidence.sha256(path.read_bytes())}])
        with self.assertRaisesRegex(ValueError, 'not capacity evidence'):
            runner.validate_verification(self.config, self.snapshot, ver, False)

    def test_advertised_mode_contradiction_is_not_ignored_by_empirical_path(self):
        self.mutate('metadata.json', lambda obj: obj['models']['qwen3:8b']['show'].update(
            thinking={'values': [False]}), rehash=True)
        self.snapshot = read_json(self.root / 'metadata.json')
        with self.assertRaisesRegex(ValueError, 'advertised modes contradict'):self.verify()

    def test_missing_pair_rejected_even_with_rehashed_inventory(self):
        (self.root / 'qwen3_8b-B/request.json').unlink()
        self.index['files'] = evidence.inventory(self.root)
        with self.assertRaisesRegex(ValueError, 'missing probes'):self.verify()

    def test_contradictory_summary_is_rejected(self):
        self.mutate('qwen3_8b-B/summary.json', lambda obj: obj.update(done=False), rehash=True)
        with self.assertRaisesRegex(ValueError, 'summary'):self.verify()

    def test_symlink_evidence_rejected(self):
        (self.root / 'alias.json').symlink_to(self.root / 'metadata.json')
        with self.assertRaisesRegex(ValueError, 'symlinks'):self.verify()

    def test_index_builder_refuses_writing_inside_saved_experiment(self):
        with self.assertRaises(SystemExit):
            evidence.main(['--run-dir', str(self.root), '--output', str(self.root / 'index.json')])
        self.assertFalse((self.root / 'index.json').exists())
