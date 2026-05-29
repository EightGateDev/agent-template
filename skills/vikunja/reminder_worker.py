#!/usr/bin/env python3
"""
Vikunja reminder worker — runs every 60s via systemd timer.
Finds due tasks, sends Telegram message, marks them with 'reminded' label.
Independent of Claude Code — no new Claude session spawned.
"""
from __future__ import annotations
import json, os, sys, urllib.request
from datetime import datetime, timezone
from pathlib import Path

AGENT_DIR = Path(os.environ.get("AGENT_DIR", "/opt/{{AGENT_NAME}}"))
REMINDED_LABEL = "reminded"


def load_env() -> dict:
    env: dict = {}
    f = AGENT_DIR / ".env"
    if f.exists():
        for line in f.read_text().splitlines():
            s = line.strip()
            if "=" in s and not s.startswith("#"):
                k, v = s.split("=", 1)
                env[k.strip()] = v.strip().strip('"\'')
    return {**os.environ, **env}


def _json_req(url: str, method: str = "GET", body=None, headers: dict | None = None) -> dict | list | None:
    headers = headers or {}
    data = json.dumps(body).encode() if body is not None else None
    if data:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"[vikunja] {method} {url}: {e}", file=sys.stderr)
        return None


def get_jwt(env: dict) -> str:
    u = env.get("VIKUNJA_USERNAME", "")
    p = env.get("VIKUNJA_PASSWORD", "")
    base = env.get("VIKUNJA_URL", "").rstrip("/")
    if not u or not base:
        return env.get("VIKUNJA_TOKEN", "")
    result = _json_req(f"{base}/api/v1/login", "POST", {"username": u, "password": p})
    if result and "token" in result:
        return result["token"]
    return env.get("VIKUNJA_TOKEN", "")


def vikunja(env: dict, method: str, path: str, body=None) -> dict | list | None:
    base = env.get("VIKUNJA_URL", "").rstrip("/")
    token = env["_jwt"]
    return _json_req(f"{base}/api/v1{path}", method, body, {"Authorization": f"Bearer {token}"})


def send_tg(env: dict, text: str) -> None:
    bot_token = env.get("TELEGRAM_BOT_TOKEN", "")
    owner_id  = env.get("TELEGRAM_OWNER_ID", "")
    if not bot_token or not owner_id:
        return
    _json_req(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        "POST",
        {"chat_id": owner_id, "text": text, "parse_mode": "HTML"},
    )


def ensure_label(env: dict) -> int | None:
    labels = vikunja(env, "GET", "/labels") or []
    for lb in labels:
        if lb.get("title") == REMINDED_LABEL:
            return lb["id"]
    result = vikunja(env, "POST", "/labels", {"title": REMINDED_LABEL, "hex_color": "888888"})
    return result["id"] if result and "id" in result else None


def is_due(due_str: str) -> bool:
    if not due_str:
        return False
    try:
        due = datetime.fromisoformat(due_str.replace("Z", "+00:00"))
        return due <= datetime.now(timezone.utc)
    except Exception:
        return False


def run(env: dict) -> None:
    project_id = env.get("VIKUNJA_PROJECT_ID", "")
    if not project_id:
        projects = vikunja(env, "GET", "/projects") or []
        # Pick first non-archived user project
        for p in sorted(projects, key=lambda x: x.get("id", 0)):
            if not p.get("is_archived") and p.get("id", 0) > 0:
                project_id = str(p["id"])
                break
    if not project_id:
        return

    tasks = vikunja(env, "GET", f"/projects/{project_id}/tasks") or []
    if not tasks:
        return

    reminded_id = ensure_label(env)
    sent = 0

    for task in tasks:
        if task.get("done"):
            continue
        if not is_due(task.get("due_date", "")):
            continue

        # Skip if already reminded
        if reminded_id and any(lb.get("id") == reminded_id for lb in task.get("labels", [])):
            continue

        title = task.get("title", "Без назви")
        desc  = (task.get("description") or "").strip()[:120]
        msg   = f"⏰ <b>Нагадування</b>: {title}"
        if desc:
            msg += f"\n<i>{desc}</i>"
        send_tg(env, msg)
        sent += 1

        # Mark reminded
        if reminded_id:
            vikunja(env, "PUT", f"/tasks/{task['id']}/labels",
                    {"label_id": reminded_id})

    if sent:
        print(f"[reminder] {sent} reminder(s) sent", flush=True)


def main() -> None:
    env = load_env()
    if not env.get("VIKUNJA_URL"):
        sys.exit(0)  # Vikunja not configured — silent exit
    env["_jwt"] = get_jwt(env)
    if not env["_jwt"]:
        print("[reminder] cannot get Vikunja token — skip", file=sys.stderr)
        sys.exit(0)
    run(env)


if __name__ == "__main__":
    main()
