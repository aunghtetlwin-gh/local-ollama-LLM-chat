from pathlib import Path
import subprocess,json,hashlib,datetime,secrets,urllib.request,urllib.error
import os
os.umask(0o077)
r=Path('/home/lailai/ollama-test/chat_deployment_readiness')/('readiness-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+secrets.token_hex(4));r.mkdir(parents=True,exist_ok=False);Path('/tmp/nectec-chat-readiness-path.txt').write_text(str(r))
def call(args):
 p=subprocess.run(args,capture_output=True,text=True,timeout=30)
 if p.returncode:raise RuntimeError('Read-only command failed: '+str(args[:2])+'; exit '+str(p.returncode))
 return p.stdout

def inspect(name):return json.loads(call(['docker','inspect',name]))[0]
def safe_container(d):
 env=dict(v.split('=',1) for v in d['Config'].get('Env',[]) if '=' in v)
 return {'id':d['Id'],'name':d['Name'],'image_id':d['Image'],'image_reference':d['Config']['Image'],'state':{'status':d['State']['Status'],'running':d['State']['Running'],'started':d['State']['StartedAt'],'restart_count':d.get('RestartCount'),'health_status':d['State'].get('Health',{}).get('Status'),'health_failing_streak':d['State'].get('Health',{}).get('FailingStreak')},'cmd':d['Config']['Cmd'],'entrypoint':d['Config']['Entrypoint'],'working_dir':d['Config']['WorkingDir'],'network_mode':d['HostConfig']['NetworkMode'],'port_bindings':d['HostConfig']['PortBindings'],'network_ports':d['NetworkSettings']['Ports'],'restart_policy':d['HostConfig']['RestartPolicy'],'mounts':[{'type':x['Type'],'name':x.get('Name'),'source':x['Source'],'destination':x['Destination'],'rw':x['RW']} for x in d['Mounts']],'compose_labels':{k:v for k,v in (d['Config'].get('Labels') or {}).items() if k in ['com.docker.compose.project','com.docker.compose.service','com.docker.compose.project.config_files','com.docker.compose.project.working_dir','com.docker.compose.config-hash']},'selected_env':{k:env[k] for k in ['DB_HOST','DB_PORT','SESSION_COOKIE_SECURE','SESSION_TTL_SECONDS','FORWARDED_ALLOW_IPS'] if k in env},'credential_variable_presence_only':{k:k in env for k in ['DB_NAME','DB_USER','DB_PASSWORD','POSTGRES_DB','POSTGRES_USER','POSTGRES_PASSWORD']}}
a=inspect('local-ollama-chat');db=inspect('ollama-chat-db');image=json.loads(call(['docker','image','inspect',a['Image']]))[0]
code="import sys,json,hashlib,importlib.metadata; from pathlib import Path; p=Path('/app'); names=['server.py','auth.py','database.py','migrate.py','index.html','login.html','register.html','requirements.txt']; files={n:hashlib.sha256((p/n).read_bytes()).hexdigest() for n in names if (p/n).is_file()}; files.update({str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted((p/'migrations').rglob('*.sql'))}); print(json.dumps({'python':sys.version,'packages':{d.metadata['Name'].lower().replace('_','-'):d.version for d in importlib.metadata.distributions()},'files_sha256':files}))"
current=json.loads(call(['docker','exec','local-ollama-chat','python','-B','-c',code]));expected=json.loads(Path('/home/lailai/ollama-test/deployment_readiness/readiness-20261104T174239Z-c87c014c/evidence/chat-runtime-packages.json').read_text());prior=json.loads(Path('/home/lailai/ollama-test/deployment_readiness/readiness-20261104T174239Z-c87c014c/evidence/chat-container.json').read_text());diff=call(['docker','diff','local-ollama-chat'])
health={}
for route in ['/health','/openapi.json']:
 try:
  with urllib.request.urlopen('http://127.0.0.1:8000'+route,timeout=10) as f:
   data=json.load(f);health[route]={'status':f.status}
   if route=='/health':health[route]['body']=data
   else:health[route]['operations']=[{'method':k,'path':p} for p,v in data['paths'].items() for k in v if k in ['get','post','delete','put','patch']]
 except urllib.error.HTTPError as e:health[route]={'status':e.code}
files={n:hashlib.sha256((Path('/home/lailai/ollama-test')/n).read_bytes()).hexdigest() for n in current['files_sha256'] if (Path('/home/lailai/ollama-test')/n).is_file()}
volumes=[]
for mount in db['Mounts']:
 if mount['Type']=='volume':
  v=json.loads(call(['docker','volume','inspect',mount['Name']]))[0];volumes.append({k:v.get(k) for k in ['Name','Driver','Mountpoint','Scope','Labels']})
seals={}
for root in [Path('/home/lailai/ollama-test/security_remediation/remediation-20261104T111222Z-e4089eae'),Path('/home/lailai/ollama-test/deployment_readiness/readiness-20261104T174239Z-c87c014c')]:
 entries=json.loads((root/'FILES_SHA256.json').read_text());ok=all(hashlib.sha256((root/n).read_bytes()).hexdigest()==h for n,h in entries.items());seals[str(root)]={'files_verified':len(entries),'matches':ok}
out={'timestamp':datetime.datetime.now(datetime.timezone.utc).isoformat(),'app':safe_container(a),'database':safe_container(db),'image':{k:image.get(k) for k in ['Id','RepoTags','RepoDigests','Created','Architecture','Os']},'runtime':current,'live_files_match_workspace':files==current['files_sha256'],'workspace_hashes':files,'python_matches_tested':current['python']==expected['python'],'all_recorded_packages_match':all(current['packages'].get(k)==v for k,v in expected['packages'].items()),'image_matches_tested':a['Image']==prior['image_id'],'container_same_as_prior':a['Id']==prior['id'],'container_filesystem_diff':diff,'health':health,'volumes':volumes,'compose_file_sha256':hashlib.sha256(Path('/home/lailai/ollama-test/docker-compose.yml').read_bytes()).hexdigest(),'dockerfile_sha256':hashlib.sha256(Path('/home/lailai/ollama-test/Dockerfile').read_bytes()).hexdigest(),'sealed_evidence':seals,'docker_version':call(['docker','version','--format','{{.Server.Version}}']).strip(),'compose_version':call(['docker','compose','version','--short']).strip(),'database_queries_performed':False,'inference_requests':False,'production_changes':False}
(r/'inventory.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({'directory':str(r),'app':out['app'],'database':out['database'],'image':out['image'],'matches':{k:out[k] for k in ['live_files_match_workspace','python_matches_tested','all_recorded_packages_match','image_matches_tested','container_same_as_prior']},'health':health,'seals':seals},indent=2))
