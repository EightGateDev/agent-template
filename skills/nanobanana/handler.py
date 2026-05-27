#!/usr/bin/env python3
"""Image generation via Google Gemini Imagen.

Usage: python handler.py <prompt> [chat_id]
       With chat_id: generates image and sends to that Telegram chat
       Without: saves to /tmp/generated.png and prints path
Env:   GEMINI_API_KEY, TELEGRAM_BOT_TOKEN (needed if chat_id provided)
"""
import sys
import os
import json
import base64
import tempfile
import urllib.request

try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "_shared"))
    from usage_logger import log_usage as _log_usage
except Exception:
    def _log_usage(*a, **kw): pass

GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def generate_image(prompt: str) -> bytes:
    if not GEMINI_KEY:
        raise RuntimeError("GEMINI_API_KEY not set. Add it to agent secrets.")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-001:predict?key={GEMINI_KEY}"
    payload = json.dumps({
        "instances": [{"prompt": prompt}],
        "parameters": {"sampleCount": 1},
    }).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        result = json.loads(r.read())
    b64 = result["predictions"][0]["bytesBase64Encoded"]
    return base64.b64decode(b64)


def _tg_send_photo(chat_id: str, image_bytes: bytes, caption: str) -> str:
    boundary = "----FormBoundaryImg123"
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"chat_id\"\r\n\r\n{chat_id}\r\n"
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"caption\"\r\n\r\n{caption}\r\n"
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"photo\"; filename=\"image.png\"\r\nContent-Type: image/png\r\n\r\n"
    ).encode() + image_bytes + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        f"{TG_API}/sendPhoto", data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        result = json.loads(r.read())
    return "Photo sent." if result.get("ok") else f"Error: {result}"


def make_image(prompt: str, chat_id: str = "") -> str:
    try:
        image_bytes = generate_image(prompt)
        _log_usage("gemini", 1, "images", {"model": "imagen-3.0"})
        if chat_id and BOT_TOKEN:
            return _tg_send_photo(chat_id, image_bytes, prompt[:200])
        else:
            path = "/tmp/generated.png"
            with open(path, "wb") as f:
                f.write(image_bytes)
            return f"Image saved: {path}"
    except Exception as e:
        return f"Image generation error: {e}"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: handler.py <prompt> [chat_id]", file=sys.stderr)
        sys.exit(1)
    prompt = sys.argv[1]
    chat_id = sys.argv[2] if len(sys.argv) > 2 else ""
    print(make_image(prompt, chat_id))
