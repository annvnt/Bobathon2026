"""APScheduler daily MCP sync (Workflow B trigger)."""
from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import settings
from .database import SessionLocal
from .services.gap_analysis import run_sync

logger = logging.getLogger("ecocomply.scheduler")
_scheduler: BackgroundScheduler | None = None


def _job() -> None:
    db = SessionLocal()
    try:
        result = run_sync(db)
        logger.info("Daily sync complete: %s", result.message)
    except Exception:  # noqa: BLE001
        logger.exception("Daily sync failed")
    finally:
        db.close()


def start_scheduler() -> None:
    global _scheduler
    if not settings.ENABLE_SCHEDULER or _scheduler is not None:
        return
    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(
        _job,
        CronTrigger(hour=settings.SYNC_HOUR, minute=settings.SYNC_MINUTE),
        id="daily_mcp_sync",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info(
        "Scheduler started — daily sync at %02d:%02d",
        settings.SYNC_HOUR, settings.SYNC_MINUTE,
    )


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
