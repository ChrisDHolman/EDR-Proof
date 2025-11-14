"""
Windows Defender AV Scanner Integration
Uses PowerShell cmdlets for scanning
"""

import subprocess
import json
import time
from datetime import datetime
from typing import Optional, Dict, Any
import logging
import os
import platform

from .base import AVScanner, AVScanResult
from ...utils.config import AVConfig
from ...utils.helpers import calculate_file_hash

logger = logging.getLogger(__name__)


class WindowsDefenderScanner(AVScanner):
    """Windows Defender antivirus scanner"""

    def __init__(self, config: AVConfig):
        """
        Initialize Windows Defender scanner

        Args:
            config: AV configuration
        """
        super().__init__(config)
        self.scanner_name = "Windows Defender"
        self.enabled = config.defender_enabled

    def scan_file(self, file_path: str) -> AVScanResult:
        """
        Scan file with Windows Defender

        Args:
            file_path: Path to file

        Returns:
            Scan result
        """
        if not self.is_available():
            raise RuntimeError("Windows Defender is not available on this system")

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        start_time = time.time()
        scan_time = datetime.now()
        file_hash = calculate_file_hash(file_path)

        try:
            # Use PowerShell to invoke Defender scan
            # Start-MpScan -ScanPath "path" -ScanType CustomScan
            ps_command = f'Start-MpScan -ScanPath "{file_path}" -ScanType CustomScan'

            result = subprocess.run(
                ['powershell', '-Command', ps_command],
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            scan_duration = time.time() - start_time

            # Check if scan found threats
            # Defender returns non-zero exit code if threats found
            is_malicious = result.returncode != 0

            threat_name = None
            if is_malicious:
                # Get threat details using Get-MpThreatDetection
                threat_cmd = 'Get-MpThreatDetection | ConvertTo-Json'
                threat_result = subprocess.run(
                    ['powershell', '-Command', threat_cmd],
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                if threat_result.returncode == 0 and threat_result.stdout:
                    try:
                        threats = json.loads(threat_result.stdout)
                        if isinstance(threats, list) and threats:
                            threat_name = threats[0].get('ThreatName', 'Unknown threat')
                        elif isinstance(threats, dict):
                            threat_name = threats.get('ThreatName', 'Unknown threat')
                    except json.JSONDecodeError:
                        threat_name = "Threat detected (name unavailable)"

            return AVScanResult(
                scanner_name=self.scanner_name,
                file_path=file_path,
                file_hash=file_hash,
                scan_time=scan_time,
                is_malicious=is_malicious,
                threat_name=threat_name,
                threat_type='malware' if is_malicious else None,
                confidence=1.0 if is_malicious else 0.0,
                scan_duration_seconds=scan_duration,
                raw_result={
                    'stdout': result.stdout,
                    'stderr': result.stderr,
                    'returncode': result.returncode
                }
            )

        except subprocess.TimeoutExpired:
            scan_duration = time.time() - start_time
            self.logger.error(f"Defender scan timed out for {file_path}")
            return AVScanResult(
                scanner_name=self.scanner_name,
                file_path=file_path,
                file_hash=file_hash,
                scan_time=scan_time,
                is_malicious=False,
                scan_duration_seconds=scan_duration,
                raw_result={'error': 'scan_timeout'}
            )

        except Exception as e:
            scan_duration = time.time() - start_time
            self.logger.error(f"Error scanning with Defender: {e}")
            return AVScanResult(
                scanner_name=self.scanner_name,
                file_path=file_path,
                file_hash=file_hash,
                scan_time=scan_time,
                is_malicious=False,
                scan_duration_seconds=scan_duration,
                raw_result={'error': str(e)}
            )

    def is_available(self) -> bool:
        """
        Check if Windows Defender is available

        Returns:
            True if Defender is available
        """
        if not self.enabled:
            return False

        # Check if running on Windows
        if platform.system() != 'Windows':
            return False

        try:
            # Try to get Defender status
            result = subprocess.run(
                ['powershell', '-Command', 'Get-MpComputerStatus'],
                capture_output=True,
                timeout=10
            )
            return result.returncode == 0

        except Exception as e:
            self.logger.debug(f"Defender availability check failed: {e}")
            return False

    def get_version(self) -> Optional[str]:
        """
        Get Windows Defender version

        Returns:
            Version string
        """
        try:
            result = subprocess.run(
                ['powershell', '-Command',
                 '(Get-MpComputerStatus).AMProductVersion'],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                return result.stdout.strip()

        except Exception as e:
            self.logger.debug(f"Failed to get Defender version: {e}")

        return None

    def update_signatures(self) -> bool:
        """
        Update Defender virus signatures

        Returns:
            True if update successful
        """
        try:
            result = subprocess.run(
                ['powershell', '-Command', 'Update-MpSignature'],
                capture_output=True,
                timeout=300
            )
            return result.returncode == 0

        except Exception as e:
            self.logger.error(f"Failed to update Defender signatures: {e}")
            return False
