"""CPU-only validation of evidence/output consistency and protected source hashes."""
import csv,hashlib,json,sys,xml.etree.ElementTree as ET
from pathlib import Path
root=Path(__file__).resolve().parent

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
checks={};total=0
for name,n in [('portal-host',96),('chat-host',35),('postgres-host',11),('portal-characterization-host',2),('chat-characterization-host',2)]:
 command=json.loads((root/'raw'/f'{name}-command.json').read_text());assert command['exit_code']==0
 tree=ET.parse(root/'raw'/f'{name}.xml');cases=tree.findall('.//testcase');assert len(cases)==n
 assert not any(tree.findall('.//'+x) for x in ['failure','error','skipped']);assert f'{n} passed' in (root/'raw'/f'{name}.log').read_text()
 assert command['environment_overrides']['PYTHONDONTWRITEBYTECODE']=='1';checks[name]=True;total+=n
assert total==146;checks['146_passed_junit_cases']=True
with (root/'reports/test_cases.csv').open() as f:cases=list(csv.DictReader(f))
assert len(cases)==146 and all(x['outcome']=='passed' for x in cases);checks['case_csv_matches_junit']=True
with (root/'reports/security_control_matrix.csv').open() as f:matrix=list(csv.DictReader(f))
assert len({r['id'] for r in matrix})==len(matrix)==27;assert all(r['evidence'] and r['scope_or_limitation'] for r in matrix);checks['27_controls_have_evidence_and_limits']=True
inventory=json.loads((root/'source_inventory.json').read_text())
for row in inventory:
 assert sha(Path(row['source_path']))==row['sha256']==sha(root/row['snapshot_path'])
checks['37_source_snapshots_match_originals']=len(inventory)==37
before=json.loads((root/'evidence/preservation_before.json').read_text());assert all(Path(name).is_file() and sha(Path(name))==h for name,h in before.items());checks['1584_original_files_unchanged']=len(before)==1584
meta=json.loads((root/'evidence/deployment_metadata.json').read_text());assert meta['commands']['hostname']['stdout'].strip()=='lai512'
assert all(set(p['selected_environment'])<={'PORTAL_COOKIE_SECURE','SESSION_COOKIE_SECURE','SESSION_TTL_SECONDS','inspection'} for p in meta['runtime_cookie_environment']);checks['runtime_environment_filtered']=True
# Verify prior sealed research packages without regenerating or editing them.
for name in ['/home/lailai/ollama-test/evaluation_final_report/2026-11-03T114345.873149_0000_35a3d7539e39-final-7a5bd582fbbc','/home/lailai/slurm_contention_runs/mps-20261104T082034Z-cee9c5d4']:
 p=Path(name);manifest=json.loads((p/'FILES_SHA256.json').read_text());assert all(sha(p/key)==value for key,value in manifest.items());checks[p.parent.name+'_seal']=True
checks['no_production_source_modification']=True
assert all(checks.values());result={'all_passed':True,'checks_n':len(checks),'checks':checks,'note':'Validation of evidence consistency, not additional application or host-security test coverage'}
(root/'reports/output_validation.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS:',len(checks),'package checks;',total,'recorded passing tests;',len(before),'unchanged originals')
