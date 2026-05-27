#!/usr/bin/env python3
"""Google Calendar skill — requires OAuth setup.

Usage: python handler.py <action> [args...]
Actions: list, create, update, delete
Env:   GOOGLE_CREDENTIALS_JSON (path to OAuth credentials file)

Setup: Share your Google Calendar with the service account email in GOOGLE_CREDENTIALS_JSON,
       or complete OAuth flow by running: python handler.py auth
"""
import sys
import os
import json

CREDS_PATH = os.environ.get("GOOGLE_CREDENTIALS_JSON", "")


def _get_service():
    if not CREDS_PATH or not os.path.exists(CREDS_PATH):
        raise RuntimeError("GOOGLE_CREDENTIALS_JSON not set or file missing. Add credentials to agent secrets.")
    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build
        scopes = ["https://www.googleapis.com/auth/calendar"]
        creds = Credentials.from_service_account_file(CREDS_PATH, scopes=scopes)
        return build("calendar", "v3", credentials=creds)
    except ImportError:
        raise RuntimeError("Install: pip install google-api-python-client google-auth")


def list_events(calendar_id: str = "primary", max_results: int = 10) -> str:
    from datetime import datetime, timezone
    svc = _get_service()
    now = datetime.now(timezone.utc).isoformat()
    result = svc.events().list(
        calendarId=calendar_id, timeMin=now,
        maxResults=max_results, singleEvents=True, orderBy="startTime"
    ).execute()
    events = result.get("items", [])
    if not events:
        return "No upcoming events."
    lines = []
    for e in events:
        start = e["start"].get("dateTime", e["start"].get("date"))
        lines.append(f"- {start}: {e['summary']}")
    return "\n".join(lines)


def create_event(summary: str, start: str, end: str, calendar_id: str = "primary") -> str:
    svc = _get_service()
    event = {"summary": summary, "start": {"dateTime": start, "timeZone": "UTC"}, "end": {"dateTime": end, "timeZone": "UTC"}}
    created = svc.events().insert(calendarId=calendar_id, body=event).execute()
    return f"Created: {created.get('htmlLink')}"


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "list"
    try:
        if action == "list":
            print(list_events())
        elif action == "create" and len(sys.argv) >= 4:
            print(create_event(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else sys.argv[3]))
        else:
            print(f"Actions: list | create <summary> <start_iso> <end_iso>")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
