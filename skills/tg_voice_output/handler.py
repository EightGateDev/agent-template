#!/usr/bin/env python3
"""Send a voice reply via ElevenLabs TTS + Telegram sendVoice.

Usage: python handler.py <chat_id> "text to speak"
Env:   ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID (optional), TELEGRAM_BOT_TOKEN
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

ELEVEN_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")  # Rachel
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def _elevenlabs_tts(text: str) -> tuple[bytes, int]:
    """Returns (audio_bytes, chars_used). chars_used from character-cost response header."""
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
    payload = json.dumps({
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "xi-api-key": ELEVEN_KEY,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        audio = r.read()
        chars_used = int(r.headers.get("character-cost", len(text)))
    return audio, chars_used


def _tg_send_voice(chat_id: str, audio_path: str) -> dict:
    boundary = "----FormBoundary9XMkTrZu0gW"
    with open(audio_path, "rb") as f:
        audio_bytes = f.read()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="chat_id"\r\n\r\n'
        f"{chat_id}\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="voice"; filename="voice.mp3"\r\n'
        f"Content-Type: audio/mpeg\r\n\r\n"
    ).encode() + audio_bytes + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        f"{TG_API}/sendVoice",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def speak(chat_id: str, text: str) -> str:
    if not ELEVEN_KEY:
        return "ELEVENLABS_API_KEY not set. Add it to agent secrets."
    if not BOT_TOKEN:
        return "TELEGRAM_BOT_TOKEN not set."
    try:
        audio, chars_used = _elevenlabs_tts(text)
        _log_usage("elevenlabs", chars_used, "chars", {"voice_id": VOICE_ID})
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp.write(audio)
            tmp_path = tmp.name
        result = _tg_send_voice(chat_id, tmp_path)
        os.unlink(tmp_path)
        if result.get("ok"):
            return "Voice message sent."
        return f"Telegram error: {result}"
    except Exception as e:
        return f"Voice output error: {e}"


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: handler.py <chat_id> <text>", file=sys.stderr)
        sys.exit(1)
    chat_id = sys.argv[1]
    text = " ".join(sys.argv[2:])
    print(speak(chat_id, text))
