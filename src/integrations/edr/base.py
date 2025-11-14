"""
Base EDR Client Interface
All EDR integrations implement this interface
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class EDRAlert:
    """Standardized EDR alert structure"""
    alert_id: str
    timestamp: datetime
    severity: str  # critical, high, medium, low, info
    alert_type: str  # malware, suspicious_activity, policy_violation, etc.
    description: str
    file_hash: Optional[str] = None
    file_path: Optional[str] = None
    process_name: Optional[str] = None
    command_line: Optional[str] = None
    parent_process: Optional[str] = None
    user: Optional[str] = None
    host_name: Optional[str] = None
    ip_address: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None
    edr_vendor: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            'alert_id': self.alert_id,
            'timestamp': self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else self.timestamp,
            'severity': self.severity,
            'alert_type': self.alert_type,
            'description': self.description,
            'file_hash': self.file_hash,
            'file_path': self.file_path,
            'process_name': self.process_name,
            'command_line': self.command_line,
            'parent_process': self.parent_process,
            'user': self.user,
            'host_name': self.host_name,
            'ip_address': self.ip_address,
            'edr_vendor': self.edr_vendor
        }


@dataclass
class EDRDeploymentInfo:
    """Information about EDR agent deployment"""
    agent_id: str
    agent_version: str
    install_status: str  # installed, running, error
    host_name: str
    ip_address: Optional[str] = None
    last_seen: Optional[datetime] = None
    error_message: Optional[str] = None


class EDRClient(ABC):
    """
    Abstract base class for EDR integrations

    All EDR clients (CrowdStrike, SentinelOne, Sophos) implement this interface
    to provide a consistent API for the pipeline.
    """

    def __init__(self, config: Any):
        """
        Initialize EDR client

        Args:
            config: EDR-specific configuration object
        """
        self.config = config
        self.vendor_name = "Generic EDR"
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    def authenticate(self) -> bool:
        """
        Authenticate with EDR API

        Returns:
            True if authentication successful
        """
        pass

    @abstractmethod
    def deploy_agent(self, vm_name: str, vm_ip: str) -> EDRDeploymentInfo:
        """
        Deploy EDR agent to a VM

        Args:
            vm_name: Name of the VM
            vm_ip: IP address of the VM

        Returns:
            Deployment information
        """
        pass

    @abstractmethod
    def verify_agent_running(self, agent_id: str) -> bool:
        """
        Verify EDR agent is running and reporting

        Args:
            agent_id: Agent identifier

        Returns:
            True if agent is active
        """
        pass

    @abstractmethod
    def get_alerts(
        self,
        agent_id: Optional[str] = None,
        host_name: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[EDRAlert]:
        """
        Retrieve alerts from EDR console

        Args:
            agent_id: Filter by agent ID
            host_name: Filter by host name
            start_time: Start of time range
            end_time: End of time range

        Returns:
            List of EDR alerts
        """
        pass

    @abstractmethod
    def get_alert_count(
        self,
        agent_id: Optional[str] = None,
        host_name: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        severity: Optional[str] = None
    ) -> int:
        """
        Get count of alerts matching criteria

        Args:
            agent_id: Filter by agent ID
            host_name: Filter by host name
            start_time: Start of time range
            end_time: End of time range
            severity: Filter by severity level

        Returns:
            Number of alerts
        """
        pass

    @abstractmethod
    def uninstall_agent(self, agent_id: str) -> bool:
        """
        Uninstall EDR agent from a host

        Args:
            agent_id: Agent identifier

        Returns:
            True if uninstall successful
        """
        pass

    def get_installer_url(self) -> str:
        """
        Get URL or path to EDR agent installer

        Returns:
            Installer URL/path
        """
        raise NotImplementedError(f"{self.vendor_name} does not support automatic installer retrieval")

    def test_connection(self) -> bool:
        """
        Test connection to EDR API

        Returns:
            True if connection successful
        """
        try:
            return self.authenticate()
        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return False

    def get_vendor_name(self) -> str:
        """Get EDR vendor name"""
        return self.vendor_name

    def _normalize_severity(self, vendor_severity: str) -> str:
        """
        Normalize vendor-specific severity to standard format

        Args:
            vendor_severity: Vendor's severity string

        Returns:
            Normalized severity (critical, high, medium, low, info)
        """
        vendor_severity = vendor_severity.lower()

        # Common severity mappings
        if vendor_severity in ['critical', 'crit']:
            return 'critical'
        elif vendor_severity in ['high', 'important']:
            return 'high'
        elif vendor_severity in ['medium', 'moderate', 'warning']:
            return 'medium'
        elif vendor_severity in ['low', 'minor']:
            return 'low'
        elif vendor_severity in ['info', 'informational', 'notice']:
            return 'info'
        else:
            return 'medium'  # Default
