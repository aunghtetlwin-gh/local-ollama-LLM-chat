import requests
from getpass import getpass

BASE_URL = "http://127.0.0.1:8002"

TEST_JOB_IDS = {106, 107, 108}


def test_history(username):
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
    print("Login status:", login.status_code)

    if login.status_code != 200:
        session.close()
        return

    csrf_token = login.json()["csrf_token"]

    try:
        response = session.get(
            f"{BASE_URL}/jobs/history",
            timeout=20,
        )

        print("History status:", response.status_code)

        if not response.ok:
            print("Error:", response.text[:1000])
            return

        data = response.json()
        jobs = data.get("jobs", [])

        print("Total history jobs:", data.get("count"))

        for job in jobs:
            if job.get("job_id") in TEST_JOB_IDS:
                print(
                    f"Job={job.get('job_id')} "
                    f"Owner={job.get('user')} "
                    f"State={job.get('state')}"
                )

        # Verify normal-user isolation.
        if username == "mangkud":
            other_users = [
                job for job in jobs
                if job.get("user") != username
            ]

            if other_users:
                print("FAIL: Other users' jobs are visible")
            else:
                print("PASS: No other users' jobs returned")

    finally:
        try:
            session.post(
                f"{BASE_URL}/auth/logout",
                headers={
                    "X-Portal-CSRF": csrf_token,
                },
                timeout=10,
            )
        finally:
            session.close()


test_history("lailai")
test_history("mangkud")