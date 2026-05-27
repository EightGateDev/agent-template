#!/usr/bin/env python3
"""
Persona state machine — tracks which persona is currently active.

State: /opt/<agent>/personas/state.json
  { "role": "default", "since": "<iso>", "last_msg": "<iso>" }

Commands:
  role.py get              → print active role name
  role.py set <role>       → switch to persona (validates file exists)
  role.py touch            → extend session timeout without changing role
  role.py reset            → force back to default
  role.py status           → JSON status with idle info
  role.py list             → list available personas

Idle timeout: if last_msg > IDLE_TIMEOUT_HOURS, `get` returns "default"
regardless of stored role (auto-reset on long silence).

Usage by Claude:
  Read active role:   python personas/role.py get
  Switch persona:     python personas/role.py set finance
  After each reply:   python personas/role.py touch
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Always resolve relative to the agent's install dir
AGENT_DIR = Path(__file__).resolve().parent.parent
PERSONAS_DIR = AGENT_DIR / "personas"
STATE_FILE = PERSONAS_DIR / "state.json"
IDLE_TIMEOUT_HOURS = 2
DEFAULT_ROLE = "default"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read_state() -> dict:
    if not STATE_FILE.exists():
        return {"role": DEFAULT_ROLE, "since": _now(), "last_msg": _now()}
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {"role": DEFAULT_ROLE, "since": _now(), "last_msg": _now()}


def _write_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def _is_idle(state: dict) -> bool:
    last = state.get("last_msg")
    if not last:
        return True
    try:
        last_dt = datetime.fromisoformat(last)
        return datetime.now(timezone.utc) - last_dt > timedelta(hours=IDLE_TIMEOUT_HOURS)
    except Exception:
        return True


def _effective_role(state: dict) -> str:
    stored = state.get("role", DEFAULT_ROLE)
    if stored != DEFAULT_ROLE and _is_idle(state):
        return DEFAULT_ROLE
    return stored


def _list_personas() -> list[str]:
    roles = [DEFAULT_ROLE]
    for f in sorted(PERSONAS_DIR.glob("*.md")):
        name = f.stem
        if name not in ("shared", "README") and name != DEFAULT_ROLE:
            roles.append(name)
    return roles


def cmd_get() -> int:
    state = _read_state()
    print(_effective_role(state))
    return 0


def cmd_status() -> int:
    state = _read_state()
    eff = _effective_role(state)
    print(json.dumps({
        "stored_role": state.get("role", DEFAULT_ROLE),
        "effective_role": eff,
        "since": state.get("since"),
        "last_msg": state.get("last_msg"),
        "idle": _is_idle(state),
        "idle_timeout_hours": IDLE_TIMEOUT_HOURS,
        "available": _list_personas(),
    }, indent=2, ensure_ascii=False))
    return 0


def cmd_list() -> int:
    for p in _list_personas():
        print(p)
    return 0


def cmd_set(role: str) -> int:
    if role == DEFAULT_ROLE:
        return cmd_reset()

    persona_file = PERSONAS_DIR / f"{role}.md"
    if not persona_file.exists():
        print(f"error: persona file not found: {persona_file}", file=sys.stderr)
        print(f"Available: {', '.join(_list_personas())}", file=sys.stderr)
        return 2

    state = _read_state()
    now = _now()
    if state.get("role") != role:
        state["role"] = role
        state["since"] = now
    state["last_msg"] = now
    _write_state(state)
    print(f"role={role}")
    return 0


def cmd_touch() -> int:
    state = _read_state()
    state["last_msg"] = _now()
    _write_state(state)
    print(f"touched role={state.get('role', DEFAULT_ROLE)}")
    return 0


def cmd_reset() -> int:
    state = {"role": DEFAULT_ROLE, "since": _now(), "last_msg": _now()}
    _write_state(state)
    print(f"role={DEFAULT_ROLE} (reset)")
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: role.py {get|set <role>|touch|reset|status|list}", file=sys.stderr)
        return 2
    cmd = sys.argv[1]
    if cmd == "get":       return cmd_get()
    if cmd == "status":    return cmd_status()
    if cmd == "list":      return cmd_list()
    if cmd == "touch":     return cmd_touch()
    if cmd == "reset":     return cmd_reset()
    if cmd == "set":
        if len(sys.argv) < 3:
            print("usage: role.py set <role>", file=sys.stderr)
            return 2
        return cmd_set(sys.argv[2])
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
