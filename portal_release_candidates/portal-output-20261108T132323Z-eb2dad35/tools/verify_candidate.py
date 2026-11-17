from pathlib import Path
import json,hashlib,stat
r=Path(__file__).resolve().parents[1]
m=json.loads((r/'candidate_manifest.json').read_text())
for p,h in json.loads((r/'FILES_SHA256.json').read_text()).items():
 assert hashlib.sha256((r/p).read_bytes()).hexdigest()==h,p
for n,h in m['source_sha256'].items():
 assert hashlib.sha256((r/'portal-release'/n).read_bytes()).hexdigest()==h,n
 assert stat.S_IMODE((r/'portal-release'/n).stat().st_mode)==0o444,n
for p,h in m['base_source_sha256'].items():
 assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h,'BASE DRIFT: '+p
assert hashlib.sha256(Path(m['current_dropin']).read_bytes()).hexdigest()==m['current_dropin_sha256'],'DROP-IN DRIFT'
assert hashlib.sha256((r/'config/output-roots.json').read_bytes()).hexdigest()==m['output_roots_sha256']
print('PASS: package/candidate/policy hashes and current base match; no services changed')
