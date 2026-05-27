#!/usr/bin/env python3
"""Transcribe Telegram voice messages via Groq Whisper.

Usage: python handler.py <file_id>
Env:   GROQ_API_KEY, TELEGRAM_BOT_TOKEN
"""
import sys
import os
import json
import tempfile
import urllib.request
import urllib.parse

try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "_shared"))
    from usage_logger import log_usage as _log_usage
except Exception:
    def _log_usage(*a, **kw): pass

GROQ_KEY = os.environ.get("GROQ_API_KEY", "")
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def _tg_get_file_path(file_id: str) -> str:
    url = f"{TG_API}/getFile?file_id={urllib.parse.quote(file_id)}"
    with urllib.request.urlopen(url, timeout=10) as r:
        data = json.loads(r.read())
    if not data.get("ok"):
        raise RuntimeError(f"getFile failed: {data}")
    return data["result"]["file_path"]


def _tg_download(file_path: str, dest: str) -> None:
    url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
    urllib.request.urlretrieve(url, dest)


def _groq_transcribe(audio_path: str) -> str:
    import mimetypes
    mime = mimetypes.guess_type(audio_path)[0] or "audio/ogg"
    filename = os.path.basename(audio_path)

    # Multipart form-data build
    boundary = "----FormBoundary7MA4YWxkTrZu0gW"
    with open(audio_path, "rb") as f:
        audio_bytes = f.read()

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: {mime}\r\n\r\n"
    ).encode() + audio_bytes + (
        f"\r\n--{boundary}\r\n"
        f'Content-Disposition: form-data; name="model"\r\n\r\n'
        f"whisper-large-v3-turbo\r\n"
        f"--{boundary}--\r\n"
    ).encode()

    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/audio/transcriptions",
        data=body,
        headers={
            "Authorization": f"Bearer {GROQ_KEY}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "groq-python/0.9.0",  # Cloudflare blocks urllib default UA
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        result = json.loads(r.read())
    return result.get("text", "")


def transcribe_voice(file_id: str) -> str:
    if not GROQ_KEY:
        return "GROQ_API_KEY not set. Add it to agent secrets."
    if not BOT_TOKEN:
        return "TELEGRAM_BOT_TOKEN not set."
    try:
        file_path = _tg_get_file_path(file_id)
        ext = os.path.splitext(file_path)[1] or ".ogg"
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp_path = tmp.name
        _tg_download(file_path, tmp_path)
        audio_bytes = os.path.getsize(tmp_path)
        text = _groq_transcribe(tmp_path)
        os.unlink(tmp_path)
        _log_usage("groq", audio_bytes, "audio_bytes", {"model": "whisper-large-v3-turbo"})
        return text or "(empty transcription)"
    except Exception as e:
        return f"Transcription error: {e}"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: handler.py <file_id>", file=sys.stderr)
        sys.exit(1)
    print(transcribe_voice(sys.argv[1]))
