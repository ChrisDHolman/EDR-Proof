"""
Phase 3: EDR Testing Tasks
Execute pre-CDR and post-CDR files on VMs with EDR agents installed
Collect telemetry and compare detection rates
"""

from celery import Task, group, chord
from typing import List, Dict, Any
import logging
from datetime import datetime
import time

from tasks.celery_app import celery_app
from tasks.job_manager import JobManager
from tasks.vm_pool_manager import VMPoolManager
from src.integrations.edr.crowdstrike import CrowdStrikeClient
from src.integrations.edr.sentinelone import SentinelOneClient
from src.integrations.edr.sophos import SophosClient
from src.file_interaction.executor import FileExecutor
from src.utils.azure_storage import AzureBlobManager
from src.utils.config import ConfigManager

logger = logging.getLogger(__name__)

# Initialize clients
config_manager = ConfigManager()
blob_manager = AzureBlobManager()
job_manager = JobManager()
vm_pool_manager = VMPoolManager(config_manager)

# EDR clients for telemetry collection
edr_clients = {
    'crowdstrike': CrowdStrikeClient(config_manager),
    'sentinelone': SentinelOneClient(config_manager),
    'sophos': SophosClient(config_manager),
}

# File executor for user simulation
file_executor = FileExecutor(
    interaction_duration=300,  # 5 minutes
    enable_macros=True
)


@celery_app.task(bind=True, name='tasks.phase3_edr.test_edr_batch')
def test_edr_batch(self: Task, job_id: str) -> Dict[str, Any]:
    """
    Test all pre-CDR and post-CDR files on VMs with EDR agents

    This is the most complex and time-consuming phase:
    - For each file, we need to execute it on a VM with each EDR agent
    - Monitor telemetry from EDR consoles
    - Compare pre-CDR vs post-CDR detections

    Args:
        job_id: Job identifier

    Returns:
        Summary of EDR testing results
    """
    logger.info(f"[Job {job_id}] Starting Phase 3: EDR Testing")

    try:
        # Update job status
        job_manager.update_job(job_id, {
            'current_phase': 3,
            'phase3_started_at': datetime.now()
        })

        # Get job details
        job = job_manager.get_job(job_id)
        container_name = job.get('container_name')

        # Get phase 1 results to find all file pairs
        phase1_results = job_manager.get_phase_results(job_id, 'phase1')

        # Build list of files to test
        files_to_test = []

        # Track unique original files
        original_files = set()
        for result in phase1_results:
            if result.get('status') == 'success':
                original_file = result.get('file_path')
                original_files.add(original_file)

        # For each original file, create test tasks
        for original_file in original_files:
            # Test pre-CDR version
            files_to_test.append({
                'file_path': original_file,
                'version': 'pre-cdr',
                'cdr_engine': None
            })

            # Test all post-CDR versions
            for result in phase1_results:
                if result.get('file_path') == original_file and result.get('status') == 'success':
                    files_to_test.append({
                        'file_path': result.get('sanitized_blob_path'),
                        'version': 'post-cdr',
                        'cdr_engine': result.get('engine_name'),
                        'original_file': original_file
                    })

        total_tests = len(files_to_test) * len(edr_clients)
        logger.info(
            f"[Job {job_id}] Will perform {total_tests} EDR tests "
            f"({len(files_to_test)} files x {len(edr_clients)} EDR solutions)"
        )

        # Create test tasks for each file x EDR solution combination
        tasks = []
        for file_info in files_to_test:
            for edr_solution_name in edr_clients.keys():
                tasks.append(
                    test_single_file_edr.s(
                        job_id=job_id,
                        container_name=container_name,
                        file_info=file_info,
                        edr_solution_name=edr_solution_name
                    )
                )

        # Execute all EDR tests (limited by VM pool availability)
        callback = on_edr_batch_complete.s(job_id=job_id)
        workflow = chord(tasks)(callback)

        logger.info(f"[Job {job_id}] Dispatched {len(tasks)} EDR testing tasks")

        return {
            'job_id': job_id,
            'phase': 3,
            'total_tests': total_tests,
            'status': 'dispatched'
        }

    except Exception as e:
        logger.error(f"[Job {job_id}] Phase 3 failed: {e}", exc_info=True)
        job_manager.update_job(job_id, {
            'status': 'failed',
            'error': str(e)
        })
        raise


@celery_app.task(bind=True, name='tasks.phase3_edr.test_single_file_edr', max_retries=3)
def test_single_file_edr(
    self: Task,
    job_id: str,
    container_name: str,
    file_info: Dict[str, Any],
    edr_solution_name: str
) -> Dict[str, Any]:
    """
    Test a single file on a VM with specific EDR agent installed

    This task:
    1. Acquires a VM from the pool (waits if none available)
    2. Copies file to VM
    3. Executes file with user simulation
    4. Collects telemetry from EDR console
    5. Returns VM to pool (or destroys if contaminated)

    Args:
        job_id: Job identifier
        container_name: Azure Blob container name
        file_info: Dict with file_path, version, cdr_engine
        edr_solution_name: EDR solution to test with

    Returns:
        Test result with telemetry data
    """
    file_path = file_info['file_path']
    version = file_info['version']

    logger.info(f"[Job {job_id}] Testing {file_path} ({version}) with {edr_solution_name}")

    result = {
        'job_id': job_id,
        'file_path': file_path,
        'version': version,
        'cdr_engine': file_info.get('cdr_engine'),
        'original_file': file_info.get('original_file'),
        'edr_solution_name': edr_solution_name,
        'status': 'pending',
        'start_time': datetime.now().isoformat()
    }

    vm = None

    try:
        # Step 1: Acquire VM from pool (blocks until available)
        logger.info(f"[Job {job_id}] Waiting for {edr_solution_name} VM from pool...")
        vm = vm_pool_manager.acquire_vm(edr_solution_name)
        logger.info(f"[Job {job_id}] Acquired VM: {vm['vm_name']}")

        result['vm_name'] = vm['vm_name']
        result['vm_acquired_at'] = datetime.now().isoformat()

        # Step 2: Download file from blob storage
        local_file_path = blob_manager.download_file(
            container_name=container_name,
            blob_path=file_path,
            download_to_temp=True
        )

        # Step 3: Copy file to VM
        logger.info(f"[Job {job_id}] Copying file to VM {vm['vm_name']}")
        remote_file_path = vm_pool_manager.copy_file_to_vm(
            vm=vm,
            local_file_path=local_file_path
        )

        # Step 4: Execute file on VM with user simulation
        logger.info(f"[Job {job_id}] Executing file on VM {vm['vm_name']}")
        execution_start = datetime.now()

        execution_result = vm_pool_manager.execute_file_on_vm(
            vm=vm,
            remote_file_path=remote_file_path,
            duration_seconds=300  # 5 minute interaction
        )

        execution_end = datetime.now()

        result['execution_started_at'] = execution_start.isoformat()
        result['execution_ended_at'] = execution_end.isoformat()
        result['execution_success'] = execution_result.get('success', False)

        # Step 5: Wait for telemetry to reach EDR console
        logger.info(f"[Job {job_id}] Waiting 60s for telemetry to propagate...")
        time.sleep(60)

        # Step 6: Collect telemetry from EDR console
        logger.info(f"[Job {job_id}] Collecting telemetry from {edr_solution_name}")
        edr_client = edr_clients.get(edr_solution_name)

        # Query EDR console for alerts related to this VM during execution window
        alerts = edr_client.get_alerts(
            host_name=vm['vm_name'],
            start_time=execution_start,
            end_time=execution_end + timedelta(seconds=60)
        )

        # Analyze alerts
        alert_count = len(alerts)
        high_severity_alerts = sum(1 for a in alerts if a.get('severity') == 'high')
        threat_types = list(set(a.get('threat_type') for a in alerts if a.get('threat_type')))

        result.update({
            'status': 'success',
            'alert_count': alert_count,
            'high_severity_alerts': high_severity_alerts,
            'threat_types': threat_types,
            'alerts': alerts[:10],  # Store first 10 alerts for analysis
            'edr_detected': alert_count > 0,
            'end_time': datetime.now().isoformat()
        })

        logger.info(
            f"[Job {job_id}] {file_path} ({version}) tested with {edr_solution_name}: "
            f"{alert_count} alerts, {high_severity_alerts} high severity"
        )

        # Store result
        job_manager.add_file_result(job_id, 'phase3', result)

        return result

    except Exception as e:
        logger.error(f"[Job {job_id}] Error testing {file_path} with {edr_solution_name}: {e}", exc_info=True)

        result.update({
            'status': 'error',
            'error': str(e),
            'end_time': datetime.now().isoformat()
        })

        job_manager.add_file_result(job_id, 'phase3', result)

        # Retry if within retry limit
        if self.request.retries < self.max_retries:
            logger.info(f"[Job {job_id}] Retrying task (attempt {self.request.retries + 1}/{self.max_retries})")
            raise self.retry(exc=e, countdown=60)  # Retry after 60 seconds

        return result

    finally:
        # Step 7: Always return VM to pool (or destroy if needed)
        if vm:
            try:
                logger.info(f"[Job {job_id}] Cleaning and returning VM {vm['vm_name']} to pool")
                vm_pool_manager.release_vm(vm, clean=True)
            except Exception as cleanup_error:
                logger.error(f"[Job {job_id}] Error releasing VM: {cleanup_error}")


@celery_app.task(name='tasks.phase3_edr.on_edr_batch_complete')
def on_edr_batch_complete(results: List[Dict[str, Any]], job_id: str) -> None:
    """
    Callback after all EDR tests complete
    Analyzes results and marks job as complete

    Args:
        results: List of results from all EDR tests
        job_id: Job identifier
    """
    logger.info(f"[Job {job_id}] Phase 3 completed. Processing results...")

    try:
        # Analyze results
        total_tests = len(results)
        successful = sum(1 for r in results if r.get('status') == 'success')
        detections = sum(1 for r in results if r.get('edr_detected'))

        # Calculate detection rate comparison (pre vs post CDR)
        pre_cdr_detections = sum(
            1 for r in results
            if r.get('version') == 'pre-cdr' and r.get('edr_detected')
        )
        post_cdr_detections = sum(
            1 for r in results
            if r.get('version') == 'post-cdr' and r.get('edr_detected')
        )

        pre_cdr_total_alerts = sum(
            r.get('alert_count', 0) for r in results
            if r.get('version') == 'pre-cdr'
        )
        post_cdr_total_alerts = sum(
            r.get('alert_count', 0) for r in results
            if r.get('version') == 'post-cdr'
        )

        logger.info(
            f"[Job {job_id}] Phase 3 summary: {successful}/{total_tests} successful tests, "
            f"Pre-CDR: {pre_cdr_detections} detections ({pre_cdr_total_alerts} alerts), "
            f"Post-CDR: {post_cdr_detections} detections ({post_cdr_total_alerts} alerts)"
        )

        # Calculate ROI metrics
        alert_reduction = pre_cdr_total_alerts - post_cdr_total_alerts
        alert_reduction_pct = (
            (alert_reduction / pre_cdr_total_alerts * 100)
            if pre_cdr_total_alerts > 0 else 0
        )

        # Update job with final results
        job_manager.update_job(job_id, {
            'status': 'completed',
            'completed_at': datetime.now(),
            'phase3_completed': True,
            'phase3_summary': {
                'total_tests': total_tests,
                'successful': successful,
                'pre_cdr_detections': pre_cdr_detections,
                'post_cdr_detections': post_cdr_detections,
                'pre_cdr_total_alerts': pre_cdr_total_alerts,
                'post_cdr_total_alerts': post_cdr_total_alerts,
                'alert_reduction': alert_reduction,
                'alert_reduction_percentage': round(alert_reduction_pct, 2),
                'edr_effectiveness': {
                    'crowdstrike': calculate_edr_effectiveness(results, 'crowdstrike'),
                    'sentinelone': calculate_edr_effectiveness(results, 'sentinelone'),
                    'sophos': calculate_edr_effectiveness(results, 'sophos'),
                }
            }
        })

        logger.info(f"[Job {job_id}] All phases completed! Alert reduction: {alert_reduction_pct:.1f}%")

    except Exception as e:
        logger.error(f"[Job {job_id}] Error in EDR completion callback: {e}", exc_info=True)
        job_manager.update_job(job_id, {
            'status': 'failed',
            'error': f"Phase 3 completion error: {str(e)}"
        })


def calculate_edr_effectiveness(results: List[Dict[str, Any]], edr_solution: str) -> Dict[str, Any]:
    """Calculate effectiveness metrics for a specific EDR solution"""
    edr_results = [r for r in results if r.get('edr_solution_name') == edr_solution]

    pre_cdr = [r for r in edr_results if r.get('version') == 'pre-cdr']
    post_cdr = [r for r in edr_results if r.get('version') == 'post-cdr']

    pre_alerts = sum(r.get('alert_count', 0) for r in pre_cdr)
    post_alerts = sum(r.get('alert_count', 0) for r in post_cdr)

    return {
        'tests_performed': len(edr_results),
        'pre_cdr_alerts': pre_alerts,
        'post_cdr_alerts': post_alerts,
        'alert_reduction': pre_alerts - post_alerts,
        'alert_reduction_pct': (
            ((pre_alerts - post_alerts) / pre_alerts * 100)
            if pre_alerts > 0 else 0
        )
    }
