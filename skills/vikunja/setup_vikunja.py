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


def _api(path: str, body=None, token: str = "", method: str | None = None) -> dict | None:
    headers: dict = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if method is None:
        method = "POST" if body is not None else "GET"
    req = urllib.request.Request(
        f"{BASE}/api/v1{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers=headers, method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"[vikunja-setup] {path}: {e}", file=sys.stderr)
        return None


def _create_api_token(slug: str, login_token: str) -> str:
    """Create a long-lived Vikunja API token (tk_...) for use by the MCP server.
    Login JWTs expire in ~10 min — API tokens can be set far in the future.
    Returns the token string or empty string on failure."""
    # Discover permission groups dynamically from GET /routes
    routes = _api("/routes", token=login_token)
    permissions: dict = {}
    if isinstance(routes, list):
        for r in routes:
            group = r if isinstance(r, str) else (r.get("name") or r.get("group") or "")
            group = str(group).split("/")[0].strip().lower()
            if group and group not in permissions:
                permissions[group] = {
                    "read": True, "readAll": True,
                    "create": True, "update": True, "delete": True,
                }
    if not permissions:
        # Hardcoded fallback for v2.3.0 known groups
        for g in ("tasks", "projects", "labels", "users", "teams",
                  "filters", "subscriptions", "notifications", "buckets"):
            permissions[g] = {"read": True, "readAll": True,
                               "create": True, "update": True, "delete": True}

    result = _api("/tokens", {
        "title": f"{slug}-mcp",
        "permissions": permissions,
        "expires_at": "2125-01-01T00:00:00Z",
    }, token=login_token, method="PUT")

    if result and "token" in result:
        t = result["token"]
        print(f"[vikunja-setup] API token created (long-lived)")
        return t
    print(f"[vikunja-setup] API token creation failed: {result} — MCP will use login JWT (expires ~10 min)", file=sys.stderr)
    return ""


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

    # Create default project — Vikunja v2 uses PUT for collection create (POST = 405)
    proj = _api("/projects", {"title": "Tasks", "color": "#4776E6"}, token=token, method="PUT")
    if not (proj and "id" in proj):
        # Fallback: Vikunja auto-creates a default project on registration — find it
        projs = _api("/projects", token=token) or []
        proj = next(
            (p for p in sorted(projs, key=lambda x: x.get("id", 0))
             if not p.get("is_archived") and p.get("id", 0) > 0),
            None,
        )
    project_id = str(proj["id"]) if proj and "id" in proj else ""

    # Create long-lived API token (tk_...) so MCP doesn't expire in ~10 min
    api_token = _create_api_token(slug, token)

    append_env(
        VIKUNJA_URL="http://localhost:3456",
        VIKUNJA_USERNAME=username,
        VIKUNJA_PASSWORD=password,
        VIKUNJA_TOKEN=token,
        VIKUNJA_PROJECT_ID=project_id,
        VIKUNJA_API_TOKEN=api_token,
    )
    print(f"[vikunja-setup] configured: user={username} project_id={project_id} api_token={'ok' if api_token else 'FAILED-fallback-to-jwt'}")


if __name__ == "__main__":
    main()
