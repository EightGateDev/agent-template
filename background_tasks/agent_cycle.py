"""Background task executor — uses `claude -p` subprocess (Claude Code subscription).

No LLM API keys required. Each task runs a fresh `claude -p` invocation.
"""
from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger("background_tasks.agent_cycle")

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Systemd strips PATH — bun and gog are not in the default PATH.
_BUN_BIN = Path("/home/claudebot/.bun/bin")
_SYSTEMD_PATH = f"{_BUN_BIN}:/home/claudebot/.local/bin:/usr/local/bin:/usr/local/sbin:/usr/bin:/usr/sbin:/bin:/sbin"


def _claude_bin() -> str:
    """Locate claude binary. Systemd PATH is stripped so shutil.which may miss it."""
    found = shutil.which("claude")
    if found:
        return found
    fallback = _BUN_BIN / "claude"
    if fallback.exists():
        return str(fallback)
    raise FileNotFoundError(f"claude not found in PATH or {fallback}")
SOUL_FILE = _PROJECT_ROOT / "persona" / "SOUL.md"
MEMORY_FILE = _PROJECT_ROOT / "persona" / "MEMORY.md"


def _read_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _get_chat_id(context: dict | None) -> str:
    if context:
        chat_id = context.get("chat_id", "")
        if chat_id:
            return chat_id
    owner_ids = os.getenv("TELEGRAM_OWNER_ID", "")
    return owner_ids.split(",")[0].strip() if owner_ids else ""


def _build_prompt(goal: str, context: dict | None) -> str:
    soul = _read_file(SOUL_FILE).strip()
    memory = _read_file(MEMORY_FILE).strip()
    chat_id = _get_chat_id(context)
    agent_name = os.getenv("AGENT_NAME", "agent")
    bot_token_env = "TELEGRAM_BOT_TOKEN"

    ctx_block = ""
    if context:
        ctx_lines = "\n".join(f"  {k}: {v}" for k, v in context.items())
        ctx_block = f"\nContext:\n{ctx_lines}\n"

    parts: list[str] = []
    if soul:
        parts.append(soul)
    if memory:
        parts.append("## User memory (follow strictly)\n\n" + memory)

    persona_block = "\n\n---\n\n".join(parts) + "\n\n---\n\n" if parts else ""

    return (
        f"{persona_block}"
        f"## Task executor mode\n\n"
        f"You are executing a scheduled background task autonomously. No user is present.\n\n"
        f"**Goal:** {goal}\n"
        f"{ctx_block}\n"
        f"**User chat_id:** {chat_id}\n\n"
        f"**How to send a Telegram message** (use Bash):\n"
        f"```bash\n"
        f'curl -s -X POST "https://api.telegram.org/bot${bot_token_env}/sendMessage" \\\n'
        f'  -H "Content-Type: application/json" \\\n'
        f'  -d \'{{"chat_id": "{chat_id}", "text": "YOUR MESSAGE HERE"}}\'\n'
        f"```\n\n"
        f"Rules:\n"
        f"- If the goal is a reminder or notification, send the Telegram message NOW via curl.\n"
        f"- Be concise and direct. Never fabricate data.\n"
        f"- Do NOT schedule or create new tasks.\n"
        f"- You are agent: {agent_name}\n"
    )


async def run_agent_cycle(
    goal: str,
    tools_allowed: list[str] | None = None,
    context: dict | None = None,
    task_id: str | None = None,
) -> str:
    """Execute goal using claude -p (Claude Code subscription, no API key needed)."""
    prompt = _build_prompt(goal, context)
    logger.info("Running claude -p for task %s: %s", task_id or "?", goal[:80])

    try:
        env = os.environ.copy()
        env["PATH"] = _SYSTEMD_PATH  # ensure bun + gog are findable inside claude -p
        proc = await asyncio.to_thread(
            subprocess.run,
            [_claude_bin(), "-p", prompt, "--dangerously-skip-permissions"],
            capture_output=True,
            text=True,
            cwd=str(_PROJECT_ROOT),
            timeout=550,
            env=env,
        )
        output = (proc.stdout or "").strip()
        if proc.returncode != 0:
            err = (proc.stderr or "").strip()[:500]
            logger.error("claude -p failed (rc=%d): %s", proc.returncode, err)
            return f"Error: claude -p exited with code {proc.returncode}: {err}"
        logger.info("claude -p done for task %s. Output length=%d", task_id or "?", len(output))
        return output or "Done."
    except subprocess.TimeoutExpired:
        logger.error("claude -p timed out for task %s", task_id or "?")
        return "Error: claude -p timed out"
    except Exception as exc:
        logger.exception("claude -p error for task %s: %s", task_id or "?", exc)
        return f"Error: {exc}"
