from pathlib import Path
import subprocess,os,json,datetime,secrets,hashlib,stat,urllib.request,importlib.util
os.umask(0o077)
c=Path('/home/lailai/ollama-test/portal_release_candidates/portal-output-20261108T132323Z-eb2dad35');m=json.loads((c/'candidate_manifest.json').read_text());r=Path('/home/lailai/ollama-test/portal_ux_acceptance')/('audit-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+secrets.token_hex(4));r.mkdir(parents=True,exist_ok=False);Path('/tmp/nectec-ux-audit-path.txt').write_text(str(r))
def run(a):
 p=subprocess.run(a,capture_output=True,text=True,timeout=20,env=dict(os.environ,TZ='UTC'));return {'argv':a,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
s=run(['systemctl','show','slurm-portal.service','--property=MainPID,ActiveState,SubState,WorkingDirectory,Result,NRestarts']);props=dict(x.split('=',1) for x in s['stdout'].splitlines() if '=' in x);pid=int(props['MainPID']);release=Path(props['WorkingDirectory']);selected={}
for v in Path(f'/proc/{pid}/environ').read_bytes().split(b'\0'):
 if v.startswith((b'PORTAL_AUTH_DB=',b'PORTAL_OUTPUT_ROOTS=')):
  k,val=v.decode().split('=',1);selected[k]=val
ports={}
for port in [8001,8002]:
 with urllib.request.urlopen(f'http://127.0.0.1:{port}/openapi.json',timeout=10) as f:api=json.load(f)
 ports[str(port)]={'status':200,'operations':sum(1 for methods in api['paths'].values() for key in methods if key in ['get','post','patch','put','delete','head','options'])}
f=Path('/proc/2019096');fallback={'pid':2019096,'present':f.exists()}
if f.exists():fallback['start_ticks']=(f/'stat').read_text().split(') ',1)[1].split()[19]
q=run(['sacct','-nPX','-j','112,114,115,123,124,125,126,127,128,129,130,131','-S','2026-09-01','--format=JobIDRaw,User,Submit,Eligible,Start,End,ElapsedRaw,State,StdOut%1024,WorkDir%1024'])
assert q['exit_code']==0,q['stderr'];rows=[]
spec=importlib.util.spec_from_file_location('ux_output',release/'job_output.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);os.environ['PORTAL_OUTPUT_ROOTS']=selected['PORTAL_OUTPUT_ROOTS']
for line in q['stdout'].splitlines():
 parts=line.split('|');assert len(parts)==10,parts
 rec=dict(zip(['job_id','owner','submit_utc','eligible_utc','start_utc','end_utc','elapsed_seconds','state','stdout_pattern','workdir'],parts));rows.append(rec)
 if rec['job_id'] not in ['112','114','115']:continue
 metadata={'job_id':int(rec['job_id']),'user':rec['owner'],'stdout':rec['stdout_pattern'],'working_directory':rec['workdir']}
 try:rec['policy_resolution']={'status':'allowed','path':mod.resolve_stdout_path(metadata,int(rec['job_id']))}
 except mod.HTTPException as e:rec['policy_resolution']={'status':'denied','http_status':e.status_code,'detail':e.detail}
 try:
  p=mod.expand_pattern(rec['stdout_pattern'],int(rec['job_id']));p=Path(p) if p.startswith('/') else Path(rec['workdir'])/p
  rec['metadata_path']=str(p);info=p.lstat();rec['file_metadata']={'exists':True,'regular':stat.S_ISREG(info.st_mode),'symlink':stat.S_ISLNK(info.st_mode),'uid':info.st_uid,'gid':info.st_gid,'size':info.st_size,'mode':oct(stat.S_IMODE(info.st_mode)),'nlink':info.st_nlink,'content_read':False}
  import pwd
  rec['expected_owner_uid']=pwd.getpwnam(rec['owner']).pw_uid
  rec['parent_metadata']=[]
  for parent in [p.parent,*p.parent.parents]:
   pi=parent.lstat();rec['parent_metadata'].append({'path':str(parent),'uid':pi.st_uid,'mode':oct(stat.S_IMODE(pi.st_mode)),'symlink':stat.S_ISLNK(pi.st_mode)})
 except FileNotFoundError:rec['file_metadata']={'exists':False,'content_read':False}
 except (OSError,mod.HTTPException) as e:rec['file_metadata']={'inspection_error':type(e).__name__,'content_read':False}
j=run(['journalctl','-u','slurm-portal.service','--since','2026-11-09 00:00:00','--grep','/jobs/(112|114|115)/output','--no-pager','-o','json']);events=[]
import re
for line in j['stdout'].splitlines():
 try:
  obj=json.loads(line);a=re.search(r'"GET /jobs/(112|114|115)/output HTTP/[^\"]+" (\d+)',obj.get('MESSAGE',''))
  if a:events.append({'job_id':int(a[1]),'status':int(a[2]),'pid':obj.get('_PID'),'timestamp_us':obj.get('__REALTIME_TIMESTAMP')})
 except ValueError:pass
out={'timestamp':datetime.datetime.now(datetime.timezone.utc).isoformat(),'systemd':s,'ports':ports,'fallback':fallback,'selected_environment':selected,'source_hashes':{name:hashlib.sha256((release/name).read_bytes()).hexdigest() for name in m['source_sha256']},'frontend_sha256':hashlib.sha256(Path(m['external_frontend']['path']).read_bytes()).hexdigest(),'accounting':q,'accounting_timezone':'UTC via TZ environment','jobs':rows,'output_http_events':events,'journal_exit':j['exit_code'],'user_reported_order':[130,131,129,127,128,126,124,125,123],'browser_output_observations':{'provenance':'user reported authorized mangkud browser observations','115':'empty panel','114':'Job output not found','112':'successful output; private contents not independently read or retained'},'real_job_output_contents_read':False}
(r/'evidence.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({'directory':str(r),'ports':ports,'service':props,'jobs':rows,'events':events},indent=2))
