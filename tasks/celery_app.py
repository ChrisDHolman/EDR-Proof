"""
Celery application configuration
"""

from celery import Celery
from kombu import Queue, Exchange
import os

# Get Redis connection from environment or use default
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# Create Celery app
celery_app = Celery(
    'edr_proof',
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        'tasks.phase1_cdr',
        'tasks.phase2_av',
        'tasks.phase3_edr'
    ]
)

# Configure Celery
celery_app.conf.update(
    # Task execution
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,

    # Task routing - separate queues for each phase
    task_routes={
        'tasks.phase1_cdr.*': {'queue': 'phase1'},
        'tasks.phase2_av.*': {'queue': 'phase2'},
        'tasks.phase3_edr.*': {'queue': 'phase3'},
    },

    # Priority support
    task_queue_max_priority=10,
    task_default_priority=5,

    # Worker configuration
    worker_prefetch_multiplier=1,  # One task at a time for long-running tasks
    worker_max_tasks_per_child=50,  # Restart worker after 50 tasks to prevent memory leaks

    # Task time limits
    task_soft_time_limit=3600,  # 1 hour soft limit
    task_time_limit=7200,  # 2 hour hard limit

    # Result backend
    result_expires=86400,  # Keep results for 24 hours
    result_extended=True,

    # Retry configuration
    task_acks_late=True,  # Acknowledge after task completes
    task_reject_on_worker_lost=True,
)

# Define queues with priority support
celery_app.conf.task_queues = (
    Queue('phase1', Exchange('phase1'), routing_key='phase1',
          queue_arguments={'x-max-priority': 10}),
    Queue('phase2', Exchange('phase2'), routing_key='phase2',
          queue_arguments={'x-max-priority': 10}),
    Queue('phase3', Exchange('phase3'), routing_key='phase3',
          queue_arguments={'x-max-priority': 10}),
)

if __name__ == '__main__':
    celery_app.start()
