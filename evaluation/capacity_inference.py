"""Separately gated synthetic capacity collection; never runs the benchmark or freezes."""
import argparse
import multiprocessing
from pathlib import Path
import secrets
import threading
import time

from .common import BASE, digest, read_json, utcnow, write_new
from .runner import inspect_models, validate_config, run_lock
from .dev_inference import DevTransport, wait_empty
from .execution_guard import execution_guard, block, mark_pending, complete_pending
from .token_accounting import CpuCounter, PHASE2
from .capacity_protocol import PROFILE, VERSION, prepare, check_response, require, separate_findings
from .capacity_monitor import CapacityMonitor, telemetry


def _request_child(connection, transport, request):
    try:
        if isinstance(transport, dict):
            transport = DevTransport(transport['timeout'])
        connection.send({'raw': transport.request('/api/chat', request)})
    except BaseException as error:
        connection.send({'error': {'type': type(error).__name__, 'message': str(error)}})
    finally:
        connection.close()


def bounded_request(transport, request, timeout, monitor, on_sent=lambda: None):
    """A parent-side monotonic deadline is independent of HTTP socket/monitor timeouts.

    Killing the local HTTP worker is not server cancellation. Caller must latch uncertainty.
    """
    context = multiprocessing.get_context('spawn')
    receiver, sender = context.Pipe(duplex=False)
    transport_spec = {'timeout': transport.timeout} if type(transport) is DevTransport else transport
    worker = context.Process(target=_request_child, args=(sender, transport_spec, request), daemon=True)
    deadline_expired = threading.Event()
    watchdog_stop = threading.Event()
    started = time.monotonic()
    def watch():
        while not watchdog_stop.wait(0.02):
            expired = time.monotonic() - started >= timeout
            if expired or monitor.failed.is_set():
                if expired:
                    deadline_expired.set()
                if worker.pid is not None and worker.is_alive():
                    worker.kill()
                return
    watchdog = threading.Thread(target=watch, daemon=True)
    try:
        on_sent()  # Conservatively mark pending before process launch.
        if time.monotonic() - started >= timeout:
            raise TimeoutError('Request preparation exceeded deadline before worker launch')
        worker.start()
        watchdog.start()
        sender.close()
        while True:
            if deadline_expired.is_set() or time.monotonic() - started >= timeout:
                raise TimeoutError('Independent request wall-clock deadline exceeded; server completion unknown')
            if monitor.failed.is_set():
                raise RuntimeError('Unsafe activity/monitoring failure during request')
            if receiver.poll(min(0.05, max(0, timeout - (time.monotonic() - started)))):
                try:
                    result = receiver.recv()
                except EOFError:
                    raise RuntimeError('HTTP worker exited without response; completion unknown') from None
                elapsed = time.monotonic() - started
                if elapsed >= timeout:
                    raise TimeoutError('Response arrived after wall-clock deadline')
                if 'error' in result:
                    raise RuntimeError('HTTP worker failure: ' + str(result['error']))
                return result['raw'], elapsed
    finally:
        watchdog_stop.set()
        if watchdog.ident is not None:
            watchdog.join(timeout=0.1)
        receiver.close()
        sender.close()
        if worker.pid is not None:
            if worker.is_alive():
                worker.terminate()
            worker.join(timeout=0.2)
            if worker.is_alive():
                worker.kill()
                worker.join(timeout=0.2)


def validate_plan(plan, counter):
    validate_config(plan['config'])
    require(plan.get('version') == VERSION and plan.get('profile') == PROFILE,
            'unsupported capacity plan/profile')
    require(plan.get('config_sha256') == digest(plan['config']) and
            plan.get('snapshot_sha256') == digest(plan['snapshot']), 'plan configuration/metadata hash mismatch')
    # Regenerate content and recount tokens. Never accept a user-edited numeric claim alone.
    require(plan == prepare(plan['config'], plan['snapshot'], counter), 'plan/tokenization mismatch')


def run(plan, root, transport, counter, gpu=telemetry, coordination_root=None,
        request_call=bounded_request):
    validate_plan(plan, counter)  # No service access before exact offline prerequisites pass.
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    with execution_guard(coordination_root) as coordination, run_lock(root):
        directory = root / ('capacity-' + utcnow().replace(':', '') + '-' + secrets.token_hex(6))
        directory.mkdir(exist_ok=False)
        from .capacity_evidence import source_hashes
        write_new(directory / 'manifest.json', {'created_at': utcnow(), 'plan': plan,
            'plan_sha256': digest(plan), 'source_sha256': source_hashes(), 'maximum_requests': 9,
            'capacity_verified': False, 'resume_supported': False})
        pending = False
        try:
            initial = transport.request('/api/ps')
            write_new(directory / 'initial_ps.json', initial)
            require(initial == {'models': []}, 'initial models resident; no unloading permitted')
            actual = inspect_models(transport, plan['config']['models'])
            write_new(directory / 'metadata.json', actual)
            require(actual == plan['snapshot'], 'runtime/model metadata or digest mismatch')
            for probe in plan['probes']:
                model, case = probe['model'], probe['case']
                attempt = directory / (model.replace(':', '_') + '-' + case)
                attempt.mkdir()
                (attempt / 'monitoring').mkdir()
                write_new(attempt / 'request.json', probe['request'])
                write_new(attempt / 'tokenization.json', probe['tokenization'])
                monitor = CapacityMonitor(transport, gpu, attempt / 'monitoring', model,
                                          actual['models'][model]['digest'])
                started = utcnow()
                raw, sent, wall = None, False, None
                sent_monotonic = None
                def sent_callback():
                    nonlocal pending, sent, sent_monotonic
                    sent_monotonic = time.monotonic()
                    mark_pending(coordination, directory, attempt)
                    pending = sent = True
                    write_new(attempt / 'sent.json', {'at': utcnow(), 'monotonic_s': sent_monotonic, 'completion_unconfirmed': True})
                try:
                    monitor.start()
                    raw, wall = request_call(transport, probe['request'],
                        plan['config']['timeout_seconds'], monitor, sent_callback)
                    write_new(attempt / 'response.json', raw)
                    # Save arrival timing even if later validation/final monitoring fails.
                    write_new(attempt / 'timing.json', {'started_at': started, 'received_at': utcnow(),
                        'request_wall_time_s': wall, 'sent_monotonic_s': sent_monotonic,
                        'received_monotonic_s': time.monotonic(),
                        'deadline_s': plan['config']['timeout_seconds']})
                    require(0 <= wall < plan['config']['timeout_seconds'], 'request deadline exceeded')
                    findings = check_response(probe, raw)
                    monitor.finish()
                    write_new(attempt / 'result.json', findings)
                    complete_pending(coordination, directory, attempt)
                    pending = False
                except BaseException as error:
                    # A validator failure can have a confirmed response, but no further probes
                    # are issued. Infrastructure/monitor failures conservatively leave a latch.
                    confirmed = (isinstance(raw, dict) and raw.get('model') == model and
                                 raw.get('done') is True and raw.get('done_reason') in ('stop', 'length')
                                 and not raw.get('error') and not raw.get('_collector_error')
                                 and isinstance(raw.get('message'), dict)
                                 and raw['message'].get('role') == 'assistant'
                                 and isinstance(raw['message'].get('content'), str)
                                 and not raw['message'].get('tool_calls'))
                    try:
                        monitor.finish(resident=False)
                    except Exception:
                        confirmed = False
                    pending = sent and not confirmed
                    if pending:
                        block(coordination, directory, str(error))
                    write_new(attempt / 'error.json', {'at': utcnow(), 'type': type(error).__name__,
                        'message': str(error), 'response_received': raw is not None,
                        'server_completion_unconfirmed': pending, 'request_sent': sent,
                        'thinking_compatibility': 'not_approved', 'capacity': 'insufficient',
                        'elapsed_since_send_s': None if sent_monotonic is None else time.monotonic() - sent_monotonic,
                        'findings': separate_findings(probe, raw)})
                    if sent and confirmed:
                        complete_pending(coordination, directory, attempt)
                    raise
                if case == 'IO':
                    expired = wait_empty(transport, model=model)
                    write_new(directory / (model.replace(':', '_') + '-expired.json'), expired)
            write_new(directory / 'complete.json', {'at': utcnow(), 'requests': 9,
                'all_probes_passed': True, 'capacity_verified': False})
        except BaseException as error:
            if pending:
                block(coordination, directory, str(error))
            write_new(directory / 'stopped.json', {'at': utcnow(), 'type': type(error).__name__,
                'message': str(error), 'no_automatic_retry': True,
                'server_completion_unconfirmed': pending})
            raise
        return directory


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    prep = sub.add_parser('prepare', help='Offline only; fails closed without calibrated CPU counts')
    prep.add_argument('--config', type=Path, default=BASE / 'configs/quality_v2.draft.json')
    prep.add_argument('--metadata', type=Path, default=PHASE2 / 'metadata.json')
    prep.add_argument('--output', type=Path, required=True)
    collect = sub.add_parser('run')
    collect.add_argument('--plan', type=Path, required=True)
    collect.add_argument('--output-root', type=Path, default=BASE.parent / 'evaluation_capacity_runs')
    for flag in ('development-only', 'allow-inference', 'exclusive-gpu'):
        collect.add_argument('--' + flag, action='store_true')
    collect.add_argument('--accept-safety-profile', choices=[PROFILE])
    args = parser.parse_args(argv)
    if args.command == 'run' and not (args.development_only and args.allow_inference and
                                      args.exclusive_gpu and args.accept_safety_profile == PROFILE):
        parser.error('Requires --development-only --allow-inference --exclusive-gpu and '
                     '--accept-safety-profile; no service access performed')
    counter = None
    try:
        if args.command == 'prepare':
            snapshot = read_json(args.metadata)
            counter = CpuCounter(snapshot)
            plan = prepare(read_json(args.config), snapshot, counter)
            write_new(args.output, plan)
            print(args.output)
        else:
            plan = read_json(args.plan)
            counter = CpuCounter(plan['snapshot'])
            validate_plan(plan, counter)
            print(run(plan, args.output_root, DevTransport(plan['config']['timeout_seconds']), counter))
    except (OSError, ValueError, RuntimeError, KeyboardInterrupt) as error:
        parser.exit(1, f'Capacity framework stopped: {type(error).__name__}: {error}\n')
    finally:
        if counter:
            counter.close()


if __name__ == '__main__':
    main()
