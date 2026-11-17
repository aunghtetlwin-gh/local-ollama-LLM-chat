from pathlib import Path
import subprocess,json,datetime,os,hashlib,shutil,re,time
os.umask(0o077)
r=Path(Path('/tmp/nectec-chat-deployment-path.txt').read_text());c=Path('/home/lailai/ollama-test/chat_image_candidates/origin-20261109T060037Z-4f0fba1d');m=json.loads((c/'candidate_manifest.json').read_text());pre=json.loads((r/'preflight.json').read_text());start=datetime.datetime.fromisoformat('2026-11-09T15:00:00+07:00');end=datetime.datetime.fromisoformat('2026-11-09T15:30:00+07:00');state={'status':'PARTIAL','phase':'pre-activation','maintenance_start':start.isoformat(),'maintenance_end':end.isoformat(),'production_recreation_attempted':False};private=r/'private';private.mkdir(mode=0o700,exist_ok=False)
def save(): (r/'deployment-state.json').write_text(json.dumps(state,indent=2)+'\n')
def run(a,timeout=30):
 p=subprocess.run(a,capture_output=True,text=True,timeout=timeout)
 if p.returncode:raise RuntimeError('Command failed: '+str(a[:2])+' exit '+str(p.returncode))
 return p.stdout

def inspect(name):return json.loads(run(['docker','inspect',name]))[0]
def window():
 now=datetime.datetime.now(datetime.timezone.utc)
 if not start<=now<end:raise RuntimeError('Maintenance window not current; no activation permitted')
 if (end-now).total_seconds()<120:raise RuntimeError('Less than two minutes remain for activation/verification; stop')
 return now.isoformat()

def proc_snapshot():
 result={}
 for pid in [2610502,2019096]:
  p=Path('/proc')/str(pid);result[str(pid)]={'present':p.exists()}
  if p.exists():result[str(pid)]['start_ticks']=(p/'stat').read_text().split(') ',1)[1].split()[19]
 return result

def no_activity():
 p=subprocess.run(['ss','-Htn','state','established'],capture_output=True,text=True);assert p.returncode==0,'Cannot inspect current activity';connections=[x for x in p.stdout.splitlines() if ':8000 ' in x or x.endswith(':8000')]
 if connections:raise RuntimeError('Chat connections resumed; activation stopped')
 p=subprocess.run(['docker','logs','--since','2m','--tail','200','local-ollama-chat'],capture_output=True,text=True);assert p.returncode==0,'Cannot inspect recent chat requests'
 if re.search(r'"(?:GET|POST|PUT|PATCH|DELETE) [^ ]+ HTTP/[^\"]+" \d+',p.stdout+'\n'+p.stderr):raise RuntimeError('Recent chat request activity resumed; activation stopped')
try:
 state['window_checked_at']=window();save();assert all(pre['checks'].values());assert all(hashlib.sha256((c/n).read_bytes()).hexdigest()==h for n,h in json.loads((c/'FILES_SHA256.json').read_text()).items())
 a=inspect('local-ollama-chat');db=inspect('ollama-chat-db');assert a['Id']==m['production_container_id'] and a['Image']==m['base_image_id'];assert db['Id']==m['database_container_id'] and db['Image']==m['database_image_id'];assert db['State']['Health']['Status']=='healthy';assert inspect(m['candidate_tag'])['Id']==m['candidate_image_id'];assert inspect(m['rollback_tag'])['Id']==m['base_image_id'];assert run(['docker','diff','local-ollama-chat']).strip()=='';no_activity()
 base=['docker','compose','-p','ollama-test','-f','/home/lailai/ollama-test/docker-compose.yml'];cfg=json.loads(run(base+['-f',str(c/'config/compose.security.yml'),'config','--format','json']));appenv=dict(x.split('=',1) for x in a['Config']['Env'] if '=' in x);dbenv=dict(x.split('=',1) for x in db['Config']['Env'] if '=' in x);assert all(appenv.get(k)==str(v) for k,v in cfg['services']['app']['environment'].items());assert all(dbenv.get(k)==str(v) for k,v in cfg['services']['db']['environment'].items());assert cfg['services']['app']['image']==m['candidate_tag'];assert any(x.get('Name')==m['database_volume'] for x in db['Mounts'])
 # Private operational backups contain secrets. Never print or publish their contents.
 (private/'app-inspect-before.json').write_text(json.dumps(a,indent=2)+'\n');(private/'database-inspect-before.json').write_text(json.dumps(db,indent=2)+'\n');(private/'resolved-compose-before.json').write_text(json.dumps(cfg,indent=2)+'\n');shutil.copyfile('/home/lailai/ollama-test/.env',private/'environment.backup');shutil.copyfile('/home/lailai/ollama-test/docker-compose.yml',private/'docker-compose.before.yml');shutil.copyfile(c/'config/compose.security.yml',private/'compose.security.yml');shutil.copyfile(c/'config/compose.rollback.yml',private/'compose.rollback.yml')
 portals_before=proc_snapshot();state.update(private_backups_created=True,old_app_id=a['Id'],old_image_id=a['Image'],database_id=db['Id'],database_started=db['State']['StartedAt'],portal_processes_before=portals_before);state['activation_time']=window();no_activity();save()
 args=base+['-f',str(c/'config/compose.security.yml'),'up','-d','--no-deps','--no-build','--pull','never','--force-recreate','app'];(r/'activation-command.json').write_text(json.dumps({'argv':args,'timestamp':state['activation_time']},indent=2)+'\n');state['production_recreation_attempted']=True;state['phase']='activating-app-only';save();p=subprocess.run(args,capture_output=True,text=True,timeout=90);(r/'activation.log').write_text(p.stdout+'\n'+p.stderr);state['compose_exit_code']=p.returncode;save();assert p.returncode==0,'Reviewed Compose activation failed; preserve logs and stop'
 new=inspect('local-ollama-chat');newdb=inspect('ollama-chat-db');newenv=dict(x.split('=',1) for x in new['Config']['Env'] if '=' in x);portal_after=proc_snapshot();preservation={'app_new_id':new['Id'],'new_image_id':new['Image'],'expected_image':new['Image']==m['candidate_image_id'],'new_app_running':new['State']['Running'],'app_env_identical':newenv==appenv,'network_unchanged':new['HostConfig']['NetworkMode']==a['HostConfig']['NetworkMode'],'database_id_unchanged':newdb['Id']==db['Id'],'database_image_unchanged':newdb['Image']==db['Image'],'database_start_time_unchanged':newdb['State']['StartedAt']==db['State']['StartedAt'],'database_mounts_unchanged':newdb['Mounts']==db['Mounts'],'portal_processes_unchanged':portal_after==portals_before,'portal_processes_after':portal_after};(r/'activation-preservation.json').write_text(json.dumps(preservation,indent=2)+'\n');assert all(v for k,v in preservation.items() if isinstance(v,bool)), 'Post-activation identity/preservation mismatch; stop for review'
 state.update(status='PARTIAL',phase='activated-awaiting-http-verification',new_app_id=new['Id'],new_image_id=new['Image'],activation_finished=datetime.datetime.now(datetime.timezone.utc).isoformat());save();print(json.dumps({'status':'PARTIAL','phase':state['phase'],'evidence_directory':str(r),'new_app_id':new['Id'],'new_image_id':new['Image'],'activation_time':state['activation_time'],'database_unchanged':preservation['database_id_unchanged'] and preservation['database_start_time_unchanged'] and preservation['database_mounts_unchanged'],'portals_unchanged':preservation['portal_processes_unchanged']},indent=2))
except BaseException as e:
 state.update(status='FAILED' if state['production_recreation_attempted'] else 'BLOCKED',phase='stopped',error_type=type(e).__name__,error=str(e),stopped_at=datetime.datetime.now(datetime.timezone.utc).isoformat());save();print(json.dumps({k:v for k,v in state.items() if k not in ['portal_processes_before']},indent=2));raise
