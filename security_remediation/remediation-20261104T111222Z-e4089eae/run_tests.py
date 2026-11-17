"""Run only isolated copies; preserve command/output and propagate pytest exit codes."""
import argparse,hashlib,json,os,shlex,subprocess,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('suite',choices=['portal','chat','postgres','canary']);p.add_argument('--attempt',default='1');a=p.parse_args();r=Path(__file__).resolve().parent;tag=f'{a.suite}-{a.attempt}';python='/tmp/conversation-isolation-tools/bin/python';xml=r/'raw'/f'{tag}.xml'
if a.suite=='portal':
 paths=[r/'tests'/x for x in ['test_portal_security.py','test_portal_characterization.py','test_portal_remediations.py']];cwd=r/'portal'
elif a.suite=='chat':
 paths=[r/'chat/tests'/x for x in ['test_auth.py','test_conversation_access.py','test_migrations.py']]+[r/'tests/test_chat_characterization.py',r/'tests/test_chat_origin.py'];cwd=r/'chat'
elif a.suite=='postgres':paths=[r/'chat/integration_tests/test_postgres_isolation.py'];cwd=r/'chat'
else:paths=[r/'harness_check/test_expected_failure.py'];cwd=r
args=['-p','no:cacheprovider','-vv','--tb=short',*[str(x) for x in paths],'--junitxml='+str(xml)]
cmd=[python,'-c',"from unittest.mock import patch; import pytest;\nwith patch('dotenv.load_dotenv',return_value=False):\n raise SystemExit(pytest.main("+repr(args)+"))"]
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTEST_DISABLE_PLUGIN_AUTOLOAD='1');record={'argv':cmd,'cwd':str(cwd),'shell_command':shlex.join(cmd),'environment_overrides':{'PYTHONDONTWRITEBYTECODE':'1','PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1'},'started_epoch':time.time(),'sources_sha256':{str(x.relative_to(r)):hashlib.sha256(x.read_bytes()).hexdigest() for x in sorted(r.rglob('*.py'))}}
file=r/'raw'/f'{tag}-command.json';assert not file.exists();file.write_text(json.dumps(record,indent=2)+'\n')
try:result=subprocess.run(cmd,cwd=cwd,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=120)
except subprocess.TimeoutExpired as e:
 text=e.stdout or '';text=text.decode(errors='replace') if isinstance(text,bytes) else text;result=subprocess.CompletedProcess(cmd,124,text+'\nTEST TIMEOUT\n')
(r/'raw'/f'{tag}.log').write_text(result.stdout);record.update(exit_code=result.returncode,ended_epoch=time.time());file.write_text(json.dumps(record,indent=2)+'\n');print(result.stdout[-7000:]);print('RECORDED EXIT',result.returncode);raise SystemExit(result.returncode)
