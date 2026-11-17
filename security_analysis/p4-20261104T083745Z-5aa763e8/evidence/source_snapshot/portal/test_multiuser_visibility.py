import requests
from getpass import getpass

BASE_URL = "http://127.0.0.1:8002"

sessions = {}
job_ids = {}

USERS = ["lailai", "mangkud"]


def login(username):
    session = requests.Session()

    password = getpass(f"Portal password for {username}: ")

    response = session.post(
        f"{BASE_URL}/auth/login",
        json={
            "username": username,
            "password": password,
        },
        timeout=10,
    )

    del password

    if response.status_code != 200:
        raise RuntimeError(
            f"{username} login failed: {response.status_code}"
        )

    sessions[username] = {
        "session": session,
        "csrf_token": response.json()["csrf_token"],
    }


def submit_job(username):
    user_session = sessions[username]
    session = user_session["session"]

    job = {
        "name": f"visibility-{username}",
        "script": f"""#!/bin/bash
echo "Slurm user: $(whoami)"
echo "Job ID: $SLURM_JOB_ID"
sleep 90
echo "Finished"
""",
        "cpus": 1,
        "memory_mb": 512,
        "time_minutes": 3,
        "gpus": 0,
        "gpu_mode": "none",
        "mps_share": 0,
    }

    response = session.post(
        f"{BASE_URL}/jobs",
        json=job,
        headers={
            "X-Portal-CSRF": user_session["csrf_token"],
        },
        timeout=20,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"{username} submission failed: "
            f"{response.status_code} {response.text[:500]}"
        )

    job_id = response.json()["job_id"]

    job_ids[username] = job_id

    print(f"Submitted {username}: job {job_id}")


def check_visibility(username):
    session = sessions[username]["session"]

    response = session.get(
        f"{BASE_URL}/jobs/active",
        timeout=15,
    )

    print(f"\nLogged in as {username}")
    print("HTTP status:", response.status_code)

    if response.status_code != 200:
        print(response.text[:500])
        return

    jobs = response.json().get("jobs", [])

    for job in jobs:
        print(
            f"Job ID={job['job_id']} "
            f"Owner={job['user']} "
            f"State={job['state']}"
        )


try:
    for username in USERS:
        login(username)

    for username in USERS:
        submit_job(username)

    for username in USERS:
        check_visibility(username)

finally:
    for username, credentials in sessions.items():
        try:
            credentials["session"].post(
                f"{BASE_URL}/auth/logout",
                headers={
                    "X-Portal-CSRF": credentials["csrf_token"],
                },
                timeout=10,
            )
        except requests.RequestException:
            pass

        credentials["session"].close()