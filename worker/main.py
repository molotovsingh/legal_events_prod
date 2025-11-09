"""
Background Worker Main Entry Point
Runs RQ worker to process document extraction jobs
"""

import os
import logging
import sys
import time
import threading
import json
import socket
from datetime import datetime
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

# Heartbeat configuration
HEARTBEAT_INTERVAL = 10  # seconds
HEARTBEAT_TTL = 30  # seconds (3x interval for safety)


def emit_heartbeat(redis_conn, worker_id, worker):
    """
    Emit periodic heartbeat to Redis
    Runs in background thread to prove worker is alive
    """
    while True:
        try:
            # Get worker stats
            heartbeat_data = {
                'worker_id': worker_id,
                'hostname': socket.gethostname(),
                'pid': os.getpid(),
                'timestamp': datetime.utcnow().isoformat(),
                'successful_jobs': worker.successful_job_count if worker else 0,
                'failed_jobs': worker.failed_job_count if worker else 0,
                'current_job': worker.get_current_job_id() if worker else None,
                'state': worker.get_state() if worker else 'starting'
            }
            
            # Store heartbeat with TTL
            heartbeat_key = f"worker:heartbeat:{worker_id}"
            redis_conn.setex(
                heartbeat_key,
                HEARTBEAT_TTL,
                json.dumps(heartbeat_data)
            )
            
            logger.debug(f"💓 Heartbeat sent: {worker_id}")
            
        except Exception as e:
            logger.error(f"Failed to send heartbeat: {e}")
        
        # Wait before next heartbeat
        time.sleep(HEARTBEAT_INTERVAL)


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
    
    # Get worker ID
    worker_id = worker.name

    logger.info("✅ Worker ready and listening for jobs...")
    
    # Start heartbeat thread
    heartbeat_thread = threading.Thread(
        target=emit_heartbeat,
        args=(redis_conn, worker_id, worker),
        daemon=True,
        name="heartbeat-thread"
    )
    heartbeat_thread.start()
    logger.info(f"💓 Heartbeat thread started (interval: {HEARTBEAT_INTERVAL}s, TTL: {HEARTBEAT_TTL}s)")

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
