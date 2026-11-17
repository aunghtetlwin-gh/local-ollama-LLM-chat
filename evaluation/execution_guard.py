"""Shared advisory execution lock and durable capacity uncertainty latch."""
from contextlib import contextmanager
import fcntl
from pathlib import Path

from .common import BASE, read_json, utcnow, write_new

DEFAULT_ROOT = BASE.parent / 'evaluation_execution'


@contextmanager
def execution_guard(root=None):
    root = Path(root) if root is not None else DEFAULT_ROOT
    root.mkdir(parents=True, exist_ok=True)
    with (root / 'execution.lock').open('a') as file:
        try:
            fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Another development/capacity collector owns the execution lock') from None
        try:
            for name in ('BLOCKED.json', 'PENDING.json'):
                if (root / name).exists():
                    raise ValueError('Server completion/activity unresolved: ' + str(read_json(root / name)))
            yield root
        finally:
            fcntl.flock(file, fcntl.LOCK_UN)


def block(root, run, reason):
    path = Path(root) / 'BLOCKED.json'
    if not path.exists():
        write_new(path, {'at': utcnow(), 'run': str(run), 'reason': reason,
                         'automatic_clear': False, 'server_completion_unconfirmed': True})


def mark_pending(root, run, attempt):
    # Published before launching the HTTP worker; survives parent SIGKILL/power loss.
    write_new(Path(root) / 'PENDING.json', {'at': utcnow(), 'run': str(run),
              'attempt': str(attempt), 'server_completion_unconfirmed': True})


def complete_pending(root, run, attempt):
    path = Path(root) / 'PENDING.json'
    record = read_json(path)
    if record.get('run') != str(run) or record.get('attempt') != str(attempt):
        raise ValueError('Pending-request ownership mismatch')
    path.unlink()  # Remove only our own confirmed request state, never an uncertainty latch.
