import argparse,csv,hashlib,json,shutil
from pathlib import Path
from PIL import Image,ImageOps,ImageDraw,ImageStat
import xml.etree.ElementTree as ET

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--package',required=True);a=p.parse_args();root=Path(a.package).resolve();project=root.parent.parent
 manifest=root/'FILES_SHA256.json'
 if manifest.exists():
  files=json.loads(manifest.read_text());assert all(sha(root/k)==v for k,v in files.items());assert set(files)=={str(x.relative_to(root)) for x in root.rglob('*') if x.is_file() and x!=manifest};print('PASS: sealed package hashes',len(files));return
 checks={};thumbs=[]
 pngs=sorted((root/'figures').glob('*.png'));assert len(pngs)==7
 for path in pngs:
  with Image.open(path) as im:
   im.load();assert min(im.size)>900;assert min(im.info.get('dpi',(0,0)))>299;assert max(ImageStat.Stat(im.convert('RGB')).stddev)>10
   tile=Image.new('RGB',(700,475),'white');im.thumbnail((690,435));tile.paste(im,((700-im.width)//2,25));ImageDraw.Draw(tile).text((8,455),path.stem,fill='black');thumbs.append(tile)
  checks[path.name]=True
 svgs=sorted((root/'figures').glob('*.svg'));assert len(svgs)==7
 for path in svgs:assert ET.parse(path).getroot().tag.endswith('svg');checks[path.name]=True
 counts={'model_results':3,'automatic_categories':9,'human_categories':9,'latency_seconds':3,'tokens_and_generation':3,'ollama_memory_allocations':3,'gsm8k_paired_comparisons':3,'gsm8k_question_outcomes':50,'request_metrics':210,'notable_failures':6}
 for name,n in counts.items():
  with (root/'tables'/f'{name}.csv').open() as f:rows=list(csv.DictReader(f))
  assert len(rows)==n,(name,len(rows));checks[name+'_rows']=n
 for row in json.loads((root/'source_inventory.json').read_text()):assert sha(project/row['path'])==row['sha256'],row['path']
 checks['source_inventory_hashes']=True
 assert json.loads((root/'validation/verification.json').read_text())['all_checks_passed'];checks['3776_source_checks']=True
 sheet=Image.new('RGB',(1400,1900),'white')
 for i,tile in enumerate(thumbs):sheet.paste(tile,((i%2)*700,(i//2)*475))
 sheet.save(root/'validation/figure_contact_sheet.png')
 shutil.copyfile(__file__,root/'validate_package.py')
 with (root/'README.md').open('a') as f:f.write('\nValidate and seal a newly reproduced package (or verify an already sealed package):\n\n```sh\nPYTHONDONTWRITEBYTECODE=1 venv/bin/python PATH_TO_THIS_PACKAGE/validate_package.py \\\n  --package PATH_TO_NEW_PACKAGE\n```\n')
 (root/'validation/output_checks.json').write_text(json.dumps({'all_checks_passed':True,'checks':checks},indent=2)+'\n')
 files={str(x.relative_to(root)):sha(x) for x in sorted(root.rglob('*')) if x.is_file() and x!=manifest};manifest.write_text(json.dumps(files,indent=2)+'\n');print('PASS:',len(checks),'output checks;',len(files),'sealed files')
if __name__=='__main__':main()
