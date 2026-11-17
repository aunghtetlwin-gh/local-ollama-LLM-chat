"""Read-only characterization of a supported-looking historical custom stdout path."""
from test_portal_security import env,portal,login
from fastapi.testclient import TestClient
import os

def test_existing_custom_stdout_is_not_resolved_by_current_handler(env,monkeypatch):
 custom=env.tmp/'custom-101.out';custom.write_text('SYNTHETIC CUSTOM OUTPUT')
 env.jobs[101]['stdout_expanded']=str(custom)
 original=os.open;attempts=[]
 def open_fixture(name,flags,*args,**kwargs):
  assert name=='/tmp/slurm-101.out';attempts.append(name)
  raise FileNotFoundError('synthetic assumed path absent; custom file exists')
 monkeypatch.setattr(portal.os,'open',open_fixture)
 with TestClient(portal.app) as client:
  login(client);response=client.get('/jobs/101/output')
  assert response.status_code==404 and response.json()=={'detail':'Job output not found'}
 assert custom.is_file() and attempts==['/tmp/slurm-101.out']
 # This passing characterization confirms the limitation; it does not approve it.
