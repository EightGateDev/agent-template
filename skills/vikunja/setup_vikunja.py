#!/usr/bin/env python3
"""
First-time Vikunja setup — idempotent, called from start.sh on every boot.
If already configured (VIKUNJA_TOKEN in .env) → just verifies and exits.
If not configured → registers user, creates project, appends creds to .env.
"""
from __future__ import annotations
import json, os, secrets, sys, urllib.request
from pathlib import Path

AGENT_DIR = Path(os.environ.get("AGENT_DIR", os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
BASE = "http://localhost:3456"


def _api(path: str, body=None, token: str = "") -> dict | None:
    headers: dict = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        f"{BASE}/api/v1{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers=headers, method="POST" if body is not None else "GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"[vikunja-setup] {path}: {e}", file=sys.stderr)
        return None


def load_env() -> dict:
    env: dict = {}
    f = AGENT_DIR / ".env"
    if f.exists():
        for line in f.read_text().splitlines():
            s = line.strip()
            if "=" in s and not s.startswith("#"):
                k, v = s.split("=", 1)
                env[k.strip()] = v.strip().strip('"\'')
    return env


def append_env(**kwargs) -> None:
    f = AGENT_DIR / ".env"
    lines = "\n# Vikunja (auto-configured)\n"
    for k, v in kwargs.items():
        lines += f"{k}={v}\n"
    with open(f, "a") as fp:
        fp.write(lines)


def main() -> None:
    env = load_env()

    # Already configured — verify connection and exit
    if env.get("VIKUNJA_TOKEN") and env.get("VIKUNJA_USERNAME"):
        result = _api("/info")
        if result:
            print(f"[vikunja-setup] already configured, Vikunja OK v{result.get('version','?')}")
        return

    # Wait for Vikunja to be ready (it may have just started)
    import time
    for _ in range(6):
        result = _api("/info")
        if result:
            break
        time.sleep(2)
    else:
        print("[vikunja-setup] Vikunja not reachable after 12s — skip", file=sys.stderr)
        return

    slug = AGENT_DIR.name
    username = f"agent_{slug}"
    password = secrets.token_urlsafe(16)
    email    = f"{slug}@agent.local"

    # Register user
    reg = _api("/register", {"username": username, "password": password, "email": email})
    if not reg or "id" not in reg:
        print(f"[vikunja-setup] register failed (may already exist): {reg}", file=sys.stderr)

    # Login
    login = _api("/login", {"username": username, "password": password})
    if not login or "token" not in login:
        print(f"[vikunja-setup] login failed: {login}", file=sys.stderr)
        return
    token = login["token"]

    # Create default project
    proj = _api("/projects", {"title": "Tasks", "color": "#4776E6"}, token=token)
    project_id = str(proj["id"]) if proj and "id" in proj else ""

    append_env(
        VIKUNJA_URL="http://localhost:3456",
        VIKUNJA_USERNAME=username,
        VIKUNJA_PASSWORD=password,
        VIKUNJA_TOKEN=token,
        VIKUNJA_PROJECT_ID=project_id,
    )
    print(f"[vikunja-setup] configured: user={username} project_id={project_id}")


if __name__ == "__main__":
    main()
