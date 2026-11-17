"""Staging-only check of the documented SSH-forward browser origin shape."""
from test_chat_characterization import fixtures,server,db,register_user,block_external_services
import pytest

@pytest.mark.parametrize("base",["http://localhost:18000","http://127.0.0.1:18000"])
def test_forwarded_browser_host_and_port_keep_origin_and_session_working(db,register_user,base):
 with fixtures.TestClient(server.my_api,base_url=base,headers={"Origin":base}) as client:
  assert register_user(client).status_code==201
  assert client.get("/auth/session").status_code==200
  assert client.post("/logout",headers={"Origin":"http://untrusted.example.test"}).status_code==403
  assert client.get("/auth/session").status_code==200
  assert client.post("/logout").status_code==200
  assert client.get("/auth/session").status_code==401
