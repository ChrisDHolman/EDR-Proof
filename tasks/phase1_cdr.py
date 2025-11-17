"""
Phase 1: CDR Processing Tasks
Process files through multiple CDR engines
"""

from celery import Task, group, chord
from typing import List, Optional, Dict, Any
import logging
from datetime import datetime

from tasks.celery_app import celery_app
from tasks.job_manager import JobManager
from src.integrations.cdr.glasswall import GlasswallClient
from src.integrations.cdr.opswat import OPSWATCDRClient
from src.integrations.cdr.votiro import VotiroClient
from src.utils.azure_storage import AzureBlobManager
from src.utils.config import ConfigManager

logger = logging.getLogger(__name__)

# Initialize clients (will be configured via environment variables)
config_manager = ConfigManager()
blob_manager = AzureBlobManager()
job_manager = JobManager()

# CDR engine clients
cdr_engines = {
    'glasswall': GlasswallClient(config_manager),
    'opswat': OPSWATCDRClient(config_manager),
    'votiro': VotiroClient(config_manager),
}


@celery_app.task(bind=True, name='tasks.phase1_cdr.process_cdr_batch')
def process_cdr_batch(
    self: Task,
    job_id: str,
    container_name: str,
    file_paths: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Process a batch of files through all CDR engines

    Args:
        job_id: Unique job identifier
        container_name: Azure Blob container name
        file_paths: List of file paths to process, or None for all files

    Returns:
        Summary of CDR processing results
    """
    logger.info(f"[Job {job_id}] Starting Phase 1: CDR Processing")

    try:
        # Update job status
        job_manager.update_job(job_id, {
            'status': 'running',
            'current_phase': 1,
            'started_at': datetime.now()
        })

        # Get list of files to process
        if file_paths is None:
            logger.info(f"[Job {job_id}] Listing all files in container {container_name}")
            file_paths = blob_manager.list_files(container_name)

        total_files = len(file_paths)
        logger.info(f"[Job {job_id}] Found {total_files} files to process")

        job_manager.update_job(job_id, {'total_files': total_files})

        # Create individual tasks for each file x CDR engine combination
        # Use Celery's group to run tasks in parallel
        tasks = []
        for file_path in file_paths:
            for engine_name in cdr_engines.keys():
                tasks.append(
                    process_single_file_cdr.s(
                        job_id=job_id,
                        container_name=container_name,
                        file_path=file_path,
                        engine_name=engine_name
                    )
                )

        # Execute all CDR tasks in parallel, then trigger Phase 2
        callback = on_cdr_batch_complete.s(job_id=job_id)
        workflow = chord(tasks)(callback)

        logger.info(f"[Job {job_id}] Dispatched {len(tasks)} CDR processing tasks")

        return {
            'job_id': job_id,
            'phase': 1,
            'total_files': total_files,
            'total_tasks': len(tasks),
            'status': 'dispatched'
        }

    except Exception as e:
        logger.error(f"[Job {job_id}] Phase 1 failed: {e}", exc_info=True)
        job_manager.update_job(job_id, {
            'status': 'failed',
            'error': str(e)
        })
        raise


@celery_app.task(bind=True, name='tasks.phase1_cdr.process_single_file_cdr')
def process_single_file_cdr(
    self: Task,
    job_id: str,
    container_name: str,
    file_path: str,
    engine_name: str
) -> Dict[str, Any]:
    """
    Process a single file through a specific CDR engine

    Args:
        job_id: Job identifier
        container_name: Azure Blob container name
        file_path: Path to file in blob storage
        engine_name: CDR engine to use (glasswall, opswat, votiro)

    Returns:
        Processing result
    """
    logger.info(f"[Job {job_id}] Processing {file_path} with {engine_name}")

    result = {
        'job_id': job_id,
        'file_path': file_path,
        'engine_name': engine_name,
        'status': 'pending',
        'start_time': datetime.now().isoformat()
    }

    try:
        # Download file from blob storage to temp location
        local_file_path = blob_manager.download_file(
            container_name=container_name,
            blob_path=file_path,
            download_to_temp=True
        )

        # Get CDR engine client
        cdr_client = cdr_engines.get(engine_name)
        if not cdr_client:
            raise ValueError(f"Unknown CDR engine: {engine_name}")

        # Process file through CDR engine
        cdr_result = cdr_client.sanitize_file(local_file_path)

        if cdr_result.success:
            # Upload sanitized file back to blob storage
            # Structure: post-cdr/{engine_name}/{original_path}
            sanitized_blob_path = f"post-cdr/{engine_name}/{file_path}"

            blob_manager.upload_file(
                container_name=container_name,
                local_file_path=cdr_result.sanitized_file_path,
                blob_path=sanitized_blob_path
            )

            result.update({
                'status': 'success',
                'sanitized_blob_path': sanitized_blob_path,
                'processing_time_ms': cdr_result.processing_time_ms,
                'file_size_before': cdr_result.original_size,
                'file_size_after': cdr_result.sanitized_size,
                'threats_found': cdr_result.threats_found,
                'end_time': datetime.now().isoformat()
            })

            logger.info(f"[Job {job_id}] Successfully processed {file_path} with {engine_name}")

        else:
            result.update({
                'status': 'failed',
                'error': cdr_result.error_message,
                'end_time': datetime.now().isoformat()
            })
            logger.error(f"[Job {job_id}] CDR failed for {file_path} with {engine_name}: {cdr_result.error_message}")

        # Store result in job manager
        job_manager.add_file_result(job_id, 'phase1', result)

        # Update progress
        job_manager.increment_processed(job_id)

        return result

    except Exception as e:
        logger.error(f"[Job {job_id}] Error processing {file_path} with {engine_name}: {e}", exc_info=True)

        result.update({
            'status': 'error',
            'error': str(e),
            'end_time': datetime.now().isoformat()
        })

        job_manager.add_file_result(job_id, 'phase1', result)
        job_manager.increment_failed(job_id)

        # Don't raise - we want to continue processing other files
        return result


@celery_app.task(name='tasks.phase1_cdr.on_cdr_batch_complete')
def on_cdr_batch_complete(results: List[Dict[str, Any]], job_id: str) -> None:
    """
    Callback after all CDR tasks complete
    Triggers Phase 2 (AV scanning) if enabled

    Args:
        results: List of results from all CDR tasks
        job_id: Job identifier
    """
    logger.info(f"[Job {job_id}] Phase 1 completed. Processing results...")

    try:
        # Analyze results
        total_tasks = len(results)
        successful = sum(1 for r in results if r.get('status') == 'success')
        failed = sum(1 for r in results if r.get('status') in ['failed', 'error'])

        logger.info(f"[Job {job_id}] Phase 1 summary: {successful}/{total_tasks} successful, {failed} failed")

        # Update job status
        job_manager.update_job(job_id, {
            'phase1_completed': True,
            'phase1_summary': {
                'total_tasks': total_tasks,
                'successful': successful,
                'failed': failed
            }
        })

        # Check if Phase 2 should be triggered
        job = job_manager.get_job(job_id)
        if job and 2 in job.get('phases', []):
            logger.info(f"[Job {job_id}] Triggering Phase 2: AV Scanning")
            from tasks.phase2_av import scan_av_batch
            scan_av_batch.apply_async(args=[job_id], queue='phase2')
        else:
            logger.info(f"[Job {job_id}] Phase 2 not enabled, job complete")
            job_manager.update_job(job_id, {
                'status': 'completed',
                'completed_at': datetime.now()
            })

    except Exception as e:
        logger.error(f"[Job {job_id}] Error in CDR completion callback: {e}", exc_info=True)
        job_manager.update_job(job_id, {
            'status': 'failed',
            'error': f"Phase 1 completion error: {str(e)}"
        })
