import contextlib
import logging
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler

from scryapi.sync import run_sync

logger = logging.getLogger(__name__)


def sync_job(app):
    """Scheduler entry point: runs outside any request, so it pushes its own app context."""
    # Failures are already logged and recorded in sync_state; keep the scheduler alive.
    with app.app_context(), contextlib.suppress(Exception):
        run_sync()


def run_forever(app, interval_seconds):
    scheduler = BlockingScheduler()
    scheduler.add_job(
        sync_job,
        trigger="interval",
        seconds=interval_seconds,
        args=[app],
        next_run_time=datetime.now(),
        max_instances=1,
        coalesce=True,
    )
    logger.info("Card sync scheduler started (every %ss)", interval_seconds)
    scheduler.start()
