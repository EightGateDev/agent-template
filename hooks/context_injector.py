#!/usr/bin/env python3
"""
UserPromptSubmit hook — fires before EVERY Claude response.

Three things it does:
1. Detects if the message came from Telegram (channel tag present) and injects
   an explicit SOURCE/RULE instruction so Claude knows exactly where to reply.
   This is the most critical protection against replying in the wrong channel.
2. Injects the last 40 messages from the current chat (SQL context).
3. Queries MemPalace for broader context (if configured).
"""
import sys
import re
import json
import os
import sqlite3
from pathlib import Path
from datetime import datetime

MESSAGES_DB = Path.home() / ".claude" / "channels" / "telegram" / "messages.db"
MEMEPALACE_URL = os.environ.get("MEMEPALACE_URL", "")

# Matches <channel ... chat_id="..." ...> from the official Telegram plugin
_CHANNEL_RE = re.compile(
    r'<channel\s[^>]*?chat_id=["\']?([^"\'>\s]+)["\']?',
    re.IGNORECASE,
)
_MSG_ID_RE = re.compile(
    r'message_id=["\']?([^"\'>\s]+)["\']?',
    re.IGNORECASE,
)
_USER_RE = re.compile(
    r'\buser=["\']?([^"\'>\s]+)["\']?',
    re.IGNORECASE,
)


def extract_telegram_source(message_text: str) -> dict | None:
    """
    If the message text contains a Telegram <channel> tag, return
    {chat_id, message_id, user}. Otherwise return None (= terminal source).
    """
    m = _CHANNEL_RE.search(message_text)
    if not m:
        return None
    chat_id = m.group(1)
    msg_id_m = _MSG_ID_RE.search(message_text)
    user_m   = _USER_RE.search(message_text)
    return {
        "chat_id":    chat_id,
        "message_id": msg_id_m.group(1) if msg_id_m else "",
        "user":       user_m.group(1)   if user_m   else "",
    }


def routing_instruction(tg: dict) -> str:
    """
    Explicit routing rule injected at the START of every Telegram-sourced turn.
    This is the key protection: Claude gets a fresh, unambiguous instruction
    per turn rather than relying on a cached understanding.
    """
    return (
        f"message-source SOURCE: TELEGRAM"
        f" / chat_id={tg['chat_id']}"
        f" / msg_id={tg['message_id']}"
        f" / user={tg['user']}\n"
        f"RULE: Use the Telegram `reply` tool with chat_id={tg['chat_id']}. "
        f"Do NOT output a plain terminal answer."
    )


def get_current_chat_id() -> str | None:
    """Most recent chat_id from SQLite = the chat that just sent a message."""
    if not MESSAGES_DB.exists():
        return None
    try:
        conn = sqlite3.connect(str(MESSAGES_DB))
        row = conn.execute("SELECT chat_id FROM messages ORDER BY ts DESC LIMIT 1").fetchone()
        conn.close()
        return row[0] if row else None
    except Exception:
        return None


def read_recent(chat_id: str, limit: int = 40) -> str:
    try:
        conn = sqlite3.connect(str(MESSAGES_DB))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT direction, username, text, ts FROM messages WHERE chat_id=? ORDER BY ts DESC LIMIT ?",
            (chat_id, limit),
        ).fetchall()
        conn.close()
        if not rows:
            return ""
        lines = []
        for r in reversed(rows):
            ts  = datetime.fromtimestamp(r["ts"] / 1000).strftime("%H:%M")
            who = "you" if r["direction"] == "out" else r["username"]
            lines.append(f"[{ts}] {who}: {r['text']}")
        return "Last 40 messages in this chat:\n" + "\n".join(lines)
    except Exception:
        return ""


def query_mempalace(chat_id: str, query: str = "") -> str:
    if not MEMEPALACE_URL:
        return ""
    try:
        import urllib.request
        payload = json.dumps({"chat_id": chat_id, "query": query[:200]}).encode()
        req = urllib.request.Request(
            f"{MEMEPALACE_URL}/query", data=payload,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            return json.loads(resp.read()).get("context", "")
    except Exception:
        return ""


def current_moment_block() -> str:
    """Fresh local 'now', injected EVERY turn so the model never guesses the date/weekday and
    never reuses a stale 'today' from a long-running --continue session (the server is in UTC;
    the owner is not). The owner's zone is the process TZ (TZ=$AGENT_TIMEZONE); if zoneinfo
    can't resolve it we still print the IANA name and fall back to the process-local clock."""
    tz_name = os.environ.get("AGENT_TIMEZONE") or os.environ.get("TZ") or ""
    now = None
    if tz_name:
        try:
            from zoneinfo import ZoneInfo
            now = datetime.now(ZoneInfo(tz_name))
        except Exception:
            now = None
    if now is None:
        now = datetime.now().astimezone()
        tz_name = tz_name or str(now.tzinfo)
    off = now.strftime("%z")
    off = (off[:3] + ":" + off[3:]) if len(off) == 5 else (off or "+00:00")
    return (
        "CURRENT MOMENT (owner's timezone — AUTHORITATIVE; use THIS for today / tomorrow / "
        "this-week / weekday math. NEVER guess the weekday and NEVER reuse an older 'today' "
        "from earlier in this session):\n"
        f"{now.strftime('%A, %Y-%m-%d %H:%M')} {tz_name} (UTC{off})"
    )


def main():
    try:
        raw  = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
        message_text = data.get("prompt") or data.get("message") or data.get("text") or ""
    except Exception:
        print(json.dumps({"continue": True}))
        return

    parts: list[str] = []

    # Fresh local "now" first, on EVERY turn — kills stale-session date drift (server is UTC,
    # owner is not) and weekday guessing. Applies to all agent types (shared hook).
    parts.append(current_moment_block())

    # ── Level 2: detect source and inject routing instruction ─────────────────
    tg = extract_telegram_source(message_text)
    if tg:
        # Telegram message: prepend explicit routing rule as the very first item
        parts.append(routing_instruction(tg))
        chat_id = tg["chat_id"]
    else:
        # Terminal message: use SQLite to find the most recent chat for context
        chat_id = get_current_chat_id()

    # ── SQL context (last 40 messages) ────────────────────────────────────────
    if chat_id:
        recent = read_recent(chat_id)
        if recent:
            parts.append(recent)

        # ── MemPalace broader context ─────────────────────────────────────────
        mem = query_mempalace(chat_id, message_text)
        if mem:
            parts.append("MemPalace context:\n" + mem)

    # ── Lessons — retrieved on every message regardless of chat ──────────────
    if MEMEPALACE_URL and message_text.strip():
        lessons = query_mempalace("lessons", message_text[:200])
        if lessons:
            parts.append("Relevant lessons from past experience:\n" + lessons)

    if parts:
        print(json.dumps({
            "continue": True,
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": "\n\n".join(parts),
            },
        }))
    else:
        print(json.dumps({"continue": True}))


main()
