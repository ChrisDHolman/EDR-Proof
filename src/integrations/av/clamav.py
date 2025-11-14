"""
ClamAV Scanner Integration
Uses ClamAV command-line interface
"""

import subprocess
import time
import re
from datetime import datetime
from typing import Optional, Dict, Any
import logging
import os

from .base import AVScanner, AVScanResult
from ...utils.config import AVConfig
from ...utils.helpers import calculate_file_hash

logger = logging.getLogger(__name__)


class ClamAVScanner(AVScanner):
    """ClamAV antivirus scanner"""

    def __init__(self, config: AVConfig):
        """
        Initialize ClamAV scanner

        Args:
            config: AV configuration
        """
        super().__init__(config)
        self.scanner_name = "ClamAV"
        self.enabled = config.clamav_enabled
        self.clamscan_path = self._find_clamscan()

    def _find_clamscan(self) -> Optional[str]:
        """Find clamscan executable"""
        try:
            result = subprocess.run(
                ['which', 'clamscan'] if os.name != 'nt' else ['where', 'clamscan'],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return result.stdout.strip().split('\n')[0]
        except Exception:
            pass

        # Try common paths
        common_paths = [
            '/usr/bin/clamscan',
            '/usr/local/bin/clamscan',
            'C:\\Program Files\\ClamAV\\clamscan.exe',
            'C:\\Program Files (x86)\\ClamAV\\clamscan.exe'
        ]

        for path in common_paths:
            if os.path.exists(path):
                return path

        return None

    def scan_file(self, file_path: str) -> AVScanResult:
        """
        Scan file with ClamAV

        Args:
            file_path: Path to file

        Returns:
            Scan result
        """
        if not self.is_available():
            raise RuntimeError("ClamAV is not available on this system")

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        start_time = time.time()
        scan_time = datetime.now()
        file_hash = calculate_file_hash(file_path)

        try:
            # Run clamscan
            result = subprocess.run(
                [self.clamscan_path, '--no-summary', file_path],
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            scan_duration = time.time() - start_time

            # Parse ClamAV output
            # Exit codes: 0 = clean, 1 = infected, 2 = error
            is_malicious = result.returncode == 1

            threat_name = None
            if is_malicious:
                # ClamAV output format: "filename: THREAT_NAME FOUND"
                match = re.search(r': (.+?) FOUND', result.stdout)
                if match:
                    threat_name = match.group(1)

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
            self.logger.error(f"ClamAV scan timed out for {file_path}")
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
            self.logger.error(f"Error scanning with ClamAV: {e}")
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
        Check if ClamAV is available

        Returns:
            True if ClamAV is available
        """
        if not self.enabled:
            return False

        if not self.clamscan_path:
            return False

        try:
            result = subprocess.run(
                [self.clamscan_path, '--version'],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0

        except Exception as e:
            self.logger.debug(f"ClamAV availability check failed: {e}")
            return False

    def get_version(self) -> Optional[str]:
        """
        Get ClamAV version

        Returns:
            Version string
        """
        try:
            result = subprocess.run(
                [self.clamscan_path, '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                # Output format: "ClamAV 1.0.0/..."
                match = re.search(r'ClamAV ([\d.]+)', result.stdout)
                if match:
                    return match.group(1)
                return result.stdout.strip().split('\n')[0]

        except Exception as e:
            self.logger.debug(f"Failed to get ClamAV version: {e}")

        return None

    def update_signatures(self) -> bool:
        """
        Update ClamAV virus signatures using freshclam

        Returns:
            True if update successful
        """
        try:
            # Find freshclam
            freshclam_path = self.clamscan_path.replace('clamscan', 'freshclam')

            if not os.path.exists(freshclam_path):
                # Try to find it
                result = subprocess.run(
                    ['which', 'freshclam'] if os.name != 'nt' else ['where', 'freshclam'],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    freshclam_path = result.stdout.strip().split('\n')[0]
                else:
                    self.logger.error("freshclam not found")
                    return False

            # Run freshclam
            result = subprocess.run(
                [freshclam_path],
                capture_output=True,
                timeout=600  # 10 minutes for signature update
            )

            return result.returncode == 0

        except Exception as e:
            self.logger.error(f"Failed to update ClamAV signatures: {e}")
            return False
