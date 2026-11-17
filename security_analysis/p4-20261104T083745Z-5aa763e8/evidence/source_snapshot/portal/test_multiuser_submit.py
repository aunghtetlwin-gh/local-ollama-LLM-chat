import requests
from getpass import getpass

BASE_URL = "http://127.0.0.1:8002"

username = "mangkud"

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

if login.status_code != 200:
    print("Login failed:", login.status_code)
    raise SystemExit(1)

print("Login successful:", username)

csrf_token = login.json()["csrf_token"]

job = {
    "name": "portal-mangkud-test",
    "script": """#!/bin/bash
echo "Slurm user: $(whoami)"
echo "Job ID: $SLURM_JOB_ID"
sleep 5
echo "Job completed"
""",
    "cpus": 1,
    "memory_mb": 512,
    "time_minutes": 2,
    "gpus": 0,
    "gpu_mode": "none",
    "mps_share": 0,
}

response = session.post(
    f"{BASE_URL}/jobs",
    json=job,
    headers={
        "X-Portal-CSRF": csrf_token,
    },
    timeout=20,
)

print("Submission status:", response.status_code)

if response.ok:
    data = response.json()
    print("Job ID:", data.get("job_id"))
    print("Slurm errors:", data.get("errors", []))
    print("Warnings:", data.get("warnings", []))
else:
    print("Submission failed:", response.status_code)
    print("Error response:", response.text[:3000])

session.post(
    f"{BASE_URL}/auth/logout",
    headers={"X-Portal-CSRF": csrf_token},
    timeout=10,
)

session.close()