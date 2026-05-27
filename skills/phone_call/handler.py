#!/usr/bin/env python3
"""Outbound phone calls via Vapi.ai.

Usage: python handler.py <phone_number> <task_description>
Env:   VAPI_API_KEY, VAPI_PHONE_NUMBER_ID, VAPI_ASSISTANT_ID
"""
import sys
import os

try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "_shared"))
    from usage_logger import log_usage as _log_usage
except Exception:
    def _log_usage(*a, **kw): pass
import os
import json
import urllib.request

VAPI_KEY = os.environ.get("VAPI_API_KEY", "")
PHONE_NUMBER_ID = os.environ.get("VAPI_PHONE_NUMBER_ID", "")
ASSISTANT_ID = os.environ.get("VAPI_ASSISTANT_ID", "")


def make_call(to_number: str, task: str) -> str:
    if not VAPI_KEY:
        return "VAPI_API_KEY not set. Add it to agent secrets."
    if not PHONE_NUMBER_ID or not ASSISTANT_ID:
        return "VAPI_PHONE_NUMBER_ID and VAPI_ASSISTANT_ID must be set in agent secrets."
    payload = json.dumps({
        "phoneNumberId": PHONE_NUMBER_ID,
        "assistantId": ASSISTANT_ID,
        "customer": {"number": to_number},
        "assistantOverrides": {"variableValues": {"task": task}},
    }).encode()
    req = urllib.request.Request(
        "https://api.vapi.ai/call/phone",
        data=payload,
        headers={
            "Authorization": f"Bearer {VAPI_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            result = json.loads(r.read())
            call_id = result.get("id", "unknown")
            _log_usage("vapi", 1, "calls", {"call_id": call_id, "to": to_number})
            return f"Call initiated: {call_id} → {to_number}"
    except Exception as e:
        return f"Call error: {e}"


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: handler.py <phone_number> <task_description>", file=sys.stderr)
        sys.exit(1)
    print(make_call(sys.argv[1], " ".join(sys.argv[2:])))
