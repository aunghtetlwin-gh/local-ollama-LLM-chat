import subprocess

import requests

SLURMRESTD = "http://127.0.0.1:6820"
SLURM_API_VERSION = "v0.0.45"

# Explicit mapping of approved portal users to Slurm identities.
# Never accept arbitrary Linux usernames from browser input.
ALLOWED_SLURM_USERS = {
    "lailai",
    "mangkud",
    "apple",
}


class SlurmIdentityError(Exception):
    pass


def is_allowed_slurm_user(username: str) -> bool:
    """Single default-deny policy for onboarding and credential issuance."""
    return username in ALLOWED_SLURM_USERS


def get_slurm_token(username: str) -> str:
    """
    Generate a short-lived Slurm JWT for an approved Linux user.

    Prototype implementation:
    - lailai: run scontrol directly.
    - mangkud: execute scontrol under mangkud's Linux identity.

    Tokens are returned to the backend only.
    """

    if not is_allowed_slurm_user(username):
        raise SlurmIdentityError(
            "User is not authorized for Slurm access"
        )

    command = [
        "/usr/bin/scontrol",
        "token",
        "lifespan=300",
    ]

    if username != "lailai":
        command = [
            "/usr/bin/sudo",
            "-n",
            "-u",
            username,
            *command,
        ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )

    except (
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
    ) as exc:
        raise SlurmIdentityError(
            "Unable to obtain Slurm credentials"
        ) from exc

    output = result.stdout.strip()

    if not output.startswith("SLURM_JWT="):
        raise SlurmIdentityError(
            "Unexpected Slurm token response"
        )

    return output.split("=", 1)[1]


def slurm_headers(username: str) -> dict:
    """
    Build Slurm REST authentication headers.

    The username must come from an authenticated,
    server-side portal identity.
    """

    token = get_slurm_token(username)

    return {
        "X-SLURM-USER-NAME": username,
        "X-SLURM-USER-TOKEN": token,
    }


def test_slurm_connection(username: str) -> int:
    """
    Test authentication without submitting a job.
    """

    response = requests.get(
        f"{SLURMRESTD}/slurm/{SLURM_API_VERSION}/ping",
        headers=slurm_headers(username),
        timeout=10,
    )

    return response.status_code