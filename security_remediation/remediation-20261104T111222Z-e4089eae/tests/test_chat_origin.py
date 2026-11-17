"""Same-origin backend regressions. Browser SameSite/CORS is not simulated."""
from test_chat_characterization import db,client,register_user,block_external_services,server
import pytest

@pytest.mark.parametrize('origin',['https://untrusted.example.test','null','','http://testserver:9','https://testserver','http://testserver.evil.test','http://testserver@evil.test','http://testserver/path','http://testserver?','http://testserver:0'])
@pytest.mark.parametrize('action',['delete','logout','chat'])
def test_untrusted_or_invalid_origins_preserve_state(client,db,register_user,origin,action):
 uid=register_user(client).json()['user']['id'];cid=server.create_conversation('private',uid)
 headers={'Origin':origin}
 if action=='delete':r=client.delete(f'/conversations/{cid}',headers=headers)
 elif action=='logout':r=client.post('/logout',headers=headers)
 else:r=client.post('/chat',headers=headers,json={'conversation_id':cid,'message':'do not run'})
 assert r.status_code==403 and r.headers['cache-control']=='no-store'
 assert client.get('/auth/session').status_code==200
 assert db.raw.execute('SELECT count(*) FROM conversations').fetchone()[0]==1
 assert db.raw.execute('SELECT count(*) FROM messages').fetchone()[0]==0

@pytest.mark.parametrize('header',[None,'http://testserver.evil.test/page','https://untrusted.example.test/path'])
def test_missing_origin_requires_matching_referer(client,db,register_user,header):
 uid=register_user(client).json()['user']['id'];cid=server.create_conversation('private',uid);client.headers.pop('Origin')
 h={} if header is None else {'Referer':header};r=client.delete(f'/conversations/{cid}',headers=h);assert r.status_code==403
 assert db.raw.execute('SELECT count(*) FROM conversations').fetchone()[0]==1

@pytest.mark.parametrize('origin',['http://testserver','http://testserver:80','http://TESTSERVER'])
def test_matching_origin_allows_owned_delete_and_logout(client,db,register_user,origin):
 uid=register_user(client).json()['user']['id'];cid=server.create_conversation('private',uid)
 assert client.delete(f'/conversations/{cid}',headers={'Origin':origin}).status_code==200
 assert client.post('/logout',headers={'Origin':origin}).status_code==200
 assert client.get('/auth/session').status_code==401

def test_matching_referer_fallback(client,db,register_user):
 uid=register_user(client).json()['user']['id'];cid=server.create_conversation('private',uid);client.headers.pop('Origin')
 assert client.delete(f'/conversations/{cid}',headers={'Referer':'http://testserver/index.html?view=chat'}).status_code==200

def test_bad_origin_cannot_be_overridden_by_good_referer_or_proxy_headers(client,register_user):
 register_user(client)
 assert client.post('/logout',headers={'Origin':'http://evil.test','Referer':'http://testserver/','X-Forwarded-Host':'evil.test','X-Forwarded-Proto':'http'}).status_code==403
 assert client.get('/auth/session').status_code==200

def test_duplicate_origins_denied(client,register_user):
 register_user(client)
 assert client.post('/logout',headers=[('Origin','http://testserver'),('Origin','http://evil.test')]).status_code==403

def test_login_registration_also_require_origin(client,register_user):
 client.headers.pop('Origin')
 body={'email':'owner@example.com','password':'a synthetic password','password_confirmation':'a synthetic password'}
 assert client.post('/register',json=body).status_code==403
 assert client.post('/login',json=body).status_code==403
 assert client.post('/register',headers={'Origin':'http://testserver'},json=body).status_code==201
