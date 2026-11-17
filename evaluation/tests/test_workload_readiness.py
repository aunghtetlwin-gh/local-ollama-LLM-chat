"""Scoped readiness and residency tests; no real service/GPU access or approval."""
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evaluation import runner, workload_readiness as scope, common, scoring
from evaluation import execution_guard as guard
from evaluation.thinking_evidence import inventory
from evaluation.tests.test_evaluation import FakeTransport, frozen as full_fixture

PHASE2 = common.BASE.parent / 'evaluation_dev_runs/dev-2026-11-03T071419.213574+0000-db8509361d9e'


def candidate():
    result = common.read_json(common.BASE / 'configs/quality_v2.draft.json')
    result.update(repetitions=1, think=False, keep_alive='30s')
    return result


def metadata():
    return common.read_json(PHASE2 / 'metadata.json')


def review_fixture(config=None):
    config = config or candidate()
    value = scope.prepare(config, metadata(), common.read_json(common.BASE / 'evidence/phase2-thinking-v1.json'))
    value.update(reviewer='OFFLINE TEST FIXTURE reviewer', verified_at='2026-11-03T10:00:00+00:00')
    value['workload_readiness'].update(decision='approved', limitations_acknowledged=True)
    return value


class ResidencyTransport(FakeTransport):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.resident = None
        self.polls = 0
        self.events = []
        self.foreign = False
        self.never_expires = False
        self.bad_digest = False

    def request(self, endpoint, body=None):
        if endpoint == '/api/ps':
            self.calls.append((endpoint, body))
            if self.foreign:
                return {'models': [{'name': 'foreign:model', 'digest': 'foreign'}]}
            if self.resident:
                name = self.resident
                self.polls += 1
                # One nonempty observation during expiration, then natural expiry.
                # Before scored requests is also polled; collecting does not depend
                # on continuous residency inside a block.
                if self.polls >= 2 and not self.never_expires:
                    self.events.append(('expired', name))
                    self.resident = None
                    return {'models': []}
                return {'models': [{'name': name, 'digest': 'wrong' if self.bad_digest else 'fixture-' + name}]}
            return {'models': []}
        raw = super().request(endpoint, body)
        if endpoint == '/api/chat':
            self.events.append(('chat', body['model'], body['options']['num_predict']))
            self.resident, self.polls = body['model'], 0
        return raw


class ScopedReadinessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        p = patch.object(guard, 'DEFAULT_ROOT', self.root / 'coord')
        p.start();self.addCleanup(p.stop)
        for name in ('socket.create_connection', 'socket.socket.connect',
                     'urllib.request.OpenerDirector.open', 'subprocess.run'):
            p = patch(name, side_effect=AssertionError('Real service/GPU access forbidden'))
            p.start();self.addCleanup(p.stop)
        self.config = candidate()
        self.snapshot = metadata()
        self.verification = review_fixture(self.config)

    def test_preparation_is_pending_and_cannot_authorize_collection(self):
        pending = scope.prepare(self.config, self.snapshot,
                                common.read_json(common.BASE / 'evidence/phase2-thinking-v1.json'))
        self.assertEqual(pending['reviewer'], '')
        self.assertEqual(pending['workload_readiness']['decision'], 'pending')
        self.assertTrue(all(item['capacity_verified'] is False for item in pending['models'].values()))
        with self.assertRaisesRegex(ValueError, 'reviewer'):
            runner.validate_verification(self.config, self.snapshot, pending, False)

    def test_scoped_acceptance_keeps_capacity_false_and_freeze_checks(self):
        # In-memory synthetic approval only; no frozen artifact is written.
        runner.validate_verification(self.config, self.snapshot, self.verification, False)
        result = runner.freeze(self.config, self.snapshot, self.verification, False)
        runner.validate_config(result, frozen=True)
        self.assertTrue(all(item['capacity_verified'] is False for item in result['verification']['models'].values()))
        self.assertEqual(len(runner.make_plan(result, ['internal_v2', 'gsm8k_50_v1'])), 210)
        self.assertEqual(len(runner.make_plan(result, ['internal_v2'], ['C03', 'I01'])), 6)
        self.assertEqual(self.config['protocol_status'], 'draft')

    def test_missing_or_negative_review_rejected(self):
        for change in ('reviewer', 'decision', 'acknowledgement', 'date', 'timezone', 'version', 'hash', 'capacity'):
            with self.subTest(change=change):
                ver = deepcopy(self.verification)
                if change == 'reviewer':ver['reviewer'] = ' '
                if change == 'decision':ver['workload_readiness']['decision'] = 'pending'
                if change == 'acknowledgement':ver['workload_readiness']['limitations_acknowledged'] = False
                if change == 'date':ver['verified_at'] = ''
                if change == 'timezone':ver['verified_at'] = '2026-11-03T10:00:00'
                if change == 'version':ver['workload_readiness']['method'] = 'skip'
                if change == 'hash':ver['workload_readiness']['binding_sha256'] = 'wrong'
                if change == 'capacity':ver['models']['qwen3:1.7b']['capacity_verified'] = True
                with self.assertRaises(ValueError):runner.validate_verification(self.config, self.snapshot, ver, False)

    def test_missing_scope_does_not_skip_full_capacity_gate(self):
        ver = deepcopy(self.verification);ver.pop('workload_readiness')
        with self.assertRaisesRegex(ValueError, 'capacity'):
            runner.validate_verification(self.config, self.snapshot, ver, False)
        legacy = full_fixture()
        runner.validate_config(legacy, frozen=True)

    def test_changed_settings_and_identity_rejected(self):
        for change in ('options', 'system', 'repetitions', 'keep_alive', 'timeout', 'ordering',
                       'digest', 'version', 'template', 'thinking'):
            with self.subTest(change=change):
                cfg, snap = deepcopy(self.config), deepcopy(self.snapshot)
                thinking = False
                if change == 'options':cfg['options']['top_p'] = 0.8
                if change == 'system':cfg['system_message'] += 'changed'
                if change == 'repetitions':cfg['repetitions'] = 3
                if change == 'keep_alive':cfg['keep_alive'] = '10m'
                if change == 'timeout':cfg['timeout_seconds'] = 599
                if change == 'ordering':cfg['question_order_seed'] += 'changed'
                if change == 'digest':snap['models']['qwen3:1.7b']['digest'] = 'changed'
                if change == 'version':snap['ollama_version']['version'] = 'changed'
                if change == 'template':snap['models']['gemma4:12b']['show']['template'] = 'changed'
                if change == 'thinking':thinking = True
                with self.assertRaises(ValueError):runner.validate_verification(cfg, snap, self.verification, thinking)

    def test_missing_or_corrupt_empirical_thinking_evidence_rejected(self):
        ver = deepcopy(self.verification)
        ver['thinking_verification']['evidence']['files'].pop('metadata.json')
        ver['thinking_verification']['evidence_sha256'] = common.digest(ver['thinking_verification']['evidence'])
        with self.assertRaisesRegex(ValueError, 'inventory/hash'):
            runner.validate_verification(self.config, self.snapshot, ver, False)

    def test_source_and_dataset_binding_changes_rejected(self):
        with patch.object(runner, 'code_hashes', return_value={}):
            with self.assertRaisesRegex(ValueError, 'binding changed'):
                runner.validate_verification(self.config, self.snapshot, self.verification, False)
        altered = scope.datasets();altered['internal_v2']['manifest_sha256'] = 'wrong'
        with patch.object(scope, 'datasets', return_value=altered):
            with self.assertRaisesRegex(ValueError, 'binding changed'):
                runner.validate_verification(self.config, self.snapshot, self.verification, False)

    def test_reference_boundary_and_approved_subsets(self):
        config = runner.freeze(self.config, self.snapshot, self.verification, False)
        original = Path.open
        def guarded(path, *args, **kwargs):
            self.assertNotIn(path.name, {'references.jsonl', 'upstream_test.jsonl'})
            return original(path, *args, **kwargs)
        with patch.object(Path, 'open', guarded):
            runner.validate_config(config, frozen=True)
            self.assertEqual(len(runner.make_plan(config, ['internal_v2'], ['C03', 'I01'])), 6)
        with self.assertRaises(ValueError):runner.make_plan(config, ['internal_v2'], ['UNKNOWN'])
        with self.assertRaises(ValueError):scope.validate_selection(config, ['other'])

    def test_limitations_cannot_be_silently_rewritten(self):
        ver = deepcopy(self.verification)
        ver['workload_readiness']['binding']['limitations'] = ['Capacity fully verified']
        ver['workload_readiness']['binding_sha256'] = common.digest(ver['workload_readiness']['binding'])
        with self.assertRaisesRegex(ValueError, 'binding changed'):
            runner.validate_verification(self.config, self.snapshot, ver, False)

    def test_truncations_and_malformed_answers_never_get_success_credit(self):
        ref = {'kind': 'json', 'expected': {'answer': 323}}
        self.assertFalse(scoring.score('{"answer":323}', ref, 'truncated')['answer_correct'])
        self.assertFalse(scoring.score('prose {"answer":323}', ref)['answer_correct'])

    def new_run(self):
        return runner.new_run(self.root / 'runs', full_fixture(), ['internal_v2'], ['R02'])

    def test_transitions_wait_and_preserve_order_and_warmups(self):
        run = self.new_run();fake = ResidencyTransport();sleeps = []
        runner.collect(run, fake, residency_sleep=lambda s: sleeps.append(s))
        chats = [event for event in fake.events if event[0] == 'chat']
        self.assertEqual([(event[1], event[2]) for event in chats],
                         [(model, limit) for model in runner.MODELS for limit in (1, 4096)])
        for i, model in enumerate(runner.MODELS[:-1]):
            last_chat = max(j for j, e in enumerate(fake.events) if e[0] == 'chat' and e[1] == model)
            next_chat = next(j for j, e in enumerate(fake.events) if e[0] == 'chat' and e[1] == runner.MODELS[i + 1])
            self.assertIn(('expired', model), fake.events[last_chat + 1:next_chat])
        self.assertEqual(len(list(run.glob('warmups/*/request.json'))), 3)
        samples = [common.read_json(p) for p in sorted(run.glob('session-*-residency-*.json'))]
        self.assertEqual(samples[0]['phase'], 'initial')
        self.assertEqual(samples[-1]['phase'], 'final')
        self.assertTrue(sleeps)
        self.assertFalse(any(endpoint in ('/api/generate', '/api/stop') for endpoint, _ in fake.calls))

    def test_initial_foreign_residency_prevents_chat(self):
        fake = ResidencyTransport();fake.foreign = True
        with self.assertRaisesRegex(ValueError, 'foreign'):runner.collect(self.new_run(), fake)
        self.assertFalse(any(e == '/api/chat' for e, _ in fake.calls))

    def test_initial_known_model_must_expire_before_warmup(self):
        fake = ResidencyTransport();fake.resident = runner.MODELS[0]
        runner.collect(self.new_run(), fake, residency_sleep=lambda _: None)
        self.assertEqual(fake.events[0], ('expired', runner.MODELS[0]))

    def test_expiration_timeout_stops_before_next_model(self):
        fake = ResidencyTransport();fake.never_expires = True
        with self.assertRaises(TimeoutError):
            runner.collect(self.new_run(), fake, residency_timeout=0, residency_sleep=lambda _: None)
        chats = [event for event in fake.events if event[0] == 'chat']
        self.assertEqual([e[1] for e in chats], [runner.MODELS[0], runner.MODELS[0]])

    def test_transition_foreign_or_digest_change_stops(self):
        for fault in ('foreign', 'digest', 'overlap', 'malformed', 'transport'):
            with self.subTest(fault=fault):
                fake = FakeTransport();original = fake.request
                def changed(endpoint, body=None):
                    if endpoint == '/api/ps' and fake.scored:
                        if fault == 'transport':raise TimeoutError('ps timeout')
                        if fault == 'malformed':return {'models': None}
                        if fault == 'overlap':return {'models': [{}, {}]}
                        return {'models': [{'name': 'foreign' if fault == 'foreign' else runner.MODELS[0], 'digest': 'wrong'}]}
                    return original(endpoint, body)
                fake.request = changed
                with self.assertRaises((ValueError, TimeoutError)):
                    runner.collect(self.new_run(), fake, residency_sleep=lambda _: None)
                self.assertEqual(fake.scored, 1)

    def test_incomplete_request_stops_without_transition_or_retry(self):
        fake = FakeTransport(raw={'done': False})
        with self.assertRaises(ValueError):runner.collect(self.new_run(), fake)
        self.assertEqual(fake.scored, 1)
        self.assertEqual(sum(e == '/api/chat' for e, _ in fake.calls), 2)

    def test_transport_ps_uses_bounded_metadata_timeout(self):
        transport = runner.OllamaTransport(600)
        with patch.object(transport.opener, 'open', return_value=io.BytesIO(b'{"models":[]}')) as opened:
            self.assertEqual(transport.request('/api/ps'), {'models': []})
            self.assertEqual(opened.call_args.kwargs['timeout'], 5)

    def test_scoped_model_records_still_require_digest_options_and_evidence(self):
        for change in ('digest', 'options', 'note', 'missing_model'):
            ver = deepcopy(self.verification)
            model = ver['models'][runner.MODELS[0]]
            if change == 'digest':model['digest'] = 'wrong'
            if change == 'options':model['verified_options'] = {}
            if change == 'note':model['evidence_note'] = ''
            if change == 'missing_model':ver['models'].pop(runner.MODELS[0])
            with self.subTest(change=change), self.assertRaises((ValueError, KeyError)):
                runner.validate_verification(self.config, self.snapshot, ver, False)

    def test_actual_corrupted_or_rehashed_dataset_rejected(self):
        import shutil
        target = self.root / 'public-dataset'
        shutil.copytree(common.DATASETS['internal_v2'], target)
        path = target / 'questions.jsonl'
        rows = common.read_jsonl(path)
        rows[0]['prompt'] += ' changed'
        rows[0]['prompt_sha256'] = common.sha256(rows[0]['prompt'].encode())
        path.write_text(''.join(json.dumps(q) + '\n' for q in rows))
        with patch.dict(common.DATASETS, {'internal_v2': target}):
            with self.assertRaisesRegex(ValueError, 'checksum'):
                runner.validate_verification(self.config, self.snapshot, self.verification, False)
            manifest = common.read_json(target / 'manifest.json')
            manifest['questions_sha256'] = common.sha256(path.read_bytes())
            (target / 'manifest.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'binding changed'):
                runner.validate_verification(self.config, self.snapshot, self.verification, False)

    def test_resume_waits_for_expiry_without_overwriting_attempts(self):
        run = self.new_run();fake = ResidencyTransport(crash_at=2)
        with self.assertRaises(KeyboardInterrupt):
            runner.collect(run, fake, residency_sleep=lambda _: None)
        before = {p: p.read_bytes() for p in run.glob('requests/*/attempt-*/*') if p.is_file()}
        resumed = ResidencyTransport()
        with self.assertRaisesRegex(ValueError, 'completion uncertain'):
            runner.collect(run, resumed, residency_sleep=lambda _: None)
        self.assertEqual(resumed.calls, [])
        # Fixture assertion only: operator confirmation must establish real termination separately.
        resumed.resident = runner.MODELS[0]
        runner.collect(run, resumed, confirm_server_idle=True, residency_sleep=lambda _: None)
        self.assertEqual(resumed.scored, 2)
        self.assertEqual(resumed.events[0], ('expired', runner.MODELS[0]))
        for path, value in before.items():self.assertEqual(path.read_bytes(), value)

    def test_scoped_collection_and_scoring_use_no_capacity_tokenizer(self):
        from evaluation.score_offline import analyze
        config = runner.freeze(self.config, self.snapshot, self.verification, False)
        run = runner.new_run(self.root / 'scoped-runs', config, ['internal_v2'], ['R02'])
        fake = FakeTransport();original = fake.request
        def actual_metadata(endpoint, body=None):
            if endpoint == '/api/version':return self.snapshot['ollama_version']
            if endpoint == '/api/tags':
                return {'models': [{'name': name, 'digest': item['digest']}
                                   for name, item in self.snapshot['models'].items()]}
            if endpoint == '/api/show':return self.snapshot['models'][body['model']]['show']
            return original(endpoint, body)
        fake.request = actual_metadata
        with patch('evaluation.capacity_evidence.CpuCounter', side_effect=AssertionError('Tokenizer not needed')):
            runner.collect(run, fake)
        self.assertEqual(fake.scored, 3)
        scores = analyze(run, self.root / 'analysis')
        self.assertEqual(sum(s['answer_correct'] is True for s in scores), 3)
        self.assertTrue(all(item['capacity_verified'] is False for item in config['verification']['models'].values()))
