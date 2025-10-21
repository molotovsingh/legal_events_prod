"""
Redis Queue (RQ) Handler
Manages background job processing for document extraction
"""

import os
import logging
from typing import Optional, Dict, Any
import redis
from rq import Queue, Job, Worker
from rq.job import JobStatus
from datetime import timedelta

logger = logging.getLogger(__name__)

# Redis connection
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
redis_conn = redis.from_url(REDIS_URL)

# Queue configurations
QUEUES = {
    "high": Queue("high", connection=redis_conn, default_timeout="30m"),
    "default": Queue("default", connection=redis_conn, default_timeout="1h"),
    "low": Queue("low", connection=redis_conn, default_timeout="2h"),
}


def enqueue_job(
    func_name: str,
    queue_name: str = "default",
    **kwargs
) -> str:
    """
    Enqueue a job for background processing
    
    Args:
        func_name: Name of the function to call
        queue_name: Queue priority (high, default, low)
        **kwargs: Arguments to pass to the function
        
    Returns:
        Job ID
    """
    try:
        queue = QUEUES.get(queue_name, QUEUES["default"])
        
        # Map function names to actual functions
        if func_name == "process_run":
            from ..worker.tasks import process_run
            job = queue.enqueue(process_run, **kwargs)
        elif func_name == "process_document":
            from ..worker.tasks import process_document
            job = queue.enqueue(process_document, **kwargs)
        elif func_name == "generate_artifacts":
            from ..worker.tasks import generate_artifacts
            job = queue.enqueue(generate_artifacts, **kwargs)
        else:
            raise ValueError(f"Unknown function: {func_name}")
        
        logger.info(f"📋 Enqueued job {job.id} in {queue_name} queue")
        return job.id
        
    except Exception as e:
        logger.error(f"Failed to enqueue job: {e}")
        raise


def get_job_status(job_id: str) -> Optional[Dict[str, Any]]:
    """
    Get status of a job
    
    Args:
        job_id: Job ID
        
    Returns:
        Job status dict or None if not found
    """
    try:
        job = Job.fetch(job_id, connection=redis_conn)
        
        return {
            "id": job.id,
            "status": job.get_status(),
            "created_at": job.created_at,
            "started_at": job.started_at,
            "ended_at": job.ended_at,
            "result": job.result,
            "exc_info": job.exc_info,
            "meta": job.meta
        }
    except Exception as e:
        logger.error(f"Failed to get job status: {e}")
        return None


def cancel_job(job_id: str) -> bool:
    """
    Cancel a job
    
    Args:
        job_id: Job ID
        
    Returns:
        True if cancelled successfully
    """
    try:
        job = Job.fetch(job_id, connection=redis_conn)
        job.cancel()
        logger.info(f"❌ Cancelled job {job_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to cancel job: {e}")
        return False


def get_queue_stats(queue_name: str = "default") -> Dict[str, int]:
    """
    Get queue statistics
    
    Args:
        queue_name: Queue name
        
    Returns:
        Queue statistics
    """
    try:
        queue = QUEUES.get(queue_name, QUEUES["default"])
        
        return {
            "name": queue_name,
            "queued": len(queue),
            "started": queue.started_job_registry.count,
            "finished": queue.finished_job_registry.count,
            "failed": queue.failed_job_registry.count,
            "scheduled": queue.scheduled_job_registry.count,
            "canceled": queue.canceled_job_registry.count
        }
    except Exception as e:
        logger.error(f"Failed to get queue stats: {e}")
        return {}


def clear_queue(queue_name: str = "default") -> bool:
    """
    Clear all jobs from a queue (use with caution!)
    
    Args:
        queue_name: Queue name
        
    Returns:
        True if cleared successfully
    """
    try:
        queue = QUEUES.get(queue_name, QUEUES["default"])
        queue.empty()
        logger.warning(f"🧹 Cleared queue: {queue_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to clear queue: {e}")
        return False


def update_job_progress(
    job_id: str,
    progress: int,
    message: Optional[str] = None
) -> bool:
    """
    Update job progress (for long-running tasks)
    
    Args:
        job_id: Job ID
        progress: Progress percentage (0-100)
        message: Optional status message
        
    Returns:
        True if updated successfully
    """
    try:
        job = Job.fetch(job_id, connection=redis_conn)
        
        # Update job meta data
        job.meta["progress"] = progress
        if message:
            job.meta["message"] = message
        job.save_meta()
        
        logger.debug(f"Updated job {job_id} progress: {progress}%")
        return True
    except Exception as e:
        logger.error(f"Failed to update job progress: {e}")
        return False


def schedule_job(
    func_name: str,
    delay_seconds: int,
    queue_name: str = "default",
    **kwargs
) -> str:
    """
    Schedule a job to run after a delay
    
    Args:
        func_name: Function name to call
        delay_seconds: Delay in seconds
        queue_name: Queue priority
        **kwargs: Arguments for the function
        
    Returns:
        Job ID
    """
    try:
        from datetime import datetime, timedelta
        
        queue = QUEUES.get(queue_name, QUEUES["default"])
        
        # Map function names
        if func_name == "cleanup_old_runs":
            from ..worker.tasks import cleanup_old_runs
            job = queue.enqueue_at(
                datetime.utcnow() + timedelta(seconds=delay_seconds),
                cleanup_old_runs,
                **kwargs
            )
        else:
            raise ValueError(f"Unknown scheduled function: {func_name}")
        
        logger.info(f"⏰ Scheduled job {job.id} to run in {delay_seconds} seconds")
        return job.id
        
    except Exception as e:
        logger.error(f"Failed to schedule job: {e}")
        raise


def retry_failed_jobs(queue_name: str = "default") -> int:
    """
    Retry all failed jobs in a queue
    
    Args:
        queue_name: Queue name
        
    Returns:
        Number of jobs retried
    """
    try:
        queue = QUEUES.get(queue_name, QUEUES["default"])
        failed_registry = queue.failed_job_registry
        
        job_ids = failed_registry.get_job_ids()
        count = 0
        
        for job_id in job_ids:
            try:
                failed_registry.requeue(job_id)
                count += 1
            except Exception as e:
                logger.error(f"Failed to retry job {job_id}: {e}")
        
        logger.info(f"♻️ Retried {count} failed jobs in {queue_name} queue")
        return count
        
    except Exception as e:
        logger.error(f"Failed to retry failed jobs: {e}")
        return 0


def get_worker_stats() -> Dict[str, Any]:
    """
    Get worker statistics
    
    Returns:
        Worker stats dict
    """
    try:
        workers = Worker.all(connection=redis_conn)
        
        return {
            "total_workers": len(workers),
            "workers": [
                {
                    "name": w.name,
                    "queues": [q.name for q in w.queues],
                    "state": w.get_state(),
                    "current_job": w.get_current_job_id(),
                    "successful_job_count": w.successful_job_count,
                    "failed_job_count": w.failed_job_count,
                    "total_working_time": w.total_working_time
                }
                for w in workers
            ]
        }
    except Exception as e:
        logger.error(f"Failed to get worker stats: {e}")
        return {"total_workers": 0, "workers": []}


class JobProgress:
    """
    Context manager for tracking job progress
    Usage:
        with JobProgress(job_id) as progress:
            progress.update(10, "Starting...")
            # ... do work ...
            progress.update(50, "Processing...")
            # ... more work ...
            progress.update(100, "Complete!")
    """
    
    def __init__(self, job_id: str):
        self.job_id = job_id
        
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.update(100, "Complete")
        else:
            self.update(-1, f"Failed: {exc_val}")
    
    def update(self, percent: int, message: str = ""):
        """Update progress"""
        update_job_progress(self.job_id, percent, message)
