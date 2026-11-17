"""Synthetic stdout retrieval only: no live job/file/account access."""
from test_portal_security import env, portal, login
from fastapi.testclient import TestClient
from fastapi import HTTPException
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import job_output
import os
import json
import pytest

@pytest.fixture
def outputs(env, monkeypatch):
    root = env.tmp / 'approved-output-only'
    root.mkdir()
    monkeypatch.setenv('PORTAL_OUTPUT_ROOTS', json.dumps([str(root)]))
    return root


def get_output(user='researcher_a', job=101):
    with TestClient(portal.app) as client:
        login(client, user)
        return client.get(f'/jobs/{job}/output')


def forbid_read(monkeypatch):
    def denied(*a, **kw):
        raise AssertionError('Denied path must not be read')
    monkeypatch.setattr(portal.os, 'fdopen', denied)


@pytest.mark.parametrize('kind', ['raw-absolute', 'raw-relative', 'expanded', 'expanded-relative',
                                  'empty', 'padded', 'literal-percent', 'expanded-literal-percent'])
def test_owner_approved_custom_output(env, outputs, kind):
    content = '' if kind == 'empty' else 'EXACT SYNTHETIC OUTPUT\n'
    name = 'slurm-00101.out' if kind == 'padded' else 'slurm-101.out'
    if kind in ['literal-percent', 'expanded-literal-percent']:name = 'literal-%j-101.out'
    (outputs / name).write_text(content)
    job = env.jobs[101]
    if kind == 'expanded-literal-percent':job['stdout_expanded'] = str(outputs / name)
    elif kind.startswith('expanded'):
        job['stdout_expanded'] = name if kind.endswith('relative') else str(outputs / name)
        job['current_working_directory'] = str(outputs)
    else:
        pattern = 'literal-%%j-%j.out' if kind == 'literal-percent' else ('slurm-%5j.out' if kind == 'padded' else 'slurm-%j.out')
        job['stdout'] = pattern if kind == 'raw-relative' else str(outputs / pattern)
        job['working_directory'] = str(outputs)
    response = get_output()
    assert response.status_code == 200 and response.json() == {'job_id':101,'output':content}


@pytest.mark.parametrize('mode', ['controller-empty','controller-404'])
def test_completed_accounting_custom_output(env, outputs, monkeypatch, mode):
    (outputs/'slurm-101.out').write_text('COMPLETED SYNTHETIC')
    calls=[]
    def scheduler(method, endpoint, **kw):
        calls.append((method, endpoint, kw['username']))
        if '/slurmdb/' in endpoint:
            return {'jobs':[{'job_id':101, 'user':'researcher_a', 'stdout':'slurm-%j.out',
                             'working_directory':str(outputs)}]}
        if mode == 'controller-404':raise HTTPException(404, 'not found')
        return {'jobs':[]}
    monkeypatch.setattr(portal,'call_slurm',scheduler)
    response=get_output()
    assert response.status_code==200 and response.json()['output']=='COMPLETED SYNTHETIC'
    assert len(calls)==2 and all(x[2]=='researcher_a' for x in calls)
    assert 'users=researcher_a' in calls[1][1]


@pytest.mark.parametrize('mode',['none','raw','expanded'])
def test_legacy_standard_path(env, monkeypatch, mode):
    # No actual /tmp/slurm-101.out is opened: mapped to a disposable file.
    path=env.tmp/'synthetic-legacy.out';path.write_text('LEGACY SYNTHETIC')
    if mode=='raw':env.jobs[101]['stdout']='/tmp/slurm-%j.out'
    if mode=='expanded':env.jobs[101]['stdout_expanded']='/tmp/slurm-101.out'
    original=portal.open_stdout_file;attempts=[]
    def mapped(name):
        assert name=='/tmp/slurm-101.out';attempts.append(name)
        return original(str(path))
    monkeypatch.setattr(portal,'open_stdout_file',mapped)
    response=get_output()
    assert response.status_code==200 and response.json()['output']=='LEGACY SYNTHETIC'
    assert attempts==['/tmp/slurm-101.out']


@pytest.mark.parametrize('pattern', ['%A_%a.out','%x.out','%u.out','%N.out','%n.out','%t.out',
                                    '%J.out','%s.out','%b.out','%r.out','%S.out','%11j.out',
                                    '%0j.out','%04j.out','%99999999999999j.out','dangling%',r'\%j.out'])
def test_unsupported_patterns_rejected_before_open(env, outputs, monkeypatch, pattern):
    env.jobs[101]['stdout']=str(outputs/pattern)
    monkeypatch.setattr(portal,'open_stdout_file',lambda *a:pytest.fail('must not open unsupported path'))
    forbid_read(monkeypatch)
    assert get_output().status_code==404


@pytest.mark.parametrize('bad', ['../secret.out','sub/../secret.out','./secret.out','sub//secret.out',
                                '/etc/passwd','/proc/self/environ','/tmp/private-secret.out',
                                '/tmp/slurm-202.out','/tmp/slurm-101.out.bak','/dev/null',
                                'bad\x00.out','bad\n.out', 'bad\\name.out'])
def test_unsafe_paths_rejected_before_open(env, outputs, monkeypatch, bad):
    env.jobs[101]['stdout']=bad
    env.jobs[101]['working_directory']=str(outputs)
    monkeypatch.setattr(portal,'open_stdout_file',lambda *a:pytest.fail('must not open unsafe path'))
    forbid_read(monkeypatch)
    assert get_output().status_code==404


@pytest.mark.parametrize('kind',['relative-no-workdir','relative-bad-workdir','wrong-type','bad-expanded-type','root-prefix-confusion','root-itself'])
def test_bad_metadata_no_fallback(env, outputs, monkeypatch, kind):
    job=env.jobs[101]
    if kind=='relative-no-workdir':job['stdout']='slurm-%j.out'
    elif kind=='relative-bad-workdir':job.update(stdout='slurm-%j.out',working_directory=str(outputs/'..'))
    elif kind=='wrong-type':job['stdout']={'path':'/tmp/slurm-101.out'}
    elif kind=='bad-expanded-type':job['stdout_expanded']=[]
    elif kind=='root-prefix-confusion':job['stdout']=str(outputs)+'-private/secret.out'
    else:job['stdout']=str(outputs)
    monkeypatch.setattr(portal,'open_stdout_file',lambda *a:pytest.fail('must not fallback'))
    assert get_output().status_code==404


@pytest.mark.parametrize('policy',['not-json','{}','[42]','["/"]','["/tmp"]','["/home/lailai"]',
                                   '["/etc/private"]','["/proc/private"]','["/tmp/out/../bad"]'])
def test_invalid_operator_policy_fails_closed(env, outputs, monkeypatch, policy):
    monkeypatch.setenv('PORTAL_OUTPUT_ROOTS',policy)
    env.jobs[101]['stdout']=str(outputs/'slurm-%j.out')
    monkeypatch.setattr(portal,'open_stdout_file',lambda *a:pytest.fail('invalid policy must not open'))
    assert get_output().status_code==503


def test_custom_paths_require_explicit_policy(env, outputs, monkeypatch):
    monkeypatch.delenv('PORTAL_OUTPUT_ROOTS')
    env.jobs[101]['stdout']=str(outputs/'slurm-%j.out')
    forbid_read(monkeypatch)
    assert get_output().status_code==404


@pytest.mark.parametrize('kind,code', [('missing',404),('leaf-link',404),('parent-link',404),
                                     ('root-link',404),('directory',404),('fifo',404),
                                     ('wrong-uid',404),('hardlink',404),('oversize',413)])
def test_filesystem_denials_never_read(env, outputs, monkeypatch, kind, code):
    path=outputs/'slurm-101.out'
    if kind=='leaf-link':
        target=env.tmp/'outside-secret';target.write_text('SYNTHETIC SECRET');path.symlink_to(target)
    elif kind=='parent-link':
        target=env.tmp/'outside';target.mkdir();(target/'out').write_text('SYNTHETIC SECRET')
        (outputs/'link').symlink_to(target,target_is_directory=True);path=outputs/'link/out'
    elif kind=='root-link':
        target=env.tmp/'outside';target.mkdir();(target/'out').write_text('SYNTHETIC SECRET')
        link=env.tmp/'linked-root';link.symlink_to(target,target_is_directory=True)
        monkeypatch.setenv('PORTAL_OUTPUT_ROOTS',json.dumps([str(link)]));path=link/'out'
    elif kind=='directory':path.mkdir()
    elif kind=='fifo':os.mkfifo(path)
    elif kind=='hardlink':
        target=env.tmp/'outside-secret';target.write_text('SYNTHETIC SECRET');os.link(target,path)
    elif kind=='oversize':path.write_bytes(b'x'*(1024*1024+1))
    elif kind=='wrong-uid':
        path.write_text('SYNTHETIC SECRET');monkeypatch.setattr(portal.pwd,'getpwnam',lambda name:SimpleNamespace(pw_uid=os.getuid()+12345))
    env.jobs[101]['stdout']=str(path)
    forbid_read(monkeypatch)
    assert get_output().status_code==code


@pytest.mark.parametrize('user,completed', [('researcher_b',False),('admin_test',False),
                                          ('researcher_b',True),('admin_test',True)])
def test_foreign_or_admin_denied_before_filesystem(env, outputs, monkeypatch, user, completed):
    if completed:
        env.jobs.pop(101)
        env.history[0]['stdout']=str(outputs/'secret.out')
    else:env.jobs[101]['stdout']=str(outputs/'secret.out')
    monkeypatch.setattr(portal,'resolve_stdout_path',lambda *a:pytest.fail('foreign user must not resolve'))
    monkeypatch.setattr(portal.pwd,'getpwnam',lambda *a:pytest.fail('foreign user must not resolve UID'))
    monkeypatch.setattr(portal,'open_stdout_file',lambda *a:pytest.fail('foreign user must not open'))
    forbid_read(monkeypatch)
    assert get_output(user=user).status_code==404


@pytest.mark.parametrize('status',[403,500,502,503])
def test_scheduler_failure_never_opens(env, outputs, monkeypatch, status):
    def scheduler(*a,**kw):raise HTTPException(status,'synthetic failure')
    monkeypatch.setattr(portal,'call_slurm',scheduler)
    monkeypatch.setattr(portal,'open_stdout_file',lambda *a:pytest.fail('must not open after scheduler failure'))
    assert get_output().status_code==status


def test_empty_scheduler_record_never_opens(env, outputs, monkeypatch):
    monkeypatch.setattr(portal,'call_slurm',lambda *a,**k:{'jobs':[]})
    monkeypatch.setattr(portal,'open_stdout_file',lambda *a:pytest.fail('missing job must not open'))
    assert get_output().status_code==404


def test_file_growth_is_still_bounded(env, outputs, monkeypatch):
    path=outputs/'slurm-101.out';path.write_text('small')
    env.jobs[101]['stdout']=str(path)
    class GrowingFile:
        def __enter__(self):return self
        def __exit__(self,*a):os.close(self.fd)
        def read(self,n):assert n==1024*1024+1;return b'x'*n
    def grow(fd,*a):f=GrowingFile();f.fd=fd;return f
    monkeypatch.setattr(portal.os,'fdopen',grow)
    assert get_output().status_code==413


def test_fd_walk_uses_nofollow_for_every_component(env, outputs, monkeypatch):
    path=outputs/'slurm-101.out';path.write_text('SYNTHETIC')
    env.jobs[101]['stdout']=str(path)
    actual=os.open;calls=[]
    def record(name, flags, *a, **kw):
        calls.append((name,flags,kw));return actual(name,flags,*a,**kw)
    monkeypatch.setattr(job_output.os,'open',record)
    assert get_output().status_code==200
    assert calls and all(flags&os.O_NOFOLLOW for _,flags,_ in calls)
    assert all(flags&os.O_DIRECTORY for _,flags,_ in calls[:-1])
    assert all('dir_fd' in kw for _,_,kw in calls[1:])

@pytest.mark.parametrize('job_id',[127,129])
def test_observed_historical_pattern_resolves_without_file_access(monkeypatch,job_id):
    # Saved accounting metadata only; never stat/open any real job output.
    report=Path(__file__).resolve().parents[1]/'evidence/accounting-metadata-prior.json'
    rows=json.loads(report.read_text())['accounting']['stdout'].strip().splitlines()
    row=next(line.split('|') for line in rows if line.startswith(str(job_id)+'|'))
    root='/home/lailai/slurm_contention_runs/mps-20261104T082034Z-cee9c5d4/jobs'
    monkeypatch.setenv('PORTAL_OUTPUT_ROOTS',json.dumps([root]))
    with patch.object(job_output.os,'open',side_effect=AssertionError('Pure resolution must not open real files')):
        result=job_output.resolve_stdout_path({'stdout':row[4],'working_directory':row[5]},job_id)
    assert result==row[4].replace('%j',str(job_id))


def test_client_path_query_cannot_override_metadata(env,outputs):
    (outputs/'slurm-101.out').write_text('APPROVED SYNTHETIC')
    env.jobs[101]['stdout']=str(outputs/'slurm-%j.out')
    with TestClient(portal.app) as client:
        login(client)
        response=client.get('/jobs/101/output',params={'path':'/etc/passwd','stdout':'/etc/passwd','user':'admin_test'})
    assert response.status_code==200 and response.json()['output']=='APPROVED SYNTHETIC'
