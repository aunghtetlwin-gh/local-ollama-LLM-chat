"""Read-only metadata capture; no application endpoints, databases, GPU APIs or workloads."""
import glob,hashlib,json,os,stat,subprocess,time
from pathlib import Path
root=Path('/home/lailai/ollama-test/security_analysis/p4-20261104T083745Z-5aa763e8');report={'captured_epoch':time.time(),'commands':{},'permissions':[],'runtime_cookie_environment':[]}
for args in [['hostname'],['date','-Is'],['ss','-ltnp'],['loginctl','list-sessions','--no-legend']]:
 r=subprocess.run(args,capture_output=True,text=True,timeout=15);report['commands'][' '.join(args)]={'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr}
for name in ['/home/lailai','/home/lailai/slurm-portal','/home/lailai/slurm-portal/portal_users.db','/tmp','/tmp/slurm-103.out','/tmp/slurm-104.out','/tmp/slurm-107.out','/tmp/slurm-108.out','/tmp/nvidia-mps','/tmp/nvidia-mps/control','/tmp/nvidia-mps/control_privileged','/dev/nvidia0','/dev/nvidiactl','/dev/nvidia-uvm']:
 try:
  s=os.stat(name);report['permissions'].append({'path':name,'mode':oct(stat.S_IMODE(s.st_mode)),'uid':s.st_uid,'gid':s.st_gid,'type':'socket' if stat.S_ISSOCK(s.st_mode) else 'device' if stat.S_ISCHR(s.st_mode) else 'directory' if stat.S_ISDIR(s.st_mode) else 'file'})
 except OSError as e:report['permissions'].append({'path':name,'unavailable':type(e).__name__})
for name in ['/etc/slurm/cgroup.conf','/etc/slurm/gres.conf']:
 p=Path(name);report[name]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'text':p.read_text()}
report['slurm_configuration_relevant_lines']=[x for x in Path('/etc/slurm/slurm.conf').read_text().splitlines() if x.startswith(('TaskPlugin','ProctrackType','Prolog=','GresTypes','AccountingStorageTRES','SelectType'))]
keys={'PORTAL_COOKIE_SECURE','SESSION_COOKIE_SECURE','SESSION_TTL_SECONDS'}
for folder in Path('/proc').glob('[0-9]*'):
 try:
  cmd=(folder/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
  if not any(x in cmd for x in ['uvicorn','server:my_api','app:app']):continue
  # Do not save command lines or unrelated environment values, which may contain credentials.
  selected={}
  try:
   for pair in (folder/'environ').read_bytes().split(b'\0'):
    key,sep,value=pair.partition(b'=')
    if key.decode(errors='replace') in keys:selected[key.decode()]=value.decode(errors='replace')
  except PermissionError:selected={'inspection':'permission denied'}
  report['runtime_cookie_environment'].append({'pid':int(folder.name),'comm':(folder/'comm').read_text().strip(),'selected_environment':selected})
 except (OSError,ProcessLookupError):pass
(root/'evidence/deployment_metadata.json').write_text(json.dumps(report,indent=2)+'\n');print('Read-only deployment metadata saved; no application or database connection made.')
