#!/usr/bin/env python3
"""Google Sheets skill — read and write spreadsheets.

Usage: python handler.py <action> [args...]
Actions: read <sheet_id> [range], append <sheet_id> <json_row>, clear <sheet_id> <range>
Env:   GOOGLE_CREDENTIALS_JSON
"""
import sys
import os
import json

CREDS_PATH = os.environ.get("GOOGLE_CREDENTIALS_JSON", "")


def _get_service():
    if not CREDS_PATH or not os.path.exists(CREDS_PATH):
        raise RuntimeError("GOOGLE_CREDENTIALS_JSON not set. Add credentials to agent secrets.")
    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_file(CREDS_PATH, scopes=scopes)
        return build("sheets", "v4", credentials=creds).spreadsheets()
    except ImportError:
        raise RuntimeError("Install: pip install google-api-python-client google-auth")


def read_sheet(sheet_id: str, range_: str = "Sheet1") -> str:
    svc = _get_service()
    result = svc.values().get(spreadsheetId=sheet_id, range=range_).execute()
    rows = result.get("values", [])
    if not rows:
        return "Empty range."
    return "\n".join("\t".join(str(c) for c in row) for row in rows)


def append_row(sheet_id: str, row: list) -> str:
    svc = _get_service()
    svc.values().append(
        spreadsheetId=sheet_id, range="Sheet1",
        valueInputOption="USER_ENTERED",
        body={"values": [row]}
    ).execute()
    return f"Row appended to {sheet_id}"


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "help"
    try:
        if action == "read" and len(sys.argv) > 2:
            range_ = sys.argv[3] if len(sys.argv) > 3 else "Sheet1"
            print(read_sheet(sys.argv[2], range_))
        elif action == "append" and len(sys.argv) > 3:
            row = json.loads(sys.argv[3])
            print(append_row(sys.argv[2], row))
        else:
            print("Actions: read <sheet_id> [range] | append <sheet_id> <json_array>")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
