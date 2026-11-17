"""Offline final evidence/source/hash validation. Does not deploy or start services."""
import csv,hashlib,json,xml.etree.ElementTree as ET
from pathlib import Path
r=Path(__file__).resolve().parent

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
checks={};n=0
for tag,count in [('portal-2',108),('chat-1',77),('postgres-1',11)]:
 cmd=json.loads((r/'raw'/f'{tag}-command.json').read_text());tree=ET.parse(r/'raw'/f'{tag}.xml');assert cmd['exit_code']==0 and len(tree.findall('.//testcase'))==count
 assert not any(tree.findall('.//'+k) for k in ['failure','error','skipped']);assert f'{count} passed' in (r/'raw'/f'{tag}.log').read_text();checks[tag]=True;n+=count
 assert str(r) in cmd['cwd']
 relevant=['portal/app.py','portal/auth.py','portal/slurm_identity.py','tests/test_portal_security.py','tests/test_portal_characterization.py','tests/test_portal_remediations.py'] if tag.startswith('portal') else ['chat/server.py','chat/auth.py','chat/database.py','chat/tests/conftest.py']
 if tag=='chat-1':relevant+=['tests/test_chat_origin.py','tests/test_chat_characterization.py','chat/tests/test_conversation_access.py','chat/tests/test_auth.py','chat/tests/test_migrations.py']
 else:
  if tag=='postgres-1':relevant+=['chat/integration_tests/test_postgres_isolation.py']
 for path in relevant:assert sha(r/path)==cmd['sources_sha256'][path]
 checks[tag+'_tested_sources_unchanged']=True
assert n==196;checks['196_final_cases']=True
assert json.loads((r/'raw/canary-1-command.json').read_text())['exit_code']==1;assert len(ET.parse(r/'raw/canary-1.xml').findall('.//failure'))==1;checks['expected_failure_propagates_exit_1']=True
for name in ['portal','chat']:assert json.loads((r/'raw'/f'{name}-patch-check.json').read_text())['exit_code']==0
checks['runtime_patches_apply_check']=True
for row in json.loads((r/'reports/changed_application_files.json').read_text()):assert sha(Path(row['original_path']))==row['original_sha256'] and sha(r/row['isolated_path'])==row['remediated_sha256']
checks['4_changed_runtime_files_bound']=True
originals=json.loads((r/'preservation_before.json').read_text());assert all(Path(p).is_file() and sha(Path(p))==h for p,h in originals.items());checks['1666_originals_unchanged']=len(originals)==1666
for path in ['/home/lailai/ollama-test/evaluation_final_report/2026-11-03T114345.873149_0000_35a3d7539e39-final-7a5bd582fbbc','/home/lailai/slurm_contention_runs/mps-20261104T082034Z-cee9c5d4','/home/lailai/ollama-test/security_analysis/p4-20261104T083745Z-5aa763e8']:
 root=Path(path);assert all(sha(root/p)==h for p,h in json.loads((root/'FILES_SHA256.json').read_text()).items());checks[root.parent.name+'_prior_seal']=True
with (r/'reports/test_cases.csv').open() as f:assert len(list(csv.DictReader(f)))==196
checks['case_inventory']=True
assert all(checks.values());(r/'reports/output_validation.json').write_text(json.dumps({'all_passed':True,'checks_n':len(checks),'checks':checks},indent=2)+'\n');print('PASS:',len(checks),'checks; 196 final application cases; 1666 unchanged originals')
