#!/usr/bin/env python3
"""MemPalace skill — query context or store a lesson.

Usage:
  python handler.py <chat_id> [query_text]          # query context for a chat
  python handler.py store "LESSON: ... FIX: ..."    # store a lesson (chat_id=lessons)

Returns empty string if MEMEPALACE_URL is not configured.
"""
import sys
import os
import time
import urllib.request
import json

MEMEPALACE_URL = os.environ.get("MEMEPALACE_URL", "http://localhost:7766")


def mempalace_query(chat_id: str, query: str = "") -> str:
    if not MEMEPALACE_URL:
        return ""
    try:
        payload = json.dumps({"chat_id": str(chat_id), "query": query}).encode()
        req = urllib.request.Request(
            f"{MEMEPALACE_URL}/query",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            result = json.loads(resp.read())
            return result.get("context", "")
    except Exception as e:
        return f"[mempalace unavailable: {e}]"


def mempalace_store(text: str, chat_id: str = "lessons") -> str:
    if not MEMEPALACE_URL:
        return "[mempalace not configured]"
    try:
        payload = json.dumps({
            "chat_id": chat_id,
            "user_id": "agent",
            "username": "lesson",
            "direction": "in",
            "text": text[:4000],
            "ts": int(time.time() * 1000),
        }).encode()
        req = urllib.request.Request(
            f"{MEMEPALACE_URL}/ingest",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            json.loads(resp.read())
            return f"[lesson stored]"
    except Exception as e:
        return f"[mempalace unavailable: {e}]"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: handler.py <chat_id> [query]  |  handler.py store <text>", file=sys.stderr)
        sys.exit(1)

    if sys.argv[1] == "store":
        text = " ".join(sys.argv[2:])
        if not text:
            print("Usage: handler.py store <lesson text>", file=sys.stderr)
            sys.exit(1)
        print(mempalace_store(text))
    else:
        chat_id = sys.argv[1]
        query = sys.argv[2] if len(sys.argv) > 2 else ""
        print(mempalace_query(chat_id, query) or "(no context)")
