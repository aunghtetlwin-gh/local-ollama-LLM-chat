import requests
import time
from getpass import getpass

BASE_URL = "http://127.0.0.1:8002"

sessions = {}
job_ids = {}

USERS = ("lailai", "mangkud")


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
        "csrf": response.json()["csrf_token"],
    }

    print(f"{username}: Login successful")


def submit_job(username):
    credentials = sessions[username]

    payload = {
        "name": f"ownership-{username}",
        "script": """#!/bin/bash
echo "Testing job ownership"
sleep 90
echo "Completed"
""",
        "cpus": 1,
        "memory_mb": 512,
        "time_minutes": 3,
        "gpus": 0,
        "gpu_mode": "none",
        "mps_share": 0,
    }

    response = credentials["session"].post(
        f"{BASE_URL}/jobs",
        json=payload,
        headers={"X-Portal-CSRF": credentials["csrf"]},
        timeout=20,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"{username} submission failed: "
            f"{response.status_code} {response.text[:500]}"
        )

    job_id = response.json()["job_id"]
    job_ids[username] = job_id

    print(f"Submitted {username}: Job {job_id}")


def check_job(viewer, owner):
    job_id = job_ids[owner]
    session = sessions[viewer]["session"]

    response = session.get(
        f"{BASE_URL}/jobs/{job_id}",
        timeout=15,
    )

    expected = 200 if viewer == "lailai" or viewer == owner else 404

    result = "PASS" if response.status_code == expected else "FAIL"

    print(
        f"{result}: Viewer={viewer}, "
        f"JobOwner={owner}, "
        f"JobID={job_id}, "
        f"HTTP={response.status_code}, "
        f"Expected={expected}"
    )

    if response.status_code == 200:
        data = response.json()
        actual_owner = data.get("user")

        print(f"  Returned job owner: {actual_owner}")

        if actual_owner != owner:
            print("  FAIL: Incorrect job owner returned")


try:
    for username in USERS:
        login(username)

    for username in USERS:
        submit_job(username)

    print("\n--- Testing job ownership ---")

    for viewer in USERS:
        for owner in USERS:
            check_job(viewer, owner)

finally:
    for credentials in sessions.values():
        try:
            credentials["session"].post(
                f"{BASE_URL}/auth/logout",
                headers={
                    "X-Portal-CSRF": credentials["csrf"],
                },
                timeout=10,
            )
        except requests.RequestException:
            pass

        credentials["session"].close()