"""
Job Manager for tracking job state and results
Uses Redis for job state storage (fast, shared across workers)
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import redis
import os

logger = logging.getLogger(__name__)


class JobManager:
    """
    Manages job state and results using Redis

    Job structure in Redis:
    - job:{job_id} -> job metadata (hash)
    - job:{job_id}:phase1 -> phase 1 results (list)
    - job:{job_id}:phase2 -> phase 2 results (list)
    - job:{job_id}:phase3 -> phase 3 results (list)
    - jobs:list -> ordered list of job IDs (for listing)
    """

    def __init__(self):
        """Initialize job manager with Redis connection"""
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        self.redis_client = redis.from_url(redis_url, decode_responses=True)
        logger.info(f"JobManager initialized with Redis at {redis_url}")

    def create_job(
        self,
        job_id: str,
        container_name: str,
        file_paths: Optional[List[str]],
        phases: List[int],
        priority: str
    ):
        """
        Create a new job

        Args:
            job_id: Unique job identifier
            container_name: Azure Blob container name
            file_paths: List of file paths to process
            phases: List of phases to run [1, 2, 3]
            priority: Job priority (low, normal, high)
        """
        job_data = {
            'job_id': job_id,
            'container_name': container_name,
            'phases': json.dumps(phases),
            'priority': priority,
            'status': 'pending',
            'created_at': datetime.now().isoformat(),
            'total_files': 0,
            'processed_files': 0,
            'failed_files': 0,
            'current_phase': None,
            'progress_percentage': 0.0
        }

        # Store job metadata
        self.redis_client.hset(f"job:{job_id}", mapping=job_data)

        # Add to jobs list (for listing)
        self.redis_client.lpush('jobs:list', job_id)

        # Set expiry (keep for 7 days)
        self.redis_client.expire(f"job:{job_id}", 604800)

        logger.info(f"Created job {job_id}")

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get job metadata

        Args:
            job_id: Job identifier

        Returns:
            Job data dict or None if not found
        """
        job_data = self.redis_client.hgetall(f"job:{job_id}")

        if not job_data:
            return None

        # Parse JSON fields
        if 'phases' in job_data:
            job_data['phases'] = json.loads(job_data['phases'])

        # Convert numeric fields
        for field in ['total_files', 'processed_files', 'failed_files']:
            if field in job_data:
                job_data[field] = int(job_data[field])

        if 'progress_percentage' in job_data:
            job_data['progress_percentage'] = float(job_data['progress_percentage'])

        return job_data

    def update_job(self, job_id: str, updates: Dict[str, Any]):
        """
        Update job metadata

        Args:
            job_id: Job identifier
            updates: Dict of fields to update
        """
        # Serialize datetime objects
        for key, value in updates.items():
            if isinstance(value, datetime):
                updates[key] = value.isoformat()
            elif isinstance(value, (list, dict)):
                updates[key] = json.dumps(value)

        self.redis_client.hset(f"job:{job_id}", mapping=updates)

        # Update progress percentage
        job = self.get_job(job_id)
        if job and job['total_files'] > 0:
            progress = (job['processed_files'] / job['total_files']) * 100
            self.redis_client.hset(f"job:{job_id}", 'progress_percentage', progress)

    def list_jobs(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        List recent jobs

        Args:
            limit: Max number of jobs to return

        Returns:
            List of job data dicts
        """
        job_ids = self.redis_client.lrange('jobs:list', 0, limit - 1)

        jobs = []
        for job_id in job_ids:
            job = self.get_job(job_id)
            if job:
                jobs.append(job)

        return jobs

    def add_file_result(self, job_id: str, phase: str, result: Dict[str, Any]):
        """
        Add a file result to a phase

        Args:
            job_id: Job identifier
            phase: Phase name (phase1, phase2, phase3)
            result: Result dict
        """
        result_json = json.dumps(result)
        self.redis_client.rpush(f"job:{job_id}:{phase}", result_json)

    def get_phase_results(self, job_id: str, phase: str) -> List[Dict[str, Any]]:
        """
        Get all results for a phase

        Args:
            job_id: Job identifier
            phase: Phase name (phase1, phase2, phase3)

        Returns:
            List of result dicts
        """
        results_json = self.redis_client.lrange(f"job:{job_id}:{phase}", 0, -1)

        results = []
        for result_json in results_json:
            try:
                results.append(json.loads(result_json))
            except json.JSONDecodeError:
                logger.error(f"Failed to parse result JSON: {result_json}")

        return results

    def get_job_results(self, job_id: str) -> Dict[str, Any]:
        """
        Get complete job results (all phases)

        Args:
            job_id: Job identifier

        Returns:
            Dict with job metadata and all phase results
        """
        job = self.get_job(job_id)

        if not job:
            return None

        return {
            'job': job,
            'phase1_results': self.get_phase_results(job_id, 'phase1'),
            'phase2_results': self.get_phase_results(job_id, 'phase2'),
            'phase3_results': self.get_phase_results(job_id, 'phase3'),
        }

    def increment_processed(self, job_id: str):
        """Increment processed files counter"""
        self.redis_client.hincrby(f"job:{job_id}", 'processed_files', 1)

        # Update progress
        job = self.get_job(job_id)
        if job and job['total_files'] > 0:
            progress = (job['processed_files'] / job['total_files']) * 100
            self.redis_client.hset(f"job:{job_id}", 'progress_percentage', progress)

    def increment_failed(self, job_id: str):
        """Increment failed files counter"""
        self.redis_client.hincrby(f"job:{job_id}", 'failed_files', 1)
        self.increment_processed(job_id)  # Also count as processed

    def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a job

        Args:
            job_id: Job identifier

        Returns:
            True if cancelled, False if job not found
        """
        job = self.get_job(job_id)

        if not job:
            return False

        if job['status'] in ['completed', 'failed', 'cancelled']:
            return False

        self.update_job(job_id, {
            'status': 'cancelled',
            'cancelled_at': datetime.now()
        })

        logger.info(f"Cancelled job {job_id}")
        return True

    def delete_job(self, job_id: str):
        """
        Delete a job and all its data

        Args:
            job_id: Job identifier
        """
        # Delete job metadata
        self.redis_client.delete(f"job:{job_id}")

        # Delete phase results
        self.redis_client.delete(f"job:{job_id}:phase1")
        self.redis_client.delete(f"job:{job_id}:phase2")
        self.redis_client.delete(f"job:{job_id}:phase3")

        # Remove from jobs list
        self.redis_client.lrem('jobs:list', 0, job_id)

        logger.info(f"Deleted job {job_id}")

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get overall statistics

        Returns:
            Statistics dict
        """
        all_jobs = self.list_jobs(limit=1000)

        total_jobs = len(all_jobs)
        completed = sum(1 for j in all_jobs if j['status'] == 'completed')
        running = sum(1 for j in all_jobs if j['status'] == 'running')
        failed = sum(1 for j in all_jobs if j['status'] == 'failed')
        pending = sum(1 for j in all_jobs if j['status'] == 'pending')

        total_files = sum(j['total_files'] for j in all_jobs)
        processed_files = sum(j['processed_files'] for j in all_jobs)

        return {
            'total_jobs': total_jobs,
            'completed_jobs': completed,
            'running_jobs': running,
            'failed_jobs': failed,
            'pending_jobs': pending,
            'total_files': total_files,
            'processed_files': processed_files
        }
