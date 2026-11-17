import requests
from getpass import getpass

BASE_URL = "http://127.0.0.1:8002"

TEST_JOBS = {
    109: "lailai",
    110: "mangkud",
}

for username in ("lailai", "mangkud"):
    session = requests.Session()

    password = getpass(f"Portal password for {username}: ")

    login = session.post(
        f"{BASE_URL}/auth/login",
        json={
            "username": username,
            "password": password,
        },
        timeout=10,
    )

    del password

    print(f"\nLogged in as: {username}")
    print("Login HTTP:", login.status_code)

    if login.status_code != 200:
        session.close()
        continue

    csrf = login.json()["csrf_token"]

    try:
        for job_id, owner in TEST_JOBS.items():
            response = session.get(
                f"{BASE_URL}/jobs/{job_id}",
                timeout=15,
            )

            expected = (
                200
                if username == "lailai" or username == owner
                else 404
            )

            result = (
                "PASS"
                if response.status_code == expected
                else "FAIL"
            )

            print(
                f"{result}: Viewer={username}, "
                f"Job={job_id}, "
                f"Owner={owner}, "
                f"HTTP={response.status_code}, "
                f"Expected={expected}"
            )

            if response.status_code == 200:
                actual_owner = response.json().get("user")

                if actual_owner != owner:
                    print(
                        "FAIL: Returned job owner is incorrect"
                    )

    finally:
        session.post(
            f"{BASE_URL}/auth/logout",
            headers={"X-Portal-CSRF": csrf},
            timeout=10,
        )
        session.close()