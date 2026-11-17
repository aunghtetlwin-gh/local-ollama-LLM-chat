"""Offline validation; no service, database, network or GPU calls."""
import csv,hashlib,json,xml.etree.ElementTree as ET
from pathlib import Path
r=Path(Path('/tmp/nectec-readiness-path.txt').read_text().strip());checks={}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for suite,n in [('portal',108),('chat',77),('postgres',11),('chat-forwarding',2)]:
 command=json.loads((r/'raw'/f'{suite}-1-command.json').read_text());tree=ET.parse(r/'raw'/f'{suite}-1.xml');assert command['exit_code']==0 and len(tree.findall('.//testcase'))==n;assert not any(tree.findall('.//'+k) for k in ['failure','error','skipped'])
 meta=json.loads(next(line.split('=',1)[1] for line in (r/'raw'/f'{suite}-1.log').read_text().splitlines() if line.startswith('STAGING_ENVIRONMENT=')))
 expected=json.loads((r/'evidence'/f'{command["runtime_profile"]}-runtime-packages.json').read_text());assert all(meta['packages'].get(k)==v for k,v in expected['packages'].items())
 if suite!='postgres':assert meta['python']==expected['python']
 checks[suite+'_tests_and_environment']=True
with (r/'reports/test_cases.csv').open() as f:assert len(list(csv.DictReader(f)))==198
checks['198_test_inventory']=True
rem=Path('/home/lailai/ollama-test/security_remediation/remediation-20261104T111222Z-e4089eae')
for row in json.loads((rem/'reports/changed_application_files.json').read_text()):assert sha(r/'staging'/row['isolated_path'])==row['remediated_sha256'] and sha(Path(row['original_path']))==row['original_sha256']
checks['four_reviewed_fixes_match_and_originals_unchanged']=True
before=json.loads((r/'evidence/preservation_before.json').read_text());pres=json.loads((r/'reports/preservation.json').read_text());appends={x['path']:x for x in pres['append_only_runtime_logs']}
for name,h in before.items():
 if name in appends:
  data=Path(name).read_bytes();row=appends[name];assert hashlib.sha256(data[:row['original_prefix_bytes']]).hexdigest()==h
  assert len(data)-row['original_prefix_bytes']==row['new_bytes']
 else:assert sha(Path(name))==h,name
checks['1727_byte_identical_and_one_preserved_log_prefix']=True
for root in [Path('/home/lailai/ollama-test/evaluation_final_report/2026-11-03T114345.873149_0000_35a3d7539e39-final-7a5bd582fbbc'),Path('/home/lailai/slurm_contention_runs/mps-20261104T082034Z-cee9c5d4'),Path('/home/lailai/ollama-test/security_analysis/p4-20261104T083745Z-5aa763e8'),rem]:
 assert all(sha(root/p)==h for p,h in json.loads((root/'FILES_SHA256.json').read_text()).items());checks[root.parent.name+'_prior_seal']=True
cfg=json.loads((r/'evidence/cloudflare-current-routing.json').read_text())['endpoints'];assert cfg['/config']['status']==200 and len(cfg['/config']['ingress'])==2 and cfg['/config']['ingress'][0]['service']=='ssh://localhost:22' and cfg['/config']['ingress'][1]['service']=='http_status:404';assert cfg['/diag/tunnel']['tunnelID']=='9e2093df-2a57-4116-afc8-6b96cacc9f64'
checks['loaded_connector_ssh_only']=True
summary=json.loads((r/'reports/portal_route_summary.json').read_text());assert summary['8001_operations']==10 and summary['8002_operations']==16 and len(summary['new_operations_8002'])==6
checks['portal_route_difference']=True
post=json.loads((r/'evidence/post-validation-deployment.json').read_text());assert post['container_and_image_unchanged'] and post['production_container_filesystem_unchanged'] and not post['ephemeral_test_containers_remaining'];checks['production_container_unchanged_and_test_containers_removed']=True
assert all(checks.values());(r/'reports/output_validation.json').write_text(json.dumps({'all_passed':True,'checks_n':len(checks),'checks':checks},indent=2)+'\n');print('PASS:',len(checks),'checks; 198 tests; original source and sealed evidence preserved')
