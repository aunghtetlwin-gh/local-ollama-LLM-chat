from pathlib import Path
import subprocess,json,os,datetime,hashlib,time,re
r=Path(Path('/tmp/nectec-chat-image-path.txt').read_text());plan=json.loads((r/'plan.json').read_text());prior=json.loads((Path(plan['readiness'])/'inventory.json').read_text())
def command(name,args,timeout=30):
 p=subprocess.run(args,capture_output=True,text=True,timeout=timeout);record={'argv':args,'exit_code':p.returncode,'started_or_recorded':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 (r/'raw'/f'{name}-command.json').write_text(json.dumps(record,indent=2)+'\n')
 if p.returncode:raise RuntimeError(name+' failed with exit '+str(p.returncode))
 return p.stdout

def inspect(name):return json.loads(subprocess.check_output(['docker','inspect',name],text=True))[0]
a=inspect('local-ollama-chat');db=inspect('ollama-chat-db');assert a['Id']==plan['production_container_id'] and a['Image']==plan['base_image_id'];assert db['Id']==plan['database_container_id'] and db['Image']==plan['database_image_id'];assert a['State']['Running'] and db['State']['Health']['Status']=='healthy';assert db['Mounts'][0]['Name']==plan['database_volume'];assert a['State']['StartedAt']==prior['app']['state']['started'];assert hashlib.sha256(Path('/home/lailai/ollama-test/docker-compose.yml').read_bytes()).hexdigest()==prior['compose_file_sha256']
metadata_code="import sys,json,hashlib,importlib.metadata; from pathlib import Path; names="+repr(list(prior['runtime']['files_sha256']))+"; print(json.dumps({'python':sys.version,'packages':{d.metadata['Name'].lower().replace('_','-'):d.version for d in importlib.metadata.distributions()},'files_sha256':{n:hashlib.sha256((Path('/app')/n).read_bytes()).hexdigest() for n in names}}))"
live=json.loads(command('live-runtime',['docker','exec','local-ollama-chat','python','-B','-c',metadata_code]));assert live==prior['runtime'];assert command('production-diff',['docker','diff','local-ollama-chat']).strip()==''
activity=[]
for i in range(3):
 p=subprocess.run(['ss','-Htn','state','established'],capture_output=True,text=True);lines=[line for line in p.stdout.splitlines() if ':8000 ' in line or line.endswith(':8000')];activity.append({'timestamp':datetime.datetime.now(datetime.timezone.utc).isoformat(),'ss_exit':p.returncode,'chat_connections':lines});time.sleep(1 if i<2 else 0)
p=subprocess.run(['docker','logs','--since','10m','--tail','200','local-ollama-chat'],capture_output=True,text=True);events=[]
for line in (p.stdout+'\n'+p.stderr).splitlines():
 match=re.search(r'"(GET|POST|PUT|PATCH|DELETE) ([^ ?]+)(?:\?[^ ]*)? HTTP/[^\"]+" (\d+)',line)
 if match:events.append({'method':match[1],'path':match[2],'status':int(match[3])})
(r/'evidence/activity.json').write_text(json.dumps({'samples':activity,'recent_http_events':events,'logs_exit':p.returncode,'raw_logs_saved':False,'headerless_client_detection':'Origin/Referer are not recorded in access logs; cannot prove no such clients','streaming_completion':'socket samples and access-log status do not prove no in-flight/idle clients; operator drain still required'},indent=2)+'\n')
(r/'evidence/preflight.json').write_text(json.dumps({'live_runtime':live,'production_container':{'id':a['Id'],'image':a['Image'],'started':a['State']['StartedAt']},'database':{'id':db['Id'],'image':db['Image'],'started':db['State']['StartedAt'],'volume':db['Mounts'][0]['Name'],'healthy':True},'compose_hash_matches':True},indent=2)+'\n')
for tag in [plan['candidate_tag'],plan['rollback_tag']]:
 probe=subprocess.run(['docker','image','inspect',tag],capture_output=True)
 assert probe.returncode!=0,'Unique image tag already exists'
command('retain-base',['docker','tag',plan['base_image_id'],plan['rollback_tag']]);base=json.loads(command('base-image',['docker','image','inspect',plan['rollback_tag']]))[0];assert base['Id']==plan['base_image_id']
args=['docker','build','--pull=false','--network=none','-t',plan['candidate_tag'],str(r/'context')];start=datetime.datetime.now(datetime.timezone.utc).isoformat();p=subprocess.run(args,capture_output=True,text=True,timeout=180);(r/'raw/build.log').write_text(p.stdout+'\n'+p.stderr);(r/'raw/build-command.json').write_text(json.dumps({'argv':args,'exit_code':p.returncode,'started':start,'ended':datetime.datetime.now(datetime.timezone.utc).isoformat()},indent=2)+'\n');assert p.returncode==0,'Build failed: see preserved log'
image=json.loads(command('candidate-image',['docker','image','inspect',plan['candidate_tag']]))[0];assert image['RootFS']['Layers'][:-1]==base['RootFS']['Layers'];assert len(image['RootFS']['Layers'])==len(base['RootFS']['Layers'])+1
configfields=['Env','Cmd','Entrypoint','User','WorkingDir','ExposedPorts','Volumes','Healthcheck','StopSignal'];configmatches={k:image['Config'].get(k)==base['Config'].get(k) for k in configfields};assert all(configmatches.values())
args=['docker','run','--rm','--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges','--entrypoint','python',image['Id'],'-B','-c',metadata_code];new=json.loads(command('candidate-runtime',args));expected=json.loads(json.dumps(live));expected['files_sha256']['server.py']=plan['patched_server_sha256'];assert new==expected
result={'candidate_tag':plan['candidate_tag'],'candidate_image_id':image['Id'],'rollback_tag':plan['rollback_tag'],'rollback_image_id':base['Id'],'runtime':new,'image_configuration_unchanged':configmatches,'base_layers_preserved':True,'one_new_copy_layer':True,'only_expected_app_file_hash_changed':'server.py','production_container_unchanged':inspect('local-ollama-chat')['Id']==a['Id'],'database_container_unchanged':inspect('ollama-chat-db')['Id']==db['Id']};(r/'evidence/image-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='runtime'},indent=2))
