"""Offline staging preparation: copies, patch application, runtime packages, test-only extras."""
import hashlib,importlib.metadata,json,os,shutil,subprocess,sys
from pathlib import Path
r=Path(Path('/tmp/nectec-readiness-path.txt').read_text().strip());rem=Path('/home/lailai/ollama-test/security_remediation/remediation-20261104T111222Z-e4089eae')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
records=[]
for label,base,names in [('portal',Path('/home/lailai/slurm-portal'),['app.py','auth.py','slurm_identity.py']),('chat',Path('/home/lailai/ollama-test'),['server.py'])]:
 for name in names:shutil.copyfile(base/name,r/'staging'/label/name)
 patch=rem/'patches'/f'{label}-application.patch';cmd=['patch','--batch','--forward','-p1','-d',str(r/'staging'/label),'-i',str(patch)];p=subprocess.run(cmd,capture_output=True,text=True);records.append({'argv':cmd,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'patch_sha256':sha(patch)});assert p.returncode==0,p.stderr
for row in json.loads((rem/'reports/changed_application_files.json').read_text()):assert sha(r/'staging'/row['isolated_path'])==row['remediated_sha256']
(r/'raw/staging-patch-application.json').write_text(json.dumps(records,indent=2)+'\n')
# Test runner dependencies are copied offline; no pip/network or production installation.
source_site=Path('/tmp/conversation-isolation-tools/lib/python3.10/site-packages')
test_names=['pytest','pluggy','iniconfig','pygments','httpx','httpcore','packaging','tomli','sniffio','certifi','python-dotenv']
extras={}
for profile in ['portal','chat']:
 runtime=json.loads((r/'evidence'/f'{profile}-runtime-packages.json').read_text())['packages'];target=r/'test_extras'/profile;target.mkdir();added={}
 for name in test_names:
  if name in runtime:continue
  try:dist=importlib.metadata.distribution(name)
  except importlib.metadata.PackageNotFoundError:continue
  added[name]=dist.version
  for file in dist.files or []:
   if '..' in file.parts or '__pycache__' in file.parts or str(file).endswith('.pyc'):continue
   source=Path(dist.locate_file(file));assert source.resolve().is_relative_to(source_site)
   dest=target/file;dest.parent.mkdir(exist_ok=True,parents=True)
   if source.is_file():shutil.copyfile(source,dest)
 extras[profile]=added
(r/'evidence/test-only-extras.json').write_text(json.dumps(extras,indent=2)+'\n')
for name,source,extra in [('portal',Path('/home/lailai/slurm-portal/.venv/lib/python3.10/site-packages'),r/'test_extras/portal'),('chat-host',r/'exports/chat-site-packages',r/'test_extras/chat')]:
 env=r/'envs'/name;subprocess.run(['/usr/bin/python3','-m','venv','--without-pip',str(env)],check=True)
 target=env/'lib/python3.10/site-packages';shutil.copytree(source,target,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
 shutil.copytree(extra,target,dirs_exist_ok=True)
 cmd=[str(env/'bin/python'),'-c',"import importlib.metadata,json,sys; print(json.dumps({'python':sys.version,'packages':{d.metadata['Name'].lower().replace('_','-'):d.version for d in importlib.metadata.distributions()}}))"]
 p=subprocess.run(cmd,capture_output=True,text=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'));assert p.returncode==0,p.stderr;d=json.loads(p.stdout);profile='portal' if name=='portal' else 'chat';runtime=json.loads((r/'evidence'/f'{profile}-runtime-packages.json').read_text());assert all(d['packages'].get(k)==v for k,v in runtime['packages'].items()),(name,d)
 (r/'evidence'/f'{name}-staging-packages.json').write_text(json.dumps(d,indent=2)+'\n')
 print(name,'all',len(runtime['packages']),'deployed package versions match; Python',d['python'].split()[0])
