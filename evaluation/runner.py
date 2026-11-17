"""Explicitly gated, sequential Ollama collection. No references are imported/read."""
import argparse
import base64
from contextlib import contextmanager
import fcntl
import json
import os
import platform
from pathlib import Path
import secrets
import tempfile
import time
import urllib.error
import urllib.request

from .execution_guard import execution_guard
from .common import BASE, DATASETS, digest, load_questions, read_json, sha256, utcnow, write_new

MODELS = ['qwen3:1.7b', 'qwen3:8b', 'gemma4:12b']
MAX_RESPONSE_BYTES = 2_000_000


class OllamaTransport:
    """Only constructed after a CLI authorization gate. No redirects/proxies."""
    def __init__(self, timeout=600):
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                raise ValueError('Redirects are forbidden')
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        self.timeout = timeout

    def request(self, endpoint, body=None):
        if endpoint not in {'/api/version', '/api/tags', '/api/show', '/api/chat', '/api/ps'}:
            raise ValueError('Endpoint not permitted')
        request = urllib.request.Request('http://127.0.0.1:11434'+endpoint,
            data=None if body is None else json.dumps(body).encode(),
            headers={'Content-Type':'application/json'})
        http_error = None
        try:
            response = self.opener.open(request, timeout=min(self.timeout, 5) if endpoint == '/api/ps' else self.timeout)
        except urllib.error.HTTPError as error:
            if endpoint != '/api/chat': raise
            http_error = error.code
            response = error
        with response:
            data = response.read(MAX_RESPONSE_BYTES+1)
        if http_error is not None:
            return {'_collector_error':'http_error', 'http_status':http_error,
                    'body_prefix_base64':base64.b64encode(data[:MAX_RESPONSE_BYTES]).decode('ascii'),
                    'body_truncated':len(data)>MAX_RESPONSE_BYTES}
        if len(data) > MAX_RESPONSE_BYTES:
            if endpoint != '/api/chat': raise ValueError('Response exceeds size limit')
            return {'_collector_error':'oversized_http_body',
                    'body_prefix_base64':base64.b64encode(data[:MAX_RESPONSE_BYTES]).decode('ascii'),
                    'body_truncated':True}
        def reject_constant(value):
            raise ValueError('Nonfinite JSON')
        try:
            return json.loads(data, parse_constant=reject_constant)
        except (ValueError, UnicodeDecodeError):
            if endpoint != '/api/chat': raise ValueError('Invalid metadata JSON') from None
            return {'_collector_error':'invalid_json',
                    'body_base64':base64.b64encode(data).decode('ascii')}


def inspect_models(transport, models):
    version = transport.request('/api/version')
    tags = transport.request('/api/tags')
    records = {}
    for name in models:
        matches = [m for m in tags.get('models',[]) if m.get('name') == name or m.get('model') == name]
        if len(matches) != 1 or not matches[0].get('digest'):
            raise ValueError('Model must already exist locally with an unambiguous digest: '+name)
        records[name] = {'digest':matches[0]['digest'], 'show':transport.request('/api/show',{'model':name})}
    return {'ollama_version':version, 'models':records}


def validate_config(config, frozen=False):
    if config.get('models') != MODELS: raise ValueError('Expected the three specified model tags')
    if config.get('stream') is not False: raise ValueError('Non-streaming protocol required')
    if not isinstance(config.get('system_message'),str): raise ValueError('System message missing')
    if config.get('repetitions') not in (1,2,3): raise ValueError('Use 1–3 repetitions')
    options = config.get('options',{})
    required = {'num_ctx','num_predict','temperature','seed','top_k','top_p','repeat_last_n','repeat_penalty'}
    if set(options) != required: raise ValueError('Explicit generation options required')
    if options['temperature'] != 0 or options['seed'] != 42: raise ValueError('Primary protocol uses temperature 0, seed 42')
    for key in ('num_ctx','num_predict','top_k','repeat_last_n'):
        if type(options[key]) is not int or options[key] <= 0: raise ValueError('Invalid option '+key)
    if options['num_predict'] >= options['num_ctx']: raise ValueError('Reserve context for prompt and template')
    if not 0 < options['top_p'] <= 1 or options['repeat_penalty'] <= 0: raise ValueError('Invalid sampling control')
    if not 1 <= config.get('timeout_seconds',0) <= 3600: raise ValueError('Invalid timeout')
    if frozen:
        if config.get('protocol_status') != 'frozen' or type(config.get('think')) is not bool:
            raise ValueError('Draft protocol: thinking compatibility must be verified before inference')
        if not config.get('model_snapshot') or not config.get('verification'):
            raise ValueError('Frozen model metadata and compatibility evidence required')
        validate_verification(config, config['model_snapshot'], config['verification'], config['think'])


def validate_verification(config, snapshot, verification, thinking):
    if not isinstance(verification.get('reviewer'),str) or not verification['reviewer'].strip():
        raise ValueError('Compatibility reviewer required')
    pathway = verification.get('thinking_verification', {'method': 'advertised-metadata-v1'})
    method = pathway.get('method')
    if method == 'empirical-thinking-v1':
        from .thinking_evidence import validate_index
        evidence_index = pathway.get('evidence', {})
        if pathway.get('evidence_sha256') != digest(evidence_index):
            raise ValueError('Thinking evidence index hash mismatch')
        validate_index(config, snapshot, evidence_index)
    elif method != 'advertised-metadata-v1':
        raise ValueError('Unknown thinking verification method')
    if type(thinking) is not bool:
        raise ValueError('Explicit boolean thinking mode required')
    scoped = 'workload_readiness' in verification
    if scoped:
        from .workload_readiness import validate_scope
        validate_scope(config, snapshot, verification, thinking)
    for name in config['models']:
        model = snapshot['models'][name]
        values = model['show'].get('thinking',{}).get('values',[])
        if method == 'advertised-metadata-v1' and not any(type(v) is bool and v == thinking for v in values):
            raise ValueError('Common thinking mode not advertised for '+name+'; do not guess compatibility')
        evidence = verification.get('models',{}).get(name,{})
        if evidence.get('digest') != model['digest']: raise ValueError('Verification digest mismatch')
        if not scoped and (evidence.get('capacity_verified') is not True or not evidence.get('evidence_note')):
            raise ValueError('Record approved development-stage context/output capacity verification')
        if scoped and not evidence.get('evidence_note'):
            raise ValueError('Workload readiness evidence note required')
        if method == 'empirical-thinking-v1' and not scoped:
            # Thinking probes cannot certify capacity. Require separately archived review evidence.
            from .thinking_evidence import evidence_root
            records = evidence.get('capacity_evidence', [])
            if not isinstance(records, list) or not records:
                raise ValueError('Separate capacity evidence files required')
            thinking_root = evidence_root(evidence_index).resolve()
            for record in records:
                path = Path(record['path'])
                path = path if path.is_absolute() else BASE.parent / path
                if path.resolve().is_relative_to(thinking_root):
                    raise ValueError('Thinking probe artifacts are not capacity evidence')
                if sha256(path.read_bytes()) != record.get('sha256'):
                    raise ValueError('Capacity evidence file hash mismatch')
                from .capacity_evidence import validate_report
                validate_report(read_json(path), dict(config, think=thinking), snapshot, verification['reviewer'])
        if evidence.get('verified_options') != config['options']:
            raise ValueError('Verification must cover the exact generation options')


def freeze(config, inspection, verification, thinking):
    validate_config(config)
    validate_verification(config, inspection, verification, thinking)
    result = dict(config, protocol_status='frozen', think=thinking,
                  model_snapshot=inspection, verification=verification, frozen_at=utcnow())
    validate_config(result, frozen=True)
    return result


def build_payload(config, model, question, warmup=False):
    # Construct a new allowlisted payload. Never serialize a dataset record wholesale.
    options = dict(config['options'])
    if warmup: options['num_predict'] = 1
    return {'model':model, 'messages':[{'role':'system','content':config['system_message']},
             {'role':'user','content':question['prompt']}], 'stream':False,
            'keep_alive':config['keep_alive'], 'think':config['think'], 'options':options}


def make_plan(config, suites, question_ids=None):
    validate_config(config)
    if not suites or len(suites) != len(set(suites)): raise ValueError('Choose distinct suites')
    from .workload_readiness import validate_selection
    validate_selection(config, suites, question_ids)
    questions = [q for suite in suites for q in load_questions(suite)]
    if question_ids:
        if len(set(question_ids)) != len(question_ids): raise ValueError('Duplicate requested ID')
        if set(question_ids) - {q['id'] for q in questions}: raise ValueError('Unknown requested question ID')
        questions = [q for q in questions if q['id'] in question_ids]
    if not questions: raise ValueError('Empty selection')
    rows = []
    for repeat in range(1,config['repetitions']+1):
        offset = (repeat-1) % len(config['models'])
        models = config['models'][offset:]+config['models'][:offset]
        ordered = sorted(questions, key=lambda q: (sha256(f"{config['question_order_seed']}:{repeat}:{q['id']}".encode()),q['id']))
        for model in models:
            for q in ordered:
                item = {'model':model,'question_id':q['id'],'repetition':repeat,
                        'prompt_sha256':q['prompt_sha256'], 'payload':build_payload(config,model,q)}
                item['request_id'] = digest(item)
                rows.append(item)
    return rows


def code_hashes():
    return {p.name:sha256(p.read_bytes()) for p in sorted(BASE.glob('*.py'))}


def new_run(root, config, suites, question_ids=None):
    """Offline creation only; unique directory, no reuse of historical outputs."""
    plan = make_plan(config,suites,question_ids)
    root = Path(root)
    root.mkdir(parents=True,exist_ok=True)
    run = root/(utcnow().replace(':','').replace('+','_')+'_'+secrets.token_hex(6))
    run.mkdir(exist_ok=False)
    (run/'requests').mkdir()
    (run/'warmups').mkdir()
    write_new(run/'manifest.json',{'created_at':utcnow(),'config':config,'config_sha256':digest(config),
              'suites':suites,'question_ids':question_ids,'plan_sha256':digest(plan),
              'dataset_manifests':{suite:read_json(DATASETS[suite]/'manifest.json') for suite in suites},
              'runtime':{'python':platform.python_version(),'platform':platform.platform(),
                         'machine':platform.machine()},
              'source_sha256':code_hashes(),'request_count':len(plan)})
    write_new(run/'plan.json',plan)
    return run


@contextmanager
def run_lock(run):
    # Advisory process lock releases automatically after interruption. Never truncate.
    with (run/'.lock').open('a') as file:
        try: fcntl.flock(file,fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: raise ValueError('Another collector owns this run') from None
        try: yield
        finally: fcntl.flock(file,fcntl.LOCK_UN)


def publish(path, value):
    """Publish a complete JSON via exclusive hard link. Partial temp files are not results."""
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix='.pending-', dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as file:
            json.dump(value,file,ensure_ascii=False,allow_nan=False)
            file.write('\n'); file.flush(); os.fsync(file.fileno())
        os.link(temporary,path)  # Fails if path exists; never replaces data.
        directory_fd = os.open(path.parent,os.O_RDONLY)
        try: os.fsync(directory_fd)
        finally: os.close(directory_fd)
    finally:
        os.unlink(temporary)


def response_status(raw):
    if not isinstance(raw,dict): return 'malformed_response'
    if raw.get('_collector_error'): return 'malformed_response'
    if raw.get('error'): return 'server_error'
    if raw.get('done') is not True: return 'incomplete_response'
    if raw.get('done_reason') not in {'stop', 'length'}: return 'unexpected_done_reason'
    message = raw.get('message')
    if (not isinstance(message,dict) or message.get('role', 'assistant') != 'assistant'
            or not isinstance(message.get('content'),str)):
        return 'empty_or_malformed_content'
    if message.get('tool_calls'): return 'unexpected_tool_calls'
    if len(message['content']) > 100_000: return 'oversized_content'
    if raw.get('done_reason') == 'length': return 'truncated'
    if not message['content'].strip():
        return 'empty_or_malformed_content'
    return 'completed'


def residency_status(transport, snapshot, allowed_models, record):
    """Save bounded metadata before validation; never unload models."""
    try:
        status = transport.request('/api/ps')
    except Exception as error:
        record({'at': utcnow(), 'error': {'type': type(error).__name__, 'message': str(error)}})
        raise
    record({'at': utcnow(), 'ollama_ps': status})
    if not isinstance(status, dict) or not isinstance(status.get('models'), list):
        raise ValueError('Malformed Ollama residency response')
    if len(status['models']) > 1:
        raise ValueError('Unexpected overlapping model residency')
    for model in status['models']:
        if not isinstance(model, dict):
            raise ValueError('Malformed resident model')
        name = model.get('name', model.get('model'))
        if name not in allowed_models or model.get('digest') != snapshot['models'][name]['digest']:
            raise ValueError('Unexpected foreign model or resident digest mismatch')
    return status


def await_empty_residency(transport, snapshot, allowed_models, record, timeout=120, sleep=time.sleep):
    deadline = time.monotonic() + timeout
    while True:
        status = residency_status(transport, snapshot, allowed_models, record)
        if not status['models']:
            return
        if time.monotonic() >= deadline:
            raise TimeoutError('Models did not expire naturally; stopped without unloading')
        sleep(min(1, max(0, deadline - time.monotonic())))


def collect(run, transport, retry_errors=False, confirm_server_idle=False,
            residency_timeout=120, residency_sleep=time.sleep):
    """Injected transport makes this testable without any network. CLI is separately gated."""
    import time
    run = Path(run)
    if run.is_symlink(): raise ValueError('Symlink run directories forbidden')
    # Coordinate different runs under one output root, without changing request order/residency.
    with execution_guard(), run_lock(run.parent), run_lock(run):
        pending = list(run.glob('requests/*/attempt-*')) + list(run.glob('warmups/*'))
        uncertain = any(not (p / 'complete.json').exists() or
                        read_json(p / 'complete.json').get('server_completion_unconfirmed', False)
                        for p in pending)
        if uncertain and not confirm_server_idle:
            raise ValueError('Prior request completion uncertain; inspect server separately and '
                             'resume only with --confirm-server-idle')
        manifest = read_json(run/'manifest.json'); config = manifest['config']
        validate_config(config,frozen=True)
        if manifest['config_sha256'] != digest(config) or manifest['source_sha256'] != code_hashes():
            raise ValueError('Configuration or collector source changed; start a new run')
        if manifest['dataset_manifests'] != {suite:read_json(DATASETS[suite]/'manifest.json') for suite in manifest['suites']}:
            raise ValueError('Dataset provenance changed; start a new run')
        plan = read_json(run/'plan.json')
        if digest(plan) != manifest['plan_sha256'] or plan != make_plan(config,manifest['suites'],manifest['question_ids']):
            raise ValueError('Dataset or plan changed; start a new run')
        snapshot = inspect_models(transport,config['models'])
        if snapshot != config['model_snapshot']: raise ValueError('Model/runtime metadata changed; refusing collection')
        session = run/('session-'+secrets.token_hex(8)+'.json')
        write_new(session,{'started_at':utcnow(),'model_snapshot':snapshot})
        warmed = set()
        active_block = None
        sample_count = 0
        def residency_record(phase):
            def save(value):
                nonlocal sample_count
                publish(run / f'{session.stem}-residency-{sample_count:06d}.json',
                        {'phase': phase, **value})
                sample_count += 1
            return save
        await_empty_residency(transport, snapshot, set(config['models']), residency_record('initial'),
                              residency_timeout, residency_sleep)
        for item in plan:
            request_dir = run/'requests'/item['request_id']
            request_dir.mkdir(exist_ok=True)
            attempts = sorted(request_dir.glob('attempt-*'))
            previous = []
            for attempt in attempts:
                if (attempt/'complete.json').exists():
                    record = read_json(attempt/'complete.json')
                    if record['request_sha256'] != digest(item): raise ValueError('Attempt request hash mismatch')
                    if sha256((attempt/'request.json').read_bytes()) != record['request_file_sha256']:
                        raise ValueError('Saved request changed')
                    if record.get('response_sha256') and sha256((attempt/'response.json').read_bytes()) != record['response_sha256']:
                        raise ValueError('Saved response changed')
                    previous.append(record)
            if previous and (previous[-1]['status'] != 'transport_error' or not retry_errors): continue
            # At most one explicit transport-error retry. Incomplete attempts remain visible.
            if sum(r['status']=='transport_error' for r in previous) >= 2: continue
            block = (item['repetition'],item['model'])
            if active_block != block:
                if active_block is not None:
                    await_empty_residency(transport, snapshot, {active_block[1]}, residency_record('transition'),
                                          residency_timeout, residency_sleep)
                active_block = block
            if block not in warmed:
                residency_status(transport, snapshot, set(), residency_record('before_warmup'))
                warm = run/'warmups'/secrets.token_hex(8);warm.mkdir()
                payload = build_payload(config,item['model'],{'prompt':'Reply with OK.'},warmup=True)
                write_new(warm/'request.json',payload)
                try:
                    raw_warm = transport.request('/api/chat',payload)
                except (OSError, ValueError) as error:
                    publish(warm/'complete.json', {'status': 'transport_error',
                        'error_type': type(error).__name__, 'server_completion_unconfirmed': True})
                    raise
                publish(warm/'response.json', raw_warm)
                warm_status = response_status(raw_warm)
                warm_safe = warm_status in {'completed', 'truncated'} and raw_warm.get('model') == item['model']
                publish(warm/'complete.json', {'status': warm_status,
                    'server_completion_unconfirmed': not warm_safe})
                if not warm_safe:
                    raise ValueError('Unsafe warm-up response; collection stopped')
                warmed.add(block)
            residency_status(transport, snapshot, {item['model']}, residency_record('before_scored'))
            attempt = request_dir/f'attempt-{len(attempts)+1:04d}'
            attempt.mkdir(exist_ok=False)
            write_new(attempt/'request.json',item)
            started = utcnow(); timer = time.perf_counter()
            try:
                raw = transport.request('/api/chat',item['payload'])
            except (OSError,ValueError) as error:
                publish(attempt/'complete.json',{'request_sha256':digest(item),
                    'request_file_sha256':sha256((attempt/'request.json').read_bytes()),
                    'status':'transport_error','error_type':type(error).__name__,
                    'server_completion_unconfirmed':True,
                    'started_at':started,'finished_at':utcnow(),'wall_time_s':time.perf_counter()-timer})
                raise
            # BaseException/KeyboardInterrupt is deliberately not caught: preserve incomplete attempt.
            publish(attempt/'response.json',raw)
            status = response_status(raw)
            safe = status in {'completed', 'truncated'} and raw.get('model') == item['model']
            if status in {'completed', 'truncated'} and not safe:
                status = 'unexpected_response_model'
            publish(attempt/'complete.json',{'request_sha256':digest(item),
                'request_file_sha256':sha256((attempt/'request.json').read_bytes()),
                'response_sha256':sha256((attempt/'response.json').read_bytes()),
                'status':status,'server_completion_unconfirmed':not safe,'started_at':started,'finished_at':utcnow(),
                'wall_time_s':time.perf_counter()-timer})
            if not safe:
                raise ValueError('Unsafe response: ' + status + '; collection stopped')
        if active_block is not None:
            await_empty_residency(transport, snapshot, {active_block[1]}, residency_record('final'),
                                  residency_timeout, residency_sleep)
    return run


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command',required=True)
    inspect = sub.add_parser('inspect',help='Metadata only; no inference; requires explicit permission')
    inspect.add_argument('--output',type=Path,required=True)
    inspect.add_argument('--allow-ollama',action='store_true')
    frozen = sub.add_parser('freeze',help='Offline freeze using previously verified evidence')
    frozen.add_argument('--config',type=Path,required=True)
    frozen.add_argument('--inspection',type=Path,required=True)
    frozen.add_argument('--verification',type=Path,required=True)
    frozen.add_argument('--think',choices=['true','false'],required=True)
    frozen.add_argument('--output',type=Path,required=True)
    for name in ('plan','run'):
        p = sub.add_parser(name)
        p.add_argument('--config',type=Path,required=True)
        p.add_argument('--suite',action='append',choices=list(DATASETS),required=True)
        p.add_argument('--question-id',action='append')
        if name == 'run':
            p.add_argument('--output-root',type=Path,default=BASE.parent/'evaluation_runs')
            p.add_argument('--allow-inference',action='store_true')
    resume = sub.add_parser('resume')
    resume.add_argument('--run-dir',type=Path,required=True)
    resume.add_argument('--allow-inference',action='store_true')
    resume.add_argument('--retry-errors',action='store_true')
    resume.add_argument('--confirm-server-idle',action='store_true',
        help='Operator confirms separate inspection established prior generation stopped')
    args = parser.parse_args(argv)
    try:
        if args.command == 'inspect':
            if not args.allow_ollama: raise ValueError('Requires --allow-ollama; no request sent')
            if args.output.exists(): raise ValueError('Inspection output already exists')
            write_new(args.output,inspect_models(OllamaTransport(),MODELS))
        elif args.command == 'freeze':
            write_new(args.output,freeze(read_json(args.config),read_json(args.inspection),
                      read_json(args.verification),args.think=='true'))
        elif args.command == 'plan':
            plan = make_plan(read_json(args.config),args.suite,args.question_id)
            print(json.dumps({'requests':len(plan),'plan_sha256':digest(plan),'inference':'not performed'}))
        elif args.command == 'run':
            if not args.allow_inference: raise ValueError('Requires --allow-inference; no request sent')
            config = read_json(args.config); validate_config(config,frozen=True)
            run = new_run(args.output_root,config,args.suite,args.question_id)
            print('Run directory:',run,flush=True)
            collect(run,OllamaTransport(config['timeout_seconds']))
        else:
            if not args.allow_inference: raise ValueError('Requires --allow-inference; no request sent')
            config = read_json(args.run_dir/'manifest.json')['config']
            validate_config(config,frozen=True)
            collect(args.run_dir,OllamaTransport(config['timeout_seconds']),args.retry_errors,
                    args.confirm_server_idle)
    except (ValueError,KeyError,OSError) as error:
        parser.exit(1,f'Evaluation stopped: {error}\n')


if __name__ == '__main__': main()
