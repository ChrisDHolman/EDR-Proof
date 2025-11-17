"""
ReversingLabs AP Integration
"""

import requests
import logging
import time
from typing import Optional

from .opswat_av import AVScanResult

logger = logging.getLogger(__name__)


class ReversingLabsClient:
    """
    ReversingLabs Advanced Platform (A1000/TitaniumCloud) Client

    API Documentation: https://docs.reversinglabs.com/
    """

    def __init__(self, config_manager):
        """Initialize ReversingLabs client"""
        self.config = config_manager.load_av_config()
        self.api_url = self.config.get('reversinglabs_api_url', 'https://data.reversinglabs.com/api')
        self.api_key = self.config.get('reversinglabs_api_key')
        self.api_username = self.config.get('reversinglabs_api_username')

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'EDR-PROOF/1.0'
        })
        self.session.auth = (self.api_username, self.api_key)

        logger.info(f"Initialized ReversingLabs client: {self.api_url}")

    def scan_file(self, file_path: str) -> AVScanResult:
        """
        Scan file with ReversingLabs

        Args:
            file_path: Path to file to scan

        Returns:
            AVScanResult object
        """
        logger.info(f"Scanning file with ReversingLabs: {file_path}")

        start_time = time.time()

        try:
            # Upload file for analysis
            with open(file_path, 'rb') as f:
                response = self.session.post(
                    f"{self.api_url}/uploads",
                    files={'file': ('sample', f)},
                    timeout=300
                )

            if response.status_code not in [200, 201]:
                raise Exception(f"Upload failed: {response.status_code} - {response.text}")

            result_data = response.json()

            # Parse ReversingLabs response
            # Structure varies by API endpoint, adjust based on actual API
            classification = result_data.get('classification', 'UNKNOWN')
            threat_name = result_data.get('threat_name')
            threat_level = result_data.get('threat_level', 0)

            is_malicious = classification in ['MALICIOUS', 'SUSPICIOUS']

            processing_time = int((time.time() - start_time) * 1000)

            return AVScanResult(
                is_malicious=is_malicious,
                threat_name=threat_name,
                confidence=float(threat_level) * 10 if threat_level else 0,  # Convert to 0-100
                scan_time_ms=processing_time,
                engine_version='ReversingLabs AP'
            )

        except Exception as e:
            logger.error(f"ReversingLabs scan failed: {e}", exc_info=True)
            processing_time = int((time.time() - start_time) * 1000)

            return AVScanResult(
                is_malicious=False,
                threat_name=None,
                confidence=0,
                scan_time_ms=processing_time,
                engine_version='ReversingLabs AP (error)'
            )

    def is_available(self) -> bool:
        """Check if ReversingLabs API is available"""
        try:
            response = self.session.get(f"{self.api_url}/system/heartbeat", timeout=10)
            return response.status_code == 200
        except:
            return False
