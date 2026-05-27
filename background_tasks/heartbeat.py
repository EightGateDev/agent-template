"""Heartbeat scheduler — ticks every 30s, dispatches due tasks."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time as _time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from background_tasks.models import Task, load_tasks, update_task, modify_tasks, add_task, init_lock
from background_tasks.agent_cycle import run_agent_cycle
from background_tasks.telegram_notify import telegram_send

HEARTBEAT_FILE = Path(__file__).parent / "heartbeat.json"
TICK_INTERVAL = int(os.getenv("TICK_INTERVAL", "30"))
MAX_CONCURRENT = int(os.getenv("MAX_CONCURRENT", "3"))
CLEANUP_DAYS = int(os.getenv("CLEANUP_DAYS", "7"))

_semaphore: Optional[asyncio.Semaphore] = None
_running_tasks: set[str] = set()
_uptime_since: Optional[str] = None

logger = logging.getLogger("background_tasks.heartbeat")


def _write_heartbeat(active_tasks: list[str]) -> None:
    data = {"last_tick": datetime.now(timezone.utc).isoformat(), "active_tasks": active_tasks, "uptime_since": _uptime_since}
    try:
        HEARTBEAT_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as exc:
        logger.warning("Failed to write heartbeat.json: %s", exc)


async def _recover_running_tasks() -> None:
    def _do(tasks: list[Task]) -> None:
        for task in tasks:
            if task.status == "running":
                task.retries += 1
                if task.retries >= task.max_retries:
                    task.status = "failed"
                    task.result = "Crash-recovered: max retries exceeded"
                else:
                    task.status = "pending"
    await modify_tasks(_do)


async def _cleanup_old_tasks() -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(days=CLEANUP_DAYS)
    terminal = {"done", "failed", "cancelled"}

    def _do(tasks: list[Task]) -> None:
        to_remove = [i for i, t in enumerate(tasks) if t.status in terminal and
                     _safe_dt(t.created_at) < cutoff]
        for i in reversed(to_remove):
            tasks.pop(i)
        if to_remove:
            logger.info("Cleaned up %d old terminal tasks", len(to_remove))

    await modify_tasks(_do)


def _safe_dt(val: str) -> datetime:
    try:
        dt = datetime.fromisoformat(val)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def _get_chat_id(task: Task) -> str:
    if task.payload and task.payload.context:
        cid = task.payload.context.get("chat_id", "")
        if cid:
            return cid
    owner_ids = os.getenv("TELEGRAM_OWNER_ID", "")
    return owner_ids.split(",")[0].strip() if owner_ids else ""


async def _notify(task: Task, msg: str) -> None:
    chat_id = _get_chat_id(task)
    if chat_id:
        try:
            await telegram_send(chat_id, msg)
        except Exception as e:
            logger.error("Notification error for %s: %s", task.id, e)


async def _handle_task_failure(task: Task, error: str) -> None:
    retries = task.retries + 1
    if retries < task.max_retries:
        backoff_s = (task.backoff_ms / 1000) * (4 ** (retries - 1))
        new_sched = (datetime.now(timezone.utc) + timedelta(seconds=backoff_s)).isoformat()
        await update_task(task.id, status="pending", retries=retries, scheduled_for=new_sched, result=f"Retry {retries}: {error}")
    else:
        await update_task(task.id, status="failed", retries=retries, result=f"Failed after {retries} retries: {error}")
        if task.task_type == "recurring" and task.recurring_interval:
            await _reschedule_recurring(task)
            await _notify(task, f"⚠️ *Task failed, rescheduled*\n\n*Goal:* {task.payload.goal[:300]}\n*Error:* {error[:200]}")
        else:
            await _notify(task, f"❌ *Task permanently failed*\n\n*Goal:* {task.payload.goal[:300]}\n*Error:* {error[:200]}")


async def _reschedule_recurring(task: Task) -> None:
    new_task = Task.create(
        goal=task.payload.goal, tools_allowed=task.payload.tools_allowed,
        scheduled_for=task.recurring_interval, context=task.payload.context,
        max_retries=task.max_retries, backoff_ms=task.backoff_ms,
        task_type="recurring", recurring_interval=task.recurring_interval,
    )
    await add_task(new_task)
    logger.info("Rescheduled recurring task %s → %s (next: %s)", task.id, new_task.id, new_task.scheduled_for)


def _get_langfuse():
    if not hasattr(_get_langfuse, "_lf"):
        _get_langfuse._lf = None
        try:
            pub = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
            sec = os.environ.get("LANGFUSE_SECRET_KEY", "")
            host = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")
            if pub and sec:
                from langfuse import Langfuse
                _get_langfuse._lf = Langfuse(public_key=pub, secret_key=sec, host=host)
        except Exception:
            pass
    return _get_langfuse._lf


async def _run_task(task: Task) -> None:
    global _semaphore
    assert _semaphore is not None
    async with _semaphore:
        logger.info("Starting task %s: %s", task.id, task.payload.goal[:80])
        await update_task(task.id, status="running")
        lf = _get_langfuse()
        lf_trace = None
        start = _time.time()
        if lf:
            try:
                lf_trace = lf.trace(name=f"task:{task.id}", input={"goal": task.payload.goal, "task_id": task.id, "task_type": task.task_type or "one_time"})
            except Exception:
                pass
        try:
            result = await asyncio.wait_for(
                run_agent_cycle(goal=task.payload.goal, tools_allowed=task.payload.tools_allowed, context=task.payload.context, task_id=task.id),
                timeout=600,
            )
            duration_ms = int((_time.time() - start) * 1000)
            await update_task(task.id, status="done", result=result)
            if lf_trace:
                try: lf_trace.update(output={"result": result[:2000], "status": "done"}, metadata={"duration_ms": duration_ms})
                except Exception: pass
            if task.task_type == "recurring" and task.recurring_interval:
                await _reschedule_recurring(task)
            await _notify(task, f"✅ *Task done*\n\n*Goal:* {task.payload.goal[:200]}\n\n*Result:*\n{result[:1000]}")
        except asyncio.TimeoutError:
            await _notify(task, f"⏱ *Task timed out*\n\n*Goal:* {task.payload.goal[:200]}")
            await _handle_task_failure(task, "Timed out after 600s")
        except Exception as exc:
            logger.exception("Task %s raised: %s", task.id, exc)
            await _handle_task_failure(task, str(exc))
        finally:
            _running_tasks.discard(task.id)
            if lf:
                try: lf.flush()
                except Exception: pass


async def heartbeat_loop() -> None:
    global _semaphore, _uptime_since
    _semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    _uptime_since = datetime.now(timezone.utc).isoformat()
    init_lock()
    logger.info("Heartbeat starting — recovering crashed tasks")
    await _recover_running_tasks()
    await _cleanup_old_tasks()
    logger.info("Heartbeat loop started. Tick every %ds, max concurrent=%d", TICK_INTERVAL, MAX_CONCURRENT)

    tick = 0
    while True:
        try:
            tick += 1
            now = datetime.now(timezone.utc)
            tasks = await load_tasks()
            pending = [t for t in tasks if t.status == "pending" and t.id not in _running_tasks]

            for task in pending:
                scheduled = _safe_dt(task.scheduled_for)
                if scheduled <= now:
                    logger.info("Dispatching task %s: %s", task.id, task.payload.goal[:60])
                    _running_tasks.add(task.id)
                    asyncio.create_task(_run_task(task))

            _write_heartbeat(list(_running_tasks))
        except Exception as exc:
            logger.exception("Heartbeat tick error (non-fatal): %s", exc)
        await asyncio.sleep(TICK_INTERVAL)
