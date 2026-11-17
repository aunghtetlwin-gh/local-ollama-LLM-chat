"""Backend policy characterization, NOT a real-browser CSRF exploit demonstration."""
import importlib.util,sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,'/home/lailai/ollama-test')
with patch('dotenv.load_dotenv',return_value=False):
 spec=importlib.util.spec_from_file_location('isolated_chat_fixture_source','/home/lailai/ollama-test/tests/conftest.py');fixtures=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixtures)
import server
block_external_services=fixtures.block_external_services
db=fixtures.db
client=fixtures.client
register_user=fixtures.register_user

def test_authenticated_delete_has_no_origin_or_csrf_check(client,db,register_user):
 uid=register_user(client).json()['user']['id'];cid=server.create_conversation('Synthetic CSRF policy check',uid)
 response=client.delete(f'/conversations/{cid}',headers={'Origin':'https://untrusted.example.test'})
 # TestClient supplies the authenticated cookie; it does NOT model browser SameSite rules.
 assert response.status_code==200
 assert db.raw.execute('SELECT count(*) FROM conversations').fetchone()[0]==0

def test_logout_has_no_origin_or_csrf_check(client,register_user):
 register_user(client);response=client.post('/logout',headers={'Origin':'https://untrusted.example.test'})
 assert response.status_code==200 and client.get('/auth/session').status_code==401
