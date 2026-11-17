from pathlib import Path
import json,os,tempfile,importlib.util,hashlib,datetime
from unittest.mock import patch
r=Path(Path('/tmp/nectec-output-verification-path.txt').read_text());release=Path('/home/lailai/nectec-changes/portal-output-20261108T132323Z-eb2dad35/portal-release');spec=importlib.util.spec_from_file_location('accepted_output',release/'job_output.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);checks=[]
with tempfile.TemporaryDirectory(prefix='nectec-output-synthetic-acceptance-') as td:
 root=Path(td);approved=root/'approved';approved.mkdir();os.environ['PORTAL_OUTPUT_ROOTS']=json.dumps([str(approved)])
 for label,data in [('custom','SYNTHETIC ACCEPTANCE ONLY'),('empty','')]:
  p=approved/'slurm-101.out';p.write_text(data);resolved=module.resolve_stdout_path({'stdout':str(approved/'slurm-%j.out')},101);fd=module.open_stdout_file(resolved)
  try:assert os.read(fd,4096)==data.encode()
  finally:os.close(fd)
  checks.append({'name':label,'passed':True,'scope':'synthetic tempfile only'})
 target=root/'synthetic-target';target.write_text('SYNTHETIC TARGET ONLY');link=approved/'link.out';link.symlink_to(target)
 fd=None
 try:fd=module.open_stdout_file(str(link))
 except OSError:checks.append({'name':'leaf_symlink_denied','passed':True})
 else:os.close(fd);raise AssertionError('symlink opened')
 outside=root/'synthetic-parent';outside.mkdir();(outside/'out').write_text('SYNTHETIC');(approved/'parent-link').symlink_to(outside,target_is_directory=True)
 try:fd=module.open_stdout_file(str(approved/'parent-link/out'))
 except OSError:checks.append({'name':'parent_symlink_denied','passed':True})
 else:os.close(fd);raise AssertionError('parent symlink followed')
 with patch.object(module.os,'open',side_effect=AssertionError('Outside policy must not open')):
  try:module.resolve_stdout_path({'stdout':str(root/'outside-secret')},101)
  except module.HTTPException as e:assert e.status_code==404
  else:raise AssertionError('Outside root permitted')
  checks.append({'name':'outside_policy_denied_without_open','passed':True})
  assert module.resolve_stdout_path({},101)=='/tmp/slurm-101.out';checks.append({'name':'legacy_path_resolution_without_open','passed':True})
result={'timestamp':datetime.datetime.now(datetime.timezone.utc).isoformat(),'module':str(release/'job_output.py'),'module_sha256':hashlib.sha256((release/'job_output.py').read_bytes()).hexdigest(),'passed':len(checks),'checks':checks,'real_job_output_opened':False,'production_environment_changed':False,'note':'Policy environment changed only inside this short-lived test process; no production app import or DB initialization; endpoint ownership/UID/size cases use sealed 190-test evidence'}
(r/'evidence/fresh-synthetic-fixtures.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
