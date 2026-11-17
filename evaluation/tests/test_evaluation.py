"""Offline only: network methods are blocked for the entire test module."""
import ast
from copy import deepcopy
import json
import io
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch
import urllib.request

from evaluation import common, runner, scoring, validate
from evaluation.score_offline import analyze, csv_safe

NETWORK_PATCHES=[]


def setUpModule():
    for target in ('socket.create_connection','socket.socket.connect','urllib.request.OpenerDirector.open'):
        p=patch(target,side_effect=AssertionError('Network forbidden in offline tests'))
        p.start();NETWORK_PATCHES.append(p)


def tearDownModule():
    for p in reversed(NETWORK_PATCHES):p.stop()


def draft(): return common.read_json(common.BASE/'configs/quality_v2.draft.json')


def snapshot():
    return {'ollama_version':{'version':'offline-fixture'},'models':{
        name:{'digest':'fixture-'+name,'show':{'thinking':{'values':[True,False]},'template':'fixture'}}
        for name in runner.MODELS}}


def frozen():
    config=draft();config['repetitions']=1
    metadata=snapshot()
    evidence={'reviewer':'offline test only','models':{name:{'digest':metadata['models'][name]['digest'],
        'capacity_verified':True,'evidence_note':'synthetic fixture; not real compatibility evidence',
        'verified_options':config['options']} for name in config['models']}}
    return runner.freeze(config,metadata,evidence,True)


class FakeTransport:
    def __init__(self, crash_at=None, raw=None, transport_error=False):
        self.calls=[];self.scored=0;self.crash_at=crash_at;self.raw=raw;self.transport_error=transport_error
    def request(self,endpoint,body=None):
        self.calls.append((endpoint,body))
        data=snapshot()
        if endpoint=='/api/ps':return {'models':[]}
        if endpoint=='/api/version':return data['ollama_version']
        if endpoint=='/api/tags':return {'models':[{'name':n,'digest':m['digest']} for n,m in data['models'].items()]}
        if endpoint=='/api/show':return data['models'][body['model']]['show']
        if endpoint!='/api/chat':raise AssertionError(endpoint)
        if body['options']['num_predict']!=1:
            self.scored+=1
            if self.scored==self.crash_at:raise KeyboardInterrupt()
            if self.transport_error:raise OSError('synthetic failure')
            if self.raw is not None:return self.raw
        return {'model':body['model'],'done':True,'done_reason':'stop','message':{'content':'90'},'eval_count':1,'total_duration':1000}


class DatasetTests(unittest.TestCase):
    def test_all_datasets_provenance_and_historical_integrity(self):
        self.assertEqual(validate.validate(),{'internal_v2':20,'gsm8k_50_v1':50,'pilot_v1':5})

    def test_every_question_has_aligned_reference_and_scoring_rules(self):
        for suite,directory in common.DATASETS.items():
            rows=common.load_questions(suite);refs=common.read_jsonl(directory/'references.jsonl')
            for q,r in zip(rows,refs):
                self.assertEqual(q['id'],r['id'])
                self.assertTrue(r['acceptance_criteria']);self.assertTrue(r['scoring_rules'])
                self.assertEqual(set(q),common.PUBLIC_FIELDS)

    def test_runner_public_loader_never_reads_references(self):
        original=Path.open
        def guarded(path,*args,**kwargs):
            self.assertNotIn(path.name,{'references.jsonl','upstream_test.jsonl'})
            return original(path,*args,**kwargs)
        with patch.object(Path,'open',guarded):
            plan=runner.make_plan(draft(),['internal_v2','gsm8k_50_v1'])
        self.assertEqual(len(plan),630)
        self.assertTrue(all(set(x['payload'])=={'model','messages','stream','keep_alive','think','options'} for x in plan))

    def test_loader_rejects_reference_field_even_with_updated_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);q=common.load_questions('internal_v2')[0];q['answer']='SECRET'
            (p/'questions.jsonl').write_text(json.dumps(q)+'\n')
            common.write_new(p/'manifest.json',{'count':1,'questions_sha256':common.sha256((p/'questions.jsonl').read_bytes())})
            with patch.dict(common.DATASETS,{'bad':p}):
                with self.assertRaises(ValueError):common.load_questions('bad')

    def test_loader_rejects_checksum_and_duplicate_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);q=common.load_questions('internal_v2')[0]
            (p/'questions.jsonl').write_text(json.dumps(q)+'\n'+json.dumps(q)+'\n')
            common.write_new(p/'manifest.json',{'count':2,'questions_sha256':'wrong'})
            with patch.dict(common.DATASETS,{'bad':p}):
                with self.assertRaisesRegex(ValueError,'checksum'):common.load_questions('bad')
                (p/'manifest.json').write_text(json.dumps({'count':2,'questions_sha256':common.sha256((p/'questions.jsonl').read_bytes())}))
                with self.assertRaisesRegex(ValueError,'duplicate'):common.load_questions('bad')


class ScoringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.refs={r['id']:r for suite,d in common.DATASETS.items() for r in common.read_jsonl(d/'references.jsonl')}

    def test_all_objective_reference_answers_pass(self):
        for ref in self.refs.values():
            if ref['kind']=='exact':text=ref['expected']
            elif ref['kind']=='json':text=json.dumps(ref['expected'])
            elif ref['kind']=='json_alternatives':text=json.dumps(ref['expected'][0])
            elif ref['kind']=='numeric':text='FINAL_ANSWER: '+ref['expected']
            else:continue
            with self.subTest(id=ref['id']):self.assertTrue(scoring.score(text,ref)['answer_correct'])

    def test_reasoning_oracle_not_keyword_presence(self):
        for text in ['A B C 18','{"A":1,"B":1,"C":1,"total":18}',
                     '{"A":0,"B":3,"C":0,"total":19}']:
            self.assertFalse(scoring.score(text,self.refs['R01'])['answer_correct'])

    def test_both_topological_orders_pass(self):
        for answer in self.refs['R04']['expected']:
            self.assertTrue(scoring.score(json.dumps(answer),self.refs['R04'])['answer_correct'])
        self.assertFalse(scoring.score('["B","A","C","D"]',self.refs['R04'])['answer_correct'])

    def test_exact_format_preserves_blank_lines_and_spaces(self):
        ref=self.refs['I04'];expected=ref['expected']
        self.assertTrue(scoring.score(expected+'\n',ref)['answer_correct'])
        self.assertTrue(scoring.score(expected.replace('\n','\r\n'),ref)['answer_correct'])
        for bad in [expected+'\n\n',' '+expected,expected.replace('\n','\n\n'),expected+' extra']:
            self.assertFalse(scoring.score(bad,ref)['format_compliant'])

    def test_json_duplicate_keys_nonfinite_boolean_float_extra_fields(self):
        for bad in ['{"count":4,"count":4,"sum":16,"max":10}',
                    '{"count":NaN,"sum":16,"max":10}',
                    '{"count":true,"sum":16,"max":10}',
                    '{"count":4.0,"sum":16,"max":10}',
                    '{"count":4,"sum":16,"max":10,"extra":0}',
                    '```json\n{"count":4,"sum":16,"max":10}\n```',
                    '[4,16,10]']:
            with self.subTest(text=bad):self.assertFalse(scoring.score(bad,self.refs['I01'])['format_compliant'])

    def test_numeric_normalization_and_failures(self):
        ref={'kind':'numeric','expected':'1200'}
        for good in ['FINAL_ANSWER: 1200','Explanation.\nFINAL_ANSWER: +1,200.00\n']:
            self.assertTrue(scoring.score(good,ref)['answer_correct'])
        for bad in ['1200','FINAL_ANSWER: 12,00','FINAL_ANSWER: 1200 units',
                    'FINAL_ANSWER: 1200\nMore text','FINAL_ANSWER: 1200\nFINAL_ANSWER: 1200',
                    'FINAL_ANSWER: NaN','FINAL_ANSWER: 1.2e3','FINAL_ANSWER: 2400/2',
                    'FINAL_ANSWER: ١٢٠٠',
                    'FINAL_ANSWER: __import__("os").system("false")']:
            self.assertFalse(scoring.score(bad,ref)['answer_correct'])

    def test_wrong_numeric_format_valid_but_answer_wrong(self):
        result=scoring.score('FINAL_ANSWER: 8',{'kind':'numeric','expected':'9'})
        self.assertTrue(result['format_compliant']);self.assertFalse(result['answer_correct'])

    def test_semantic_checks_require_manual_review(self):
        result=scoring.score('- False statement.\n- Another false statement.',self.refs['K01'])
        self.assertTrue(result['format_compliant']);self.assertIsNone(result['answer_correct'])
        self.assertTrue(result['manual_review_required'])

    def test_summary_format_only(self):
        result=scoring.score('First sentence. Second sentence.',self.refs['S01'])
        self.assertTrue(result['format_compliant']);self.assertIsNone(result['answer_correct'])
        self.assertFalse(scoring.score('Only one sentence.',self.refs['S01'])['format_compliant'])

    def test_valid_structure_is_not_functional_correctness(self):
        result=scoring.score('def stable_unique(items):\n    return None',self.refs['C01'])
        self.assertTrue(result['static_checks_pass']);self.assertIsNone(result['answer_correct'])
        self.assertEqual(result['runtime_correctness'],'not evaluated')

    def test_generated_function_and_top_level_are_never_executed(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker=Path(tmp)/'executed'
            for source in [f"open({str(marker)!r}, 'w').write('bad')\ndef stable_unique(items):\n    return []",
                           f"def stable_unique(items):\n    open({str(marker)!r}, 'w').write('bad')\n    return []",
                           'def stable_unique(items=1/0):\n    return []',
                           '@nonexistent\ndef stable_unique(items):\n    return []']:
                scoring.score(source,self.refs['C01'])
                self.assertFalse(marker.exists())

    def test_bad_code_structure(self):
        for text in ['def broken(:','\x00','import os\ndef stable_unique(items):\n    return []',
                     'def stable_unique(other):\n    return []','async def stable_unique(items):\n    return []',
                     'def stable_unique(items: str):\n    return []',
                     'def stable_unique(items):\n    return []\nprint(1)']:
            self.assertFalse(scoring.score(text,self.refs['C01'])['static_checks_pass'])

    def test_oversized_and_malformed_outputs(self):
        with patch.object(scoring.ast,'parse') as parse:
            for text in ['x'*(common.MAX_TEXT+1),None,{},'',123]:
                result=scoring.score(text,self.refs['C01'])
                self.assertEqual(result['status'],'invalid_output')
            parse.assert_not_called()
        with patch.object(scoring.ast,'parse',side_effect=RecursionError):
            self.assertFalse(scoring.score('def stable_unique(items): pass',self.refs['C01'])['static_checks_pass'])

    def test_noncompleted_output_never_gets_success(self):
        for status in ['truncated','missing','transport_error','interrupted']:
            self.assertFalse(scoring.score('90',self.refs['R02'],status)['answer_correct'])

    def test_scorer_contains_no_execution_primitives(self):
        tree=ast.parse(Path(scoring.__file__).read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.Call):
                name=getattr(node.func,'id',getattr(node.func,'attr',''))
                self.assertNotIn(name,{'exec','eval','compile','Popen','run','system','check_call','check_output'})


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)

    def new(self,ids=None):return runner.new_run(self.root,frozen(),['internal_v2'],ids or ['R02'])

    def test_draft_and_missing_permissions_never_connect(self):
        with patch.object(runner,'OllamaTransport') as network:
            for args in [ ['run','--config',str(common.BASE/'configs/quality_v2.draft.json'),'--suite','internal_v2'],
                          ['run','--config',str(common.BASE/'configs/quality_v2.draft.json'),'--suite','internal_v2','--allow-inference'],
                          ['inspect','--output',str(self.root/'inspection.json')],
                          ['resume','--run-dir',str(self.root)]]:
                with patch('sys.stderr'),self.assertRaises(SystemExit):runner.main(args)
            network.assert_not_called()

    def test_freeze_requires_supported_mode_exact_options_and_capacity(self):
        config=frozen()
        for change in ['mode','digest','capacity','options']:
            snap=deepcopy(config['model_snapshot']);ver=deepcopy(config['verification']);name=runner.MODELS[0]
            if change=='mode':snap['models'][name]['show']['thinking']['values']=[False]
            if change=='digest':ver['models'][name]['digest']='different'
            if change=='capacity':ver['models'][name]['capacity_verified']=False
            if change=='options':ver['models'][name]['verified_options']['num_predict']=128
            with self.assertRaises(ValueError):runner.freeze(draft(),snap,ver,True)

    def test_plan_is_deterministic_and_counterbalanced(self):
        config=draft();a=runner.make_plan(config,['internal_v2'],['R01','R02'])
        self.assertEqual(a,runner.make_plan(config,['internal_v2'],['R01','R02']))
        self.assertEqual(len(a),18)
        self.assertEqual([a[i]['model'] for i in [0,6,12]],runner.MODELS)
        for rep in (1,2,3):
            orders=[[r['question_id'] for r in a if r['model']==m and r['repetition']==rep] for m in runner.MODELS]
            self.assertEqual(orders[0],orders[1]);self.assertEqual(orders[1],orders[2])

    def test_bad_selection_rejected(self):
        for ids in [['MISSING'],['R01','R01']]:
            with self.assertRaises(ValueError):runner.make_plan(draft(),['internal_v2'],ids)

    def test_payload_does_not_serialize_reference_fields(self):
        q={'prompt':'public text','expected':'SECRET','reference':'SECRET'}
        payload=runner.build_payload(frozen(),runner.MODELS[0],q)
        self.assertNotIn('SECRET',json.dumps(payload))

    def test_unique_directories_and_exclusive_publish(self):
        a=self.new();b=self.new();self.assertNotEqual(a,b)
        p=self.root/'artifact.json';runner.publish(p,{'old':1});before=p.read_bytes()
        with self.assertRaises(FileExistsError):runner.publish(p,{'new':2})
        self.assertEqual(before,p.read_bytes())
        with self.assertRaises(FileExistsError):common.write_new(p,{'new':3})

    def test_successful_run_and_resume_skip_completed(self):
        run=self.new();fake=FakeTransport();runner.collect(run,fake)
        self.assertEqual(fake.scored,3)
        before={str(p):p.read_bytes() for p in run.rglob('*.json')}
        second=FakeTransport();runner.collect(run,second)
        self.assertEqual(second.scored,0)
        for path,data in before.items():self.assertEqual(Path(path).read_bytes(),data)
        self.assertEqual(len(list(run.glob('requests/*/attempt-*/response.json'))),3)

    def test_interruption_resume_preserves_attempts(self):
        run=self.new();fake=FakeTransport(crash_at=2)
        with self.assertRaises(KeyboardInterrupt):runner.collect(run,fake)
        old={str(p):p.read_bytes() for p in run.glob('requests/*/attempt-*/*.json')}
        resumed=FakeTransport()
        with self.assertRaisesRegex(ValueError,'completion uncertain'):
            runner.collect(run,resumed)
        self.assertEqual(resumed.calls,[])
        runner.collect(run,resumed,confirm_server_idle=True)
        self.assertEqual(resumed.scored,2)
        for path,data in old.items():self.assertEqual(Path(path).read_bytes(),data)
        self.assertEqual(len(list(run.glob('requests/*/attempt-*'))),4)

    def test_transport_error_requires_explicit_bounded_retry(self):
        run=self.new()
        with self.assertRaises(OSError):runner.collect(run,FakeTransport(transport_error=True))
        skipped=FakeTransport()
        with self.assertRaisesRegex(ValueError,'completion uncertain'):runner.collect(run,skipped)
        self.assertEqual(skipped.calls,[])
        retry=FakeTransport(transport_error=True)
        with self.assertRaises(OSError):
            runner.collect(run,retry,retry_errors=True,confirm_server_idle=True)
        self.assertEqual(retry.scored,1)
        # Each failed request gets at most one explicitly requested retry.
        last=FakeTransport();runner.collect(run,last,retry_errors=True,confirm_server_idle=True)
        self.assertEqual(last.scored,2)

    def test_changed_model_refuses_chat(self):
        run=self.new();fake=FakeTransport();original=fake.request
        def changed(endpoint,body=None):
            response=original(endpoint,body)
            if endpoint=='/api/version':return {'version':'changed'}
            return response
        fake.request=changed
        with self.assertRaises(ValueError):runner.collect(run,fake)
        self.assertEqual(fake.scored,0)

    def test_modified_plan_config_and_responses_rejected(self):
        run=self.new();plan=common.read_json(run/'plan.json');plan[0]['payload']['messages'][0]['content']='changed'
        (run/'plan.json').write_text(json.dumps(plan))
        with self.assertRaises(ValueError):runner.collect(run,FakeTransport())
        run=self.new();runner.collect(run,FakeTransport())
        next(run.glob('requests/*/attempt-*/response.json')).write_text('{}')
        with self.assertRaises(ValueError):runner.collect(run,FakeTransport())
        with self.assertRaises(ValueError):analyze(run,self.root/'analysis')

    def test_modified_configuration_and_collector_source_rejected(self):
        run=self.new()
        manifest=common.read_json(run/'manifest.json')
        manifest['config']['system_message']='changed'
        (run/'manifest.json').write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError,'Configuration'):runner.collect(run,FakeTransport())
        with self.assertRaisesRegex(ValueError,'Configuration'):analyze(run,self.root/'analysis')
        run=self.new()
        with patch.object(runner,'code_hashes',return_value={}):
            with self.assertRaisesRegex(ValueError,'source changed'):runner.collect(run,FakeTransport())

    def test_dataset_provenance_is_bound_to_run(self):
        run=self.new()
        manifest=common.read_json(run/'manifest.json')
        self.assertEqual(manifest['dataset_manifests']['internal_v2']['count'],20)
        manifest['dataset_manifests']['internal_v2']['version']='changed'
        (run/'manifest.json').write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError,'provenance changed'):runner.collect(run,FakeTransport())
        with self.assertRaisesRegex(ValueError,'provenance changed'):analyze(run,self.root/'analysis')

    def test_missing_saved_response_is_integrity_failure(self):
        run=self.new();runner.collect(run,FakeTransport())
        # Remove only a synthetic response in this test's temporary directory.
        next(run.glob('requests/*/attempt-*/response.json')).unlink()
        with self.assertRaises(FileNotFoundError):analyze(run,self.root/'analysis')

    def test_transport_keeps_malformed_http_bodies_without_network(self):
        import base64
        for data in [b'not JSON',b'\xff',b'{"value":NaN}']:
            transport=runner.OllamaTransport()
            with patch.object(transport.opener,'open',return_value=io.BytesIO(data)):
                result=transport.request('/api/chat',{'model':'fixture'})
            self.assertEqual(result['_collector_error'],'invalid_json')
            self.assertEqual(base64.b64decode(result['body_base64']),data)
            self.assertEqual(runner.response_status(result),'malformed_response')

    def test_transport_limits_and_http_error_body(self):
        import base64
        import urllib.error
        transport=runner.OllamaTransport()
        with patch.object(runner,'MAX_RESPONSE_BYTES',8), patch.object(transport.opener,'open',return_value=io.BytesIO(b'x'*9)):
            result=transport.request('/api/chat',{})
        self.assertTrue(result['body_truncated'])
        self.assertEqual(base64.b64decode(result['body_prefix_base64']),b'x'*8)
        error=urllib.error.HTTPError('http://fixture',503,'fixture',{},io.BytesIO(b'unavailable'))
        with patch.object(transport.opener,'open',side_effect=error):
            result=transport.request('/api/chat',{})
        self.assertEqual(result['http_status'],503)
        self.assertEqual(base64.b64decode(result['body_prefix_base64']),b'unavailable')

    def test_invalid_metadata_stops_and_unknown_endpoint_is_blocked(self):
        transport=runner.OllamaTransport()
        with patch.object(transport.opener,'open',return_value=io.BytesIO(b'bad JSON')):
            with self.assertRaisesRegex(ValueError,'metadata'):transport.request('/api/version')
        with self.assertRaisesRegex(ValueError,'Endpoint'):transport.request('/api/pull',{})

    def test_lock_prevents_concurrent_collectors(self):
        run=self.new()
        with runner.run_lock(run):
            with self.assertRaises(ValueError):runner.collect(run,FakeTransport())

    def test_unsafe_responses_saved_and_stop_immediately(self):
        for raw,status in [([], 'malformed_response'),({'done':False},'incomplete_response'),
                           ({'done':True,'done_reason':'length'},'empty_or_malformed_content'),
                           ({'done':True,'done_reason':'stop','message':{'content':''}},'empty_or_malformed_content'),
                           ({'error':'CUDA out of memory'},'server_error'),
                           ({'_collector_error':'invalid_json'},'malformed_response'),
                           ({'_collector_error':'http_error','http_status':500},'malformed_response'),
                           ({'model':'wrong','done':True,'done_reason':'stop',
                             'message':{'content':'90'}},'unexpected_response_model'),
                           ({'done':True,'done_reason':'other'},'unexpected_done_reason')]:
            with self.subTest(status=status):
                run=self.new();fake=FakeTransport(raw=raw)
                with self.assertRaises(ValueError):runner.collect(run,fake)
                self.assertEqual(fake.scored,1)
                records=[common.read_json(p) for p in run.glob('requests/*/attempt-*/complete.json')]
                self.assertEqual(len(records),1)
                self.assertEqual(records[0]['status'],status)
                self.assertEqual(common.read_json(next(run.glob('requests/*/attempt-*/response.json'))),raw)
                resumed=FakeTransport()
                with self.assertRaises(ValueError):runner.collect(run,resumed,retry_errors=True)
                self.assertEqual(resumed.calls,[])

    def test_confirmed_truncation_is_saved_without_retry(self):
        class Truncated(FakeTransport):
            def request(self,endpoint,body=None):
                raw=super().request(endpoint,body)
                if endpoint=='/api/chat':raw['done_reason']='length'
                return raw
        run=self.new();fake=Truncated();runner.collect(run,fake)
        self.assertEqual(fake.scored,3)
        for p in run.glob('requests/*/attempt-*/complete.json'):
            self.assertEqual(common.read_json(p)['status'],'truncated')
        resumed=FakeTransport();runner.collect(run,resumed);self.assertEqual(resumed.scored,0)

    def test_warmup_infrastructure_failure_stops_before_scored_requests(self):
        for failure in (TimeoutError('fixture'), {'_collector_error':'invalid_json'},
                        {'error':'GPU OOM'}, {'model':'other','done':True,'done_reason':'stop',
                                             'message':{'content':'OK'}}):
            run=self.new();fake=FakeTransport();original=fake.request
            def request(endpoint,body=None):
                if endpoint=='/api/chat':
                    fake.calls.append((endpoint,body))
                    if isinstance(failure,Exception):raise failure
                    return failure
                return original(endpoint,body)
            fake.request=request
            with self.assertRaises((ValueError,TimeoutError)):runner.collect(run,fake)
            self.assertEqual(sum(e=='/api/chat' for e,_ in fake.calls),1)
            self.assertFalse(list(run.glob('requests/*/attempt-*')))
            before={p:p.read_bytes() for p in run.glob('warmups/*/*')}
            with self.assertRaisesRegex(ValueError,'completion uncertain'):
                runner.collect(run,FakeTransport())
            for p,content in before.items():self.assertEqual(p.read_bytes(),content)

    def test_shared_output_root_lock_blocks_different_runs(self):
        a=self.new();b=self.new();fake=FakeTransport()
        with runner.run_lock(a.parent):
            with self.assertRaises(ValueError):runner.collect(b,fake)
        self.assertEqual(fake.calls,[])

    def test_offline_score_export_blinding_and_preservation(self):
        run=self.new(['K01','R02']);runner.collect(run,FakeTransport())
        output=self.root/'analysis';scores=analyze(run,output)
        self.assertEqual(len(scores),6)
        self.assertEqual(sum(s['answer_correct'] is True for s in scores),3)
        review=(output/'manual_review.csv').read_text()
        import csv
        with (output/'manual_review.csv').open() as file:
            self.assertEqual(len(list(csv.DictReader(file))),6)
        for model in runner.MODELS:self.assertNotIn(model,review)
        before=(output/'scores.json').read_bytes()
        with self.assertRaises(FileExistsError):analyze(run,output)
        self.assertEqual((output/'scores.json').read_bytes(),before)

    def test_missing_attempts_reported_not_dropped(self):
        run=self.new();scores=analyze(run,self.root/'missing')
        self.assertEqual(len(scores),3)
        self.assertTrue(all(s['status']=='missing' and s['answer_correct'] is False for s in scores))

    def test_csv_formula_escape_does_not_change_raw_results(self):
        for text in ['=1+1',' +cmd','-1','@SUM(A1)']:
            self.assertTrue(csv_safe(text).startswith("'"))
        self.assertEqual(csv_safe('ordinary'),'ordinary')


if __name__=='__main__':unittest.main()
