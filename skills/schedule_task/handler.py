"""Schedule task skill — creates a new background task from the agent."""
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


def schedule_task(
    goal: str,
    scheduled_for: str = "+0s",
    task_type: str = "one_time",
    recurring_interval: str | None = None,
    context: dict | None = None,
) -> dict:
    """
    Create a new background task.

    Args:
        goal: What the agent should do
        scheduled_for: '+30m', '+2h', '03:00', or ISO UTC string
        task_type: 'one_time' | 'recurring' | 'todo'
        recurring_interval: For recurring tasks: '+24h', '+1h', '09:00', etc.
        context: Extra context dict (e.g. {'chat_id': '123'})

    Returns:
        {'task_id': str, 'scheduled_for': str}
    """
    import asyncio
    from background_tasks.models import Task, add_task

    task = Task.create(
        goal=goal,
        tools_allowed=[],
        scheduled_for=scheduled_for,
        context=context or {},
        task_type=task_type,
        recurring_interval=recurring_interval,
    )

    asyncio.run(add_task(task))
    return {"task_id": task.id, "scheduled_for": task.scheduled_for}


if __name__ == "__main__":
    result = schedule_task(goal=sys.argv[1] if len(sys.argv) > 1 else "Test task")
    print(json.dumps(result, indent=2))
