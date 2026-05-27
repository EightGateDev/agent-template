"""Usage logger stub — no-op for standalone deployments.

Each skill calls log_usage() after a paid API call.
This is a no-op stub. Override with your own implementation to track usage.
Never raises — a logging failure must never break the skill.
"""

def log_usage(service: str, units: float, unit_type: str, meta: dict | None = None) -> None:
    """Log paid API usage. No-op in this standalone build."""
    pass
