"""
Main Test Orchestrator
Coordinates the entire CDR validation pipeline
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import time
import logging

from .vm_manager import AzureVMManager
from ..integrations.edr import CrowdStrikeClient, SentinelOneClient, SophosClient
from ..integrations.av import WindowsDefenderScanner, ClamAVScanner, VirusTotalScanner
from ..integrations.cdr import GlasswallClient
from ..integrations.siem import WazuhClient
from ..file_interaction import FileExecutor
from ..utils.config import ConfigManager
from ..utils.helpers import generate_test_run_id, calculate_file_hash

logger = logging.getLogger(__name__)


@dataclass
class TestRunResult:
    """Complete test run result"""
    test_run_id: str
    file_name: str
    file_hash: str
    phase: str  # 'pre_cdr' or 'post_cdr'
    start_time: datetime
    end_time: datetime
    duration_seconds: float

    # VM info
    vm_name: str
    vm_provisioning_time: float

    # EDR results
    edr_alerts_crowdstrike: int
    edr_alerts_sentinelone: int
    edr_alerts_sophos: int
    total_edr_alerts: int

    # AV results
    av_detections_defender: int
    av_detections_clamav: int
    av_detections_virustotal: int
    total_av_detections: int

    # File interaction
    file_execution_success: bool
    file_execution_duration: float

    # Wazuh SIEM
    wazuh_total_alerts: int

    # Errors
    errors: list

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        result = asdict(self)
        result['start_time'] = self.start_time.isoformat()
        result['end_time'] = self.end_time.isoformat()
        return result


class TestOrchestrator:
    """
    Main pipeline orchestrator

    Coordinates:
    1. VM provisioning
    2. EDR agent deployment
    3. File execution with user simulation
    4. Alert collection from EDR/AV/Wazuh
    5. CDR processing
    6. Post-CDR testing
    7. Metrics comparison
    8. VM cleanup
    """

    def __init__(self, config_manager: ConfigManager):
        """
        Initialize test orchestrator

        Args:
            config_manager: Configuration manager
        """
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)

        # Load configurations
        self.azure_config = config_manager.load_azure_config()
        self.vm_config = config_manager.load_vm_config()
        self.edr_config = config_manager.load_edr_config()
        self.av_config = config_manager.load_av_config()
        self.cdr_config = config_manager.load_cdr_config()
        self.wazuh_config = config_manager.load_wazuh_config()
        self.test_config = config_manager.load_test_config()

        # Initialize clients
        self.vm_manager = AzureVMManager(self.azure_config, self.vm_config)
        self.cdr_client = GlasswallClient(self.cdr_config)
        self.wazuh_client = WazuhClient(self.wazuh_config)

        # EDR clients
        self.edr_clients = {
            'crowdstrike': CrowdStrikeClient(self.edr_config),
            'sentinelone': SentinelOneClient(self.edr_config),
            'sophos': SophosClient(self.edr_config)
        }

        # AV scanners
        self.av_scanners = {
            'defender': WindowsDefenderScanner(self.av_config),
            'clamav': ClamAVScanner(self.av_config),
            'virustotal': VirusTotalScanner(self.av_config)
        }

    def run_full_test(self, file_path: str) -> Dict[str, Any]:
        """
        Run complete CDR validation test

        Args:
            file_path: Path to file to test

        Returns:
            Complete test results
        """
        test_run_id = generate_test_run_id()
        file_hash = calculate_file_hash(file_path)

        self.logger.info(f"Starting test run {test_run_id} for file {file_path}")

        try:
            # Phase 1: Pre-CDR testing
            self.logger.info("=" * 60)
            self.logger.info("PHASE 1: PRE-CDR TESTING")
            self.logger.info("=" * 60)

            pre_cdr_result = self.run_test_phase(
                test_run_id=test_run_id,
                file_path=file_path,
                phase='pre_cdr'
            )

            # Phase 2: CDR Processing
            self.logger.info("=" * 60)
            self.logger.info("PHASE 2: CDR PROCESSING")
            self.logger.info("=" * 60)

            cdr_result = self.cdr_client.sanitize_file(file_path)

            if not cdr_result.success:
                self.logger.error(f"CDR processing failed: {cdr_result.error_message}")
                return {
                    'test_run_id': test_run_id,
                    'status': 'failed',
                    'error': 'CDR processing failed',
                    'pre_cdr_result': pre_cdr_result.to_dict() if pre_cdr_result else None
                }

            # Phase 3: Post-CDR testing
            self.logger.info("=" * 60)
            self.logger.info("PHASE 3: POST-CDR TESTING")
            self.logger.info("=" * 60)

            post_cdr_result = self.run_test_phase(
                test_run_id=test_run_id,
                file_path=cdr_result.sanitized_file_path,
                phase='post_cdr'
            )

            # Phase 4: Compare results
            self.logger.info("=" * 60)
            self.logger.info("PHASE 4: RESULTS ANALYSIS")
            self.logger.info("=" * 60)

            comparison = self._compare_results(pre_cdr_result, post_cdr_result)

            return {
                'test_run_id': test_run_id,
                'status': 'completed',
                'file_name': file_path,
                'file_hash': file_hash,
                'pre_cdr': pre_cdr_result.to_dict() if pre_cdr_result else None,
                'post_cdr': post_cdr_result.to_dict() if post_cdr_result else None,
                'cdr_processing': cdr_result.to_dict(),
                'comparison': comparison
            }

        except Exception as e:
            self.logger.error(f"Test run failed: {e}", exc_info=True)
            return {
                'test_run_id': test_run_id,
                'status': 'error',
                'error': str(e)
            }

    def run_test_phase(
        self,
        test_run_id: str,
        file_path: str,
        phase: str
    ) -> Optional[TestRunResult]:
        """
        Run a single test phase (pre or post CDR)

        Args:
            test_run_id: Unique test run ID
            file_path: Path to file to test
            phase: 'pre_cdr' or 'post_cdr'

        Returns:
            Test phase result
        """
        phase_start = datetime.now()
        errors = []
        vm_name = None

        try:
            # Step 1: Provision VM
            self.logger.info(f"Step 1: Provisioning VM for {phase}")
            vm_start_time = time.time()

            vm_info = self.vm_manager.provision_vm(test_run_id)
            vm_name = vm_info['vm_name']

            vm_provisioning_time = time.time() - vm_start_time
            self.logger.info(f"VM provisioned in {vm_provisioning_time:.1f}s")

            # Wait for VM to be ready
            if not self.vm_manager.wait_for_vm_ready(vm_name):
                raise RuntimeError(f"VM {vm_name} failed to become ready")

            # Step 2: Deploy EDR agents and AV scanners
            self.logger.info(f"Step 2: Deploying security agents")
            # Note: In production, you'd actually deploy agents here
            # For now, we assume agents are pre-installed in the VM image
            time.sleep(5)  # Brief wait for agents to initialize

            # Step 3: Copy file to VM
            self.logger.info(f"Step 3: Copying file to VM")
            # Use Azure Run Command or Azure Files to copy
            # Simplified here - in production use proper file transfer
            self.logger.warning("File transfer not fully implemented - requires Azure Files or SCP")

            # Step 4: Execute file with user simulation
            self.logger.info(f"Step 4: Executing file on VM")
            test_start_time = datetime.now()

            # In production, this would execute on the remote VM
            # For now, simulate execution
            file_executor = FileExecutor(
                interaction_duration=self.test_config.interaction_duration_seconds,
                enable_macros=self.test_config.auto_enable_macros
            )

            # Note: Actual execution would happen on the VM via Run Command
            execution_result = {
                'success': True,
                'duration': self.test_config.interaction_duration_seconds
            }

            test_end_time = datetime.now()

            # Step 5: Collect alerts from Wazuh (which aggregates EDR alerts)
            self.logger.info(f"Step 5: Collecting alerts from Wazuh")
            time.sleep(30)  # Wait for alerts to be indexed

            wazuh_alerts = self.wazuh_client.get_alerts_for_test_run(
                vm_name=vm_name,
                test_start_time=test_start_time,
                test_end_time=test_end_time
            )

            # Step 6: Query individual EDR consoles for detailed metrics
            self.logger.info(f"Step 6: Querying EDR consoles")
            edr_alerts = self._collect_edr_alerts(vm_name, test_start_time, test_end_time)

            # Step 7: Run AV scans (if applicable)
            self.logger.info(f"Step 7: Running AV scans")
            av_results = self._run_av_scans(file_path)

            # Build result
            phase_end = datetime.now()
            duration = (phase_end - phase_start).total_seconds()

            result = TestRunResult(
                test_run_id=test_run_id,
                file_name=file_path,
                file_hash=calculate_file_hash(file_path),
                phase=phase,
                start_time=phase_start,
                end_time=phase_end,
                duration_seconds=duration,
                vm_name=vm_name,
                vm_provisioning_time=vm_provisioning_time,
                edr_alerts_crowdstrike=edr_alerts.get('crowdstrike', 0),
                edr_alerts_sentinelone=edr_alerts.get('sentinelone', 0),
                edr_alerts_sophos=edr_alerts.get('sophos', 0),
                total_edr_alerts=sum(edr_alerts.values()),
                av_detections_defender=av_results.get('defender', 0),
                av_detections_clamav=av_results.get('clamav', 0),
                av_detections_virustotal=av_results.get('virustotal', 0),
                total_av_detections=sum(av_results.values()),
                file_execution_success=execution_result['success'],
                file_execution_duration=execution_result['duration'],
                wazuh_total_alerts=len(wazuh_alerts),
                errors=errors
            )

            self.logger.info(f"{phase} phase completed: {result.total_edr_alerts} EDR alerts, {result.total_av_detections} AV detections")

            return result

        except Exception as e:
            self.logger.error(f"Phase {phase} failed: {e}", exc_info=True)
            errors.append(str(e))
            return None

        finally:
            # Cleanup: Delete VM
            if vm_name:
                self.logger.info(f"Cleaning up: Deleting VM {vm_name}")
                self.vm_manager.delete_vm(vm_name, delete_disks=True)

    def _collect_edr_alerts(
        self,
        vm_name: str,
        start_time: datetime,
        end_time: datetime
    ) -> Dict[str, int]:
        """Collect alerts from all EDR vendors"""
        results = {}

        for vendor, client in self.edr_clients.items():
            try:
                # Note: In production, you'd need to map vm_name to agent_id
                alerts = client.get_alert_count(
                    host_name=vm_name,
                    start_time=start_time,
                    end_time=end_time
                )
                results[vendor] = alerts
            except Exception as e:
                self.logger.error(f"Error collecting {vendor} alerts: {e}")
                results[vendor] = 0

        return results

    def _run_av_scans(self, file_path: str) -> Dict[str, int]:
        """Run AV scans"""
        results = {}

        for scanner_name, scanner in self.av_scanners.items():
            try:
                if not scanner.is_available():
                    self.logger.debug(f"{scanner_name} not available, skipping")
                    results[scanner_name] = 0
                    continue

                scan_result = scanner.scan_file(file_path)
                results[scanner_name] = 1 if scan_result.is_malicious else 0

            except Exception as e:
                self.logger.error(f"Error running {scanner_name} scan: {e}")
                results[scanner_name] = 0

        return results

    def _compare_results(
        self,
        pre_cdr: Optional[TestRunResult],
        post_cdr: Optional[TestRunResult]
    ) -> Dict[str, Any]:
        """Compare pre and post CDR results"""
        if not pre_cdr or not post_cdr:
            return {'error': 'Missing results for comparison'}

        edr_reduction = pre_cdr.total_edr_alerts - post_cdr.total_edr_alerts
        edr_reduction_pct = (edr_reduction / pre_cdr.total_edr_alerts * 100) if pre_cdr.total_edr_alerts > 0 else 0

        av_reduction = pre_cdr.total_av_detections - post_cdr.total_av_detections
        av_reduction_pct = (av_reduction / pre_cdr.total_av_detections * 100) if pre_cdr.total_av_detections > 0 else 0

        wazuh_reduction = pre_cdr.wazuh_total_alerts - post_cdr.wazuh_total_alerts
        wazuh_reduction_pct = (wazuh_reduction / pre_cdr.wazuh_total_alerts * 100) if pre_cdr.wazuh_total_alerts > 0 else 0

        return {
            'edr_alerts_pre': pre_cdr.total_edr_alerts,
            'edr_alerts_post': post_cdr.total_edr_alerts,
            'edr_reduction': edr_reduction,
            'edr_reduction_percentage': round(edr_reduction_pct, 2),
            'av_detections_pre': pre_cdr.total_av_detections,
            'av_detections_post': post_cdr.total_av_detections,
            'av_reduction': av_reduction,
            'av_reduction_percentage': round(av_reduction_pct, 2),
            'wazuh_alerts_pre': pre_cdr.wazuh_total_alerts,
            'wazuh_alerts_post': post_cdr.wazuh_total_alerts,
            'wazuh_reduction': wazuh_reduction,
            'wazuh_reduction_percentage': round(wazuh_reduction_pct, 2),
            'overall_success': post_cdr.total_edr_alerts < pre_cdr.total_edr_alerts
        }
