"""Explicit isolated test commands with raw stdout/stderr, JUnit, and exit status."""
import argparse,json,os,shlex,subprocess,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('suite',choices=['portal','chat','postgres']);a=p.parse_args();root=Path(__file__).resolve().parent;project=Path('/home/lailai/ollama-test');python='/tmp/conversation-isolation-tools/bin/python'
base=[python,'-m','pytest','-p','no:cacheprovider','-vv','--tb=short']
if a.suite=='portal':tests=[str(root/'tests/test_portal_security.py')];cmd=base+tests
elif a.suite=='chat':
 tests=['tests/test_auth.py','tests/test_conversation_access.py','tests/test_migrations.py'];cmd=[python,'-c',"from unittest.mock import patch; import pytest;\nwith patch('dotenv.load_dotenv',return_value=False):\n raise SystemExit(pytest.main("+repr(['-p','no:cacheprovider','-vv','--tb=short',*tests,'--junitxml='+str(root/'raw/chat.xml')])+"))"]
else:tests=['integration_tests/test_postgres_isolation.py'];cmd=base+tests
if a.suite!='chat':cmd+=['--junitxml='+str(root/'raw'/f'{a.suite}.xml')]
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
# Only guard-generated synthetic test credentials appear in isolated tests.
record={'suite':a.suite,'cwd':str(project),'argv':cmd,'shell_command':shlex.join(cmd),'environment_overrides':{'PYTHONDONTWRITEBYTECODE':'1','PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1'},'started_epoch':time.time()}
path=root/'raw'/f'{a.suite}-command.json';assert not path.exists(),'refuse overwriting previous test run';path.write_text(json.dumps(record,indent=2)+'\n')
result=subprocess.run(cmd,cwd=project,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=240)
(root/'raw'/f'{a.suite}.log').write_text(result.stdout);record.update(exit_code=result.returncode,ended_epoch=time.time());path.write_text(json.dumps(record,indent=2)+'\n');print(result.stdout[-7000:]);print('Recorded exit:',result.returncode);raise SystemExit(result.returncode)
