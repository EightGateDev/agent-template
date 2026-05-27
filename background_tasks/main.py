"""Background tasks entrypoint — starts heartbeat loop."""
import asyncio
import logging
import os
import signal
import sys
from pathlib import Path
from dotenv import load_dotenv

_project_root = Path(__file__).parent.parent
load_dotenv(_project_root / ".env")


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


async def main() -> None:
    setup_logging()
    logger = logging.getLogger("background_tasks.main")
    logger.info("Background tasks starting (agent: %s)", os.getenv("AGENT_NAME", "unknown"))

    required = ["TELEGRAM_BOT_TOKEN"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        logger.error("Missing required env vars: %s", ", ".join(missing))
        sys.exit(1)

    from background_tasks.heartbeat import heartbeat_loop

    loop = asyncio.get_running_loop()
    shutdown_event = asyncio.Event()

    def _shutdown():
        logger.info("Shutdown signal received")
        shutdown_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _shutdown)
        except NotImplementedError:
            signal.signal(sig, lambda s, f: _shutdown())

    heartbeat_task = asyncio.create_task(heartbeat_loop())
    done, pending = await asyncio.wait(
        [heartbeat_task, asyncio.create_task(shutdown_event.wait())],
        return_when=asyncio.FIRST_COMPLETED,
    )
    for task in pending:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    logger.info("Background tasks stopped")


if __name__ == "__main__":
    asyncio.run(main())
