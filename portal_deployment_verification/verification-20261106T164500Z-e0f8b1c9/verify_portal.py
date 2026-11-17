"""Post-deployment verification ONLY. No service writes, database queries or real login."""
import hashlib,json,os,secrets,subprocess,time,urllib.error,urllib.request
from datetime import datetime,timezone
from pathlib import Path
os.umask(0o077)
prepared=Path('/home/lailai/nectec-changes/portal-security-20261106T125653Z-30beac16');m=json.loads((prepared/'release_manifest.json').read_text());release=Path(m['release_directory']);root=Path('/home/lailai/ollama-test/portal_deployment_verification')/('verification-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+secrets.token_hex(4));root.mkdir(parents=True,exist_ok=False);(root/'evidence').mkdir();checks=[];pending=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(name,value):(root/name).write_text(json.dumps(value,indent=2)+'\n')
def command(args,timeout=15):
 p=subprocess.run(args,text=True,capture_output=True,timeout=timeout)
 if p.returncode:raise RuntimeError('Read-only command failed: '+str(args)+' '+p.stderr.strip())
 return p.stdout

def check(name,passed,**details):checks.append({'check':name,'passed':bool(passed),'epoch':time.time(),**details});save('acceptance.json',checks)
def request(method,path,payload=None,headers=None,port=8001):
 data=json.dumps(payload).encode() if payload is not None else None;h={'Content-Type':'application/json','User-Agent':'NECTEC-read-only-postdeployment-verification'};h.update(headers or {});req=urllib.request.Request(f'http://127.0.0.1:{port}'+path,data=data,headers=h,method=method)
 try:
  with urllib.request.urlopen(req,timeout=5) as response:return response.status,response.read()
 except urllib.error.HTTPError as exc:return exc.code,exc.read()

def operations(api):return {(verb,path) for path,methods in api['paths'].items() for verb in methods if verb in ['get','post','put','patch','delete','head','options']}
start=time.time();save('verification-plan.json',{'started_epoch':start,'prepared_release':str(prepared),'version':m['version'],'scope':'read-only service/source metadata and unauthenticated/invalid-session API checks; no real credentials, account writes, jobs or inference','mutating_privileged_commands':[]})
try:
 raw=command(['systemctl','show','slurm-portal.service','--property=MainPID,User,Group,WorkingDirectory,FragmentPath,DropInPaths,NeedDaemonReload,ActiveState,SubState,Result,ExecMainStatus,ExecMainStartTimestamp,ExecMainStartTimestampMonotonic,NRestarts']);props=dict(line.split('=',1) for line in raw.splitlines() if '=' in line);save('evidence/systemd-properties.json',props)
 check('managed_service_active_healthy',props['ActiveState']=='active' and props['SubState']=='running' and props['Result']=='success' and props['NRestarts']=='0',pid=int(props['MainPID']),n_restarts=props['NRestarts'])
 check('effective_working_directory',props['WorkingDirectory']==str(release))
 check('service_identity_and_reload_state',props['User']=='lailai' and props['Group']=='lailai' and props['NeedDaemonReload']=='no')
 dropin=Path('/etc/systemd/system/slurm-portal.service.d/90-nectec-security-30beac16.conf');check('approved_dropin_exact_bytes',props['DropInPaths']==str(dropin) and dropin.is_file() and sha(dropin)==sha(prepared/'portal-release.conf'),sha256=sha(dropin) if dropin.is_file() else None)
 pid=int(props['MainPID']);p=Path('/proc')/str(pid);args=[x.decode(errors='replace') for x in (p/'cmdline').read_bytes().split(b'\0') if x];selected={}
 for field in (p/'environ').read_bytes().split(b'\0'):
  key,_,value=field.partition(b'=')
  if key in [b'PORTAL_AUTH_DB',b'PORTAL_COOKIE_SECURE']:selected[key.decode()]=value.decode(errors='replace')
 proc={'pid':pid,'cwd':os.readlink(p/'cwd'),'argv':args,'selected_environment':selected,'start_ticks':(p/'stat').read_text().split(') ',1)[1].split()[19]};save('evidence/running-process.json',proc)
 check('running_process_uses_release_and_localhost8001',proc['cwd']==str(release) and args[-4:]==['--host','127.0.0.1','--port','8001'] and '--reload' not in args)
 check('original_authentication_database_path',selected.get('PORTAL_AUTH_DB')==m['database_location'] and Path(m['database_location']).is_file(),database_location=m['database_location'])
 hashes={name:sha(release/name) for name in m['release_files_sha256']};save('evidence/deployed-source-hashes.json',{'version':m['version'],'directory':str(release),'sha256':hashes});check('deployed_sources_match_reviewed_manifest',hashes==m['release_files_sha256'])
 code,body=request('GET','/openapi.json');api=json.loads(body);save('evidence/openapi-8001.json',api);expected=json.loads((prepared/'evidence/openapi-before-8002.json').read_text());check('expected_authenticated16_operations',code==200 and operations(api)==operations(expected) and len(operations(api))==16,operations=len(operations(api)))
 for verb,path in [('post','/jobs'),('post','/jobs/{job_id}/cancel'),('post','/jobs/{job_id}/requeue'),('post','/auth/logout'),('post','/admin/users'),('patch','/admin/users/{username}/status')]:
  params={(x.get('in'),x.get('name')) for x in api['paths'].get(path,{}).get(verb,{}).get('parameters',[])};check('csrf_and_session_route_metadata:'+verb+path,('cookie','portal_session') in params and ('header','x-portal-csrf') in params)
 sentinel='SYNTHETIC-REDACTION-'+secrets.token_hex(12)
 for label,payload in [('missing_username',{'password':sentinel}),('invalid_username_type',{'username':[],'password':sentinel})]:
  code,body=request('POST','/auth/login',payload);check('password_redaction:'+label,code==422 and sentinel.encode() not in body and json.loads(body)=={'detail':'Invalid request fields.'},status=code)
 for path in ['/auth/me','/admin/users','/jobs/active','/jobs/history','/cluster/node']:
  code,body=request('GET',path);check('unauthenticated_denied:'+path,code==401,status=code)
 code,body=request('GET','/auth/me',headers={'Cookie':'portal_session=SYNTHETIC-INVALID-SESSION'});check('invalid_session_denied',code==401,status=code)
 for label,h in [('missing_csrf',{}),('invalid_csrf',{'X-Portal-CSRF':'SYNTHETIC-INVALID-CSRF'})]:
  code,body=request('POST','/auth/logout',headers=h);check('anonymous_logout_denied:'+label,code==401,status=code)
 # These tests do not claim authenticated CSRF/role functionality; no real session is used.
 pending.extend(['Owner performs normal login/session/logout through actual browser/SSH forward','Authenticated missing/invalid CSRF must return403 and preserve session','Researcher administrator access must return403; authorized administrator read access must work','Owner-scoped read/list behavior with explicitly designated authorized test resources; no job mutations'])
 old=json.loads((prepared/'evidence/fallback-before.json').read_text());fp=Path('/proc')/str(old['pid']);fallback={'pid':old['pid'],'cwd':os.readlink(fp/'cwd'),'argv':[x.decode(errors='replace') for x in (fp/'cmdline').read_bytes().split(b'\0') if x],'start_ticks':(fp/'stat').read_text().split(') ',1)[1].split()[19]};save('evidence/fallback-process.json',fallback)
 check('fallback8002_same_process',fallback['cwd']==old['cwd'] and fallback['argv']==old['argv'] and fallback['start_ticks']==old['proc_stat'].split(') ',1)[1].split()[19])
 code,body=request('GET','/openapi.json',port=8002);oldapi=json.loads(body);save('evidence/openapi-8002.json',oldapi);check('fallback8002_healthy_unchanged_api',code==200 and hashlib.sha256(json.dumps(oldapi,sort_keys=True).encode()).hexdigest()==json.loads((prepared/'evidence/api-before-8002.json').read_text())['canonical_sha256'],operations=len(operations(oldapi)))
 check('original_source_frontend_and_base_unit_unchanged',all(sha(Path(name))==h for name,h in m['original_files_sha256'].items()))
 # Inspect startup logs without printing or retaining raw messages/cookies/credentials.
 since=props['ExecMainStartTimestamp'];until=datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S');argv=['journalctl','-u','slurm-portal.service','--since',since,'--until',until,'--no-pager','-o','json'];j=subprocess.run(argv,text=True,capture_output=True,timeout=15);records=[]
 for line in j.stdout.splitlines():
  try:records.append(json.loads(line))
  except ValueError:pass
 own=[x for x in records if x.get('_PID')==str(pid)];messages=[x.get('MESSAGE','') for x in own];markers=['Traceback (most recent call last)','ERROR','CRITICAL','Failed to start','Exception:'];errors=[{'marker':marker,'count':sum(marker in msg for msg in messages)} for marker in markers if any(marker in msg for msg in messages)]
 startup=any('Application startup complete' in msg for msg in messages)
 review={'argv':argv,'exit_code':j.returncode,'raw_messages_saved':False,'journal_stdout_sha256':hashlib.sha256(j.stdout.encode()).hexdigest(),'service_records':len(records),'current_pid_records':len(own),'startup_complete_observed':startup,'error_markers':errors,'synthetic_sentinel_present':any(sentinel in msg for msg in messages),'log_permission_notice_present':bool(j.stderr.strip())};save('evidence/startup-log-review.json',review)
 if j.returncode==0 and own:
  check('startup_logs_no_error_markers',not errors,current_pid_records=len(own),startup_complete_observed=startup);check('password_sentinel_absent_from_reviewed_logs',not review['synthetic_sentinel_present'])
  if not startup:pending.append('Operator confirms complete startup journal; reviewed records did not include startup-complete marker')
 else:pending.append('Operator reviews startup journal; current execution identity could not obtain sufficient records')
 time.sleep(3);newpid=command(['systemctl','show','slurm-portal.service','--property=MainPID','--value']).strip();state=command(['systemctl','is-active','slurm-portal.service']).strip();check('service_remains_stable',newpid==str(pid) and state=='active')
 seals={}
 for base in [Path(m['source_package']),Path(m['readiness_package'])]:seals[str(base)]=all(sha(base/name)==h for name,h in json.loads((base/'FILES_SHA256.json').read_text()).items())
 check('sealed_remediation_and_readiness_unchanged',all(seals.values()));save('evidence/seal-verification.json',seals)
 status='FAILED' if any(not x['passed'] for x in checks) else 'PARTIAL' if not (j.returncode==0 and own and startup) else 'SUCCESS'
 result={'status':status,'scope':'automated non-destructive post-deployment verification; authenticated browser acceptance remains pending','version':m['version'],'release_directory':str(release),'managed_pid':pid,'port8001_operations':len(operations(api)),'fallback_pid':old['pid'],'port8002_operations':len(operations(oldapi)),'checks_passed':sum(x['passed'] for x in checks),'checks_failed':sum(not x['passed'] for x in checks),'pending_browser_or_operator_checks':pending,'started_epoch':start,'finished_epoch':time.time(),'services_restarted_or_modified':False,'accounts_or_database_modified_by_verification':False,'real_login_or_tokens_used':False,'job_actions_or_inference':False,'evidence_directory':str(root)};save('result.json',result)
 (root/'REPORT.md').write_text('# Portal post-deployment verification\n\nStatus: '+status+'. Automated read-only/non-destructive scope only; authenticated browser acceptance remains pending.\n\nRelease: '+m['version']+'\n\nPort8001: active PID'+str(pid)+', expected16 operations, prepared source hashes and original authentication DB path verified. Port8002: unchanged PID'+str(old['pid'])+',16 operations and matching API fingerprint.\n\nChecks passed: '+str(result['checks_passed'])+'; failed: '+str(result['checks_failed'])+'. See acceptance.json for exact cases. Password sentinel values, cookie/session tokens and raw journal messages were not recorded.\n\nPending:\n\n'+''.join('- '+x+'\n' for x in pending)+'\nNo restart, configuration/database/account change, live job action, GPU workload or inference was performed. Read-only API calls naturally append access logs.\n')
 print(json.dumps(result,indent=2))
except BaseException as exc:
 save('verification-error.json',{'error_type':type(exc).__name__,'message':str(exc),'epoch':time.time(),'no_remediation_or_restart_attempted':True});print(json.dumps({'status':'FAILED','evidence_directory':str(root),'error_type':type(exc).__name__,'message':str(exc)}));raise
finally:
 Path('/tmp/nectec-portal-postverify-path.txt').write_text(str(root)+'\n')
