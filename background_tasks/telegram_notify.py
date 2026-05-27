"""Minimal Telegram send helper for background task notifications."""
import os
import asyncio
import logging
import json
import urllib.request
import urllib.error

logger = logging.getLogger("background_tasks.telegram_notify")


def _send_sync(chat_id: str, text: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN not set — cannot send notification")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
    except urllib.error.HTTPError as e:
        logger.error("Telegram sendMessage HTTP %d: %s", e.code, e.read()[:200])
    except Exception as e:
        logger.error("Telegram sendMessage error: %s", e)


async def telegram_send(chat_id: str, text: str) -> None:
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _send_sync, chat_id, text)
