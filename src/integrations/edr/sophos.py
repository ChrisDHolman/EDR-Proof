"""
Sophos Central EDR Integration
Uses Sophos Central API
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import requests
import logging

from .base import EDRClient, EDRAlert, EDRDeploymentInfo
from ...utils.config import EDRConfig

logger = logging.getLogger(__name__)


class SophosClient(EDRClient):
    """Sophos Central EDR client"""

    def __init__(self, config: EDRConfig):
        """
        Initialize Sophos client

        Args:
            config: EDR configuration with Sophos credentials
        """
        super().__init__(config)
        self.vendor_name = "Sophos Central"
        self.api_key = config.sophos_api_key
        self.api_url = config.sophos_api_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'X-API-KEY': self.api_key,
            'Content-Type': 'application/json'
        })
        self.tenant_id = None
        self.data_region_url = None

    def authenticate(self) -> bool:
        """
        Authenticate with Sophos Central API

        Returns:
            True if authentication successful
        """
        try:
            # Get whoami info to determine tenant and data region
            response = self.session.get(
                f'{self.api_url}/whoami/v1',
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                self.tenant_id = data.get('id')
                self.data_region_url = data.get('apiHosts', {}).get('dataRegion', self.api_url)

                # Update session with data region URL
                self.logger.info(f"Sophos authentication successful. Tenant: {self.tenant_id}")
                return True
            else:
                self.logger.error(f"Sophos authentication failed: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            self.logger.error(f"Sophos authentication error: {e}")
            return False

    def deploy_agent(self, vm_name: str, vm_ip: str) -> EDRDeploymentInfo:
        """
        Deploy Sophos agent to VM

        Args:
            vm_name: Name of the VM
            vm_ip: IP address of the VM

        Returns:
            Deployment information
        """
        self.logger.info(f"Sophos agent deployment for {vm_name} ({vm_ip})")

        # Sophos deployment involves:
        # 1. Download installer from Sophos Central
        # 2. Install with product key
        # 3. Wait for endpoint to register

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
        Verify Sophos agent is running

        Args:
            agent_id: Sophos Endpoint ID

        Returns:
            True if agent is active
        """
        try:
            if not self.data_region_url:
                self.authenticate()

            response = self.session.get(
                f'{self.data_region_url}/endpoint/v1/endpoints/{agent_id}',
                timeout=10
            )

            if response.status_code == 200:
                endpoint = response.json()
                health_status = endpoint.get('health', {}).get('overall', 'unknown')
                # Consider healthy if status is 'good'
                return health_status.lower() == 'good'

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
        Retrieve alerts from Sophos Central

        Args:
            agent_id: Filter by endpoint ID
            host_name: Filter by hostname
            start_time: Start of time range
            end_time: End of time range

        Returns:
            List of EDR alerts
        """
        try:
            if not self.data_region_url:
                self.authenticate()

            # Build query parameters
            params = {
                'pageSize': 100,
                'sort': 'raisedAt desc'
            }

            # Sophos uses "from" and "to" for time range
            if start_time:
                params['from'] = start_time.isoformat()
            if end_time:
                params['to'] = end_time.isoformat()

            all_alerts = []
            next_key = None

            # Sophos uses pagination
            while True:
                if next_key:
                    params['pageFromKey'] = next_key

                response = self.session.get(
                    f'{self.data_region_url}/common/v1/alerts',
                    params=params,
                    timeout=30
                )

                if response.status_code != 200:
                    self.logger.error(f"Failed to query alerts: {response.status_code} - {response.text}")
                    break

                data = response.json()
                alerts = data.get('items', [])

                # Filter by endpoint or hostname if specified
                if agent_id or host_name:
                    filtered = []
                    for alert in alerts:
                        location = alert.get('location', {})
                        if agent_id and location.get('id') == agent_id:
                            filtered.append(alert)
                        elif host_name and location.get('name', '').lower() == host_name.lower():
                            filtered.append(alert)
                    alerts = filtered

                # Convert to standardized format
                for alert in alerts:
                    converted = self._convert_alert_to_edr_alert(alert)
                    all_alerts.append(converted)

                # Check for next page
                next_key = data.get('pages', {}).get('nextKey')
                if not next_key:
                    break

            self.logger.info(f"Retrieved {len(all_alerts)} Sophos alerts")
            return all_alerts

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
        Get count of Sophos alerts

        Args:
            agent_id: Filter by endpoint ID
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
        Uninstall Sophos agent

        Note: Sophos requires tamper protection to be disabled first

        Args:
            agent_id: Sophos Endpoint ID

        Returns:
            True if uninstall initiated
        """
        try:
            if not self.data_region_url:
                self.authenticate()

            # Delete endpoint from Sophos Central
            response = self.session.delete(
                f'{self.data_region_url}/endpoint/v1/endpoints/{agent_id}',
                timeout=10
            )

            if response.status_code in [200, 204]:
                self.logger.info(f"Sophos endpoint {agent_id} deleted from console")
                return True
            else:
                self.logger.error(f"Failed to delete endpoint: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            self.logger.error(f"Error uninstalling agent: {e}")
            return False

    def _convert_alert_to_edr_alert(self, alert: Dict[str, Any]) -> EDRAlert:
        """
        Convert Sophos alert to standardized format

        Args:
            alert: Raw alert data from Sophos

        Returns:
            Standardized EDRAlert
        """
        location = alert.get('location', {})
        data_fields = alert.get('data', {})

        return EDRAlert(
            alert_id=alert.get('id', ''),
            timestamp=datetime.fromisoformat(
                alert.get('raisedAt', datetime.now().isoformat()).replace('Z', '+00:00')
            ),
            severity=self._normalize_severity(alert.get('severity', 'medium')),
            alert_type=alert.get('type', 'unknown'),
            description=alert.get('description', 'Sophos alert'),
            file_hash=data_fields.get('sha256', None),
            file_path=data_fields.get('path', None),
            process_name=data_fields.get('process', None),
            command_line=data_fields.get('commandLine', None),
            user=data_fields.get('userName', None),
            host_name=location.get('name', None),
            ip_address=None,  # Sophos doesn't always include IP in alerts
            raw_data=alert,
            edr_vendor='Sophos'
        )

    def _normalize_severity(self, sophos_severity: str) -> str:
        """
        Convert Sophos severity to standard format

        Args:
            sophos_severity: Sophos severity level

        Returns:
            Normalized severity
        """
        severity_map = {
            'critical': 'critical',
            'high': 'high',
            'medium': 'medium',
            'low': 'low'
        }
        return severity_map.get(sophos_severity.lower(), 'medium')
