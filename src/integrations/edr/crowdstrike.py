"""
CrowdStrike Falcon EDR Integration
Uses FalconPy SDK for API interaction
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from falconpy import Hosts, Detects, OAuth2
import logging

from .base import EDRClient, EDRAlert, EDRDeploymentInfo
from ...utils.config import EDRConfig

logger = logging.getLogger(__name__)


class CrowdStrikeClient(EDRClient):
    """CrowdStrike Falcon EDR client"""

    def __init__(self, config: EDRConfig):
        """
        Initialize CrowdStrike client

        Args:
            config: EDR configuration with CrowdStrike credentials
        """
        super().__init__(config)
        self.vendor_name = "CrowdStrike Falcon"
        self.client_id = config.crowdstrike_client_id
        self.client_secret = config.crowdstrike_client_secret
        self.base_url = config.crowdstrike_base_url

        self.oauth_client = None
        self.hosts_client = None
        self.detects_client = None
        self.access_token = None

    def authenticate(self) -> bool:
        """
        Authenticate with CrowdStrike API

        Returns:
            True if authentication successful
        """
        try:
            self.oauth_client = OAuth2(
                client_id=self.client_id,
                client_secret=self.client_secret,
                base_url=self.base_url
            )

            # Test authentication by getting token
            token_result = self.oauth_client.token()
            if token_result.get('status_code') == 201:
                self.access_token = token_result['body']['access_token']

                # Initialize API clients
                self.hosts_client = Hosts(auth_object=self.oauth_client)
                self.detects_client = Detects(auth_object=self.oauth_client)

                self.logger.info("CrowdStrike authentication successful")
                return True
            else:
                self.logger.error(f"CrowdStrike authentication failed: {token_result}")
                return False

        except Exception as e:
            self.logger.error(f"CrowdStrike authentication error: {e}")
            return False

    def deploy_agent(self, vm_name: str, vm_ip: str) -> EDRDeploymentInfo:
        """
        Deploy CrowdStrike Falcon agent to VM

        Note: This typically requires manual installation or scripted deployment
        via PowerShell/Bash. The API doesn't directly install agents.

        Args:
            vm_name: Name of the VM
            vm_ip: IP address of the VM

        Returns:
            Deployment information
        """
        self.logger.info(f"CrowdStrike agent deployment for {vm_name} ({vm_ip})")

        # For automated deployment, you would:
        # 1. Download the Falcon sensor installer from CrowdStrike
        # 2. Copy it to the target VM
        # 3. Execute installation with CID (Customer ID)
        # 4. Wait for agent to check in

        # For now, return pending status
        # This should be implemented with actual deployment logic
        return EDRDeploymentInfo(
            agent_id="",  # Will be populated after agent checks in
            agent_version="unknown",
            install_status="pending",
            host_name=vm_name,
            ip_address=vm_ip,
            error_message="Manual deployment required - see documentation"
        )

    def verify_agent_running(self, agent_id: str) -> bool:
        """
        Verify Falcon agent is running

        Args:
            agent_id: CrowdStrike Agent ID (AID)

        Returns:
            True if agent is active
        """
        try:
            if not self.hosts_client:
                self.authenticate()

            # Query host details
            response = self.hosts_client.get_device_details(ids=[agent_id])

            if response['status_code'] == 200 and response['body']['resources']:
                device = response['body']['resources'][0]
                # Check if agent is online and last seen recently
                last_seen = device.get('last_seen')
                if last_seen:
                    last_seen_time = datetime.fromisoformat(last_seen.replace('Z', '+00:00'))
                    time_diff = datetime.now(last_seen_time.tzinfo) - last_seen_time
                    # Consider online if seen in last 5 minutes
                    return time_diff.total_seconds() < 300

            return False

        except Exception as e:
            self.logger.error(f"Error verifying agent status: {e}")
            return False

    def get_alerts(
        self,
        agent_id: Optional[str] = None,
        host_name: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[EDRAlert]:
        """
        Retrieve detections from CrowdStrike

        Args:
            agent_id: Filter by agent ID (AID)
            host_name: Filter by hostname
            start_time: Start of time range
            end_time: End of time range

        Returns:
            List of EDR alerts
        """
        try:
            if not self.detects_client:
                self.authenticate()

            # Build filter query
            filters = []
            if agent_id:
                filters.append(f"device.device_id:'{agent_id}'")
            if host_name:
                filters.append(f"device.hostname:'{host_name}'")
            if start_time:
                filters.append(f"first_behavior:>='{start_time.isoformat()}'")
            if end_time:
                filters.append(f"first_behavior:<='{end_time.isoformat()}'")

            filter_string = "+".join(filters) if filters else None

            # Query detection IDs
            detects_response = self.detects_client.query_detects(
                filter=filter_string,
                limit=500
            )

            if detects_response['status_code'] != 200:
                self.logger.error(f"Failed to query detections: {detects_response}")
                return []

            detection_ids = detects_response['body']['resources']
            if not detection_ids:
                return []

            # Get detailed detection info
            details_response = self.detects_client.get_detect_summaries(
                ids=detection_ids
            )

            if details_response['status_code'] != 200:
                self.logger.error(f"Failed to get detection details: {details_response}")
                return []

            # Convert to standardized EDRAlert format
            alerts = []
            for detection in details_response['body']['resources']:
                alert = self._convert_detection_to_alert(detection)
                alerts.append(alert)

            self.logger.info(f"Retrieved {len(alerts)} CrowdStrike alerts")
            return alerts

        except Exception as e:
            self.logger.error(f"Error retrieving alerts: {e}")
            return []

    def get_alert_count(
        self,
        agent_id: Optional[str] = None,
        host_name: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        severity: Optional[str] = None
    ) -> int:
        """
        Get count of CrowdStrike detections

        Args:
            agent_id: Filter by agent ID
            host_name: Filter by hostname
            start_time: Start of time range
            end_time: End of time range
            severity: Filter by severity

        Returns:
            Number of alerts
        """
        alerts = self.get_alerts(agent_id, host_name, start_time, end_time)

        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        return len(alerts)

    def uninstall_agent(self, agent_id: str) -> bool:
        """
        Uninstall Falcon agent

        Note: CrowdStrike doesn't support remote uninstall via API.
        This must be done manually or via script on the host.

        Args:
            agent_id: CrowdStrike Agent ID

        Returns:
            True if uninstall initiated
        """
        self.logger.warning(f"CrowdStrike agent uninstall for {agent_id} requires manual action")
        # In a real implementation, you would:
        # 1. Execute uninstall script on the VM via Azure VM commands
        # 2. Or hide the host in CrowdStrike console
        return False

    def get_installer_url(self) -> str:
        """
        Get Falcon sensor installer download URL

        Returns:
            Installer URL
        """
        # Note: Actual implementation would need to use the Sensor Download API
        # This requires specific API scopes and customer CID
        self.logger.warning("Installer URL retrieval not implemented")
        return ""

    def _convert_detection_to_alert(self, detection: Dict[str, Any]) -> EDRAlert:
        """
        Convert CrowdStrike detection to standardized alert

        Args:
            detection: Raw detection data from CrowdStrike

        Returns:
            Standardized EDRAlert
        """
        behaviors = detection.get('behaviors', [])
        first_behavior = behaviors[0] if behaviors else {}

        return EDRAlert(
            alert_id=detection.get('detection_id', ''),
            timestamp=datetime.fromisoformat(
                detection.get('first_behavior', datetime.now().isoformat()).replace('Z', '+00:00')
            ),
            severity=self._normalize_severity(detection.get('max_severity_displayname', 'medium')),
            alert_type=first_behavior.get('tactic', 'unknown'),
            description=first_behavior.get('scenario', 'CrowdStrike detection'),
            file_hash=first_behavior.get('sha256', None),
            file_path=first_behavior.get('filename', None),
            process_name=first_behavior.get('parent_details', {}).get('parent_process', None),
            command_line=first_behavior.get('cmdline', None),
            user=first_behavior.get('user_name', None),
            host_name=detection.get('device', {}).get('hostname', None),
            ip_address=detection.get('device', {}).get('local_ip', None),
            raw_data=detection,
            edr_vendor='CrowdStrike'
        )

    def _normalize_severity(self, cs_severity: str) -> str:
        """
        Convert CrowdStrike severity to standard format

        Args:
            cs_severity: CrowdStrike severity

        Returns:
            Normalized severity
        """
        severity_map = {
            'Critical': 'critical',
            'High': 'high',
            'Medium': 'medium',
            'Low': 'low',
            'Informational': 'info'
        }
        return severity_map.get(cs_severity, 'medium')
