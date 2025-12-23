"""arq worker runner.

Run with: python -m services.queue.worker
Or: arq services.queue.tasks.WorkerSettings

This module configures and runs the async task worker.
"""

import logging

from arq import run_worker

from services.queue.tasks import WorkerSettings
from services.shared.config import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


def main() -> None:
    """Run the arq worker."""
    settings = get_settings()

    logger.info(f"Starting worker with Redis: {settings.redis_url}")
    logger.info(f"Max jobs: {settings.queue_max_jobs}")
    logger.info(f"Job timeout: {settings.queue_job_timeout}s")

    # Update worker settings from config
    WorkerSettings.redis_settings = WorkerSettings.get_redis_settings()
    WorkerSettings.max_jobs = settings.queue_max_jobs
    WorkerSettings.job_timeout = settings.queue_job_timeout

    # Run worker
    run_worker(WorkerSettings)  # type: ignore[arg-type]


if __name__ == "__main__":
    main()
