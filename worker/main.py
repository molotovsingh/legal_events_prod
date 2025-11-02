"""
Background Worker Main Entry Point
Runs RQ worker to process document extraction jobs
"""

import os
import logging
import sys
from rq import Worker, Queue
import redis

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Redis connection
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")


def main():
    """
    Main worker entry point
    """
    logger.info("🚀 Starting Legal Events Worker...")
    
    # Connect to Redis
    redis_conn = redis.from_url(REDIS_URL)
    
    # Define queues to listen to (in priority order)
    queues = [
        Queue("high", connection=redis_conn),
        Queue("default", connection=redis_conn),
        Queue("low", connection=redis_conn),
    ]
    
    logger.info(f"📋 Listening to queues: {[q.name for q in queues]}")

    # Create and start worker (Connection context manager is deprecated in RQ)
    worker = Worker(
        queues,
        connection=redis_conn,
        name="legal-events-worker",
        log_job_description=True,
    )

    logger.info("✅ Worker ready and listening for jobs...")

    # Start working
    worker.work(with_scheduler=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("👋 Worker shutting down...")
    except Exception as e:
        logger.error(f"❌ Worker failed: {e}")
        sys.exit(1)
