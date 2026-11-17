"""Standard-library data and exclusive-output primitives; no service access."""
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
DATASETS = {'internal_v2': BASE / 'datasets/internal_v2',
            'gsm8k_50_v1': BASE / 'datasets/gsm8k_50_v1'}
PUBLIC_FIELDS = {'id', 'category', 'difficulty', 'prompt', 'prompt_sha256'}
MAX_TEXT = 100_000


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                             separators=(',', ':'), allow_nan=False).encode())


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines()]


def write_new(path, value):
    """Exclusive create, flush and fsync. Never replace a previous artifact."""
    with Path(path).open('x', encoding='utf-8') as file:
        json.dump(value, file, indent=2, ensure_ascii=False, allow_nan=False)
        file.write('\n')
        file.flush()
        os.fsync(file.fileno())


def load_questions(suite):
    """Runner-facing loader: never opens references or raw upstream solutions."""
    directory = DATASETS[suite]
    manifest = read_json(directory / 'manifest.json')
    path = directory / 'questions.jsonl'
    if sha256(path.read_bytes()) != manifest['questions_sha256']:
        raise ValueError('Question file checksum mismatch')
    rows = read_jsonl(path)
    ids = set()
    for row in rows:
        if set(row) != PUBLIC_FIELDS:
            raise ValueError('Unexpected public question fields (possible reference leakage)')
        if not isinstance(row['id'], str) or not row['id'] or row['id'] in ids:
            raise ValueError('Invalid or duplicate question ID')
        ids.add(row['id'])
        if not isinstance(row['prompt'], str) or not 0 < len(row['prompt']) <= MAX_TEXT:
            raise ValueError('Invalid prompt')
        if sha256(row['prompt'].encode()) != row['prompt_sha256']:
            raise ValueError('Prompt checksum mismatch')
        if row['difficulty'] not in {'easy', 'medium', 'hard', 'unrated'}:
            raise ValueError('Invalid difficulty')
        if row['category'] not in {'knowledge', 'reasoning', 'coding', 'summarization', 'instruction', 'gsm8k'}:
            raise ValueError('Invalid category')
    if len(rows) != manifest['count']:
        raise ValueError('Dataset count mismatch')
    return rows
