"""Standalone: python -m pytest integration_tests/test_postgres_isolation.py -q.

Never accepts a database URL. Creates and stops only its own temporary cluster.
Requires PostgreSQL binaries (PG_TEST_BIN may select the binary directory).
"""
import io
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
from unittest.mock import patch

import pytest
import psycopg
from fastapi.testclient import TestClient as BaseTestClient

def TestClient(*args, **kwargs):
    kwargs.setdefault("headers", {"Origin": "http://testserver"})
    return BaseTestClient(*args, **kwargs)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
# Prevent application imports from reading .env, even during test collection.
with patch('dotenv.load_dotenv', return_value=False):
    import database
    import auth
    import server


@pytest.fixture(scope='module')
def isolated_app():
    binaries = Path(os.environ.get('PG_TEST_BIN', '/usr/lib/postgresql/14/bin'))
    if not all((binaries / tool).is_file() for tool in ('initdb', 'pg_ctl')):
        pytest.skip('Isolated PostgreSQL binaries unavailable; no existing database fallback')
    with tempfile.TemporaryDirectory(prefix='conversation-isolation-') as tmp:
        base = Path(tmp)
        data = base / 'data'
        password = secrets.token_urlsafe(32)
        password_file = base / 'bootstrap-password'
        password_file.write_text(password)
        password_file.chmod(0o600)
        # Minimal environment prevents inherited libpq/service configuration.
        env = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'HOME': tmp}
        def run(*args):
            result = subprocess.run([str(binaries / args[0]), *args[1:]], env=env,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            if result.returncode:
                raise RuntimeError('Disposable PostgreSQL command failed: ' + args[0])
        run('initdb', '-D', str(data), '-U', 'isolation_runner',
            '--pwfile', str(password_file), '--auth-local=scram-sha-256',
            '--auth-host=reject')
        password_file.unlink()
        started = False
        try:
            run('pg_ctl', '-D', str(data), '-l', str(base / 'postgres.log'),
                '-o', f"-k {tmp} -c listen_addresses='' -c unix_socket_permissions=0700", '-w', 'start')
            started = True
            connect_raw = psycopg.connect
            def connect():
                return connect_raw(host=tmp, port=5432, dbname='postgres',
                                   user='isolation_runner', password=password)
            def blocked(*a, **kw):
                raise AssertionError('External database or network access forbidden')
            with patch.object(psycopg, 'connect', blocked), \
                 patch.object(database, 'get_db_connection', connect), \
                 patch.object(auth, 'get_db_connection', connect), \
                 patch.object(server, 'get_db_connection', connect), \
                 patch.object(auth, 'COOKIE_SECURE', False), \
                 patch.object(server.urllib.request, 'urlopen', blocked):
                with connect() as conn:
                    conn.execute('''CREATE TABLE conversations (
                        id BIGSERIAL PRIMARY KEY, title TEXT NOT NULL DEFAULT 'New Chat',
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW());
                        CREATE TABLE messages (
                        id BIGSERIAL PRIMARY KEY, conversation_id BIGINT NOT NULL
                        REFERENCES conversations(id) ON DELETE CASCADE,
                        role VARCHAR(20) NOT NULL CHECK (role IN ('system','user','assistant')),
                        content TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), model TEXT);''')
                    conn.execute((ROOT / 'migrations/001_users_sessions.sql').read_text())
                with TestClient(server.my_api) as a, TestClient(server.my_api) as b:
                    ids = []
                    for client, name in [(a, 'researcher_a'), (b, 'researcher_b')]:
                        credential = secrets.token_urlsafe(24)
                        response = client.post('/register', json={'email': name + '@example.test',
                            'password': credential, 'password_confirmation': credential})
                        assert response.status_code == 201
                        ids.append(response.json()['user']['id'])
                    with connect() as conn:
                        conn.execute("SELECT set_config('app.migration_owner_id', %s, true)", (str(ids[0]),))
                        conn.execute((ROOT / 'migrations/002_conversation_ownership.sql').read_text())
                    yield a, b, ids, connect
        finally:
            if started:
                run('pg_ctl', '-D', str(data), '-m', 'fast', '-w', 'stop')


def test_two_researcher_isolation(isolated_app):
    a, b, (aid, bid), connect = isolated_app
    calls = []
    def fake_ollama(request, **kwargs):
        calls.append(json.loads(request.data))
        return io.BytesIO(b'{"message":{"content":"Test reply"},"done":true}\n')
    with patch.object(server.urllib.request, 'urlopen', fake_ollama):
        created = a.post('/chat', json={'message': 'A private message', 'user_id': bid})
        assert created.status_code == 200
        cid = int(created.headers['x-conversation-id'])
        with connect() as conn:
            assert conn.execute('SELECT user_id FROM conversations WHERE id=%s', (cid,)).fetchone() == (aid,)
        assert a.get('/conversations').json()['conversations'][0]['id'] == cid
        own = a.get(f'/conversations/{cid}')
        assert own.status_code == 200
        assert own.json()['messages'][0]['content'] == 'A private message'
        assert b.get('/conversations', params={'user_id': aid}).json() == {'conversations': []}
        before = own.json()
        call_count = len(calls)
        for target in (cid, 999999, 0, -1):
            for response in (
                b.get(f'/conversations/{target}', params={'user_id': aid}),
                b.delete(f'/conversations/{target}', params={'user_id': aid}),
                b.post('/chat', json={'conversation_id': target, 'message': 'Intrusion', 'user_id': aid}),
            ):
                assert response.status_code == 404
                assert response.json() == {'detail': 'Conversation not found.'}
        assert len(calls) == call_count
        assert a.get(f'/conversations/{cid}').json() == before
        assert server.get_conversation_messages(cid, bid) == []
        with pytest.raises(Exception) as denied:
            server.save_message(cid, bid, 'user', 'Intrusion')
        assert getattr(denied.value, 'status_code', None) == 404
        assert a.post('/chat', json={'conversation_id': cid, 'message': 'A follow-up', 'user_id': bid}).status_code == 200
        assert [m['content'] for m in calls[-1]['messages']] == ['A private message', 'Test reply', 'A follow-up']
        other = b.post('/chat', json={'message': 'B private message', 'user_id': aid})
        bcid = int(other.headers['x-conversation-id'])
        with connect() as conn:
            assert conn.execute('SELECT user_id FROM conversations WHERE id=%s', (bcid,)).fetchone() == (bid,)
        assert a.get(f'/conversations/{bcid}').status_code == 404
        assert len(b.get('/conversations').json()['conversations']) == 1
        assert a.delete(f'/conversations/{cid}').status_code == 200
        with connect() as conn:
            assert conn.execute('SELECT count(*) FROM messages WHERE conversation_id=%s', (cid,)).fetchone() == (0,)
        assert b.get(f'/conversations/{bcid}').status_code == 200


@pytest.mark.parametrize('cookie', [None, 'invalid-session'])
@pytest.mark.parametrize('method,path,payload', [
    ('GET', '/conversations', None), ('GET', '/conversations/1', None),
    ('DELETE', '/conversations/1', None), ('POST', '/chat', {'message': 'New'}),
    ('POST', '/chat', {'message': 'Continue', 'conversation_id': 1, 'user_id': 1}),
])
def test_unauthenticated(isolated_app, cookie, method, path, payload):
    with TestClient(server.my_api) as client:
        if cookie:
            client.cookies.set(auth.COOKIE_NAME, cookie)
        assert client.request(method, path, json=payload).status_code == 401
