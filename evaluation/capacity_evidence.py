"""Versioned offline substantive validation of synthetic capacity artifacts."""
import argparse
import math
from pathlib import Path

from .common import BASE, digest, read_json, sha256, write_new
from .thinking_evidence import inventory
from .capacity_protocol import VERSION as PROBE_VERSION, check_response, require, capacity_config
from .capacity_monitor import check_sample
from .token_accounting import CpuCounter

VERSION = 'capacity-report-v1'
SOURCES = ('capacity_evidence.py', 'capacity_protocol.py', 'capacity_inference.py',
           'capacity_monitor.py', 'token_accounting.py', 'execution_guard.py',
           'dev_inference.py', 'runner.py', 'scoring.py', 'common.py')


def source_hashes():
    return {name: sha256((BASE / name).read_bytes()) for name in SOURCES}


def _location(root):
    root = Path(root).absolute()
    try:
        return root.relative_to(BASE.parent).as_posix()
    except ValueError:
        return str(root)


def _root(report):
    root = Path(report['root'])
    return root if root.is_absolute() else BASE.parent / root


def inspect_run(root, config, snapshot, counter):
    """Recompute counts, synthetic content, telemetry and outcomes, not saved pass flags."""
    from .capacity_inference import validate_plan
    root = Path(root)
    manifest = read_json(root / 'manifest.json')
    plan = manifest['plan']
    require(capacity_config(plan['config']) == capacity_config(config) and plan['snapshot'] == snapshot, 'capacity configuration/metadata mismatch')
    require(manifest.get('plan_sha256') == digest(plan), 'capacity plan hash mismatch')
    require(manifest.get('source_sha256') == source_hashes(), 'capacity validator/collector source changed')
    validate_plan(plan, counter)
    require(read_json(root / 'metadata.json') == snapshot, 'captured model/runtime mismatch')
    require(read_json(root / 'initial_ps.json') == {'models': []}, 'initial models resident')
    complete = read_json(root / 'complete.json')
    require(complete.get('requests') == 9 and complete.get('all_probes_passed') is True and
            complete.get('capacity_verified') is False, 'incomplete/unreviewed experiment record invalid')
    require(not (root / 'stopped.json').exists(), 'capacity experiment stopped')
    expected = {p['model'].replace(':', '_') + '-' + p['case'] for p in plan['probes']}
    require({p.parent.name for p in root.glob('*/request.json')} == expected, 'missing/unexpected capacity attempts')
    findings, gpu_identity = {}, None
    for probe in plan['probes']:
        attempt = root / (probe['model'].replace(':', '_') + '-' + probe['case'])
        require(not (attempt / 'error.json').exists(), 'probe error artifact present')
        require(read_json(attempt / 'request.json') == probe['request'], 'saved request mismatch')
        require(read_json(attempt / 'tokenization.json') == probe['tokenization'], 'tokenization evidence mismatch')
        require(read_json(attempt / 'sent.json').get('completion_unconfirmed') is True, 'missing sent record')
        raw = read_json(attempt / 'response.json')
        result = check_response(probe, raw)
        require(read_json(attempt / 'result.json') == result, 'saved findings mismatch')
        timing = read_json(attempt / 'timing.json')
        wall = timing.get('request_wall_time_s')
        require(type(wall) in (int, float) and math.isfinite(wall) and
                0 <= wall < config['timeout_seconds'] and timing.get('deadline_s') == config['timeout_seconds'],
                'deadline/timing evidence invalid')
        require(raw['total_duration'] <= (wall + 1) * 1_000_000_000 and
                max(raw['load_duration'], raw['eval_duration']) <= raw['total_duration'],
                'inconsistent server/request durations')
        sent_mono, received_mono = timing.get('sent_monotonic_s'), timing.get('received_monotonic_s')
        require(all(type(t) in (int, float) and math.isfinite(t) for t in (sent_mono, received_mono)) and
                sent_mono <= received_mono, 'invalid request observation times')
        paths = sorted((attempt / 'monitoring').glob('sample-*.json'))
        samples = [read_json(p) for p in paths]
        require(len(samples) >= 2 and samples[0].get('phase') == 'preflight' and
                samples[-1].get('phase') == 'final', 'incomplete monitoring coverage')
        times = [s.get('monotonic_s') for s in samples]
        require(all(type(t) in (int, float) and math.isfinite(t) for t in times) and
                times == sorted(times) and all(b - a <= 20 for a, b in zip(times, times[1:])),
                'invalid monitoring timestamps/coverage gaps')
        if wall >= 1:
            require(any(s.get('phase') == 'inflight' and sent_mono <= s['monotonic_s'] <= received_mono
                        for s in samples), 'missing in-flight monitoring')
        for i, sample in enumerate(samples):
            check_sample(sample, probe['model'], snapshot['models'][probe['model']]['digest'],
                         resident=i == len(samples) - 1)
            card = sample['telemetry']['gpus'][0]
            identity = {k: card[k] for k in ('uuid', 'name', 'total_mib', 'driver')}
            if gpu_identity is None:
                gpu_identity = identity
            require(identity == gpu_identity, 'GPU identity changed between probes')
        findings[attempt.name] = {**result, 'prompt_tokens': raw['prompt_eval_count'],
            'output_tokens': raw['eval_count'], 'wall_time_s': wall,
            'load_duration_ns': raw['load_duration'], 'eval_duration_ns': raw['eval_duration'],
            'peak_used_mib': max(s['telemetry']['gpus'][0]['used_mib'] for s in samples),
            'min_free_mib': min(s['telemetry']['gpus'][0]['free_mib'] for s in samples)}
    for model in config['models']:
        require(read_json(root / (model.replace(':', '_') + '-expired.json')) == {'models': []},
                'model expiration not confirmed')
    return {'models': findings, 'gpu': gpu_identity, 'thinking_compatibility': 'separate_verification_required',
            'capacity': 'probe_criteria_met_pending_review', 'capacity_verified': False}


def build_report(root, counter):
    root = Path(root)
    files = inventory(root)
    manifest = read_json(root / 'manifest.json')
    plan = manifest['plan']
    findings = inspect_run(root, plan['config'], plan['snapshot'], counter)
    return {'version': VERSION, 'root': _location(root), 'files': files,
            'validator_sha256': source_hashes(), 'findings': findings,
            'config_sha256': digest(capacity_config(plan['config'])), 'snapshot_sha256': digest(plan['snapshot']),
            'capacity_verified': False, 'reviewer': None}


def validate_report(report, config, snapshot, reviewer, counter=None):
    require(isinstance(reviewer, str) and bool(reviewer.strip()), 'named capacity reviewer required')
    require(report.get('version') == VERSION and report.get('capacity_verified') is False,
            'unsupported capacity report or fabricated approval')
    require(report.get('validator_sha256') == source_hashes(), 'capacity validator source mismatch')
    require(report.get('config_sha256') == digest(capacity_config(config)) and
            report.get('snapshot_sha256') == digest(snapshot), 'capacity report configuration mismatch')
    root = _root(report)
    require(inventory(root) == report.get('files'), 'capacity evidence inventory/hash mismatch')
    owned = counter is None
    counter = counter or CpuCounter(snapshot)
    try:
        findings = inspect_run(root, config, snapshot, counter)
    finally:
        if owned:
            counter.close()
    require(report.get('findings') == findings, 'capacity findings inconsistent')
    return {'reviewer': reviewer, 'capacity_criteria_met': True, 'capacity_verified': False,
            'note': 'Validation is not protocol freeze or reviewer approval'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    build = sub.add_parser('build')
    build.add_argument('--run-dir', type=Path, required=True)
    build.add_argument('--output', type=Path, required=True)
    check = sub.add_parser('validate')
    check.add_argument('--report', type=Path, required=True)
    check.add_argument('--config', type=Path, required=True)
    check.add_argument('--metadata', type=Path, required=True)
    check.add_argument('--reviewer', required=True)
    args = parser.parse_args(argv)
    counter = None
    try:
        if args.command == 'build':
            require(not args.output.resolve().is_relative_to(args.run_dir.resolve()),
                    'report must be outside immutable experiment')
            plan = read_json(args.run_dir / 'manifest.json')['plan']
            counter = CpuCounter(plan['snapshot'])
            write_new(args.output, build_report(args.run_dir, counter))
            print(args.output)
        else:
            print(validate_report(read_json(args.report), read_json(args.config),
                                  read_json(args.metadata), args.reviewer))
    finally:
        if counter:
            counter.close()


if __name__ == '__main__':
    main()
