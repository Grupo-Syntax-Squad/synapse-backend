from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore[import-untyped]
from apscheduler.triggers.interval import IntervalTrigger  # type: ignore[import-untyped]
from datetime import datetime
from src.modules.nlp import ReportGenerator
from src.logger_instance import logger

scheduler = BackgroundScheduler()
job = None


def generate_report_job() -> None:
    logger.info(f"Scheduled report generation started at {datetime.utcnow()}")
    ReportGenerator().execute()


def start_scheduler() -> None:
    global job
    if job:
        scheduler.remove_job(job.id)
    job = scheduler.add_job(
        generate_report_job,
        trigger=IntervalTrigger(minutes=5),
        id="report_job",
        replace_existing=True,
    )
    logger.info("Scheduler started / reset with 5min interval")


def reset_scheduler() -> None:
    start_scheduler()
