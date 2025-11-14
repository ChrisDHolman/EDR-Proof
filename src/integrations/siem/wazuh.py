"""
Wazuh SIEM Integration
Collects alerts from Wazuh for all EDR agents
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import requests
import logging
from requests.auth import HTTPBasicAuth

from ...utils.config import WazuhConfig

logger = logging.getLogger(__name__)


class WazuhClient:
    """
    Wazuh SIEM client for collecting EDR/AV alerts

    In your architecture, EDR agents send alerts to Wazuh,
    which centralizes all security events.
    """

    def __init__(self, config: WazuhConfig):
        """
        Initialize Wazuh client

        Args:
            config: Wazuh configuration
        """
        self.config = config
        self.api_url = config.api_url.rstrip('/')
        self.username = config.api_username
        self.password = config.api_password
        self.indexer_url = config.indexer_url

        self.session = requests.Session()
        self.session.verify = False  # Disable SSL verification for self-signed certs
        self.token = None

        self.logger = logging.getLogger(__name__)

    def authenticate(self) -> bool:
        """
        Authenticate with Wazuh API

        Returns:
            True if authentication successful
        """
        try:
            response = self.session.post(
                f'{self.api_url}/security/user/authenticate',
                auth=HTTPBasicAuth(self.username, self.password),
                verify=False,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                self.token = data.get('data', {}).get('token')

                # Update session headers with token
                self.session.headers.update({
                    'Authorization': f'Bearer {self.token}'
                })

                self.logger.info("Wazuh authentication successful")
                return True
            else:
                self.logger.error(f"Wazuh authentication failed: {response.status_code}")
                return False

        except Exception as e:
            self.logger.error(f"Wazuh authentication error: {e}")
            return False

    def get_agents(self) -> List[Dict[str, Any]]:
        """
        Get list of all Wazuh agents

        Returns:
            List of agents
        """
        if not self.token:
            self.authenticate()

        try:
            response = self.session.get(
                f'{self.api_url}/agents',
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                agents = data.get('data', {}).get('affected_items', [])
                return agents
            else:
                self.logger.error(f"Failed to get agents: {response.status_code}")
                return []

        except Exception as e:
            self.logger.error(f"Error getting agents: {e}")
            return []

    def get_agent_by_name(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """
        Get agent by hostname

        Args:
            agent_name: Agent hostname

        Returns:
            Agent info or None
        """
        agents = self.get_agents()
        for agent in agents:
            if agent.get('name', '').lower() == agent_name.lower():
                return agent
        return None

    def get_alerts(
        self,
        agent_id: Optional[str] = None,
        agent_name: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        rule_level: Optional[int] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Get alerts from Wazuh

        Args:
            agent_id: Filter by agent ID
            agent_name: Filter by agent hostname
            start_time: Start of time range
            end_time: End of time range
            rule_level: Minimum rule level (1-15)
            limit: Maximum number of alerts

        Returns:
            List of alerts
        """
        if not self.token:
            self.authenticate()

        try:
            # Build query parameters
            params = {
                'limit': limit,
                'sort': '-timestamp'
            }

            if agent_id:
                params['agent_id'] = agent_id
            if agent_name:
                params['agent_name'] = agent_name
            if rule_level:
                params['rule_level'] = f'>{rule_level}'

            # Time range filtering (if using Wazuh API v4+)
            if start_time:
                params['older_than'] = start_time.strftime('%Y-%m-%dT%H:%M:%S')
            if end_time:
                params['newer_than'] = end_time.strftime('%Y-%m-%dT%H:%M:%S')

            response = self.session.get(
                f'{self.api_url}/security_events',
                params=params,
                timeout=60
            )

            if response.status_code == 200:
                data = response.json()
                alerts = data.get('data', {}).get('affected_items', [])
                self.logger.info(f"Retrieved {len(alerts)} alerts from Wazuh")
                return alerts
            else:
                self.logger.error(f"Failed to get alerts: {response.status_code} - {response.text}")
                return []

        except Exception as e:
            self.logger.error(f"Error getting alerts: {e}")
            return []

    def get_alert_count(
        self,
        agent_id: Optional[str] = None,
        agent_name: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        severity_level: Optional[int] = None
    ) -> int:
        """
        Get count of alerts matching criteria

        Args:
            agent_id: Filter by agent ID
            agent_name: Filter by agent hostname
            start_time: Start of time range
            end_time: End of time range
            severity_level: Minimum severity level

        Returns:
            Number of alerts
        """
        alerts = self.get_alerts(agent_id, agent_name, start_time, end_time, severity_level)
        return len(alerts)

    def query_elasticsearch(self, query: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Query Wazuh Indexer (OpenSearch/Elasticsearch) directly

        Args:
            query: Elasticsearch query DSL

        Returns:
            Query results
        """
        try:
            response = self.session.post(
                f'{self.indexer_url}/wazuh-alerts-*/_search',
                json=query,
                auth=HTTPBasicAuth(self.username, self.password),
                verify=False,
                timeout=60
            )

            if response.status_code == 200:
                data = response.json()
                hits = data.get('hits', {}).get('hits', [])
                return [hit.get('_source') for hit in hits]
            else:
                self.logger.error(f"Elasticsearch query failed: {response.status_code}")
                return []

        except Exception as e:
            self.logger.error(f"Error querying Elasticsearch: {e}")
            return []

    def get_alerts_for_test_run(
        self,
        vm_name: str,
        test_start_time: datetime,
        test_end_time: datetime
    ) -> List[Dict[str, Any]]:
        """
        Get all alerts for a specific test run

        Args:
            vm_name: Name of the test VM
            test_start_time: When test started
            test_end_time: When test ended

        Returns:
            List of alerts during test window
        """
        # Add buffer time to catch delayed alerts
        start_with_buffer = test_start_time - timedelta(minutes=1)
        end_with_buffer = test_end_time + timedelta(minutes=2)

        # Query using Elasticsearch for more precise time filtering
        query = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "term": {
                                "agent.name": vm_name
                            }
                        },
                        {
                            "range": {
                                "timestamp": {
                                    "gte": start_with_buffer.isoformat(),
                                    "lte": end_with_buffer.isoformat()
                                }
                            }
                        }
                    ]
                }
            },
            "size": 10000,
            "sort": [{"timestamp": "asc"}]
        }

        return self.query_elasticsearch(query)

    def test_connection(self) -> bool:
        """
        Test connection to Wazuh API

        Returns:
            True if connection successful
        """
        try:
            return self.authenticate()
        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return False
