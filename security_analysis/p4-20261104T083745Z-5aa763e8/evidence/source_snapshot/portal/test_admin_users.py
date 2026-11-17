import getpass
import requests

BASE = "http://127.0.0.1:8002"

username = input("Portal username: ")
password = getpass.getpass("Portal password: ")

session = requests.Session()

login = session.post(
    f"{BASE}/auth/login",
    json={
        "username": username,
        "password": password,
    },
    timeout=10,
)

print("Login status:", login.status_code)

if login.status_code != 200:
    raise SystemExit("Login failed")

response = session.get(
    f"{BASE}/admin/users",
    timeout=10,
)

print("User list status:", response.status_code)

if response.status_code == 200:
    for user in response.json().get("users", []):
        print(
            user["username"],
            user["role"],
            "enabled" if user["enabled"] else "disabled",
        )
else:
    print(response.json())