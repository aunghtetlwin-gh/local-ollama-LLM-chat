import time
import requests
from getpass import getpass

BASE = "http://127.0.0.1:8002"
USERNAME = "mangkud"

session = requests.Session()

password = getpass(f"Portal password for {USERNAME}: ")

login = session.post(
    f"{BASE}/auth/login",
    json={
        "username": USERNAME,
        "password": password,
    },
    timeout=10,
)

del password

if login.status_code != 200:
    raise SystemExit(f"Login failed: HTTP {login.status_code}")

csrf = login.json()["csrf_token"]

try:
    # Submit a disposable job.
    response = session.post(
        f"{BASE}/jobs",
        json={
            "name": "requeue-test-mangkud",
            "script": "#!/bin/bash\nsleep 120\n",
            "cpus": 1,
            "memory_mb": 512,
            "time_minutes": 4,
            "gpus": 0,
            "gpu_mode": "none",
            "mps_share": 0,
        },
        headers={"X-Portal-CSRF": csrf},
        timeout=20,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"Submission failed: {response.status_code} "
            f"{response.text[:500]}"
        )

    data = response.json()

    if data.get("errors"):
        raise RuntimeError(f"Slurm submission errors: {data['errors']}")

    job_id = data["job_id"]
    print(f"Submitted job: {job_id}")

    # Wait until the job starts running.
    running = False

    for attempt in range(20):
        response = session.get(
            f"{BASE}/jobs/{job_id}",
            timeout=10,
        )

        if response.status_code == 200:
            state = response.json().get("state")
            print("Current state:", state)

            if state == "RUNNING":
                running = True
                break

        time.sleep(2)

    if not running:
        print("Job did not reach RUNNING; no requeue attempted.")
    else:
        print(f"\nRequeueing own job {job_id}")

        response = session.post(
            f"{BASE}/jobs/{job_id}/requeue",
            headers={"X-Portal-CSRF": csrf},
            timeout=15,
        )

        print("Requeue HTTP:", response.status_code)

        try:
            result = response.json()
            print("Response:", result)
        except ValueError:
            print("Non-JSON response")

finally:
    try:
        session.post(
            f"{BASE}/auth/logout",
            headers={"X-Portal-CSRF": csrf},
            timeout=10,
        )
    finally:
        session.close()