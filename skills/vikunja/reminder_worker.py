#!/usr/bin/env python3
"""
Vikunja reminder WAKER — systemd timer, every 60s.

Architecture (tmux send-keys, NOT direct Telegram):
  - Finds due / not-done / not-"reminded"-labelled tasks
  - Checks if the agent's tmux session is idle and alive
  - Injects a СИСТЕМА-НАГАДУВАННЯ: system prompt via tmux send-keys
  - The AGENT then: pulls task via MCP → formulates in its own voice
                    → sends via Telegram reply tool → marks via MCP label

What this worker does NOT do:
  - Never sends Telegram messages directly (would bypass the agent)
  - Never creates a new Claude session (claude -p / --continue)
  - Never marks tasks itself (agent does it after delivery confirmation)

If session is busy or crashed → retry on next tick. No delivery without agent.
"""
from __future__ import annotations
import json, os, subprocess, sys, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path

AGENT_DIR = Path(os.environ.get("AGENT_DIR", "/opt/{{AGENT_NAME}}"))
REMINDED_LABEL = "reminded"
STATE_FILE = AGENT_DIR / "vikunja-data" / "reminder_state.json"
WAKE_DEBOUNCE_SEC = 600  # do not re-wake for same task within 10 min


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


def _json_req(url: str, method: str = "GET", body=None, headers: dict | None = None):
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
    r = _json_req(f"{base}/api/v1/login", "POST", {"username": u, "password": p})
    return r["token"] if r and "token" in r else env.get("VIKUNJA_TOKEN", "")


def vikunja(env: dict, method: str, path: str, body=None):
    base = env.get("VIKUNJA_URL", "").rstrip("/")
    return _json_req(
        f"{base}/api/v1{path}", method, body,
        {"Authorization": f"Bearer {env['_jwt']}"},
    )


def is_due(s: str) -> bool:
    if not s:
        return False
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")) <= datetime.now(timezone.utc)
    except Exception:
        return False


def session_ready(session: str) -> bool:
    """True only when Claude is idle at the prompt (not generating, not in bash crash)."""
    try:
        out = subprocess.run(
            ["tmux", "capture-pane", "-t", session, "-p"],
            capture_output=True, text=True, timeout=5,
        ).stdout or ""
    except Exception:
        return False
    # "bypass permissions on" is unique text visible when Claude waits at the prompt
    return ("bypass permissions on" in out) and ("esc to interrupt" not in out.lower())


def wake_session(session: str, text: str) -> bool:
    """Inject text as a prompt into the running tmux session."""
    try:
        subprocess.run(
            ["tmux", "send-keys", "-t", session, "-l", text],
            check=True, capture_output=True, timeout=5,
        )
        time.sleep(0.3)
        subprocess.run(
            ["tmux", "send-keys", "-t", session, "Enter"],
            check=True, capture_output=True, timeout=5,
        )
        return True
    except Exception as e:
        print(f"[reminder] wake failed: {e}", file=sys.stderr)
        return False


def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {}


def save_state(s: dict) -> None:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(s))
    except Exception as e:
        print(f"[reminder] state save: {e}", file=sys.stderr)


def run(env: dict) -> None:
    # Session name = agent slug (same as tmux session name in start.sh)
    session = env.get("TMUX_SESSION") or env.get("AGENT_NAME") or AGENT_DIR.name
    owner = env.get("TELEGRAM_OWNER_ID", "")
    project_id = env.get("VIKUNJA_PROJECT_ID", "")

    if not project_id:
        for p in sorted(vikunja(env, "GET", "/projects") or [], key=lambda x: x.get("id", 0)):
            if not p.get("is_archived") and p.get("id", 0) > 0:
                project_id = str(p["id"])
                break
    if not project_id:
        return

    tasks = vikunja(env, "GET", f"/projects/{project_id}/tasks") or []
    state = load_state()
    now = time.time()
    woke = 0

    for task in tasks:
        if task.get("done"):
            continue
        if not is_due(task.get("due_date", "")):
            continue
        # Skip if already labelled "reminded"
        if any(lb.get("title") == REMINDED_LABEL for lb in (task.get("labels") or [])):
            continue
        tid = str(task["id"])
        # Debounce: skip if woken for this task recently
        if now - float(state.get(tid, 0)) < WAKE_DEBOUNCE_SEC:
            continue
        # Readiness gate: only inject if session is idle at the Claude prompt
        if not session_ready(session):
            print(f"[reminder] task #{tid} due but session '{session}' not ready — retry next tick", file=sys.stderr)
            continue

        prompt = (
            f"СИСТЕМА-НАГАДУВАННЯ: настав час Vikunja таски #{tid}. "
            f"Витягни її через Vikunja MCP (task_get #{tid}), сформулюй нагадування своїм голосом і "
            f"надішли власнику в Telegram через reply-тул (chat_id={owner}). "
            f"Потім через MCP додай таску лейбл '{REMINDED_LABEL}' (label_create якщо нема + label_add_to_task), "
            f"щоб не повторювалось. Це системний тригер без channel-тегу — маршрутизацію зроби сам через reply з chat_id."
        )
        if wake_session(session, prompt):
            state[tid] = now
            woke += 1

    if woke:
        save_state(state)
        print(f"[reminder] woke session '{session}' for {woke} task(s)", flush=True)


def main() -> None:
    env = load_env()
    if not env.get("VIKUNJA_URL"):
        sys.exit(0)
    env["_jwt"] = get_jwt(env)
    if not env["_jwt"]:
        print("[reminder] no token — skip", file=sys.stderr)
        sys.exit(0)
    run(env)


if __name__ == "__main__":
    main()
