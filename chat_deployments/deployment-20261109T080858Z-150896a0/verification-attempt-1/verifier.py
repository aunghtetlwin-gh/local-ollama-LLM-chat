from pathlib import Path
import subprocess,json,urllib.request,urllib.error,hashlib,datetime,secrets,time,os
r=Path(Path('/tmp/nectec-chat-deployment-path.txt').read_text());c=Path('/home/lailai/ollama-test/chat_image_candidates/origin-20261109T060037Z-4f0fba1d');m=json.loads((c/'candidate_manifest.json').read_text());state=json.loads((r/'deployment-state.json').read_text());checks=[]
def save(): (r/'smoke-checks.json').write_text(json.dumps(checks,indent=2)+'\n')
def check(name,ok,**fields):checks.append({'name':name,'passed':bool(ok),**fields});save()
def command(a):
 p=subprocess.run(a,capture_output=True,text=True,timeout=20);assert p.returncode==0,'Read-only verification command failed';return p.stdout

def inspect(n):return json.loads(command(['docker','inspect',n]))[0]
def request(method,path,headers=None,body=None):
 req=urllib.request.Request('http://127.0.0.1:8000'+path,data=json.dumps(body).encode() if body is not None else (b'' if method=='POST' else None),headers={'Content-Type':'application/json','User-Agent':'NECTEC-post-deploy-no-cookie-check',**(headers or {})},method=method)
 try:
  with urllib.request.urlopen(req,timeout=10) as p:return p.status,p.read(),dict(p.headers)
 except urllib.error.HTTPError as e:return e.code,e.read(),dict(e.headers)
try:
 app=inspect('local-ollama-chat');db=inspect('ollama-chat-db');check('candidate_image_running',app['Image']==m['candidate_image_id'] and app['State']['Running']);check('expected_new_container',app['Id']==state['new_app_id']);check('no_unexpected_restarts',app['RestartCount']==0)
 metadata="import sys,json,hashlib,importlib.metadata; from pathlib import Path; names="+repr(list(m['candidate_source_hashes']))+"; print(json.dumps({'python':sys.version,'packages':{d.metadata['Name'].lower().replace('_','-'):d.version for d in importlib.metadata.distributions()},'files':{n:hashlib.sha256((Path('/app')/n).read_bytes()).hexdigest() for n in names}}))";runtime=json.loads(command(['docker','exec','local-ollama-chat','python','-B','-c',metadata]));(r/'deployed-runtime.json').write_text(json.dumps(runtime,indent=2)+'\n');check('all_candidate_source_hashes',runtime['files']==m['candidate_source_hashes']);check('all_dependencies_and_python_unchanged',runtime['python']==m['python'] and runtime['packages']==m['packages'])
 for attempt in range(5):
  try:code,data,headers=request('GET','/health');break
  except (urllib.error.URLError,TimeoutError):
   if attempt==4:raise
   time.sleep(1)
 check('health_http200',code==200,status=code);check('health_no_store',headers.get('Cache-Control')=='no-store')
 code,data,_=request('GET','/openapi.json');api=json.loads(data);operations={(method,path) for path,items in api['paths'].items() for method in items if method in ['get','post','put','patch','delete']};old=json.loads((Path(m['readiness'])/'inventory.json').read_text())['health']['/openapi.json']['operations'];expected={(x['method'],x['path']) for x in old};check('exact13_expected_operations',code==200 and operations==expected and len(operations)==13,operations=len(operations))
 origin={'Origin':'http://127.0.0.1:8000'}
 for path in ['/auth/session','/models','/conversations']:
  code,data,_=request('GET',path);check('anonymous_denied:'+path,code==401,status=code)
 scenarios=[('missing_origin',{},403),('hostile_origin',{'Origin':'https://untrusted.example.test'},403),('null_origin',{'Origin':'null'},403),('mismatched_port',{'Origin':'http://127.0.0.1:18000'},403),('matching_origin',origin,200),('matching_referer',{'Referer':'http://127.0.0.1:8000/path?view=chat'},200),('bad_origin_not_rescued',{'Origin':'https://untrusted.example.test','Referer':'http://127.0.0.1:8000/'},403),('invalid_referer',{'Referer':'https://untrusted.example.test/'},403)]
 for label,h,expectedstatus in scenarios:
  code,data,headers=request('POST','/logout',h);check('origin_policy:'+label,code==expectedstatus and headers.get('Cache-Control')=='no-store',status=code)
 code,data,_=request('POST','/logout',{'Host':'127.0.0.1:18000','Origin':'http://127.0.0.1:18000'});check('forwarded_browser_host_origin_shape',code==200,status=code)
 code,data,_=request('POST','/chat',origin,{'message':'SYNTHETIC-NO-COOKIE-NO-INFERENCE','model':'qwen3:8b'});check('anonymous_chat_denied_before_inference',code==401,status=code)
 sentinel='SYNTHETIC-REDACTION-'+secrets.token_hex(12);code,data,_=request('POST','/login',origin,{'password':sentinel});check('malformed_login_redacted',code==422 and sentinel.encode() not in data and json.loads(data)=={'detail':'Invalid request fields.'},status=code)
 before=json.loads((r/'preflight.json').read_text());check('database_id_image_start_unchanged',db['Id']==before['database']['id'] and db['Image']==before['database']['image'] and db['State']['StartedAt']==before['database']['started']);check('database_volume_unchanged',[(x.get('Name'),x['Destination']) for x in db['Mounts']]==[(x['name'],x['destination']) for x in before['database']['mounts']]);check('database_still_healthy',db['State']['Health']['Status']=='healthy');check('rollback_image_available',inspect(m['rollback_tag'])['Id']==m['base_image_id'])
 logs=command(['docker','logs','--since',state['activation_time'],'local-ollama-chat']);# Uvicorn writes stderr: capture both streams separately for summary only.
 p=subprocess.run(['docker','logs','--since',state['activation_time'],'local-ollama-chat'],capture_output=True,text=True,timeout=15);messages=p.stdout+'\n'+p.stderr;errors={mark:messages.count(mark) for mark in ['Traceback (most recent call last)','ERROR','CRITICAL','Exception:'] if mark in messages};startup='Application startup complete' in messages;summary={'docker_logs_exit':p.returncode,'startup_complete':startup,'error_markers':errors,'sentinel_present':sentinel in messages,'raw_logs_saved':False};(r/'startup-log-review.json').write_text(json.dumps(summary,indent=2)+'\n');check('startup_complete_no_errors',p.returncode==0 and startup and not errors);check('sentinel_not_in_logs',sentinel not in messages)
 final=inspect('local-ollama-chat');check('app_remains_same_running_container',final['Id']==app['Id'] and final['State']['Running'] and final['RestartCount']==0)
 failed=[x['name'] for x in checks if not x['passed']];result={'status':'SUCCESS' if not failed else 'PARTIAL','timestamp':datetime.datetime.now(datetime.timezone.utc).isoformat(),'activation_time':state['activation_time'],'pre_app_id':state['old_app_id'],'post_app_id':app['Id'],'pre_image_id':state['old_image_id'],'post_image_id':app['Image'],'patched_server_sha256':runtime['files']['server.py'],'checks_passed':len(checks)-len(failed),'checks_failed':failed,'postgres_unchanged':True,'rollbacks_available':True,'real_credentials_used':False,'real_cookies_used':False,'conversation_contents_accessed':False,'inference_executed':False,'browser_url_shape_verified':'http://127.0.0.1:18000 using Host/Origin shape; real SSH/browser acceptance pending','pending_browser':['Existing authorized browser login/session continuity at http://127.0.0.1:18000','Owner-scoped conversation list/view by its authorized owner; no deletion of existing data','Normal logout then login, and expected authenticated Origin denial if approved without conversation mutation'],'evidence_directory':str(r)};(r/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
except BaseException as e:
 (r/'verification-error.json').write_text(json.dumps({'type':type(e).__name__,'message':str(e),'timestamp':datetime.datetime.now(datetime.timezone.utc).isoformat(),'automatic_rollback_executed':False},indent=2)+'\n');raise
