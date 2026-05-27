#!/usr/bin/env python3
"""Gmail skill — requires Google service account with domain-wide delegation.

Usage: python handler.py <action> [args...]
Actions: list, read <msg_id>, send <to> <subject> <body>, search <query>
Env:   GOOGLE_CREDENTIALS_JSON, GMAIL_USER_EMAIL
"""
import sys
import os
import base64

CREDS_PATH = os.environ.get("GOOGLE_CREDENTIALS_JSON", "")
USER_EMAIL = os.environ.get("GMAIL_USER_EMAIL", "")


def _get_service():
    if not CREDS_PATH or not os.path.exists(CREDS_PATH):
        raise RuntimeError("GOOGLE_CREDENTIALS_JSON not set. Add credentials to agent secrets.")
    if not USER_EMAIL:
        raise RuntimeError("GMAIL_USER_EMAIL not set.")
    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build
        scopes = ["https://www.googleapis.com/auth/gmail.modify"]
        creds = Credentials.from_service_account_file(CREDS_PATH, scopes=scopes).with_subject(USER_EMAIL)
        return build("gmail", "v1", credentials=creds)
    except ImportError:
        raise RuntimeError("Install: pip install google-api-python-client google-auth")


def list_messages(max_results: int = 10, query: str = "is:unread") -> str:
    svc = _get_service()
    result = svc.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
    msgs = result.get("messages", [])
    if not msgs:
        return "No messages found."
    lines = []
    for m in msgs[:max_results]:
        detail = svc.users().messages().get(userId="me", id=m["id"], format="metadata",
                                            metadataHeaders=["Subject", "From"]).execute()
        headers = {h["name"]: h["value"] for h in detail.get("payload", {}).get("headers", [])}
        lines.append(f"- [{m['id']}] {headers.get('From','')} | {headers.get('Subject','(no subject)')}")
    return "\n".join(lines)


def send_email(to: str, subject: str, body: str) -> str:
    svc = _get_service()
    from email.mime.text import MIMEText
    msg = MIMEText(body)
    msg["to"] = to
    msg["subject"] = subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    svc.users().messages().send(userId="me", body={"raw": raw}).execute()
    return f"Email sent to {to}"


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "list"
    try:
        if action == "list":
            print(list_messages())
        elif action == "search" and len(sys.argv) > 2:
            print(list_messages(query=" ".join(sys.argv[2:])))
        elif action == "send" and len(sys.argv) >= 5:
            print(send_email(sys.argv[2], sys.argv[3], " ".join(sys.argv[4:])))
        else:
            print("Actions: list | search <query> | send <to> <subject> <body>")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
