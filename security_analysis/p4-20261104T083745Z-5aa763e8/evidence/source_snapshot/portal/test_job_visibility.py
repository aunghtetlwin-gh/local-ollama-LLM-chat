import requests
from getpass import getpass

BASE_URL = "http://127.0.0.1:8002"


def test_user(username):
    session = requests.Session()

    password = getpass(
        f"Portal password for {username}: "
    )

    login = session.post(
        f"{BASE_URL}/auth/login",
        json={
            "username": username,
            "password": password,
        },
        timeout=10,
    )

    del password

    print(f"\nUser: {username}")
    print("Login:", login.status_code)

    if login.status_code != 200:
        session.close()
        return

    response = session.get(
        f"{BASE_URL}/jobs/active",
        timeout=15,
    )

    print("Active jobs status:", response.status_code)

    if response.ok:
        data = response.json()

        print("Visible jobs:", data.get("count"))

        for job in data.get("jobs", []):
            print(
                f"ID={job.get('job_id')} "
                f"Owner={job.get('user')} "
                f"State={job.get('state')}"
            )
    else:
        print("Request failed:", response.text[:1000])

    me = session.get(
        f"{BASE_URL}/auth/me",
        timeout=10,
    )

    if me.ok:
        csrf_token = me.json()["csrf_token"]

        session.post(
            f"{BASE_URL}/auth/logout",
            headers={"X-Portal-CSRF": csrf_token},
            timeout=10,
        )

    session.close()


test_user("lailai")
test_user("mangkud")