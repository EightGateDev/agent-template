#!/usr/bin/env python3
"""Query MemPalace service for broader chat context.

Usage: python handler.py <chat_id> [query_text]
Returns empty string if MEMEPALACE_URL is not configured.
"""
import sys
import os
import urllib.request
import json

MEMEPALACE_URL = os.environ.get("MEMEPALACE_URL", "")


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


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: handler.py <chat_id> [query]", file=sys.stderr)
        sys.exit(1)
    chat_id = sys.argv[1]
    query = sys.argv[2] if len(sys.argv) > 2 else ""
    result = mempalace_query(chat_id, query)
    print(result or "(no context)")
