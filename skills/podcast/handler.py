#!/usr/bin/env python3
"""
Podcast generation via Google NotebookLM (free, 3/day on free tier).

Auth setup (one-time, or when session expires):
  python skills/podcast/handler.py login
  → follow instructions → user sends cookies.txt file

Generate podcast:
  python skills/podcast/handler.py generate "Тема"
  python skills/podcast/handler.py generate "Тема" --format deep_dive|brief|critique|debate
  python skills/podcast/handler.py generate "Тема" --duration brief|standard|extended
  python skills/podcast/handler.py generate "Тема" --preset casual|formal|educational|debate|critique
  python skills/podcast/handler.py generate "Тема" --instructions "Explain for beginners"
  python skills/podcast/handler.py generate "Тема" --source "https://example.com/article"
  python skills/podcast/handler.py generate "Тема" --lang uk --chat-id 123456789

Check auth:
  python skills/podcast/handler.py status

--- Formats ---
  deep_dive  Deep discussion, two hosts explore topic in depth (default)
  brief      Condensed ~2min overview
  critique   Critical analysis, pros and cons
  debate     Two hosts argue opposite sides

--- Duration (may be ignored for non-English) ---
  brief      2-3 min
  standard   5-6 min (default)
  extended   8-10 min

--- Presets (sets instructions automatically) ---
  casual        Friendly, conversational tone
  formal        Professional academic tone
  educational   Beginner-friendly, no jargon
  expert        For senior practitioners, skip basics
  ukrainian     Enforce Ukrainian language throughout

Rate limit: 3 podcasts/day (free), 20/day (Google One AI Premium $20/mo)
"""

import argparse
import asyncio
import base64
import json
import os
import sys
import urllib.request
from pathlib import Path

AGENT_DIR = Path(os.environ.get("AGENT_DIR", Path.home()))
STATE_FILE = AGENT_DIR / ".notebooklm" / "storage_state.json"
BOT_TOKEN  = os.environ.get("TELEGRAM_BOT_TOKEN", "")


# ── Presets ───────────────────────────────────────────────────────────────────

PRESETS = {
    "casual": (
        "Keep it casual and conversational. Use simple everyday language, "
        "feel free to use humor and relatable examples. The hosts should sound "
        "like friends chatting, not academics presenting."
    ),
    "formal": (
        "Use a professional, formal academic tone. Structure the discussion clearly "
        "with an introduction, key points, and summary. Cite reasoning carefully. "
        "Avoid slang or colloquialisms."
    ),
    "educational": (
        "Target audience is complete beginners with no prior knowledge. "
        "Explain every concept from scratch, avoid jargon, use simple analogies "
        "and real-world examples. Never assume prior knowledge."
    ),
    "expert": (
        "Target audience is senior practitioners and domain experts. "
        "Skip basic definitions, dive straight into nuances, edge cases, and "
        "advanced implications. Use technical terminology freely."
    ),
    "ukrainian": (
        "Conduct this entire episode in Ukrainian language only. "
        "All discussion, examples, and commentary must be in Ukrainian. "
        "Do not switch to any other language at any point."
    ),
}


# ── Cookie parsers ────────────────────────────────────────────────────────────

def _netscape_txt_to_storage_state(txt: str) -> dict:
    """Parse Netscape cookies.txt (from 'Get cookies.txt LOCALLY') → Playwright storage_state."""
    cookies = []
    for line in txt.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 7:
            continue
        domain, _include_sub, path, secure, expiry, name, value = parts[:7]
        cookies.append({
            "name":     name,
            "value":    value,
            "domain":   domain,
            "path":     path,
            "expires":  int(expiry) if expiry.isdigit() else -1,
            "httpOnly": False,
            "secure":   secure.upper() == "TRUE",
            "sameSite": "None",
        })
    return {"cookies": cookies, "origins": []}


def _json_to_storage_state(cookies: list) -> dict:
    """Cookie Editor JSON array → Playwright storage_state."""
    same_site_map = {
        "no_restriction": "None", "lax": "Lax",
        "strict": "Strict", "unspecified": "None",
    }
    return {
        "cookies": [
            {
                "name":     c["name"],
                "value":    c["value"],
                "domain":   c.get("domain", ".google.com"),
                "path":     c.get("path", "/"),
                "expires":  c.get("expirationDate", -1),
                "httpOnly": c.get("httpOnly", False),
                "secure":   c.get("secure", False),
                "sameSite": same_site_map.get(c.get("sameSite", "no_restriction"), "None"),
            }
            for c in cookies
        ],
        "origins": [],
    }


# ── Auth helpers ──────────────────────────────────────────────────────────────

def _seed_from_env():
    """If storage_state.json missing, restore from NOTEBOOKLM_STORAGE_STATE_B64 env."""
    if STATE_FILE.exists():
        return
    b64 = os.environ.get("NOTEBOOKLM_STORAGE_STATE_B64", "").strip()
    if not b64:
        return
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_bytes(base64.b64decode(b64))
        print(f"[podcast] Відновлено авторизацію з NOTEBOOKLM_STORAGE_STATE_B64 → {STATE_FILE}")
    except Exception as e:
        print(f"[podcast] Помилка декодування NOTEBOOKLM_STORAGE_STATE_B64: {e}", file=sys.stderr)


def _is_authed() -> bool:
    return STATE_FILE.exists() and STATE_FILE.stat().st_size > 50


def _clear_auth():
    STATE_FILE.unlink(missing_ok=True)


# ── Login ─────────────────────────────────────────────────────────────────────

LOGIN_INSTRUCTIONS = """
=== Авторизація NotebookLM ===

Потрібне розширення Chrome: "Get cookies.txt LOCALLY"
https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc

Кроки:
1. Відкрий https://notebooklm.google.com в Chrome, залогінься
2. Клікни на розширення → натисни "Export All"
   (саме Export ALL, а не просто Export — щоб взяло всі google.com домени)
3. Збережи файл cookies.txt
4. Надішли мені цей файл

Чому саме це розширення:
Chrome 127+ шифрує cookie SID через App-Bound Encryption.
Cookie Editor не бачить її. Get cookies.txt LOCALLY читає через інший
механізм і SID є.

Примітка: сесія діє кілька тижнів. Коли застаріє — агент сам попросить повторити.
"""


def cmd_login(cookie_raw: str | None):
    if not cookie_raw:
        print(LOGIN_INSTRUCTIONS)
        return

    raw = cookie_raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    if raw.startswith("# Netscape HTTP Cookie File") or (
        "\t" in raw and not raw.startswith("[")
    ):
        storage_state = _netscape_txt_to_storage_state(raw)
        n = len(storage_state["cookies"])
        if n == 0:
            print("ERROR: Не знайдено кукі в cookies.txt. Переконайся що натиснув 'Export All'.", file=sys.stderr)
            sys.exit(1)
        fmt = "Netscape cookies.txt"
    else:
        try:
            cookies = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"ERROR: Невалідний формат. Очікується cookies.txt або JSON масив.\nДеталі: {e}", file=sys.stderr)
            sys.exit(1)
        if not isinstance(cookies, list):
            print("ERROR: JSON має бути масивом кукі.", file=sys.stderr)
            sys.exit(1)
        storage_state = _json_to_storage_state(cookies)
        n = len(storage_state["cookies"])
        fmt = "Cookie Editor JSON"

    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(storage_state, indent=2, ensure_ascii=False))
    print(f"Авторизацію збережено: {STATE_FILE}")
    print(f"Формат: {fmt}, кукі: {n} шт.")
    print("Готово! Тепер можна генерувати подкасти.")


# ── Status ────────────────────────────────────────────────────────────────────

def cmd_status():
    _seed_from_env()
    if _is_authed():
        data = json.loads(STATE_FILE.read_text())
        n = len(data.get("cookies", []))
        print("AUTHENTICATED")
        print(f"Файл: {STATE_FILE}")
        print(f"Кукі: {n} шт.")
        print("Ліміт: 3 подкасти/день (free tier)")
    else:
        print("NOT_AUTHENTICATED")
        print("Запусти: python skills/podcast/handler.py login")


# ── Telegram audio send ───────────────────────────────────────────────────────

def _send_tg_audio(chat_id: str, file_path: Path, title: str):
    if not BOT_TOKEN:
        print("WARNING: TELEGRAM_BOT_TOKEN не задано — файл не відправлено", file=sys.stderr)
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendAudio"
    boundary = "---PodcastBoundary7766"
    audio_bytes = file_path.read_bytes()

    def part(name, value):
        return (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{value}\r\n"
        ).encode()

    body = bytearray()
    body += part("chat_id", chat_id)
    body += part("title", title[:64])
    body += part("caption", f"Подкаст: {title[:200]}")
    body += (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="audio"; filename="{file_path.name}"\r\n'
        f"Content-Type: audio/mpeg\r\n\r\n"
    ).encode()
    body += audio_bytes
    body += f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        url,
        data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
        if result.get("ok"):
            print(f"Відправлено в Telegram (chat_id={chat_id})")
        else:
            print(f"WARNING: Telegram error: {result.get('description')}", file=sys.stderr)
    except Exception as e:
        print(f"WARNING: Не вдалось відправити в Telegram: {e}", file=sys.stderr)


# ── Generate ──────────────────────────────────────────────────────────────────

DURATION_LABELS = {"brief": "2-3 хв", "standard": "5-6 хв", "extended": "8-10 хв"}
FORMAT_LABELS = {
    "deep_dive": "глибока дискусія",
    "brief":     "стислий огляд",
    "critique":  "критичний аналіз",
    "debate":    "дебати",
}

async def cmd_generate(
    topic: str,
    fmt: str,
    duration: str,
    source: str | None,
    lang: str,
    chat_id: str | None,
    instructions: str,
    preset: str | None,
):
    _seed_from_env()

    if not _is_authed():
        print("ERROR: Не авторизований.", file=sys.stderr)
        print(LOGIN_INSTRUCTIONS)
        sys.exit(1)

    try:
        from notebooklm import NotebookLMClient, AudioLength, AudioFormat
    except ImportError:
        print("ERROR: pip install notebooklm-py", file=sys.stderr)
        sys.exit(1)

    duration_map = {
        "brief":    AudioLength.SHORT,
        "standard": AudioLength.DEFAULT,
        "extended": AudioLength.LONG,
    }
    format_map = {
        "deep_dive": AudioFormat.DEEP_DIVE,
        "brief":     AudioFormat.BRIEF,
        "critique":  AudioFormat.CRITIQUE,
        "debate":    AudioFormat.DEBATE,
    }

    audio_length = duration_map.get(duration, AudioLength.DEFAULT)
    audio_format = format_map.get(fmt, AudioFormat.DEEP_DIVE)

    # Combine preset + custom instructions
    final_instructions = ""
    if preset and preset in PRESETS:
        final_instructions = PRESETS[preset]
    if instructions:
        final_instructions = (final_instructions + " " + instructions).strip() if final_instructions else instructions

    output_dir = AGENT_DIR / "tmp" / "podcasts"
    output_dir.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() else "_" for c in topic[:50]).strip("_")
    output_file = output_dir / f"podcast_{safe}.mp3"

    notebook_id = None
    print(f"[1/4] Підключення до NotebookLM...")
    if final_instructions:
        print(f"      Інструкції: {final_instructions[:120]}{'...' if len(final_instructions) > 120 else ''}")

    try:
        async with await NotebookLMClient.from_storage(path=str(STATE_FILE)) as client:
            print(f"[2/4] Створення notebook: «{topic[:60]}»")
            notebook = await client.notebooks.create(title=f"Podcast: {topic[:80]}")
            notebook_id = notebook.id

            source_content = source if source else topic
            if source_content.startswith("http://") or source_content.startswith("https://"):
                print(f"[2/4] Додаю URL: {source_content[:80]}")
                await client.sources.add_url(notebook_id, source_content, wait=True)
            else:
                print(f"[2/4] Додаю текст ({len(source_content)} символів)")
                await client.sources.add_text(notebook_id, topic[:80], source_content, wait=True)

            print(
                f"[3/4] Генерація подкасту "
                f"({FORMAT_LABELS.get(fmt, fmt)}, "
                f"{DURATION_LABELS.get(duration, duration)}, "
                f"мова: {lang})..."
            )
            status = await client.artifacts.generate_audio(
                notebook_id,
                language=lang,
                audio_length=audio_length,
                audio_format=audio_format,
                instructions=final_instructions,
            )

            # extended = up to ~4 min generation, use 10 min timeout
            poll_timeout = 600.0
            print(f"[3/4] Очікую завершення (до {int(poll_timeout // 60)} хв)...")
            final_status = await client.artifacts.wait_for_completion(
                notebook_id,
                status.task_id,
                timeout=poll_timeout,
            )

            if final_status.error:
                print(f"ERROR: Генерація провалилась: {final_status.error}", file=sys.stderr)
                sys.exit(1)

            print(f"[4/4] Завантаження аудіо...")
            audio_artifacts = await client.artifacts.list_audio(notebook_id)
            artifact_id = audio_artifacts[0].id if audio_artifacts else None

            await client.artifacts.download_audio(notebook_id, str(output_file), artifact_id=artifact_id)

            try:
                await client.notebooks.delete(notebook_id)
                notebook_id = None
            except Exception:
                pass

    except Exception as e:
        msg = str(e).lower()
        if any(x in msg for x in ("401", "403", "unauthorized", "autherror", "cookie", "auth", "session", "invalid")):
            print("ERROR: Авторизація застаріла — потрібно повторити логін.", file=sys.stderr)
            _clear_auth()
            print(LOGIN_INSTRUCTIONS)
            sys.exit(1)
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    if not output_file.exists():
        print("ERROR: Файл не завантажено", file=sys.stderr)
        sys.exit(1)

    size_kb = output_file.stat().st_size // 1024
    print(f"\nПодкаст готовий!")
    print(f"  Файл:       {output_file}")
    print(f"  Розмір:     {size_kb} KB")
    print(f"  Формат:     {FORMAT_LABELS.get(fmt, fmt)}")
    print(f"  Тривалість: ~{DURATION_LABELS.get(duration, '?')}")
    print(f"FILE:{output_file}")

    if chat_id:
        print(f"\nВідправляю в Telegram...")
        _send_tg_audio(chat_id, output_file, topic)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(
        description="Podcast skill — Google NotebookLM (free)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="Check auth status")

    lg = sub.add_parser("login", help="Setup auth via cookies.txt")
    lg.add_argument("cookies", nargs="?", help="cookies.txt content or JSON (omit for instructions)")

    gen = sub.add_parser("generate", help="Generate podcast audio")
    gen.add_argument("topic", help="Podcast topic or title")
    gen.add_argument(
        "--format", dest="fmt", default="deep_dive",
        choices=["deep_dive", "brief", "critique", "debate"],
        help="Podcast format (default: deep_dive)",
    )
    gen.add_argument(
        "--duration", default="standard",
        choices=["brief", "standard", "extended"],
        help="Podcast length: brief=2-3хв, standard=5-6хв, extended=8-10хв (default: standard)",
    )
    gen.add_argument(
        "--preset", choices=list(PRESETS.keys()),
        help="Pre-built instruction set: casual|formal|educational|expert|ukrainian",
    )
    gen.add_argument(
        "--instructions",
        help="Custom instructions for the podcast hosts (combined with --preset if both given)",
    )
    gen.add_argument("--source", help="URL or text to use as source (default: topic itself)")
    gen.add_argument("--lang", default="uk", help="Podcast language BCP47 code (default: uk)")
    gen.add_argument("--chat-id", dest="chat_id", help="Telegram chat_id to auto-send audio after generation")

    args = p.parse_args()

    if args.cmd == "status":
        cmd_status()
    elif args.cmd == "login":
        cmd_login(args.cookies)
    elif args.cmd == "generate":
        asyncio.run(cmd_generate(
            topic=args.topic,
            fmt=args.fmt,
            duration=args.duration,
            source=args.source,
            lang=args.lang,
            chat_id=args.chat_id,
            instructions=args.instructions or "",
            preset=args.preset,
        ))


if __name__ == "__main__":
    main()
