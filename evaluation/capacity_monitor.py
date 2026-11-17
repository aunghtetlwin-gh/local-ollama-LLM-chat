"""Capacity telemetry providers and pure validation; providers run only after gating."""
from pathlib import Path
import subprocess
import threading
import time

from .common import utcnow, write_new
from .capacity_protocol import require


def _query(columns):
    result = subprocess.run(['nvidia-smi', *columns, '--format=csv,noheader,nounits'],
                            capture_output=True, text=True, timeout=5)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or 'nvidia-smi failed')
    return result.stdout


def _owner(pid):
    # A compute PID is admissible only when its executable is the installed
    # llama-server and its direct parent is the local ollama serve process.
    root = Path('/proc')
    executable = (root / str(pid) / 'exe').resolve(strict=True)
    require(executable == Path('/usr/local/lib/ollama/llama-server'), 'unknown GPU executable')
    fields = (root / str(pid) / 'status').read_text().splitlines()
    parent = int(next(line.split(':', 1)[1] for line in fields if line.startswith('PPid:')))
    parent_exe = (root / str(parent) / 'exe').resolve(strict=True)
    command = (root / str(parent) / 'cmdline').read_bytes().split(b'\0')
    require(parent_exe == Path('/usr/local/bin/ollama') and b'serve' in command,
            'GPU process is not owned by local Ollama')
    return parent


def telemetry():
    gpu_csv = _query(['--query-gpu=index,uuid,name,memory.total,memory.used,memory.free,driver_version'])
    process_csv = _query(['--query-compute-apps=pid,process_name,used_gpu_memory,gpu_uuid'])
    gpus, processes = [], []
    for line in gpu_csv.strip().splitlines():
        index, uuid, name, total, used, free, driver = [s.strip() for s in line.split(',')]
        gpus.append({'index': int(index), 'uuid': uuid, 'name': name, 'total_mib': int(total),
                     'used_mib': int(used), 'free_mib': int(free), 'driver': driver})
    for line in process_csv.strip().splitlines():
        pid, name, used, uuid = [s.strip() for s in line.split(',')]
        pid = int(pid)
        processes.append({'pid': pid, 'name': name, 'used_mib': int(used), 'gpu_uuid': uuid,
                          'ollama_server_pid': _owner(pid)})
    return {'gpus': gpus, 'processes': processes, 'gpu_csv': gpu_csv, 'process_csv': process_csv}


def check_sample(sample, model, model_digest, resident=False):
    require(not sample.get('error'), 'monitoring failure')
    gpu = sample.get('telemetry', {})
    gpus, processes = gpu.get('gpus'), gpu.get('processes')
    require(isinstance(gpus, list) and len(gpus) == 1, 'unexpected GPU topology')
    card = gpus[0]
    require(card.get('name') == 'NVIDIA GeForce RTX 5060 Ti' and card.get('driver') == '580.178.04',
            'GPU/driver identity mismatch')
    require(all(type(card.get(k)) is int and card[k] >= 0
                for k in ('total_mib', 'used_mib', 'free_mib')), 'malformed GPU memory')
    require(0 < card['total_mib'] and card['used_mib'] <= card['total_mib'] and
            2048 <= card['free_mib'] <= card['total_mib'], 'insufficient GPU memory safety margin')
    require(isinstance(processes, list) and len(processes) <= 1, 'unsafe concurrent GPU activity')
    for item in processes:
        require(type(item.get('pid')) is int and item['pid'] > 0 and
                type(item.get('ollama_server_pid')) is int and item['ollama_server_pid'] > 0 and
                item.get('gpu_uuid') == card.get('uuid') and
                Path(item.get('name', '')).name == 'llama-server', 'unapproved compute process')
    ps = sample.get('ollama_ps')
    require(isinstance(ps, dict) and isinstance(ps.get('models'), list), 'malformed residency response')
    models = ps['models']
    require(len(models) <= 1, 'unsafe concurrent model residency')
    for item in models:
        require(item.get('name', item.get('model')) == model and item.get('digest') == model_digest,
                'resident model/digest mismatch')
        require(item.get('context_length') == 8192 and type(item.get('size')) is int and
                item['size'] > 0 and item.get('size_vram') == item['size'], 'GPU residency/context mismatch')
    require(not resident or len(models) == 1, 'resident model observation missing')
    return bool(models)


class CapacityMonitor:
    def __init__(self, transport, gpu, path, model, model_digest, interval=0.5):
        self.transport, self.gpu, self.path = transport, gpu, Path(path)
        self.model, self.model_digest, self.interval = model, model_digest, interval
        self.stop = threading.Event()
        self.failed = threading.Event()
        self.error = None
        self.count = 0
        self.thread = None

    def sample(self, phase, resident=False):
        record = {'at': utcnow(), 'monotonic_s': time.monotonic(), 'phase': phase}
        try:
            record['telemetry'] = self.gpu()
            record['ollama_ps'] = self.transport.request('/api/ps')
            check_sample(record, self.model, self.model_digest, resident)
        except Exception as error:
            record['error'] = {'type': type(error).__name__, 'message': str(error)}
            self.error = record['error']
            self.failed.set()
        write_new(self.path / f'sample-{self.count:06d}.json', record)
        self.count += 1
        if self.failed.is_set():
            raise RuntimeError('Capacity monitoring failed: ' + str(self.error))

    def start(self):
        self.sample('preflight')
        def loop():
            try:
                while not self.stop.wait(self.interval):
                    self.sample('inflight')
            except Exception as error:
                self.error = {'type': type(error).__name__, 'message': str(error)}
                self.failed.set()
        self.thread = threading.Thread(target=loop, daemon=True)
        self.thread.start()

    def finish(self, resident=True):
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=20)
            if self.thread.is_alive():
                self.failed.set()
                raise RuntimeError('Monitoring worker did not stop')
        if self.failed.is_set():
            raise RuntimeError('Monitoring failed: ' + str(self.error))
        self.sample('final', resident=resident)
