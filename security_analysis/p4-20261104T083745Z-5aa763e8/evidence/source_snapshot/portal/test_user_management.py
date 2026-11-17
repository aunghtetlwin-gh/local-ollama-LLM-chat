import getpass
import requests

BASE = "http://127.0.0.1:8003"
TIMEOUT = 10


def check(name, actual, expected):
    status = "PASS" if actual == expected else "FAIL"
    print(f"{status}: {name} | HTTP {actual} | Expected {expected}")

    if actual != expected:
        raise SystemExit(f"Test failed: {name}")


def login(username, password):
    session = requests.Session()

    response = session.post(
        f"{BASE}/auth/login",
        json={
            "username": username,
            "password": password,
        },
        timeout=TIMEOUT,
    )

    return session, response


def admin_headers(csrf):
    return {
        "X-Portal-CSRF": csrf,
        "Content-Type": "application/json",
    }


def main():
    print("\n=== Isolated User Management Integration Test ===")

    admin_password = getpass.getpass(
        "Existing portal password for lailai: "
    )

    researcher_password = getpass.getpass(
        "New TEST portal password for mangkud (min 12 chars): "
    )

    if len(researcher_password) < 12:
        raise SystemExit("Test password must contain at least 12 characters")

    # 1. Admin login
    admin, response = login("lailai", admin_password)
    check("Administrator login", response.status_code, 200)

    csrf = response.json()["csrf_token"]

    # 2. Verify mangkud is absent from the test DB
    response = admin.get(
        f"{BASE}/admin/users",
        timeout=TIMEOUT,
    )
    check("Admin lists users", response.status_code, 200)

    existing_users = {
        user["username"]
        for user in response.json()["users"]
    }

    if "mangkud" in existing_users:
        raise SystemExit(
            "mangkud already exists in test DB. "
            "Stop rather than modifying an existing account."
        )

    # 3. Missing CSRF must fail
    response = admin.post(
        f"{BASE}/admin/users",
        json={
            "username": "mangkud",
            "password": researcher_password,
        },
        timeout=TIMEOUT,
    )
    check("Registration without CSRF", response.status_code, 403)

    # 4. Nonexistent Linux account must fail
    response = admin.post(
        f"{BASE}/admin/users",
        headers=admin_headers(csrf),
        json={
            "username": "nonexistent_test_user_928",
            "password": researcher_password,
        },
        timeout=TIMEOUT,
    )
    check("Nonexistent Linux account", response.status_code, 400)

    # 5. Successful researcher creation
    response = admin.post(
        f"{BASE}/admin/users",
        headers=admin_headers(csrf),
        json={
            "username": "mangkud",
            "password": researcher_password,
        },
        timeout=TIMEOUT,
    )
    check("Create existing Linux/Slurm researcher", response.status_code, 201)

    # 6. Duplicate registration must fail
    response = admin.post(
        f"{BASE}/admin/users",
        headers=admin_headers(csrf),
        json={
            "username": "mangkud",
            "password": researcher_password,
        },
        timeout=TIMEOUT,
    )
    check("Duplicate researcher registration", response.status_code, 409)

    # 7. Researcher login
    researcher, response = login("mangkud", researcher_password)
    check("Researcher login", response.status_code, 200)

    researcher_csrf = response.json()["csrf_token"]

    # 8. Researcher cannot list users
    response = researcher.get(
        f"{BASE}/admin/users",
        timeout=TIMEOUT,
    )
    check("Researcher cannot list users", response.status_code, 403)

    # 9. Researcher cannot create accounts
    response = researcher.post(
        f"{BASE}/admin/users",
        headers=admin_headers(researcher_csrf),
        json={
            "username": "another_test_user",
            "password": researcher_password,
        },
        timeout=TIMEOUT,
    )
    check("Researcher cannot create users", response.status_code, 403)

    # 10. Disable researcher
    response = admin.patch(
        f"{BASE}/admin/users/mangkud/status",
        headers=admin_headers(csrf),
        json={"enabled": False},
        timeout=TIMEOUT,
    )
    check("Disable researcher", response.status_code, 200)

    # 11. Existing session must be revoked
    response = researcher.get(
        f"{BASE}/auth/me",
        timeout=TIMEOUT,
    )
    check("Existing session revoked", response.status_code, 401)

    # 12. Disabled researcher cannot log in
    _, response = login("mangkud", researcher_password)
    check("Disabled researcher login rejected", response.status_code, 401)

    # 13. Re-enable researcher
    response = admin.patch(
        f"{BASE}/admin/users/mangkud/status",
        headers=admin_headers(csrf),
        json={"enabled": True},
        timeout=TIMEOUT,
    )
    check("Re-enable researcher", response.status_code, 200)

    # 14. Researcher can log in again
    _, response = login("mangkud", researcher_password)
    check("Re-enabled researcher login", response.status_code, 200)

    print("\nAll 14 User Management tests passed.")


if __name__ == "__main__":
    main()