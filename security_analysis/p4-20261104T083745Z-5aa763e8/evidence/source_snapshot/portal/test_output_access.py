import requests
from getpass import getpass

BASE = "http://127.0.0.1:8002"

TESTS = {
    "lailai": {
        107: 200,  # Own job
        106: 404,  # mangkud's job
    },
    "mangkud": {
        106: 200,  # Own job
        107: 404,  # lailai's job
    },
}

for username, jobs in TESTS.items():
    session = requests.Session()

    password = getpass(f"Portal password for {username}: ")

    login = session.post(
        f"{BASE}/auth/login",
        json={"username": username, "password": password},
        timeout=10,
    )

    del password

    if login.status_code != 200:
        print(f"{username}: Login failed: HTTP {login.status_code}")
        session.close()
        continue

    csrf = login.json()["csrf_token"]

    try:
        for job_id, expected in jobs.items():
            response = session.get(
                f"{BASE}/jobs/{job_id}/output",
                timeout=15,
            )

            result = (
                "PASS"
                if response.status_code == expected
                else "FAIL"
            )

            print(
                f"{result}: "
                f"User={username}, "
                f"Job={job_id}, "
                f"HTTP={response.status_code}, "
                f"Expected={expected}"
            )

            # Don't print potentially sensitive job output.
            if response.status_code == 200:
                data = response.json()
                print(
                    "  Output length:",
                    len(data.get("output", "")),
                )

    finally:
        session.post(
            f"{BASE}/auth/logout",
            headers={"X-Portal-CSRF": csrf},
            timeout=10,
        )
        session.close()