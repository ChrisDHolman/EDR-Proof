"""
Phase 2: AV Scanning Tasks
Scan pre-CDR and post-CDR files through multiple AV engines
"""

from celery import Task, group, chord
from typing import List, Dict, Any
import logging
from datetime import datetime

from tasks.celery_app import celery_app
from tasks.job_manager import JobManager
from src.integrations.av.opswat_av import OPSWATAVClient
from src.integrations.av.reversinglabs import ReversingLabsClient
from src.utils.azure_storage import AzureBlobManager
from src.utils.config import ConfigManager

logger = logging.getLogger(__name__)

# Initialize clients
config_manager = ConfigManager()
blob_manager = AzureBlobManager()
job_manager = JobManager()

# AV engine clients
av_engines = {
    'opswat': OPSWATAVClient(config_manager),
    'reversinglabs': ReversingLabsClient(config_manager),
}


@celery_app.task(bind=True, name='tasks.phase2_av.scan_av_batch')
def scan_av_batch(self: Task, job_id: str) -> Dict[str, Any]:
    """
    Scan all pre-CDR and post-CDR files through AV engines

    Args:
        job_id: Job identifier

    Returns:
        Summary of AV scanning results
    """
    logger.info(f"[Job {job_id}] Starting Phase 2: AV Scanning")

    try:
        # Update job status
        job_manager.update_job(job_id, {
            'current_phase': 2,
            'phase2_started_at': datetime.now()
        })

        # Get job details to find all files
        job = job_manager.get_job(job_id)
        container_name = job.get('container_name')

        # Get phase 1 results to find all pre-CDR and post-CDR file pairs
        phase1_results = job_manager.get_phase_results(job_id, 'phase1')

        # Build list of files to scan
        # For each original file, scan pre-CDR and all post-CDR versions
        files_to_scan = []

        # Track unique original files
        original_files = set()
        for result in phase1_results:
            if result.get('status') == 'success':
                original_file = result.get('file_path')
                original_files.add(original_file)

        # For each original file, create scan tasks
        for original_file in original_files:
            # Scan pre-CDR version
            files_to_scan.append({
                'file_path': original_file,
                'version': 'pre-cdr',
                'cdr_engine': None
            })

            # Scan all post-CDR versions
            for result in phase1_results:
                if result.get('file_path') == original_file and result.get('status') == 'success':
                    files_to_scan.append({
                        'file_path': result.get('sanitized_blob_path'),
                        'version': 'post-cdr',
                        'cdr_engine': result.get('engine_name'),
                        'original_file': original_file
                    })

        total_scans = len(files_to_scan) * len(av_engines)
        logger.info(f"[Job {job_id}] Will perform {total_scans} AV scans ({len(files_to_scan)} files x {len(av_engines)} engines)")

        # Create scan tasks for each file x AV engine combination
        tasks = []
        for file_info in files_to_scan:
            for av_engine_name in av_engines.keys():
                tasks.append(
                    scan_single_file_av.s(
                        job_id=job_id,
                        container_name=container_name,
                        file_info=file_info,
                        av_engine_name=av_engine_name
                    )
                )

        # Execute all AV scans in parallel, then trigger Phase 3
        callback = on_av_batch_complete.s(job_id=job_id)
        workflow = chord(tasks)(callback)

        logger.info(f"[Job {job_id}] Dispatched {len(tasks)} AV scanning tasks")

        return {
            'job_id': job_id,
            'phase': 2,
            'total_scans': total_scans,
            'status': 'dispatched'
        }

    except Exception as e:
        logger.error(f"[Job {job_id}] Phase 2 failed: {e}", exc_info=True)
        job_manager.update_job(job_id, {
            'status': 'failed',
            'error': str(e)
        })
        raise


@celery_app.task(bind=True, name='tasks.phase2_av.scan_single_file_av')
def scan_single_file_av(
    self: Task,
    job_id: str,
    container_name: str,
    file_info: Dict[str, Any],
    av_engine_name: str
) -> Dict[str, Any]:
    """
    Scan a single file with a specific AV engine

    Args:
        job_id: Job identifier
        container_name: Azure Blob container name
        file_info: Dict with file_path, version (pre/post-cdr), cdr_engine
        av_engine_name: AV engine to use

    Returns:
        Scan result
    """
    file_path = file_info['file_path']
    version = file_info['version']

    logger.info(f"[Job {job_id}] Scanning {file_path} ({version}) with {av_engine_name}")

    result = {
        'job_id': job_id,
        'file_path': file_path,
        'version': version,
        'cdr_engine': file_info.get('cdr_engine'),
        'original_file': file_info.get('original_file'),
        'av_engine_name': av_engine_name,
        'status': 'pending',
        'start_time': datetime.now().isoformat()
    }

    try:
        # Download file from blob storage
        local_file_path = blob_manager.download_file(
            container_name=container_name,
            blob_path=file_path,
            download_to_temp=True
        )

        # Get AV engine client
        av_client = av_engines.get(av_engine_name)
        if not av_client:
            raise ValueError(f"Unknown AV engine: {av_engine_name}")

        # Scan file
        scan_result = av_client.scan_file(local_file_path)

        result.update({
            'status': 'success',
            'is_malicious': scan_result.is_malicious,
            'threat_name': scan_result.threat_name,
            'confidence': scan_result.confidence,
            'scan_time_ms': scan_result.scan_time_ms,
            'engine_version': scan_result.engine_version,
            'end_time': datetime.now().isoformat()
        })

        logger.info(
            f"[Job {job_id}] {file_path} ({version}) scanned by {av_engine_name}: "
            f"{'MALICIOUS' if scan_result.is_malicious else 'CLEAN'}"
        )

        # Store result
        job_manager.add_file_result(job_id, 'phase2', result)

        return result

    except Exception as e:
        logger.error(f"[Job {job_id}] Error scanning {file_path} with {av_engine_name}: {e}", exc_info=True)

        result.update({
            'status': 'error',
            'error': str(e),
            'end_time': datetime.now().isoformat()
        })

        job_manager.add_file_result(job_id, 'phase2', result)

        return result


@celery_app.task(name='tasks.phase2_av.on_av_batch_complete')
def on_av_batch_complete(results: List[Dict[str, Any]], job_id: str) -> None:
    """
    Callback after all AV scans complete
    Triggers Phase 3 (EDR testing) if enabled

    Args:
        results: List of results from all AV scans
        job_id: Job identifier
    """
    logger.info(f"[Job {job_id}] Phase 2 completed. Processing results...")

    try:
        # Analyze results
        total_scans = len(results)
        successful = sum(1 for r in results if r.get('status') == 'success')
        detections = sum(1 for r in results if r.get('is_malicious'))

        logger.info(
            f"[Job {job_id}] Phase 2 summary: {successful}/{total_scans} successful scans, "
            f"{detections} detections"
        )

        # Calculate detection rate comparison (pre vs post CDR)
        pre_cdr_detections = sum(
            1 for r in results
            if r.get('version') == 'pre-cdr' and r.get('is_malicious')
        )
        post_cdr_detections = sum(
            1 for r in results
            if r.get('version') == 'post-cdr' and r.get('is_malicious')
        )

        # Update job status
        job_manager.update_job(job_id, {
            'phase2_completed': True,
            'phase2_summary': {
                'total_scans': total_scans,
                'successful': successful,
                'pre_cdr_detections': pre_cdr_detections,
                'post_cdr_detections': post_cdr_detections,
                'detection_reduction': pre_cdr_detections - post_cdr_detections,
                'detection_reduction_pct': (
                    ((pre_cdr_detections - post_cdr_detections) / pre_cdr_detections * 100)
                    if pre_cdr_detections > 0 else 0
                )
            }
        })

        # Check if Phase 3 should be triggered
        job = job_manager.get_job(job_id)
        if job and 3 in job.get('phases', []):
            logger.info(f"[Job {job_id}] Triggering Phase 3: EDR Testing")
            from tasks.phase3_edr import test_edr_batch
            test_edr_batch.apply_async(args=[job_id], queue='phase3')
        else:
            logger.info(f"[Job {job_id}] Phase 3 not enabled, job complete")
            job_manager.update_job(job_id, {
                'status': 'completed',
                'completed_at': datetime.now()
            })

    except Exception as e:
        logger.error(f"[Job {job_id}] Error in AV completion callback: {e}", exc_info=True)
        job_manager.update_job(job_id, {
            'status': 'failed',
            'error': f"Phase 2 completion error: {str(e)}"
        })
