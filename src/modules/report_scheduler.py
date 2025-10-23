from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]
from apscheduler.triggers.interval import IntervalTrigger  # type: ignore[import-untyped]
from apscheduler.job import Job  # type: ignore[import-untyped]
from datetime import datetime, timezone

from src.logger_instance import logger
from src.modules.report import ReportWorkflow
from src.settings import settings

scheduler = AsyncIOScheduler()
job: Job | None = None  # type: ignore[no-any-unimported]


async def generate_report_job() -> None:
    logger.info(f"Scheduled report generation started at {datetime.now(timezone.utc)}")
    await ReportWorkflow().execute()


def start_scheduler() -> None:
    global job
    if job:
        scheduler.remove_job(job.id)
    job = scheduler.add_job(
        generate_report_job,
        trigger=IntervalTrigger(minutes=settings.SCHEDULED_REPORT_GENERATION_MINUTES),
        id="report_job",
        replace_existing=True,
    )
    logger.info(
        f"Scheduler started / reset with {settings.SCHEDULED_REPORT_GENERATION_MINUTES}min interval"
    )


def reset_scheduler() -> None:
    start_scheduler()
