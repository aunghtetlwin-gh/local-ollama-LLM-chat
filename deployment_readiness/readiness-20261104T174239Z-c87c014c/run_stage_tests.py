"""Run reviewed patches with deployed packages, using only isolated data and sources."""
import argparse,hashlib,json,os,shlex,subprocess,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('suite',choices=['portal','chat','postgres','chat-forwarding']);p.add_argument('--attempt',default='1');a=p.parse_args();r=Path(Path('/tmp/nectec-readiness-path.txt').read_text().strip());stage=r/'staging';tag=f'{a.suite}-{a.attempt}';path=r/'raw'/f'{tag}-command.json';assert not path.exists()
if a.suite=='portal':files=[stage/'tests'/x for x in ['test_portal_security.py','test_portal_characterization.py','test_portal_remediations.py']];cwd=stage/'portal';profile='portal';python=r/'envs/portal/bin/python'
elif a.suite.startswith('chat'):files=[stage/'chat/tests'/x for x in ['test_auth.py','test_conversation_access.py','test_migrations.py']]+[stage/'tests/test_chat_characterization.py',stage/'tests/test_chat_origin.py'];cwd=stage/'chat';profile='chat';python='python'
else:files=[stage/'chat/integration_tests/test_postgres_isolation.py'];cwd=stage/'chat';profile='chat';python=r/'envs/chat-host/bin/python'
if a.suite=='chat-forwarding':files=[stage/'tests/test_chat_forwarding.py']
expected=json.loads((r/'evidence'/f'{profile}-runtime-packages.json').read_text());testargs=['-p','no:cacheprovider','-vv','--tb=short',*[str(x) for x in files],'--junitxml='+str(r/'raw'/f'{tag}.xml')]
code="import sys,json,importlib.metadata; current={d.metadata['Name'].lower().replace('_','-'):d.version for d in importlib.metadata.distributions()}; expected="+repr(expected['packages'])+"; assert all(current.get(k)==v for k,v in expected.items()),'runtime package mismatch'; print('STAGING_ENVIRONMENT='+json.dumps({'python':sys.version,'packages':current}),flush=True); "
if a.suite!='postgres':code+="assert sys.version=="+repr(expected['python'])+",'interpreter mismatch'; "
code+="from unittest.mock import patch; import pytest;\nwith patch('dotenv.load_dotenv',return_value=False):\n raise SystemExit(pytest.main("+repr(testargs)+"))"
container_name=None
if a.suite.startswith('chat'):
 image=json.loads((r/'evidence/chat-container.json').read_text())['image_id'];container_name='nectec-readiness-'+a.suite+'-'+r.name.rsplit('-',1)[-1]+'-'+a.attempt
 cmd=['docker','run','--rm','--name',container_name,'--label','nectec.readiness='+r.name,'--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--user',str(os.getuid())+':'+str(os.getgid()),'--tmpfs','/tmp:rw,nosuid,nodev,size=512m','--mount','type=bind,src='+str(stage)+',dst='+str(stage)+',readonly','--mount','type=bind,src='+str(r/'raw')+',dst='+str(r/'raw'),'--mount','type=bind,src='+str(r/'test_extras/chat')+',dst=/test-extra,readonly','--workdir',str(cwd),'-e','PYTHONDONTWRITEBYTECODE=1','-e','PYTEST_DISABLE_PLUGIN_AUTOLOAD=1','-e','PYTHONPATH=/test-extra:'+str(cwd),'--entrypoint','python',image,'-c',code]
else:cmd=[str(python),'-c',code]
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTEST_DISABLE_PLUGIN_AUTOLOAD='1');record={'suite':a.suite,'argv':cmd,'shell_command':shlex.join(cmd),'cwd':str(cwd),'started_epoch':time.time(),'runtime_profile':profile,'ephemeral_container':container_name,'production_container_changed':False,'reviewed_source_hashes':{str(x.relative_to(stage)):hashlib.sha256(x.read_bytes()).hexdigest() for x in stage.rglob('*.py')}};path.write_text(json.dumps(record,indent=2)+'\n')
try:result=subprocess.run(cmd,cwd=cwd,env=env,capture_output=True,text=True,timeout=120)
except subprocess.TimeoutExpired as exc:
 output=exc.stdout or '';output=output.decode(errors='replace') if isinstance(output,bytes) else output;result=subprocess.CompletedProcess(cmd,124,output,'TEST TIMEOUT')
 if container_name:
  inspection=subprocess.run(['docker','inspect','--format','{{index .Config.Labels "nectec.readiness"}}',container_name],capture_output=True,text=True)
  if inspection.returncode==0 and inspection.stdout.strip()==r.name:subprocess.run(['docker','stop','--time','5',container_name],capture_output=True)
(r/'raw'/f'{tag}.log').write_text(result.stdout+'\n'+result.stderr);record.update(exit_code=result.returncode,ended_epoch=time.time());path.write_text(json.dumps(record,indent=2)+'\n');print((result.stdout+'\n'+result.stderr)[-6000:]);print('RECORDED EXIT',result.returncode);raise SystemExit(result.returncode)
