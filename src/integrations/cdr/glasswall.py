"""
Glasswall CDR Integration
Content Disarm and Reconstruction for file sanitization
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime
import requests
import logging
import os
import time

from ...utils.config import CDRConfig
from ...utils.helpers import calculate_file_hash, get_file_info

logger = logging.getLogger(__name__)


@dataclass
class CDRResult:
    """CDR processing result"""
    success: bool
    original_file_path: str
    sanitized_file_path: Optional[str]
    original_hash: str
    sanitized_hash: Optional[str]
    processing_time_seconds: float
    file_size_before: int
    file_size_after: Optional[int]
    threats_removed: Optional[int]
    error_message: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'success': self.success,
            'original_file_path': self.original_file_path,
            'sanitized_file_path': self.sanitized_file_path,
            'original_hash': self.original_hash,
            'sanitized_hash': self.sanitized_hash,
            'processing_time_seconds': self.processing_time_seconds,
            'file_size_before': self.file_size_before,
            'file_size_after': self.file_size_after,
            'threats_removed': self.threats_removed,
            'error_message': self.error_message
        }


class GlasswallClient:
    """
    Glasswall CDR API Client

    Handles file sanitization using Glasswall's Content Disarm and Reconstruction
    """

    def __init__(self, config: CDRConfig):
        """
        Initialize Glasswall client

        Args:
            config: CDR configuration
        """
        self.config = config
        self.api_key = config.glasswall_api_key
        self.api_url = config.glasswall_api_url.rstrip('/')
        self.timeout = config.timeout_seconds

        self.session = requests.Session()
        self.session.headers.update({
            'x-api-key': self.api_key,
            'Accept': 'application/json'
        })

        self.logger = logging.getLogger(__name__)

    def sanitize_file(self, file_path: str, output_path: Optional[str] = None) -> CDRResult:
        """
        Sanitize a file using Glasswall CDR

        Args:
            file_path: Path to original file
            output_path: Path for sanitized file (optional)

        Returns:
            CDR processing result
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        # Generate output path if not provided
        if not output_path:
            dir_name = os.path.dirname(file_path)
            base_name = os.path.basename(file_path)
            name, ext = os.path.splitext(base_name)
            output_path = os.path.join(dir_name, f"{name}_sanitized{ext}")

        # Get file info
        file_info = get_file_info(file_path)
        original_hash = file_info['sha256']
        file_size_before = file_info['file_size']

        start_time = time.time()

        try:
            self.logger.info(f"Starting CDR processing for {file_path}")

            # Upload file to Glasswall API
            with open(file_path, 'rb') as f:
                files = {
                    'file': (os.path.basename(file_path), f, 'application/octet-stream')
                }

                response = self.session.post(
                    f'{self.api_url}/api/rebuild',
                    files=files,
                    timeout=self.timeout
                )

            processing_time = time.time() - start_time

            if response.status_code == 200:
                # Save sanitized file
                with open(output_path, 'wb') as f:
                    f.write(response.content)

                # Calculate sanitized file hash
                sanitized_hash = calculate_file_hash(output_path)
                file_size_after = os.path.getsize(output_path)

                # Check if file was actually modified
                if original_hash == sanitized_hash:
                    self.logger.info(f"File {file_path} was already clean (no changes)")
                    threats_removed = 0
                else:
                    self.logger.info(f"File {file_path} successfully sanitized")
                    threats_removed = 1  # Simplified - real implementation would parse response

                return CDRResult(
                    success=True,
                    original_file_path=file_path,
                    sanitized_file_path=output_path,
                    original_hash=original_hash,
                    sanitized_hash=sanitized_hash,
                    processing_time_seconds=processing_time,
                    file_size_before=file_size_before,
                    file_size_after=file_size_after,
                    threats_removed=threats_removed,
                    raw_response={'status_code': response.status_code}
                )

            else:
                # CDR processing failed
                error_msg = f"CDR failed with status {response.status_code}: {response.text}"
                self.logger.error(error_msg)

                return CDRResult(
                    success=False,
                    original_file_path=file_path,
                    sanitized_file_path=None,
                    original_hash=original_hash,
                    sanitized_hash=None,
                    processing_time_seconds=processing_time,
                    file_size_before=file_size_before,
                    file_size_after=None,
                    threats_removed=None,
                    error_message=error_msg,
                    raw_response={
                        'status_code': response.status_code,
                        'response_text': response.text
                    }
                )

        except requests.exceptions.Timeout:
            processing_time = time.time() - start_time
            error_msg = f"CDR processing timed out after {processing_time:.1f}s"
            self.logger.error(error_msg)

            return CDRResult(
                success=False,
                original_file_path=file_path,
                sanitized_file_path=None,
                original_hash=original_hash,
                sanitized_hash=None,
                processing_time_seconds=processing_time,
                file_size_before=file_size_before,
                file_size_after=None,
                threats_removed=None,
                error_message=error_msg
            )

        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"CDR processing error: {str(e)}"
            self.logger.error(error_msg, exc_info=True)

            return CDRResult(
                success=False,
                original_file_path=file_path,
                sanitized_file_path=None,
                original_hash=original_hash,
                sanitized_hash=None,
                processing_time_seconds=processing_time,
                file_size_before=file_size_before,
                file_size_after=None,
                threats_removed=None,
                error_message=error_msg
            )

    def analyze_file(self, file_path: str) -> Dict[str, Any]:
        """
        Analyze file without sanitizing (inspection only)

        Args:
            file_path: Path to file

        Returns:
            Analysis report
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            with open(file_path, 'rb') as f:
                files = {
                    'file': (os.path.basename(file_path), f, 'application/octet-stream')
                }

                response = self.session.post(
                    f'{self.api_url}/api/analyse',
                    files=files,
                    timeout=self.timeout
                )

            if response.status_code == 200:
                return response.json()
            else:
                self.logger.error(f"Analysis failed: {response.status_code} - {response.text}")
                return {'error': f"Status {response.status_code}"}

        except Exception as e:
            self.logger.error(f"Analysis error: {e}")
            return {'error': str(e)}

    def test_connection(self) -> bool:
        """
        Test connection to Glasswall API

        Returns:
            True if API is reachable
        """
        try:
            response = self.session.get(
                f'{self.api_url}/api/health',
                timeout=10
            )
            return response.status_code == 200

        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return False

    def get_supported_file_types(self) -> list:
        """
        Get list of supported file types

        Returns:
            List of supported file extensions
        """
        # Glasswall typically supports these file types
        return [
            '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff',
            '.zip', '.7z', '.rar', '.msg', '.eml'
        ]

    def is_file_supported(self, file_path: str) -> bool:
        """
        Check if file type is supported by Glasswall

        Args:
            file_path: Path to file

        Returns:
            True if file type is supported
        """
        ext = os.path.splitext(file_path)[1].lower()
        return ext in self.get_supported_file_types()
