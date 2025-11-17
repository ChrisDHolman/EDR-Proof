"""
OPSWAT MetaDefender CDR Integration
"""

import requests
import logging
import time
import os
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CDRResult:
    """Result from CDR processing"""
    success: bool
    sanitized_file_path: Optional[str]
    processing_time_ms: int
    original_size: int
    sanitized_size: int
    threats_found: int
    error_message: Optional[str] = None

    def to_dict(self):
        return {
            'success': self.success,
            'sanitized_file_path': self.sanitized_file_path,
            'processing_time_ms': self.processing_time_ms,
            'original_size': self.original_size,
            'sanitized_size': self.sanitized_size,
            'threats_found': self.threats_found,
            'error_message': self.error_message
        }


class OPSWATCDRClient:
    """
    OPSWAT MetaDefender CDR Client

    API Documentation: https://docs.opswat.com/mdcore/metadefender-core-v4-api-quick-start-guide
    """

    def __init__(self, config_manager):
        """Initialize OPSWAT CDR client"""
        self.config = config_manager.load_cdr_config()
        self.api_url = self.config.get('opswat_api_url', 'http://your-opswat-server:8008')
        self.api_key = self.config.get('opswat_api_key')

        self.session = requests.Session()
        self.session.headers.update({
            'apikey': self.api_key
        })

        logger.info(f"Initialized OPSWAT CDR client: {self.api_url}")

    def sanitize_file(self, file_path: str) -> CDRResult:
        """
        Sanitize file using OPSWAT MetaDefender CDR

        Args:
            file_path: Path to file to sanitize

        Returns:
            CDRResult object
        """
        logger.info(f"Sanitizing file with OPSWAT: {file_path}")

        start_time = time.time()

        try:
            # Get original file size
            original_size = os.path.getsize(file_path)

            # Upload file for sanitization
            with open(file_path, 'rb') as f:
                response = self.session.post(
                    f"{self.api_url}/file",
                    files={'file': f},
                    headers={
                        'rule': 'sanitize',  # Use sanitization workflow
                    },
                    timeout=300
                )

            if response.status_code != 200:
                raise Exception(f"Upload failed: {response.status_code} - {response.text}")

            data_id = response.json().get('data_id')

            # Poll for results
            sanitized_file_path = self._wait_for_results(data_id, file_path)

            # Get sanitized file size
            sanitized_size = os.path.getsize(sanitized_file_path)

            processing_time = int((time.time() - start_time) * 1000)

            return CDRResult(
                success=True,
                sanitized_file_path=sanitized_file_path,
                processing_time_ms=processing_time,
                original_size=original_size,
                sanitized_size=sanitized_size,
                threats_found=0  # OPSWAT CDR focuses on sanitization
            )

        except Exception as e:
            logger.error(f"OPSWAT CDR failed: {e}", exc_info=True)
            processing_time = int((time.time() - start_time) * 1000)

            return CDRResult(
                success=False,
                sanitized_file_path=None,
                processing_time_ms=processing_time,
                original_size=original_size if 'original_size' in locals() else 0,
                sanitized_size=0,
                threats_found=0,
                error_message=str(e)
            )

    def _wait_for_results(self, data_id: str, original_file_path: str, max_wait: int = 300) -> str:
        """
        Wait for sanitization to complete and download sanitized file

        Args:
            data_id: Data ID from upload
            original_file_path: Original file path (for naming output)
            max_wait: Max seconds to wait

        Returns:
            Path to sanitized file
        """
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
                # Download sanitized file
                download_response = self.session.get(
                    f"{self.api_url}/file/converted/{data_id}",
                    timeout=60
                )

                if download_response.status_code != 200:
                    raise Exception(f"Download failed: {download_response.status_code}")

                # Save sanitized file
                base_name = os.path.basename(original_file_path)
                sanitized_path = f"/tmp/opswat_sanitized_{data_id}_{base_name}"

                with open(sanitized_path, 'wb') as f:
                    f.write(download_response.content)

                logger.info(f"OPSWAT sanitization complete: {sanitized_path}")
                return sanitized_path

            # Wait before polling again
            time.sleep(5)

        raise TimeoutError(f"Sanitization timed out after {max_wait}s")
