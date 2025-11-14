"""
Base AV Scanner Interface
All AV scanners implement this interface
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class AVScanResult:
    """Standardized AV scan result"""
    scanner_name: str
    file_path: str
    file_hash: str
    scan_time: datetime
    is_malicious: bool
    threat_name: Optional[str] = None
    threat_type: Optional[str] = None
    confidence: Optional[float] = None  # 0.0 to 1.0
    scan_duration_seconds: Optional[float] = None
    raw_result: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            'scanner_name': self.scanner_name,
            'file_path': self.file_path,
            'file_hash': self.file_hash,
            'scan_time': self.scan_time.isoformat() if isinstance(self.scan_time, datetime) else self.scan_time,
            'is_malicious': self.is_malicious,
            'threat_name': self.threat_name,
            'threat_type': self.threat_type,
            'confidence': self.confidence,
            'scan_duration_seconds': self.scan_duration_seconds
        }


class AVScanner(ABC):
    """
    Abstract base class for AV scanners

    All AV integrations (Defender, ClamAV, VirusTotal) implement this interface
    """

    def __init__(self, config: Any):
        """
        Initialize AV scanner

        Args:
            config: Scanner-specific configuration
        """
        self.config = config
        self.scanner_name = "Generic AV"
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    def scan_file(self, file_path: str) -> AVScanResult:
        """
        Scan a file for threats

        Args:
            file_path: Path to file to scan

        Returns:
            Scan result
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if scanner is available and functional

        Returns:
            True if scanner can be used
        """
        pass

    def scan_multiple_files(self, file_paths: List[str]) -> List[AVScanResult]:
        """
        Scan multiple files

        Args:
            file_paths: List of file paths

        Returns:
            List of scan results
        """
        results = []
        for file_path in file_paths:
            try:
                result = self.scan_file(file_path)
                results.append(result)
            except Exception as e:
                self.logger.error(f"Error scanning {file_path}: {e}")

        return results

    def get_scanner_name(self) -> str:
        """Get scanner name"""
        return self.scanner_name

    def get_version(self) -> Optional[str]:
        """
        Get scanner version

        Returns:
            Version string or None
        """
        return None
