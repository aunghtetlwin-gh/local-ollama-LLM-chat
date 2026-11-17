from pathlib import Path
import os,json,hashlib,subprocess,datetime,secrets,urllib.request,urllib.error,stat,xml.etree.ElementTree as E
os.umask(0o077)
c=Path('/home/lailai/ollama-test/portal_release_candidates/portal-output-20261108T132323Z-eb2dad35');m=json.loads((c/'candidate_manifest.json').read_text());release=Path(m['future_release']);r=Path('/home/lailai/ollama-test/portal_output_verification')/('verification-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+secrets.token_hex(4));r.mkdir(parents=True,exist_ok=False);(r/'evidence').mkdir();Path('/tmp/nectec-output-verification-path.txt').write_text(str(r));checks=[]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,d):(r/n).write_text(json.dumps(d,indent=2)+'\n')
def check(n,ok,**v):checks.append({'name':n,'passed':bool(ok),**v});save('checks.json',checks)
def cmd(a):
 p=subprocess.run(a,capture_output=True,text=True,timeout=20);return p

def request(method,path,payload=None,headers=None,port=8001):
 req=urllib.request.Request('http://127.0.0.1:'+str(port)+path,data=json.dumps(payload).encode() if payload is not None else None,headers={'Content-Type':'application/json','User-Agent':'NECTEC-read-only-output-postverify',**(headers or {})},method=method)
 try:
  with urllib.request.urlopen(req,timeout=10) as f:return f.status,f.read()
 except urllib.error.HTTPError as e:return e.code,e.read()
def ops(api):return {(method,path) for path,methods in api['paths'].items() for method in methods if method in ['get','post','put','patch','delete','head','options']}
try:
 check('candidate_seal',all(sha(c/n)==h for n,h in json.loads((c/'FILES_SHA256.json').read_text()).items()))
 p=cmd(['systemctl','show','slurm-portal.service','--property=ActiveState,SubState,MainPID,WorkingDirectory,User,Group,Result,NRestarts,ExecMainStatus,ExecMainStartTimestamp,NeedDaemonReload,DropInPaths']);assert p.returncode==0
 props=dict(x.split('=',1) for x in p.stdout.splitlines() if '=' in x);save('evidence/systemd.json',props);pid=int(props['MainPID']);check('managed_service_healthy',props['ActiveState']=='active' and props['SubState']=='running' and props['Result']=='success' and props['ExecMainStatus']=='0');check('reviewed_release_directory',props['WorkingDirectory']==str(release) and os.readlink(f'/proc/{pid}/cwd')==str(release));check('daemon_reload_complete',props['NeedDaemonReload']=='no')
 selected={}
 for v in Path(f'/proc/{pid}/environ').read_bytes().split(b'\0'):
  if v.startswith((b'PORTAL_AUTH_DB=',b'PORTAL_OUTPUT_ROOTS=')):
   k,val=v.decode().split('=',1);selected[k]=val
 args=[v.decode() for v in Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0') if v];check('localhost8001_no_reload',args[-4:]==['--host','127.0.0.1','--port','8001'] and '--reload' not in args)
 save('evidence/running-process.json',{'pid':pid,'cwd':os.readlink(f'/proc/{pid}/cwd'),'argv':args,'selected_environment':selected});check('original_db_path',selected.get('PORTAL_AUTH_DB')==m['authentication_database_path'])
 release=Path(props['WorkingDirectory']);hashes={n:sha(release/n) if (release/n).is_file() else None for n in m['source_sha256']};save('evidence/deployed-hashes.json',hashes);check('all_deployed_sources_match',hashes==m['source_sha256']);check('dropin_matches_reviewed_bytes',sha(m['current_dropin'])==m['proposed_dropin_sha256'])
 roots=json.loads(selected.get('PORTAL_OUTPUT_ROOTS','null'));check('exact_nine_directory_policy',roots==m['output_roots']);canonical_policy_hash=hashlib.sha256(json.dumps(roots,separators=(',',':')).encode()).hexdigest();save('evidence/policy-hashes.json',{'deployed_canonical_sha256':canonical_policy_hash,'candidate_canonical_sha256':hashlib.sha256(json.dumps(m['output_roots'],separators=(',',':')).encode()).hexdigest(),'candidate_policy_file_sha256':sha(c/'config/output-roots.json'),'deployed_dropin_sha256':sha(m['current_dropin']),'matches':roots==m['output_roots']})
 status,b=request('GET','/openapi.json');api=json.loads(b);save('evidence/openapi8001.json',api);prior_api=json.loads(Path('/home/lailai/ollama-test/portal_deployment_verification/verification-20261106T164500Z-e0f8b1c9/evidence/openapi-8001.json').read_text());check('exact16_expected_operations',status==200 and len(ops(api))==16 and ops(api)==ops(prior_api))
 for method,path in [('post','/jobs'),('post','/jobs/{job_id}/cancel'),('post','/jobs/{job_id}/requeue'),('post','/auth/logout'),('post','/admin/users'),('patch','/admin/users/{username}/status')]:
  params=api['paths'][path][method].get('parameters',[]);check('session_csrf_metadata:'+method+path,any(x.get('name')=='portal_session' and x.get('in')=='cookie' for x in params) and any(x.get('name')=='x-portal-csrf' and x.get('in')=='header' for x in params))
 for path in ['/auth/me','/admin/users','/jobs/active','/jobs/history','/jobs/127','/jobs/127/output','/cluster/node']:
  status,b=request('GET',path);check('anonymous_denial:'+path,status==401,status=status)
 status,b=request('GET','/auth/me',headers={'Cookie':'portal_session=SYNTHETIC-INVALID-NOT-A-REAL-SESSION'});check('invalid_session_denied',status==401,status=status)
 sentinel='SYNTHETIC-REDACTION-'+secrets.token_hex(12)
 for tag,payload in [('missing_username',{'password':sentinel}),('wrong_type',{'username':[],'password':sentinel})]:
  status,b=request('POST','/auth/login',payload);check('password_redaction:'+tag,status==422 and sentinel.encode() not in b and json.loads(b)=={'detail':'Invalid request fields.'},status=status)
 rollback={p:sha(p)==h for p,h in m['base_source_sha256'].items()};save('evidence/rollback-source-checks.json',rollback);check('previous_release_and_fallback_sources_intact',all(rollback.values()))
 backup=Path('/home/lailai/nectec-changes/'+m['version']+'-before-deploy');backup_info={'path':str(backup),'present':backup.is_dir(),'previous_override_present':(backup/'previous-dropin.conf').is_file()}
 if backup_info['previous_override_present']:
  try:backup_info['previous_override_matches_predeploy']=sha(backup/'previous-dropin.conf')==m['current_dropin_sha256']
  except PermissionError:backup_info['previous_override_hash']='operator/root verification required (unreadable to current user)'
 save('evidence/rollback-backup.json',backup_info)
 old=json.loads(Path('/home/lailai/ollama-test/portal_deployment_verification/verification-20261106T164500Z-e0f8b1c9/evidence/fallback-process.json').read_text());fp=Path('/proc')/str(old['pid']);fallback={'pid':old['pid'],'cwd':os.readlink(fp/'cwd'),'start_ticks':(fp/'stat').read_text().split(') ',1)[1].split()[19],'argv':[x.decode() for x in (fp/'cmdline').read_bytes().split(b'\0') if x]};save('evidence/fallback.json',fallback);check('fallback_identical_process',fallback==old)
 status,b=request('GET','/openapi.json',port=8002);api2=json.loads(b);previous2=json.loads(Path('/home/lailai/ollama-test/portal_deployment_verification/verification-20261106T164500Z-e0f8b1c9/evidence/openapi-8002.json').read_text());check('fallback_healthy_unchanged_api',status==200 and len(ops(api2))==16 and api2==previous2)
 # Only metadata: no open/read of real job stdout files.
 meta=[]
 for rec in json.loads((c/'evidence/exact-policy-validation.json').read_text())['positive_resolution']:
  p=Path(rec['path']);s=p.lstat();meta.append({'job_id':rec['job_id'],'path':str(p),'uid':s.st_uid,'size':s.st_size,'nlink':s.st_nlink,'regular':stat.S_ISREG(s.st_mode),'content_read':False})
 save('evidence/historical-file-metadata.json',meta)
 code="from pathlib import Path; import importlib.util,json,os; from unittest.mock import patch; p=Path("+repr(str(release/'job_output.py'))+"); spec=importlib.util.spec_from_file_location('deployed_output',p); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); os.environ['PORTAL_OUTPUT_ROOTS']="+repr(selected.get('PORTAL_OUTPUT_ROOTS','[]'))+"; paths="+repr(meta)+"; result=[];\nwith patch.object(mod.os,'open',side_effect=AssertionError('No real output open')):\n for item in paths:\n  actual=mod.resolve_stdout_path({'stdout':str(Path(item['path']).parent/'slurm-%j.out')},item['job_id']); assert actual==item['path']; result.append({'job_id':item['job_id'],'resolved':True})\n for bad in ['/etc/passwd','/home/lailai/.ssh/id_rsa','/tmp/private.out',str(Path(paths[0]['path']).parent.parent/'unapproved.out')]:\n  try:mod.resolve_stdout_path({'stdout':bad},127)\n  except mod.HTTPException as e:assert e.status_code==404\n  else:raise AssertionError('Outside policy accepted')\nprint(json.dumps({'positive':result,'negative_denials':4,'real_file_opens':0}))"
 p=cmd(['/home/lailai/slurm-portal/.venv/bin/python','-B','-c',code]) if (release/'job_output.py').is_file() and roots==m['output_roots'] else subprocess.CompletedProcess([],1,'','Expected deployed module or policy absent; production resolution check not executed');save('evidence/deployed-path-resolution.json',{'exit_code':p.returncode,'result':json.loads(p.stdout) if p.returncode==0 else None,'stderr':p.stderr});check('deployed_resolver_metadata_only_9_paths_4_denials',p.returncode==0)
 xmls=list((c/'raw').glob('rerun-*/portal-tests.xml'));t=E.parse(xmls[0]);check('sealed190_fixture_results',len(list(t.getroot().iter('testcase')))==190 and not list(t.getroot().iter('failure')) and not list(t.getroot().iter('error')));save('evidence/fixture-provenance.json',{'junit':str(xmls[0]),'rerun_now':False,'scope':'sealed isolated candidate cases; not a fresh production test','deployed_sources_match_tested_candidate':hashes==m['source_sha256']})
 j=cmd(['journalctl','-u','slurm-portal.service','--since',props['ExecMainStartTimestamp'],'--no-pager','-o','json']);records=[]
 for line in j.stdout.splitlines():
  try:records.append(json.loads(line))
  except ValueError:pass
 msgs=[x.get('MESSAGE','') for x in records if x.get('_PID')==str(pid)];markers=['Traceback (most recent call last)','ERROR','CRITICAL','Failed to start','Exception:'];errors={k:sum(k in x for x in msgs) for k in markers if any(k in x for x in msgs)};startup=any('Application startup complete' in x for x in msgs);save('evidence/startup-log-review.json',{'exit_code':j.returncode,'current_pid_records':len(msgs),'startup_complete':startup,'error_markers':errors,'sentinel_present':any(sentinel in x for x in msgs),'raw_logs_saved':False,'permission_notice':bool(j.stderr.strip())});check('startup_complete_no_errors',j.returncode==0 and startup and not errors);check('sentinel_not_in_reviewed_logs',not any(sentinel in x for x in msgs))
 check('pid_stable',cmd(['systemctl','show','slurm-portal.service','--property=MainPID','--value']).stdout.strip()==str(pid))
 failed=[x['name'] for x in checks if not x['passed']];result={'status':'FAILED' if failed else 'SUCCESS','scope':'read-only automated verification; authenticated browser acceptance pending','expected_version':m['version'],'actual_release_directory':str(release),'expected_release_directory':m['future_release'],'managed_pid':pid,'port8001_operations':len(ops(api)),'port8002_operations':len(ops(api2)),'checks_passed':len(checks)-len(failed),'checks_failed':failed,'rollback_backup':backup_info,'pending':['Owner lailai checks jobs 127/129: expect HTTP200 empty output if records/files remain current','Existing administrator/researcher login, controls, session/logout after deployment','Authenticated CSRF denial and researcher denial of administrator routes with approved non-job-mutating tests','Authorized existing standard-output job browser check if available'],'services_modified':False,'production_accounts_or_records_modified':False,'real_job_output_contents_read':False,'timestamp':datetime.datetime.now(datetime.timezone.utc).isoformat(),'evidence_directory':str(r)};save('result.json',result);print(json.dumps(result,indent=2))
except BaseException as e:
 save('verification-error.json',{'type':type(e).__name__,'message':str(e),'services_modified':False});print(json.dumps({'status':'FAILED','error_type':type(e).__name__,'evidence_directory':str(r)}));raise
