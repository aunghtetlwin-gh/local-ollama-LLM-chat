from pathlib import Path
import subprocess,json,hashlib
r=Path(Path('/tmp/nectec-chat-readiness-path.txt').read_text())
def get(args):
 p=subprocess.run(args,capture_output=True,text=True,timeout=20)
 if p.returncode:raise RuntimeError('Configuration inspection failed; raw output intentionally suppressed')
 return json.loads(p.stdout)
config=get(['docker','compose','-p','ollama-test','-f','/home/lailai/ollama-test/docker-compose.yml','config','--format','json']);checks={}
for svc,name in [('app','local-ollama-chat'),('db','ollama-chat-db')]:
 actual=get(['docker','inspect',name])[0];live=dict(v.split('=',1) for v in actual['Config']['Env'] if '=' in v);desired=config['services'][svc];env=desired.get('environment',{});different=[k for k,v in env.items() if live.get(k)!=str(v)]
 checks[svc]={'compose_service':svc,'environment_keys_compared':len(env),'changed_environment_keys':different,'all_compose_environment_values_match_live':not different,'image_reference_matches':desired.get('image')==actual['Config']['Image'],'container_name_matches':desired.get('container_name')==name,'network_mode':desired.get('network_mode'),'configured_volume_references':desired.get('volumes',[])}
checks['compose_project_name']=config.get('name');checks['volume_definition']=config.get('volumes',{});checks['credential_values_saved']=False;checks['production_changes']=False
(r/'compose-runtime-comparison.json').write_text(json.dumps(checks,indent=2)+'\n');print(json.dumps(checks,indent=2))
