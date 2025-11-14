"""
SentinelOne EDR Integration
Uses REST API for interaction
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import requests
import logging

from .base import EDRClient, EDRAlert, EDRDeploymentInfo
from ...utils.config import EDRConfig

logger = logging.getLogger(__name__)


class SentinelOneClient(EDRClient):
    """SentinelOne EDR client"""

    def __init__(self, config: EDRConfig):
        """
        Initialize SentinelOne client

        Args:
            config: EDR configuration with SentinelOne credentials
        """
        super().__init__(config)
        self.vendor_name = "SentinelOne"
        self.api_token = config.sentinelone_api_token
        self.console_url = config.sentinelone_console_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'ApiToken {self.api_token}',
            'Content-Type': 'application/json'
        })

    def authenticate(self) -> bool:
        """
        Authenticate with SentinelOne API

        Returns:
            True if authentication successful
        """
        try:
            # Test authentication by querying account info
            response = self.session.get(
                f'{self.console_url}/web/api/v2.1/system/status',
                timeout=10
            )

            if response.status_code == 200:
                self.logger.info("SentinelOne authentication successful")
                return True
            else:
                self.logger.error(f"SentinelOne authentication failed: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            self.logger.error(f"SentinelOne authentication error: {e}")
            return False

    def deploy_agent(self, vm_name: str, vm_ip: str) -> EDRDeploymentInfo:
        """
        Deploy SentinelOne agent to VM

        Args:
            vm_name: Name of the VM
            vm_ip: IP address of the VM

        Returns:
            Deployment information
        """
        self.logger.info(f"SentinelOne agent deployment for {vm_name} ({vm_ip})")

        # SentinelOne deployment typically involves:
        # 1. Download agent installer from console
        # 2. Install with site token
        # 3. Wait for agent to register

        return EDRDeploymentInfo(
            agent_id="",
            agent_version="unknown",
            install_status="pending",
            host_name=vm_name,
            ip_address=vm_ip,
            error_message="Manual deployment required - see documentation"
        )

    def verify_agent_running(self, agent_id: str) -> bool:
        """
        Verify SentinelOne agent is running

        Args:
            agent_id: SentinelOne Agent ID

        Returns:
            True if agent is active
        """
        try:
            response = self.session.get(
                f'{self.console_url}/web/api/v2.1/agents',
                params={'ids': agent_id},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                agents = data.get('data', [])
                if agents:
                    agent = agents[0]
                    is_active = agent.get('isActive', False)
                    network_status = agent.get('networkStatus', '')
                    return is_active and network_status == 'connected'

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
        Retrieve threats from SentinelOne

        Args:
            agent_id: Filter by agent ID
            host_name: Filter by hostname
            start_time: Start of time range
            end_time: End of time range

        Returns:
            List of EDR alerts
        """
        try:
            # Build query parameters
            params = {
                'limit': 1000,
                'sortBy': 'createdAt',
                'sortOrder': 'desc'
            }

            if agent_id:
                params['agentIds'] = agent_id
            if host_name:
                params['computerName'] = host_name
            if start_time:
                params['createdAt__gte'] = start_time.isoformat()
            if end_time:
                params['createdAt__lte'] = end_time.isoformat()

            response = self.session.get(
                f'{self.console_url}/web/api/v2.1/threats',
                params=params,
                timeout=30
            )

            if response.status_code != 200:
                self.logger.error(f"Failed to query threats: {response.status_code} - {response.text}")
                return []

            data = response.json()
            threats = data.get('data', [])

            # Convert to standardized EDRAlert format
            alerts = []
            for threat in threats:
                alert = self._convert_threat_to_alert(threat)
                alerts.append(alert)

            self.logger.info(f"Retrieved {len(alerts)} SentinelOne threats")
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
        Get count of SentinelOne threats

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
        Uninstall SentinelOne agent

        Args:
            agent_id: SentinelOne Agent ID

        Returns:
            True if uninstall initiated
        """
        try:
            # Initiate remote uninstall
            response = self.session.post(
                f'{self.console_url}/web/api/v2.1/agents/actions/uninstall',
                json={'filter': {'ids': [agent_id]}},
                timeout=10
            )

            if response.status_code in [200, 204]:
                self.logger.info(f"SentinelOne agent {agent_id} uninstall initiated")
                return True
            else:
                self.logger.error(f"Failed to uninstall agent: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            self.logger.error(f"Error uninstalling agent: {e}")
            return False

    def _convert_threat_to_alert(self, threat: Dict[str, Any]) -> EDRAlert:
        """
        Convert SentinelOne threat to standardized alert

        Args:
            threat: Raw threat data from SentinelOne

        Returns:
            Standardized EDRAlert
        """
        threat_info = threat.get('threatInfo', {})
        agent_detection = threat.get('agentDetectionInfo', {})

        return EDRAlert(
            alert_id=threat.get('id', ''),
            timestamp=datetime.fromisoformat(
                threat.get('createdAt', datetime.now().isoformat()).replace('Z', '+00:00')
            ),
            severity=self._normalize_severity(threat_info.get('confidenceLevel', 'medium')),
            alert_type=threat_info.get('classification', 'unknown'),
            description=threat_info.get('threatName', 'SentinelOne threat'),
            file_hash=threat_info.get('sha256', None) or threat_info.get('sha1', None),
            file_path=threat_info.get('filePath', None),
            process_name=threat_info.get('processUser', None),
            command_line=threat_info.get('engines', [{}])[0].get('title', None) if threat_info.get('engines') else None,
            user=agent_detection.get('agentOsName', None),
            host_name=agent_detection.get('agentComputerName', None),
            ip_address=agent_detection.get('agentIpV4', None),
            raw_data=threat,
            edr_vendor='SentinelOne'
        )

    def _normalize_severity(self, s1_severity: str) -> str:
        """
        Convert SentinelOne severity to standard format

        Args:
            s1_severity: SentinelOne confidence level

        Returns:
            Normalized severity
        """
        severity_map = {
            'malicious': 'critical',
            'suspicious': 'high',
            'n/a': 'medium'
        }
        return severity_map.get(s1_severity.lower(), 'medium')
