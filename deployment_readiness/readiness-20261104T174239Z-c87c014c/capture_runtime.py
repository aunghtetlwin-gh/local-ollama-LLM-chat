"""Read-only deployment metadata; credentials and private resources deliberately excluded."""
import ast,hashlib,json,os,re,shlex,stat,subprocess,sys,time,urllib.request
from pathlib import Path
r=Path(Path('/tmp/nectec-readiness-path.txt').read_text().strip())
def save(name,value):(r/name).write_text(json.dumps(value,indent=2)+'\n')
def command(args,timeout=20):
 p=subprocess.run(args,capture_output=True,text=True,timeout=timeout);return {'argv':args,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
meta={'epoch':time.time(),'hostname':command(['hostname'])['stdout'].strip(),'date':command(['date','-Is'])['stdout'].strip(),'services':{},'processes':[],'ports':{}}
for unit in ['slurm-portal.service','cloudflared.service','ollama.service']:
 result=command(['systemctl','show',unit,'--property=MainPID,User,Group,WorkingDirectory,FragmentPath,ActiveState,SubState,Restart,ExecMainStartTimestamp']);meta['services'][unit]=result
for folder in Path('/proc').glob('[0-9]*'):
 try:
  name=(folder/'comm').read_text().strip()
  if name not in ['uvicorn','cloudflared']:continue
  args=[s.decode(errors='replace') for s in (folder/'cmdline').read_bytes().split(b'\0') if s];row={'pid':int(folder.name),'comm':name}
  if name=='uvicorn':row['argv']=args
  else:
   row['launch_flags_present']={k:k in args for k in ['--token-file','--token','--config','run','--url']}
   row['safe_options']={k:args[args.index(k)+1] for k in ['--config','--token-file'] if k in args}
  for attr in ['cwd','exe']:
   try:row[attr]=os.readlink(folder/attr)
   except OSError as e:row[attr]=type(e).__name__
  meta['processes'].append(row)
 except OSError:pass
for port in [8000,8001,8002]:
 with urllib.request.urlopen(f'http://127.0.0.1:{port}/openapi.json',timeout=5) as response:data=json.load(response)
 save(f'raw/openapi-{port}.json',data)
 operations=[]
 for path,methods in data['paths'].items():
  for verb,operation in methods.items():
   if verb not in ['get','post','put','patch','delete','head','options']:continue
   operations.append({'method':verb.upper(),'path':path,'operation_id':operation.get('operationId'),'parameters':[{'in':p.get('in'),'name':p.get('name'),'required':p.get('required')} for p in operation.get('parameters',[])],'security':operation.get('security',[])})
 meta['ports'][str(port)]={'info':data.get('info'),'operations':operations}
meta['listeners']=command(['ss','-ltnp']);save('evidence/runtime.json',meta)
freeze_code="import importlib.metadata,json,sys; print(json.dumps({'python':sys.version,'prefix':sys.prefix,'packages':{d.metadata['Name'].lower().replace('_','-'):d.version for d in importlib.metadata.distributions()}}))"
p=command(['/home/lailai/slurm-portal/.venv/bin/python','-c',freeze_code]);assert p['exit_code']==0;save('evidence/portal-runtime-packages.json',json.loads(p['stdout']))
p=command(['docker','exec','local-ollama-chat','python','-c',freeze_code]);assert p['exit_code']==0;save('evidence/chat-runtime-packages.json',json.loads(p['stdout']))
info=json.loads(command(['docker','inspect','local-ollama-chat'])['stdout'])[0]
container={'id':info['Id'],'image_id':info['Image'],'started':info['State']['StartedAt'],'working_dir':info['Config']['WorkingDir'],'cmd':info['Config']['Cmd'],'entrypoint':info['Config']['Entrypoint'],'mounts':info['Mounts'],'network_mode':info['HostConfig']['NetworkMode'],'compose':{k:v for k,v in info['Config']['Labels'].items() if k in ['com.docker.compose.project','com.docker.compose.service','com.docker.compose.project.working_dir','com.docker.compose.project.config_files']},'selected_env':{x.split('=',1)[0]:x.split('=',1)[1] for x in info['Config']['Env'] if x.split('=',1)[0] in ['SESSION_COOKIE_SECURE','SESSION_TTL_SECONDS','FORWARDED_ALLOW_IPS','DB_HOST','DB_PORT']},'filesystem_diff':command(['docker','diff','local-ollama-chat'])}
save('evidence/chat-container.json',container)
# Read-only export of installed packages into NEW staging storage, no image/container modification.
p=command(['docker','cp','local-ollama-chat:/usr/local/lib/python3.10/site-packages',str(r/'exports/chat-site-packages')],timeout=60);save('raw/chat-package-export.json',p);assert p['exit_code']==0
# No token/cert content is read; obtain identifiers from sanitized journal fields only.
cloud={'credential_values_read':False,'remote_api_called':False,'management_tools_available':False,'journal':[],'local_configuration':[],'management_credentials_presence':{k:k in os.environ for k in ['CLOUDFLARE_API_TOKEN','CF_API_TOKEN','CLOUDFLARE_ACCOUNT_ID']}}
for pattern in ['Starting tunnel','Updated to new configuration']:
 p=command(['journalctl','-u','cloudflared.service','--grep',pattern,'-n','10','--no-pager','-o','cat']);row={'argv':p['argv'],'exit_code':p['exit_code'],'tunnel_ids':sorted(set(re.findall(r'tunnelID=([0-9a-fA-F-]{36})',p['stdout']))),'ingress':[]}
 for line in p['stdout'].splitlines():
  if 'config=' not in line:continue
  try:
   item=next(x for x in shlex.split(line) if x.startswith('config='));cfg=json.loads(item[7:]);row['ingress'] += [{'hostname':x.get('hostname'),'path':x.get('path'),'service':x.get('service'),'originRequest':{k:v for k,v in x.get('originRequest',{}).items() if k in ['httpHostHeader','originServerName','noTLSVerify','http2Origin']}} for x in cfg.get('ingress',[])]
  except (ValueError,StopIteration):row['parse_unavailable']=True
 cloud['journal'].append(row)
for base in [Path('/etc/cloudflared'),Path('/home/lailai/.cloudflared')]:
 try:
  for path in base.iterdir():
   entry={'path':str(path),'bytes':path.stat().st_size,'mode':oct(stat.S_IMODE(path.stat().st_mode)),'content_read':False}
   if path.suffix in ['.yml','.yaml']:
    # Retain only routing keys; never credential/tunnel-token configuration values.
    entry['routing_lines']=[x for x in path.read_text().splitlines() if any(k in x for k in ['hostname:','service:','httpHostHeader:','originServerName:','noTLSVerify:'])];entry['content_read']='routing keys only saved'
   cloud['local_configuration'].append(entry)
 except OSError as e:cloud['local_configuration'].append({'path':str(base),'unavailable':type(e).__name__})
save('evidence/cloudflare.json',cloud)
notes=[]
for path in [Path('/home/lailai/slurm-portal/note.coffee'),Path('/etc/systemd/system/slurm-portal.service')]:
 for index,line in enumerate(path.read_text().splitlines(),1):
  if any(k in line.lower() for k in ['token','password','secret','credential','jwt=']):continue
  if any(k in line for k in ['8001','8002','uvicorn','WorkingDirectory','User=','Group=']):notes.append({'path':str(path),'line':index,'text':line})
for path in sorted(Path('/home/lailai/slurm-portal').glob('test_*.py')):
 for index,line in enumerate(path.read_text().splitlines(),1):
  if re.search(r'^BASE(?:_URL)?\s*=\s*',line):notes.append({'path':str(path),'line':index,'text':line})
save('evidence/portal-use-records.json',notes)
print('Read-only metadata and package export saved:',r)
print('Tunnel identifiers from journal:',[x['tunnel_ids'] for x in cloud['journal']]);print('Routing rules recovered:',sum(len(x['ingress']) for x in cloud['journal']))
