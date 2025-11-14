"""
VirusTotal API Integration
Multi-engine AV scanning via VirusTotal API
"""

import requests
import time
from datetime import datetime
from typing import Optional, Dict, Any
import logging
import os

from .base import AVScanner, AVScanResult
from ...utils.config import AVConfig
from ...utils.helpers import calculate_file_hash

logger = logging.getLogger(__name__)


class VirusTotalScanner(AVScanner):
    """VirusTotal multi-engine scanner"""

    def __init__(self, config: AVConfig):
        """
        Initialize VirusTotal scanner

        Args:
            config: AV configuration with API key
        """
        super().__init__(config)
        self.scanner_name = "VirusTotal"
        self.api_key = config.commercial_av_api_key
        self.api_url = config.commercial_av_api_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'x-apikey': self.api_key
        })

        # VirusTotal API rate limits
        self.max_file_size = 32 * 1024 * 1024  # 32 MB for free API
        self.requests_per_minute = 4  # Free tier limit

    def scan_file(self, file_path: str) -> AVScanResult:
        """
        Scan file with VirusTotal

        Args:
            file_path: Path to file

        Returns:
            Scan result
        """
        if not self.is_available():
            raise RuntimeError("VirusTotal API key not configured")

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        # Check file size
        file_size = os.path.getsize(file_path)
        if file_size > self.max_file_size:
            self.logger.warning(f"File {file_path} exceeds VirusTotal size limit ({file_size} bytes)")

        start_time = time.time()
        scan_time = datetime.now()
        file_hash = calculate_file_hash(file_path, 'sha256')

        try:
            # First, check if file has been scanned before (by hash)
            analysis_id = self._check_existing_scan(file_hash)

            if not analysis_id:
                # Upload file for scanning
                analysis_id = self._upload_file(file_path)

            if not analysis_id:
                raise RuntimeError("Failed to initiate VirusTotal scan")

            # Poll for results
            result = self._get_analysis_result(analysis_id)

            scan_duration = time.time() - start_time

            if not result:
                return AVScanResult(
                    scanner_name=self.scanner_name,
                    file_path=file_path,
                    file_hash=file_hash,
                    scan_time=scan_time,
                    is_malicious=False,
                    scan_duration_seconds=scan_duration,
                    raw_result={'error': 'no_result'}
                )

            # Parse VirusTotal results
            stats = result.get('attributes', {}).get('stats', {})
            malicious_count = stats.get('malicious', 0)
            total_engines = sum(stats.values())

            is_malicious = malicious_count > 0
            confidence = malicious_count / total_engines if total_engines > 0 else 0.0

            # Get threat names from engines that detected
            threat_names = []
            engines = result.get('attributes', {}).get('results', {})
            for engine_name, engine_result in engines.items():
                if engine_result.get('category') == 'malicious':
                    threat_name = engine_result.get('result')
                    if threat_name and threat_name not in threat_names:
                        threat_names.append(threat_name)

            return AVScanResult(
                scanner_name=self.scanner_name,
                file_path=file_path,
                file_hash=file_hash,
                scan_time=scan_time,
                is_malicious=is_malicious,
                threat_name=threat_names[0] if threat_names else None,
                threat_type='malware' if is_malicious else None,
                confidence=confidence,
                scan_duration_seconds=scan_duration,
                raw_result={
                    'malicious_count': malicious_count,
                    'total_engines': total_engines,
                    'threat_names': threat_names,
                    'stats': stats
                }
            )

        except Exception as e:
            scan_duration = time.time() - start_time
            self.logger.error(f"Error scanning with VirusTotal: {e}")
            return AVScanResult(
                scanner_name=self.scanner_name,
                file_path=file_path,
                file_hash=file_hash,
                scan_time=scan_time,
                is_malicious=False,
                scan_duration_seconds=scan_duration,
                raw_result={'error': str(e)}
            )

    def _check_existing_scan(self, file_hash: str) -> Optional[str]:
        """
        Check if file has been scanned before

        Args:
            file_hash: SHA256 hash of file

        Returns:
            Analysis ID if found, None otherwise
        """
        try:
            response = self.session.get(
                f'{self.api_url}/files/{file_hash}',
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                # Return the latest analysis ID
                analysis_id = data.get('data', {}).get('id')
                self.logger.info(f"Found existing VirusTotal scan for {file_hash}")
                return analysis_id

            return None

        except Exception as e:
            self.logger.debug(f"No existing scan found: {e}")
            return None

    def _upload_file(self, file_path: str) -> Optional[str]:
        """
        Upload file to VirusTotal for scanning

        Args:
            file_path: Path to file

        Returns:
            Analysis ID
        """
        try:
            with open(file_path, 'rb') as f:
                files = {'file': (os.path.basename(file_path), f)}
                response = self.session.post(
                    f'{self.api_url}/files',
                    files=files,
                    timeout=300
                )

            if response.status_code in [200, 201]:
                data = response.json()
                analysis_id = data.get('data', {}).get('id')
                self.logger.info(f"Uploaded file to VirusTotal, analysis ID: {analysis_id}")
                return analysis_id
            else:
                self.logger.error(f"Failed to upload file: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            self.logger.error(f"Error uploading file: {e}")
            return None

    def _get_analysis_result(self, analysis_id: str, max_wait: int = 300) -> Optional[Dict[str, Any]]:
        """
        Poll for analysis results

        Args:
            analysis_id: Analysis ID from upload
            max_wait: Maximum seconds to wait

        Returns:
            Analysis result
        """
        start_time = time.time()

        while time.time() - start_time < max_wait:
            try:
                response = self.session.get(
                    f'{self.api_url}/analyses/{analysis_id}',
                    timeout=30
                )

                if response.status_code == 200:
                    data = response.json()
                    status = data.get('data', {}).get('attributes', {}).get('status')

                    if status == 'completed':
                        self.logger.info(f"VirusTotal analysis completed: {analysis_id}")
                        return data.get('data')

                    # Still processing, wait and retry
                    time.sleep(10)
                else:
                    self.logger.error(f"Error checking analysis: {response.status_code}")
                    return None

            except Exception as e:
                self.logger.error(f"Error getting analysis result: {e}")
                return None

        self.logger.warning(f"VirusTotal analysis timed out: {analysis_id}")
        return None

    def is_available(self) -> bool:
        """
        Check if VirusTotal API is available

        Returns:
            True if API key is configured
        """
        if not self.api_key:
            return False

        try:
            # Test API key with a simple request
            response = self.session.get(
                f'{self.api_url}/users/current',
                timeout=10
            )
            return response.status_code == 200

        except Exception as e:
            self.logger.debug(f"VirusTotal availability check failed: {e}")
            return False

    def get_version(self) -> Optional[str]:
        """
        Get VirusTotal API version

        Returns:
            API version
        """
        return "v3"  # Current VirusTotal API version
