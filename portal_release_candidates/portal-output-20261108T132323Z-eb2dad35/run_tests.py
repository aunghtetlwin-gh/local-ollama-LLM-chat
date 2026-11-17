from pathlib import Path
import subprocess,os,json,datetime,sys
r=Path(__file__).resolve().parent
import uuid
results=r/'raw'/('rerun-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:6]);results.mkdir(exist_ok=False)
python=Path('/home/lailai/ollama-test/deployment_readiness/readiness-20261104T174239Z-c87c014c/envs/portal/bin/python')
expected=json.loads(Path('/home/lailai/ollama-test/deployment_readiness/readiness-20261104T174239Z-c87c014c/evidence/portal-runtime-packages.json').read_text())
args=['-p','no:cacheprovider','-vv','--tb=short',str(r/'tests'),'--junitxml='+str(results/'portal-tests.xml')]
code="import sys,json,importlib.metadata; current={d.metadata['Name'].lower().replace('_','-'):d.version for d in importlib.metadata.distributions()}; expected="+repr(expected['packages'])+"; assert all(current.get(k)==v for k,v in expected.items()),'runtime package mismatch'; assert sys.version=="+repr(expected['python'])+"; print('ENVIRONMENT='+json.dumps({'python':sys.version,'packages':current}),flush=True); import pytest; raise SystemExit(pytest.main("+repr(args)+"))"
cmd=[str(python),'-c',code];record={'argv':cmd,'cwd':str(r/'portal-release'),'started':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'disposable SQLite, synthetic files, mocked scheduler; deployed-version dependency assertions','candidate_source':str(r/'portal-release'),'candidate_output_roots':json.loads((r/'config/output-roots.json').read_text())}
p=results/'portal-test-command.json';p.write_text(json.dumps(record,indent=2)+'\n')
try:
 result=subprocess.run(cmd,cwd=r/'portal-release',env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',PORTAL_OUTPUT_ROOTS=json.dumps(json.loads((r/'config/output-roots.json').read_text()))),capture_output=True,text=True,timeout=120)
except subprocess.TimeoutExpired as exc:
 result=subprocess.CompletedProcess(cmd,124,(exc.stdout or b'').decode(errors='replace') if isinstance(exc.stdout,bytes) else (exc.stdout or ''),'TIMEOUT after 120 seconds')
(results/'portal-tests.log').write_text(result.stdout+'\n'+result.stderr);record.update(exit_code=result.returncode,finished=datetime.datetime.now(datetime.timezone.utc).isoformat());p.write_text(json.dumps(record,indent=2)+'\n');print((result.stdout+'\n'+result.stderr)[-6500:]);sys.exit(result.returncode)
