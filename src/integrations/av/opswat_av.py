"""
OPSWAT MetaDefender AV Scanning Integration
"""

import requests
import logging
import time
import os
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class AVScanResult:
    """Result from AV scan"""
    is_malicious: bool
    threat_name: Optional[str]
    confidence: float  # 0-100
    scan_time_ms: int
    engine_version: str


class OPSWATAVClient:
    """
    OPSWAT MetaDefender AV Scanning Client
    """

    def __init__(self, config_manager):
        """Initialize OPSWAT AV client"""
        self.config = config_manager.load_av_config()
        self.api_url = self.config.get('opswat_av_api_url', 'http://your-opswat-server:8008')
        self.api_key = self.config.get('opswat_av_api_key')

        self.session = requests.Session()
        self.session.headers.update({
            'apikey': self.api_key
        })

        logger.info(f"Initialized OPSWAT AV client: {self.api_url}")

    def scan_file(self, file_path: str) -> AVScanResult:
        """
        Scan file with OPSWAT MetaDefender

        Args:
            file_path: Path to file to scan

        Returns:
            AVScanResult object
        """
        logger.info(f"Scanning file with OPSWAT AV: {file_path}")

        start_time = time.time()

        try:
            # Upload file for scanning
            with open(file_path, 'rb') as f:
                response = self.session.post(
                    f"{self.api_url}/file",
                    files={'file': f},
                    timeout=300
                )

            if response.status_code != 200:
                raise Exception(f"Upload failed: {response.status_code}")

            data_id = response.json().get('data_id')

            # Wait for scan results
            scan_result = self._wait_for_scan_results(data_id)

            processing_time = int((time.time() - start_time) * 1000)

            return AVScanResult(
                is_malicious=scan_result['is_malicious'],
                threat_name=scan_result.get('threat_name'),
                confidence=scan_result.get('confidence', 0),
                scan_time_ms=processing_time,
                engine_version='OPSWAT MetaDefender'
            )

        except Exception as e:
            logger.error(f"OPSWAT AV scan failed: {e}", exc_info=True)
            processing_time = int((time.time() - start_time) * 1000)

            return AVScanResult(
                is_malicious=False,
                threat_name=None,
                confidence=0,
                scan_time_ms=processing_time,
                engine_version='OPSWAT MetaDefender (error)'
            )

    def _wait_for_scan_results(self, data_id: str, max_wait: int = 300) -> dict:
        """Wait for scan to complete"""
        start_time = time.time()

        while time.time() - start_time < max_wait:
            response = self.session.get(
                f"{self.api_url}/file/{data_id}",
                timeout=30
            )

            if response.status_code != 200:
                raise Exception(f"Status check failed: {response.status_code}")

            result = response.json()
            scan_results = result.get('scan_results', {})
            progress_percentage = scan_results.get('progress_percentage', 0)

            if progress_percentage == 100:
                # Parse results
                scan_all_result_a = scan_results.get('scan_all_result_a', '')
                is_malicious = 'infected' in scan_all_result_a.lower()

                threat_name = None
                if is_malicious:
                    # Extract threat name from scan details
                    scan_details = scan_results.get('scan_details', {})
                    for engine_name, engine_result in scan_details.items():
                        if engine_result.get('threat_found'):
                            threat_name = engine_result.get('def_name')
                            break

                return {
                    'is_malicious': is_malicious,
                    'threat_name': threat_name,
                    'confidence': 100 if is_malicious else 0
                }

            time.sleep(5)

        raise TimeoutError(f"Scan timed out after {max_wait}s")
