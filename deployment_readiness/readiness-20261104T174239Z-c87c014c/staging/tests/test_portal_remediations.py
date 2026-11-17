from test_portal_security import env,portal,identity,auth,login,PASSWORD
from fastapi.testclient import TestClient
from fastapi import HTTPException
from types import SimpleNamespace
import pytest,subprocess

@pytest.mark.parametrize('path,body',[('/auth/login',{'password':'REDACT_THIS_SENTINEL'}),('/auth/login',{'username':[],'password':'REDACT_THIS_SENTINEL'}),('/admin/users',{'password':'REDACT_THIS_SENTINEL'}),('/admin/users',{'username':'apple','password':'REDACT_THIS_SENTINEL','nested':{'secret':'REDACT_THIS_SENTINEL'}})])
def test_validation_never_echoes_password_values(env,path,body,caplog):
 if path=='/admin/users' and 'username' in body:body['password']='short';body['nested']['secret']='REDACT_THIS_SENTINEL'
 with TestClient(portal.app) as c:
  h=login(c,'admin_test');response=c.post(path,json=body,headers=h)
  assert response.status_code==422 and response.json()=={'detail':'Invalid request fields.'}
 assert 'REDACT_THIS_SENTINEL' not in response.text+caplog.text and PASSWORD not in caplog.text

def test_credential_model_representations_redact_secrets(env):
 assert PASSWORD not in repr(auth.LoginRequest(username='lailai',password=PASSWORD))
 assert PASSWORD not in repr(portal.CreateResearcherRequest(username='apple',password=PASSWORD))

@pytest.mark.parametrize('user',['lailai','mangkud','apple'])
def test_same_explicit_policy_accepts_existing_approved_identities(env,monkeypatch,user):
 monkeypatch.setattr(portal.pwd,'getpwnam',lambda name:SimpleNamespace(pw_uid=1500,pw_shell='/bin/bash'))
 calls=[]
 def command(args,**kw):
  calls.append(args);return SimpleNamespace(stdout=f'{user}|nectec|\n' if args[0]=='sacctmgr' else 'SLURM_JWT=SYNTHETIC_ONLY')
 monkeypatch.setattr(subprocess,'run',command)
 portal.verify_researcher_identity(user);assert auth.create_researcher(user,PASSWORD)['username']==user
 assert identity.slurm_headers(user)['X-SLURM-USER-NAME']==user
 assert len(calls)==2

def test_bootstrap_cli_does_not_expand_its_original_identity_scope(env):
 # apple is approved for Slurm/researcher onboarding, not newly approved for CLI bootstrap.
 with pytest.raises(ValueError):auth.add_user('apple',PASSWORD,'admin')
 with auth.connect() as db:assert db.execute("SELECT count(*) FROM users WHERE username='apple'").fetchone()[0]==0

def test_bootstrap_cli_preserves_existing_supported_identity(env):
 auth.add_user('lailai',PASSWORD,'admin')
 with auth.connect() as db:
  row=db.execute("SELECT role,password_hash FROM users WHERE username='lailai'").fetchone()
 assert row['role']=='admin' and auth.ph.verify(row['password_hash'],PASSWORD)
