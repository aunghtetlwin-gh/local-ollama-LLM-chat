import requests
from getpass import getpass

BASE = "http://127.0.0.1:8002"
USERS = ("lailai", "mangkud")

sessions = {}
jobs = {}


def login(username):
    session = requests.Session()
    password = getpass(f"Portal password for {username}: ")

    response = session.post(
        f"{BASE}/auth/login",
        json={"username": username, "password": password},
        timeout=10,
    )
    del password

    if response.status_code != 200:
        raise RuntimeError(f"{username} login failed: {response.status_code}")

    sessions[username] = {
        "session": session,
        "csrf": response.json()["csrf_token"],
    }
    print(f"{username}: login OK")


def submit(username):
    credentials = sessions[username]

    response = credentials["session"].post(
        f"{BASE}/jobs",
        json={
            "name": f"cancel-test-{username}",
            "script": "#!/bin/bash\nsleep 180\n",
            "cpus": 1,
            "memory_mb": 512,
            "time_minutes": 5,
            "gpus": 0,
            "gpu_mode": "none",
            "mps_share": 0,
        },
        headers={"X-Portal-CSRF": credentials["csrf"]},
        timeout=20,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"{username} submission failed: "
            f"{response.status_code} {response.text[:300]}"
        )

    jobs[username] = response.json()["job_id"]
    print(f"Submitted {username}: job {jobs[username]}")


def post_action(viewer, job_id, action, csrf=None):
    credentials = sessions[viewer]

    return credentials["session"].post(
        f"{BASE}/jobs/{job_id}/{action}",
        headers={"X-Portal-CSRF": (
            credentials["csrf"] if csrf is None else csrf
        )},
        timeout=15,
    )


def check(label, response, expected):
    result = "PASS" if response.status_code == expected else "FAIL"
    print(
        f"{result}: {label}: "
        f"HTTP {response.status_code}, expected {expected}"
    )


try:
    for user in USERS:
        login(user)

    for user in USERS:
        submit(user)

    print("\n--- Cross-user cancellation ---")

    check(
        "lailai cannot cancel mangkud job",
        post_action("lailai", jobs["mangkud"], "cancel"),
        404,
    )

    check(
        "mangkud cannot cancel lailai job",
        post_action("mangkud", jobs["lailai"], "cancel"),
        404,
    )

    print("\n--- Cross-user requeue ---")

    check(
        "lailai cannot requeue mangkud job",
        post_action("lailai", jobs["mangkud"], "requeue"),
        404,
    )

    check(
        "mangkud cannot requeue lailai job",
        post_action("mangkud", jobs["lailai"], "requeue"),
        404,
    )

    print("\n--- Invalid CSRF ---")

    response = post_action(
        "mangkud",
        jobs["mangkud"],
        "cancel",
        csrf="invalid-csrf-token",
    )

    print(
        "Invalid CSRF:",
        response.status_code,
        "(must be rejected)",
    )

    if response.status_code in (200, 202, 204):
        raise RuntimeError("SECURITY FAILURE: Invalid CSRF accepted")

    print("\n--- Own-job cancellation ---")

    for user in USERS:
        response = post_action(user, jobs[user], "cancel")

        print(
            f"{user} cancel own job {jobs[user]}: "
            f"HTTP {response.status_code}"
        )

        if not response.ok:
            print("Response:", response.text[:500])

finally:
    for user, credentials in sessions.items():
        try:
            credentials["session"].post(
                f"{BASE}/auth/logout",
                headers={"X-Portal-CSRF": credentials["csrf"]},
                timeout=10,
            )
        except requests.RequestException:
            pass

        credentials["session"].close()

    print("\nSubmitted test job IDs:", jobs)