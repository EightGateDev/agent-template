#!/usr/bin/env python3
"""Read recent messages from local SQLite message history.

Usage: python handler.py <chat_id> [limit=20]
"""
import sys
import sqlite3
from pathlib import Path
from datetime import datetime

MESSAGES_DB = Path.home() / ".claude" / "channels" / "telegram" / "messages.db"


def read_messages(chat_id: str, limit: int = 40) -> str:
    if not MESSAGES_DB.exists():
        return "No message history yet."
    conn = sqlite3.connect(str(MESSAGES_DB))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT direction, username, text, ts FROM messages WHERE chat_id = ? ORDER BY ts DESC LIMIT ?",
        (str(chat_id), int(limit)),
    ).fetchall()
    conn.close()
    if not rows:
        return f"No messages found for chat {chat_id}."
    lines = []
    for r in reversed(rows):
        ts = datetime.fromtimestamp(r["ts"] / 1000).strftime("%H:%M")
        arrow = "you" if r["direction"] == "out" else r["username"]
        lines.append(f"[{ts}] {arrow}: {r['text']}")
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: handler.py <chat_id> [limit]", file=sys.stderr)
        sys.exit(1)
    chat_id = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    print(read_messages(chat_id, limit))
