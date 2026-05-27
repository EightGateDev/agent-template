"""Task data model + JSON persistence for background_tasks."""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

TASKS_FILE: Path = Path(__file__).parent / "tasks.json"
AGENT_TZ = ZoneInfo(os.getenv("AGENT_TIMEZONE", "Europe/Kyiv"))

_tasks_lock: asyncio.Lock | None = None


def _get_lock() -> asyncio.Lock:
    global _tasks_lock
    if _tasks_lock is None:
        _tasks_lock = asyncio.Lock()
    return _tasks_lock


def init_lock() -> None:
    global _tasks_lock
    _tasks_lock = asyncio.Lock()


def _generate_id() -> str:
    date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"task_{date_part}_{secrets.token_hex(3)}"


def _parse_scheduled(value: str) -> str:
    """Convert '+30m'/'+2h' to ISO UTC; cron-like 'HH:MM' to next occurrence; pass ISO through."""
    if value.startswith("+"):
        match = re.fullmatch(r"\+(\d+)(s|m|h)", value.strip())
        if not match:
            raise ValueError(f"Bad relative time format: {value!r}. Use +Ns, +Nm, or +Nh.")
        amount = int(match.group(1))
        unit = match.group(2)
        delta = {"s": timedelta(seconds=amount), "m": timedelta(minutes=amount), "h": timedelta(hours=amount)}[unit]
        return (datetime.now(timezone.utc) + delta).isoformat()
    # HH:MM — schedule for next occurrence of that time in agent's timezone
    time_match = re.fullmatch(r"(\d{1,2}):(\d{2})", value.strip())
    if time_match:
        h, m = int(time_match.group(1)), int(time_match.group(2))
        now_tz = datetime.now(AGENT_TZ)
        candidate = now_tz.replace(hour=h, minute=m, second=0, microsecond=0)
        if candidate <= now_tz:
            candidate += timedelta(days=1)
        return candidate.astimezone(timezone.utc).isoformat()
    # ISO — validate
    datetime.fromisoformat(value)
    return value


@dataclass
class TaskPayload:
    goal: str
    tools_allowed: list[str]
    context: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"goal": self.goal, "tools_allowed": self.tools_allowed, "context": self.context}

    @classmethod
    def from_dict(cls, data: dict) -> "TaskPayload":
        return cls(goal=data["goal"], tools_allowed=data["tools_allowed"], context=data.get("context", {}))


@dataclass
class Task:
    id: str
    status: str           # pending | running | done | failed | cancelled
    scheduled_for: str    # ISO UTC (irrelevant for todo tasks)
    created_at: str       # ISO UTC
    payload: TaskPayload
    retries: int = 0
    max_retries: int = 3
    backoff_ms: int = 60000
    result: Optional[str] = None
    cancellation_requested: bool = False
    task_type: str = "one_time"           # one_time | recurring | todo
    recurring_interval: Optional[str] = None  # +2h, +30m, 03:00, etc.

    def to_dict(self) -> dict:
        return {
            "id": self.id, "status": self.status, "scheduled_for": self.scheduled_for,
            "created_at": self.created_at, "payload": self.payload.to_dict(),
            "retries": self.retries, "max_retries": self.max_retries, "backoff_ms": self.backoff_ms,
            "result": self.result, "cancellation_requested": self.cancellation_requested,
            "task_type": self.task_type, "recurring_interval": self.recurring_interval,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        return cls(
            id=data["id"], status=data["status"], scheduled_for=data["scheduled_for"],
            created_at=data["created_at"], payload=TaskPayload.from_dict(data["payload"]),
            retries=data.get("retries", 0), max_retries=data.get("max_retries", 3),
            backoff_ms=data.get("backoff_ms", 60000), result=data.get("result"),
            cancellation_requested=data.get("cancellation_requested", False),
            task_type=data.get("task_type", "one_time"),
            recurring_interval=data.get("recurring_interval"),
        )

    @classmethod
    def create(
        cls, goal: str, tools_allowed: list[str], scheduled_for: str = "+0s",
        context: dict | None = None, max_retries: int = 3, backoff_ms: int = 60000,
        task_type: str = "one_time", recurring_interval: str | None = None,
    ) -> "Task":
        now = datetime.now(timezone.utc).isoformat()
        # todo tasks don't use scheduled_for — set to far future, triggered manually
        sched = "2099-01-01T00:00:00+00:00" if task_type == "todo" else _parse_scheduled(scheduled_for)
        return cls(
            id=_generate_id(), status="pending", scheduled_for=sched, created_at=now,
            payload=TaskPayload(goal=goal, tools_allowed=tools_allowed, context=context or {}),
            max_retries=max_retries, backoff_ms=backoff_ms,
            task_type=task_type, recurring_interval=recurring_interval,
        )


async def load_tasks() -> list[Task]:
    async with _get_lock():
        if not TASKS_FILE.exists():
            return []
        loop = asyncio.get_running_loop()
        raw = await loop.run_in_executor(None, TASKS_FILE.read_text, "utf-8")
        return [Task.from_dict(d) for d in json.loads(raw)]


async def save_tasks(tasks: list[Task]) -> None:
    async with _get_lock():
        payload = json.dumps([t.to_dict() for t in tasks], indent=2, ensure_ascii=False)
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, TASKS_FILE.write_text, payload, "utf-8")


async def add_task(task: Task) -> None:
    async with _get_lock():
        tasks = []
        if TASKS_FILE.exists():
            loop = asyncio.get_running_loop()
            raw = await loop.run_in_executor(None, TASKS_FILE.read_text, "utf-8")
            tasks = [Task.from_dict(d) for d in json.loads(raw)]
        tasks.append(task)
        payload = json.dumps([t.to_dict() for t in tasks], indent=2, ensure_ascii=False)
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, TASKS_FILE.write_text, payload, "utf-8")


async def update_task(task_id: str, **fields) -> Optional[Task]:
    async with _get_lock():
        if not TASKS_FILE.exists():
            return None
        loop = asyncio.get_running_loop()
        raw = await loop.run_in_executor(None, TASKS_FILE.read_text, "utf-8")
        tasks = [Task.from_dict(d) for d in json.loads(raw)]
        updated: Optional[Task] = None
        for task in tasks:
            if task.id == task_id:
                for key, val in fields.items():
                    if hasattr(task, key):
                        setattr(task, key, val)
                updated = task
                break
        if updated is not None:
            payload = json.dumps([t.to_dict() for t in tasks], indent=2, ensure_ascii=False)
            await loop.run_in_executor(None, TASKS_FILE.write_text, payload, "utf-8")
        return updated


async def trigger_todo(task_id: str) -> bool:
    """Trigger a todo task immediately. Returns True if found and triggered."""
    async with _get_lock():
        if not TASKS_FILE.exists():
            return False
        loop = asyncio.get_running_loop()
        raw = await loop.run_in_executor(None, TASKS_FILE.read_text, "utf-8")
        tasks = [Task.from_dict(d) for d in json.loads(raw)]
        found = False
        for task in tasks:
            if task.id == task_id and task.task_type == "todo" and task.status == "pending":
                task.scheduled_for = datetime.now(timezone.utc).isoformat()
                found = True
                break
        if found:
            payload = json.dumps([t.to_dict() for t in tasks], indent=2, ensure_ascii=False)
            await loop.run_in_executor(None, TASKS_FILE.write_text, payload, "utf-8")
        return found


async def modify_tasks(fn) -> None:
    async with _get_lock():
        tasks = []
        if TASKS_FILE.exists():
            loop = asyncio.get_running_loop()
            raw = await loop.run_in_executor(None, TASKS_FILE.read_text, "utf-8")
            tasks = [Task.from_dict(d) for d in json.loads(raw)]
        fn(tasks)
        payload = json.dumps([t.to_dict() for t in tasks], indent=2, ensure_ascii=False)
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, TASKS_FILE.write_text, payload, "utf-8")
