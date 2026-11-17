import requests
from getpass import getpass
from fastapi import HTTPException

from app import require_job_owner

BASE_URL = "http://127.0.0.1:8002"

USERS = ("lailai", "mangkud")

sessions = {}
job_ids = {}


def login(username):
    session = requests.Session()

    password = getpass(
        f"Portal password for {username}: "
    )

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
            f"{username} login failed: "
            f"HTTP {response.status_code}"
        )

    sessions[username] = {
        "session": session,
        "csrf": response.json()["csrf_token"],
    }


def submit_job(username):
    credentials = sessions[username]

    payload = {
        "name": f"management-test-{username}",
        "script": """#!/bin/bash
echo "Testing ownership authorization"
sleep 120
echo "Finished"
""",
        "cpus": 1,
        "memory_mb": 512,
        "time_minutes": 4,
        "gpus": 0,
        "gpu_mode": "none",
        "mps_share": 0,
    }

    response = credentials["session"].post(
        f"{BASE_URL}/jobs",
        json=payload,
        headers={
            "X-Portal-CSRF": credentials["csrf"]
        },
        timeout=20,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"Submission failed for {username}: "
            f"HTTP {response.status_code}"
        )

    job_id = response.json()["job_id"]
    job_ids[username] = job_id

    print(f"Submitted {username}: Job {job_id}")


def verify_ownership(username, job_id, expected):
    try:
        require_job_owner(job_id, username)
        status = 200

    except HTTPException as exc:
        status = exc.status_code

    result = "PASS" if status == expected else "FAIL"

    print(
        f"{result}: "
        f"User={username}, "
        f"Job={job_id}, "
        f"HTTP={status}, "
        f"Expected={expected}"
    )


try:
    for username in USERS:
        login(username)

    for username in USERS:
        submit_job(username)

    print("\n--- Ownership Verification ---")

    verify_ownership("lailai", job_ids["lailai"], 200)
    verify_ownership("lailai", job_ids["mangkud"], 404)
    verify_ownership("mangkud", job_ids["lailai"], 404)
    verify_ownership("mangkud", job_ids["mangkud"], 200)

finally:
    for credentials in sessions.values():
        try:
            credentials["session"].post(
                f"{BASE_URL}/auth/logout",
                headers={
                    "X-Portal-CSRF": credentials["csrf"]
                },
                timeout=10,
            )
        except requests.RequestException:
            pass

        credentials["session"].close()