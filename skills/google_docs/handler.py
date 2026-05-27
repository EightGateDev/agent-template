#!/usr/bin/env python3
"""Google Docs skill — read and create documents.

Usage: python handler.py <action> [args...]
Actions: read <doc_id>, create <title> <content>, append <doc_id> <text>
Env:   GOOGLE_CREDENTIALS_JSON
"""
import sys
import os

CREDS_PATH = os.environ.get("GOOGLE_CREDENTIALS_JSON", "")


def _get_service():
    if not CREDS_PATH or not os.path.exists(CREDS_PATH):
        raise RuntimeError("GOOGLE_CREDENTIALS_JSON not set. Add credentials to agent secrets.")
    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build
        scopes = ["https://www.googleapis.com/auth/documents", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_file(CREDS_PATH, scopes=scopes)
        return build("docs", "v1", credentials=creds), build("drive", "v3", credentials=creds)
    except ImportError:
        raise RuntimeError("Install: pip install google-api-python-client google-auth")


def read_doc(doc_id: str) -> str:
    docs_svc, _ = _get_service()
    doc = docs_svc.documents().get(documentId=doc_id).execute()
    content = doc.get("body", {}).get("content", [])
    text_parts = []
    for elem in content:
        for run in elem.get("paragraph", {}).get("elements", []):
            text_parts.append(run.get("textRun", {}).get("content", ""))
    return "".join(text_parts).strip()


def create_doc(title: str, content: str) -> str:
    docs_svc, drive_svc = _get_service()
    doc = docs_svc.documents().create(body={"title": title}).execute()
    doc_id = doc["documentId"]
    if content:
        docs_svc.documents().batchUpdate(
            documentId=doc_id,
            body={"requests": [{"insertText": {"location": {"index": 1}, "text": content}}]}
        ).execute()
    return f"Created doc: https://docs.google.com/document/d/{doc_id}"


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "help"
    try:
        if action == "read" and len(sys.argv) > 2:
            print(read_doc(sys.argv[2]))
        elif action == "create" and len(sys.argv) > 3:
            print(create_doc(sys.argv[2], " ".join(sys.argv[3:])))
        else:
            print("Actions: read <doc_id> | create <title> <content>")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
