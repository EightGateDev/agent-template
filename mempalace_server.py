#!/usr/bin/env python3
"""
Local MemPalace HTTP server — provides /ingest and /query endpoints
backed by the agent's existing SQLite messages database.

No external dependencies — stdlib only (http.server + sqlite3).

/ingest  POST  {"chat_id","user_id","username","direction","text","ts",...}
         → stores message (deduplicates by chat_id+ts+text)
         → returns {"ok": true}

/query   POST  {"chat_id": "...", "query": "search terms"}
         → full-text search over all messages for this chat
         → returns {"context": "formatted relevant messages"}

Run: python3 mempalace_server.py
Env: MEMPALACE_PORT (default 7766), MEMPALACE_DB (default ~/.claude/channels/telegram/messages.db)
"""

import json
import logging
import os
import sqlite3
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

PORT = int(os.environ.get("MEMPALACE_PORT", 7766))
DB_PATH = Path(
    os.environ.get(
        "MEMPALACE_DB",
        Path.home() / ".claude" / "channels" / "telegram" / "messages.db"
    )
)
MAX_RESULTS = 20  # max messages returned per query

logging.basicConfig(level=logging.WARNING, format="[mempalace] %(message)s")
log = logging.getLogger("mempalace")


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id    TEXT    NOT NULL,
            user_id    TEXT,
            username   TEXT,
            direction  TEXT    DEFAULT 'in',
            text       TEXT,
            ts         INTEGER NOT NULL,
            message_id INTEGER
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_mp_chat_ts ON messages(chat_id, ts DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_mp_text ON messages(text)"
    )
    conn.commit()
    return conn


def ingest(record: dict) -> dict:
    """Store a message. Skip if already stored (dedup by chat+ts+text)."""
    chat_id   = str(record.get("chat_id", ""))
    user_id   = str(record.get("user_id", ""))
    username  = str(record.get("username", ""))
    direction = str(record.get("direction", "in"))
    text      = str(record.get("text", ""))[:4000]
    ts        = int(record.get("ts", 0))
    msg_id    = record.get("message_id")

    if not chat_id or not text or text == "[non-text]":
        return {"ok": True, "skipped": True}

    conn = get_db()
    try:
        # Dedup: same chat + ts + text already present → skip
        existing = conn.execute(
            "SELECT id FROM messages WHERE chat_id=? AND ts=? AND text=? LIMIT 1",
            (chat_id, ts, text)
        ).fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO messages (chat_id,user_id,username,direction,text,ts,message_id)"
                " VALUES (?,?,?,?,?,?,?)",
                (chat_id, user_id, username, direction, text, ts, msg_id)
            )
            conn.commit()
        return {"ok": True}
    finally:
        conn.close()


def query(chat_id: str, query_text: str) -> dict:
    """
    Search messages for this chat matching the query.
    Uses SQLite LIKE for keyword matching across all history.
    Returns a formatted context string.
    """
    if not chat_id:
        return {"context": ""}

    conn = get_db()
    try:
        rows = []

        if query_text.strip():
            # Keyword search — split on spaces, require at least one word match
            words = [w.strip() for w in query_text.split() if len(w.strip()) > 2]
            if words:
                like_clauses = " OR ".join("text LIKE ?" for _ in words)
                params = [f"%{w}%" for w in words] + [chat_id, MAX_RESULTS]
                rows = conn.execute(
                    f"SELECT direction, username, text, ts FROM messages"
                    f" WHERE ({like_clauses}) AND chat_id=?"
                    f" ORDER BY ts DESC LIMIT ?",
                    params
                ).fetchall()

        # Fallback: most recent messages if no keyword match
        if not rows:
            rows = conn.execute(
                "SELECT direction, username, text, ts FROM messages"
                " WHERE chat_id=? ORDER BY ts DESC LIMIT ?",
                (chat_id, MAX_RESULTS)
            ).fetchall()

        if not rows:
            return {"context": ""}

        from datetime import datetime
        lines = []
        for r in reversed(rows):
            ts_str = datetime.fromtimestamp(r["ts"] / 1000).strftime("%m-%d %H:%M") \
                if r["ts"] > 1_000_000_000_000 \
                else datetime.fromtimestamp(r["ts"]).strftime("%m-%d %H:%M")
            who = "you" if r["direction"] == "out" else (r["username"] or "user")
            lines.append(f"[{ts_str}] {who}: {r['text'][:300]}")

        context = f"Relevant history ({len(lines)} messages):\n" + "\n".join(lines)
        return {"context": context}
    finally:
        conn.close()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # silence access logs

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length))

    def _respond(self, data: dict, status: int = 200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        try:
            body = self._read_json()
            if self.path == "/ingest":
                self._respond(ingest(body))
            elif self.path == "/query":
                self._respond(query(
                    str(body.get("chat_id", "")),
                    str(body.get("query", ""))
                ))
            else:
                self._respond({"error": "not found"}, 404)
        except Exception as e:
            log.exception("handler error")
            self._respond({"error": str(e)}, 500)

    def do_GET(self):
        if self.path == "/health":
            self._respond({"ok": True, "db": str(DB_PATH)})
        else:
            self._respond({"error": "not found"}, 404)


def main():
    # Ensure DB directory exists
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Pre-create tables
    get_db().close()

    server = HTTPServer(("127.0.0.1", PORT), Handler)
    print(f"[mempalace] listening on http://127.0.0.1:{PORT}  db={DB_PATH}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
