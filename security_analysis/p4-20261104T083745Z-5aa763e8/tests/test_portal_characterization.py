"""Passing characterization tests reproduce limitations; they are NOT security approvals."""
import sqlite3
from test_portal_security import env,portal,auth,login,PASSWORD
from fastapi.testclient import TestClient

def test_missing_login_field_echoes_synthetic_password(env):
 # Characterize FastAPI's actual validation response; no production credentials used.
 with TestClient(portal.app) as c:
  secret='SYNTHETIC-PASSWORD-SENTINEL-ONLY';response=c.post('/auth/login',json={'password':secret})
  assert response.status_code==422 and secret in response.text

def test_auth_database_failure_denies_access_with_500(env,monkeypatch):
 def unavailable():raise sqlite3.OperationalError('SYNTHETIC DATABASE OUTAGE')
 with TestClient(portal.app,raise_server_exceptions=False) as c:
  login(c);monkeypatch.setattr(auth,'connect',unavailable);response=c.get('/jobs/active')
  assert response.status_code==500 and response.text=='Internal Server Error'
 assert not env.calls
