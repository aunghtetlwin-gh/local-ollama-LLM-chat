"""Isolated portal security tests: synthetic SQLite users, no scheduler/network commands."""
import hashlib,importlib,os,secrets,socket,sqlite3,stat,subprocess,sys,tempfile,time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import pytest,requests
from fastapi import HTTPException
from fastapi.testclient import TestClient

# app.py initializes its database during import: redirect BEFORE importing it.
IMPORT_TMP=tempfile.TemporaryDirectory(prefix='nectec-security-portal-import-')
os.environ['PORTAL_AUTH_DB']=str(Path(IMPORT_TMP.name)/'users.sqlite')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'portal-release'))
with patch.object(subprocess,'run',side_effect=AssertionError('No host command during portal import')),patch.object(requests.sessions.Session,'request',side_effect=AssertionError('No network during portal import')):
 import auth
 import app as portal
 import slurm_identity as identity

PASSWORD='Synthetic test password 42!'
# All identities below exist only in disposable SQLite, never Linux/production.
USERS={'admin_test':'admin','researcher_a':'user','researcher_b':'user'}

@pytest.fixture
def env(tmp_path,monkeypatch):
 def blocked(*a,**k):raise AssertionError('Live network/host operation forbidden')
 monkeypatch.setattr(subprocess,'run',blocked);monkeypatch.setattr(requests.sessions.Session,'request',blocked);monkeypatch.setattr(socket,'create_connection',blocked)
 monkeypatch.setenv('PORTAL_COOKIE_SECURE','0');monkeypatch.setattr(auth,'DB_PATH',tmp_path/'users.sqlite');auth.init_db()
 with auth.connect() as db:
  for user,role in USERS.items():db.execute('INSERT INTO users(username,password_hash,role) VALUES(?,?,?)',(user,auth.ph.hash(PASSWORD),role))
 calls=[]
 jobs={101:{'job_id':101,'user_name':'researcher_a','name':'A private','job_state':['RUNNING']},202:{'job_id':202,'user_name':'researcher_b','name':'B private','job_state':['RUNNING']},303:{'job_id':303,'user_name':'admin_test','name':'Admin private','job_state':['RUNNING']}}
 history=[{'job_id':k,'user':v['user_name'],'name':v['name'],'state':{'current':['COMPLETED']},'time':{'submission':1000+k}} for k,v in jobs.items()]
 def scheduler(method,endpoint,payload=None,*,username=portal.SLURM_USER):
  calls.append({'method':method,'endpoint':endpoint,'username':username,'payload':payload})
  if '/slurmdb/' in endpoint:return {'jobs':history}
  if endpoint.endswith('/jobs/'):return {'jobs':list(jobs.values())}
  if endpoint.endswith('/submit'):return {'job_id':999,'errors':[]}
  if endpoint.endswith('/requeue') or method=='DELETE':return {'errors':[]}
  if '/job/' in endpoint:
   jid=int(endpoint.rsplit('/',1)[-1]);return {'jobs':[jobs[jid]] if jid in jobs else []}
  raise AssertionError('unexpected mocked scheduler operation '+endpoint)
 monkeypatch.setattr(portal,'call_slurm',scheduler)
 monkeypatch.setattr(portal.pwd,'getpwnam',lambda name:SimpleNamespace(pw_uid=os.getuid(),pw_shell='/bin/bash'))
 yield SimpleNamespace(tmp=tmp_path,calls=calls,jobs=jobs,history=history)

def login(client,user='researcher_a'):
 response=client.post('/auth/login',json={'username':user,'password':PASSWORD});assert response.status_code==200
 return {'X-Portal-CSRF':response.json()['csrf_token']}

def test_auth_hashes_and_session_digest(env):
 with TestClient(portal.app) as c:
  resp=c.post('/auth/login',json={'username':'researcher_a','password':PASSWORD});assert resp.status_code==200
  token=c.cookies.get(auth.COOKIE_NAME)
  with auth.connect() as db:
   user=db.execute('SELECT password_hash FROM users WHERE username=?',('researcher_a',)).fetchone()[0];session=db.execute('SELECT token_hash,expires_at FROM sessions').fetchone()
  assert user.startswith('$argon2id$') and auth.ph.verify(user,PASSWORD);assert session[0]==hashlib.sha256(token.encode()).hexdigest() and session[0]!=token;assert 28790<session[1]-time.time()<=28800
  assert 'HttpOnly' in resp.headers['set-cookie'] and 'SameSite=strict' in resp.headers['set-cookie'];assert (env.tmp/'users.sqlite').stat().st_mode&0o777==0o600
  assert 'password_hash' not in c.get('/auth/me').text and PASSWORD not in resp.text

@pytest.mark.parametrize('user,pwd',[('researcher_a','wrong'),('missing','wrong')])
def test_invalid_credentials(env,user,pwd):
 with TestClient(portal.app) as c:
  assert c.post('/auth/login',json={'username':user,'password':pwd}).status_code==401
  with auth.connect() as db:assert db.execute('SELECT count(*) FROM sessions').fetchone()[0]==0

@pytest.mark.parametrize('method,path,body',[('get','/auth/me',None),('get','/admin/users',None),('get','/jobs/active',None),('get','/jobs/history',None),('get','/jobs/101',None),('get','/jobs/101/output',None),('get','/cluster/node',None),('post','/jobs',{'script':'#!/bin/bash\ntrue\n'}),('post','/jobs/101/cancel',None),('post','/jobs/101/requeue',None),('post','/admin/users',{'username':'x','password':PASSWORD}),('patch','/admin/users/researcher_a/status',{'enabled':False})])
def test_anonymous_rejected_before_scheduler(env,method,path,body):
 with TestClient(portal.app) as c:assert c.request(method,path,json=body).status_code==401
 assert not env.calls

@pytest.mark.parametrize('route', ['/jobs/active','/admin/users','/jobs/101'])
def test_invalid_cookie_rejected(env,route):
 with TestClient(portal.app) as c:
  c.cookies.set(auth.COOKIE_NAME,'forged');assert c.get(route).status_code==401
 assert not env.calls

@pytest.mark.parametrize('mode',['expired','revoked','disabled'])
def test_session_expiry_revocation_disablement(env,mode):
 with TestClient(portal.app) as c:
  login(c)
  with auth.connect() as db:
   if mode=='expired':db.execute('UPDATE sessions SET expires_at=?',(int(time.time())-1,))
   elif mode=='revoked':db.execute('DELETE FROM sessions')
   else:db.execute("UPDATE users SET enabled=0 WHERE username='researcher_a'")
  assert c.get('/jobs/active').status_code==401
 assert not env.calls

def test_logout_replay_denied(env):
 with TestClient(portal.app) as c:
  headers=login(c);token=c.cookies.get(auth.COOKIE_NAME);assert c.post('/auth/logout',headers=headers).status_code==200;c.cookies.set(auth.COOKIE_NAME,token);assert c.get('/auth/me').status_code==401

@pytest.mark.parametrize('method,path,body,user',[('post','/auth/logout',None,'researcher_a'),('post','/jobs',{'script':'true'},'researcher_a'),('post','/jobs/101/cancel',None,'researcher_a'),('post','/jobs/101/requeue',None,'researcher_a'),('post','/admin/users',{'username':'new_test','password':PASSWORD},'admin_test'),('patch','/admin/users/researcher_b/status',{'enabled':False},'admin_test')])
@pytest.mark.parametrize('csrf',['missing','invalid','other_session'])
def test_mutations_require_session_bound_csrf(env,method,path,body,user,csrf):
 with TestClient(portal.app) as c,TestClient(portal.app) as other:
  login(c,user);other_headers=login(other,'researcher_b');headers={} if csrf=='missing' else {'X-Portal-CSRF':'wrong' if csrf=='invalid' else other_headers['X-Portal-CSRF']}
  assert c.request(method,path,json=body,headers=headers).status_code==403
 assert not env.calls

@pytest.mark.parametrize('user,expected',[('researcher_a',{101}),('researcher_b',{202}),('admin_test',{101,202,303})])
def test_listing_and_history_filter_owners(env,user,expected):
 with TestClient(portal.app) as c:
  login(c,user)
  for route in ['/jobs/active','/jobs/history']:
   response=c.get(route,params={'username':'admin_test','user':'admin_test'});assert response.status_code==200;assert {r['job_id'] for r in response.json()['jobs']}==expected
 assert all(call['username']==user for call in env.calls)
 if user!='admin_test':assert f'users={user}' in env.calls[-1]['endpoint']

@pytest.mark.parametrize('user,jid,expected',[('researcher_a',101,200),('researcher_a',202,404),('researcher_b',101,404),('admin_test',202,200),('researcher_a',999,404)])
def test_job_metadata_ownership(env,user,jid,expected):
 with TestClient(portal.app) as c:
  login(c,user);r=c.get(f'/jobs/{jid}');assert r.status_code==expected
  if expected==404:assert 'private' not in r.text

@pytest.mark.parametrize('action',['cancel','requeue'])
@pytest.mark.parametrize('user,jid,expected',[('researcher_a',101,200),('researcher_a',202,404),('researcher_b',101,404),('admin_test',101,404),('admin_test',303,200),('researcher_a',999,404)])
def test_job_mutation_owner_only_even_admin(env,action,user,jid,expected):
 with TestClient(portal.app) as c:
  headers=login(c,user);r=c.post(f'/jobs/{jid}/{action}',headers=headers);assert r.status_code==expected
 mutations=[x for x in env.calls if x['method']=='DELETE' or x['endpoint'].endswith('/requeue')]
 assert len(mutations)==(1 if expected==200 else 0);assert all(x['username']==user for x in env.calls)

@pytest.mark.parametrize('user,jid,expected',[('researcher_a',101,200),('researcher_a',202,404),('researcher_b',101,404),('admin_test',101,404),('admin_test',303,200)])
def test_output_owner_and_privileged_admin_boundary(env,monkeypatch,user,jid,expected):
 path=env.tmp/'synthetic-output';path.write_text('SYNTHETIC PRIVATE OUTPUT');original=os.open;opened=[]
 def op(name,flags,*a,**k):
  if name==f'/tmp/slurm-{jid}.out':opened.append(flags);return original(path,flags,*a,**k)
  raise AssertionError('unexpected filesystem output request')
 monkeypatch.setattr(portal,'open_stdout_file',lambda name:op(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK))
 with TestClient(portal.app) as c:
  login(c,user);r=c.get(f'/jobs/{jid}/output');assert r.status_code==expected
  if expected==200:assert r.json()['output']=='SYNTHETIC PRIVATE OUTPUT';assert opened[0]&os.O_NOFOLLOW
  else:assert not opened and 'PRIVATE' not in r.text

@pytest.mark.parametrize('kind,expected',[('symlink',404),('directory',404),('wrong_uid',404),('oversize',413),('missing',404)])
def test_output_filesystem_checks(env,monkeypatch,kind,expected):
 path=env.tmp/'output'
 if kind=='symlink':target=env.tmp/'target';target.write_text('private');path.symlink_to(target)
 elif kind=='directory':path.mkdir()
 elif kind=='oversize':path.write_bytes(b'x'*(1024*1024+1))
 elif kind=='wrong_uid':path.write_text('private');monkeypatch.setattr(portal.pwd,'getpwnam',lambda name:SimpleNamespace(pw_uid=os.getuid()+12345))
 original=os.open
 def op(name,flags,*a,**k):
  assert name=='/tmp/slurm-101.out';return original(path,flags,*a,**k)
 monkeypatch.setattr(portal,'open_stdout_file',lambda name:op(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK))
 with TestClient(portal.app) as c:login(c);assert c.get('/jobs/101/output').status_code==expected

@pytest.mark.parametrize('owner,expected',[('researcher_a',None),('researcher_b',404)])
def test_completed_output_owner_accounting_fallback(env,monkeypatch,owner,expected):
 calls=[]
 def fake(method,endpoint,**kw):
  calls.append((endpoint,kw['username']));return {'jobs':[{'job_id':101,'user':owner}]} if '/slurmdb/' in endpoint else {'jobs':[]}
 monkeypatch.setattr(portal,'call_slurm',fake)
 if expected:
  with pytest.raises(HTTPException) as e:portal.verify_output_owner(101,'researcher_a')
  assert e.value.status_code==expected
 else:portal.verify_output_owner(101,'researcher_a')
 assert len(calls)==2 and 'users=researcher_a' in calls[-1][0]

@pytest.mark.parametrize('method,path,body',[('get','/admin/users',None),('post','/admin/users',{'username':'new_test','password':PASSWORD}),('patch','/admin/users/researcher_b/status',{'enabled':False})])
def test_researcher_cannot_administer(env,method,path,body):
 with TestClient(portal.app) as c:
  h=login(c);assert c.request(method,path,json=body,headers=h).status_code==403
 with auth.connect() as db:assert db.execute("SELECT enabled FROM users WHERE username='researcher_b'").fetchone()[0]==1

def test_admin_listing_excludes_secrets(env):
 with TestClient(portal.app) as c:
  login(c,'admin_test');r=c.get('/admin/users');assert r.status_code==200;assert all(set(x)=={'username','role','enabled'} for x in r.json()['users']);assert 'password_hash' not in r.text and PASSWORD not in r.text

def test_admin_onboards_and_revokes_researcher_sessions(env,monkeypatch):
 monkeypatch.setattr(identity,'ALLOWED_SLURM_USERS',identity.ALLOWED_SLURM_USERS|{'new_test'})
 checked=[];monkeypatch.setattr(portal,'verify_researcher_identity',lambda name:checked.append(name))
 with TestClient(portal.app) as admin,TestClient(portal.app) as researcher:
  h=login(admin,'admin_test');payload={'username':'new_test','password':PASSWORD,'role':'admin'};r=admin.post('/admin/users',json=payload,headers=h);assert r.status_code==201 and r.json()['role']=='user';assert checked==['new_test']
  assert admin.post('/admin/users',json=payload,headers=h).status_code==409
  with auth.connect() as db:original=db.execute("SELECT password_hash FROM users WHERE username='new_test'").fetchone()[0]
  assert auth.ph.verify(original,PASSWORD)
  login(researcher,'new_test');token=researcher.cookies.get(auth.COOKIE_NAME)
  assert admin.patch('/admin/users/new_test/status',json={'enabled':False},headers=h).status_code==200
  assert researcher.get('/auth/me').status_code==401;assert researcher.post('/auth/login',json={'username':'new_test','password':PASSWORD}).status_code==401
  assert admin.patch('/admin/users/new_test/status',json={'enabled':True},headers=h).status_code==200
  researcher.cookies.set(auth.COOKIE_NAME,token);assert researcher.get('/auth/me').status_code==401;login(researcher,'new_test')
  assert admin.patch('/admin/users/admin_test/status',json={'enabled':False},headers=h).status_code==403

@pytest.mark.parametrize('mode,status',[('bad_name',400),('absent_linux',400),('system_uid',400),('nologin',400),('no_assoc',400),('assoc_failure',503),('eligible',None)])
def test_onboarding_linux_and_slurm_association(env,monkeypatch,mode,status):
 monkeypatch.setattr(identity,'ALLOWED_SLURM_USERS',identity.ALLOWED_SLURM_USERS|{'eligible_test'})
 def lookup(name):
  if mode=='absent_linux':raise KeyError(name)
  return SimpleNamespace(pw_uid=99 if mode=='system_uid' else 1500,pw_shell='/usr/sbin/nologin' if mode=='nologin' else '/bin/bash')
 def command(args,**kw):
  assert args[:4]==['sacctmgr','-nP','show','assoc']
  if mode=='assoc_failure':raise subprocess.CalledProcessError(1,args)
  return SimpleNamespace(stdout='eligible_test|other|\n' if mode=='no_assoc' else 'eligible_test|nectec|\n')
 monkeypatch.setattr(portal.pwd,'getpwnam',lookup);monkeypatch.setattr(subprocess,'run',command)
 if status:
  with pytest.raises(HTTPException) as e:portal.verify_researcher_identity('bad;name' if mode=='bad_name' else 'eligible_test')
  assert e.value.status_code==status
 else:portal.verify_researcher_identity('eligible_test')

@pytest.mark.parametrize('user',['lailai','mangkud','apple'])
def test_allowlisted_slurm_identity_command_mapping(env,monkeypatch,user):
 calls=[]
 def command(args,**kwargs):calls.append(args);return SimpleNamespace(stdout='SLURM_JWT=SYNTHETIC_ONLY')
 monkeypatch.setattr(subprocess,'run',command);assert identity.slurm_headers(user)=={'X-SLURM-USER-NAME':user,'X-SLURM-USER-TOKEN':'SYNTHETIC_ONLY'}
 assert calls[0]==(['/usr/bin/scontrol','token','lifespan=300'] if user=='lailai' else ['/usr/bin/sudo','-n','-u',user,'/usr/bin/scontrol','token','lifespan=300'])

def test_unapproved_identity_rejected_consistently(env,monkeypatch):
 calls=[]
 def command(*args,**kwargs):calls.append(args);return SimpleNamespace(stdout='eligible_test|nectec|\n')
 monkeypatch.setattr(subprocess,'run',command)
 assert 'eligible_test' not in identity.ALLOWED_SLURM_USERS
 with pytest.raises(HTTPException) as e:portal.verify_researcher_identity('eligible_test')
 assert e.value.status_code==400
 with pytest.raises(ValueError):auth.create_researcher('eligible_test',PASSWORD)
 with pytest.raises(identity.SlurmIdentityError):identity.slurm_headers('eligible_test')
 assert not calls
 with auth.connect() as db:assert db.execute("SELECT count(*) FROM users WHERE username='eligible_test'").fetchone()[0]==0

@pytest.mark.parametrize('mode',['command_failure','timeout','malformed'])
def test_slurm_token_failures(env,monkeypatch,mode):
 def command(args,**kw):
  if mode=='command_failure':raise subprocess.CalledProcessError(1,args)
  if mode=='timeout':raise subprocess.TimeoutExpired(args,10)
  return SimpleNamespace(stdout='NOT_A_TOKEN')
 monkeypatch.setattr(subprocess,'run',command)
 with pytest.raises(identity.SlurmIdentityError):identity.get_slurm_token('lailai')

@pytest.mark.parametrize('mode,status',[('transport',503),('nonjson',502),('backend403',403)])
def test_slurm_transport_errors_surface_without_mutation(env,monkeypatch,mode,status):
 # Exercise the REAL helper, which was fixture-replaced at the HTTP boundary elsewhere.
 original_call=ORIGINAL_CALL
 monkeypatch.setattr(portal,'user_slurm_headers',lambda user:{'X-SLURM-USER-NAME':user})
 def request(**kw):
  if mode=='transport':raise requests.ConnectionError('synthetic unavailable')
  def parsed():
   if mode=='nonjson':raise ValueError('synthetic')
   return {'errors':['synthetic denied']}
  return SimpleNamespace(status_code=403 if mode=='backend403' else 200,json=parsed,text='synthetic invalid')
 monkeypatch.setattr(requests,'request',request)
 with pytest.raises(HTTPException) as e:original_call('GET','/synthetic',username='researcher_a')
 assert e.value.status_code==status

@pytest.mark.parametrize('secure',[False,True])
def test_cookie_secure_toggle(env,monkeypatch,secure):
 monkeypatch.setenv('PORTAL_COOKIE_SECURE','1' if secure else '0')
 with TestClient(portal.app,base_url='https://testserver') as c:r=c.post('/auth/login',json={'username':'researcher_a','password':PASSWORD});assert r.status_code==200;assert ('; Secure' in r.headers['set-cookie']) is secure

ORIGINAL_CALL=portal.call_slurm
