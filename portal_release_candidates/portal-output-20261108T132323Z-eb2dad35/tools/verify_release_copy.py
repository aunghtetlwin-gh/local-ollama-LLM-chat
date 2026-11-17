from pathlib import Path
import hashlib,json,sys
r=Path(__file__).resolve().parents[1]
m=json.loads((r/'candidate_manifest.json').read_text())
d=Path(sys.argv[1])
assert d==Path(m['future_release']),'Unexpected release destination'
for n,h in m['source_sha256'].items():
 assert hashlib.sha256((d/n).read_bytes()).hexdigest()==h,n
assert sorted(p.name for p in d.iterdir())==sorted(m['source_sha256']),'Unexpected release files'
print('PASS: copied release matches reviewed candidate')
