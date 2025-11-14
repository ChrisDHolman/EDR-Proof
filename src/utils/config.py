"""
Configuration Management for CDR Validation Pipeline
Integrates with Azure Key Vault for secrets management
"""

import os
from typing import Optional, Dict, Any
from dataclasses import dataclass
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
import logging

logger = logging.getLogger(__name__)


@dataclass
class AzureConfig:
    """Azure infrastructure configuration"""
    subscription_id: str
    resource_group: str
    location: str
    vnet_name: str
    test_vm_subnet_id: str
    storage_account_name: str
    storage_account_key: str
    key_vault_url: str
    sql_server: str
    sql_database: str
    sql_username: str
    sql_password: str


@dataclass
class WazuhConfig:
    """Wazuh SIEM configuration"""
    manager_ip: str
    api_url: str
    api_username: str
    api_password: str
    indexer_ip: str
    indexer_url: str


@dataclass
class EDRConfig:
    """EDR solutions configuration"""
    crowdstrike_client_id: str
    crowdstrike_client_secret: str
    crowdstrike_base_url: str
    sentinelone_api_token: str
    sentinelone_console_url: str
    sophos_api_key: str
    sophos_api_url: str


@dataclass
class AVConfig:
    """AV scanners configuration"""
    defender_enabled: bool = True
    clamav_enabled: bool = True
    commercial_av_api_key: str = ""
    commercial_av_api_url: str = ""


@dataclass
class CDRConfig:
    """CDR solution configuration"""
    glasswall_api_key: str
    glasswall_api_url: str
    timeout_seconds: int = 300


@dataclass
class VMConfig:
    """Test VM configuration"""
    vm_size: str = "Standard_D4s_v3"
    os_disk_size_gb: int = 128
    use_spot_instances: bool = True
    spot_max_price: float = -1.0
    admin_username: str = "vmadmin"
    admin_password: str = ""
    image_publisher: str = "MicrosoftWindowsServer"
    image_offer: str = "WindowsServer"
    image_sku: str = "2022-datacenter"
    image_version: str = "latest"


@dataclass
class TestConfig:
    """Test execution configuration"""
    interaction_duration_seconds: int = 180  # 2-5 minutes
    enable_user_simulation: bool = True
    auto_enable_macros: bool = True
    max_retries: int = 3
    timeout_seconds: int = 600


class ConfigManager:
    """Centralized configuration management with Key Vault integration"""

    def __init__(self, key_vault_url: Optional[str] = None):
        """
        Initialize configuration manager

        Args:
            key_vault_url: Azure Key Vault URL. If not provided, uses environment variable.
        """
        self.key_vault_url = key_vault_url or os.getenv("AZURE_KEY_VAULT_URL")
        self.credential = DefaultAzureCredential()
        self.secret_client = None
        self._cache: Dict[str, str] = {}

        if self.key_vault_url:
            try:
                self.secret_client = SecretClient(
                    vault_url=self.key_vault_url,
                    credential=self.credential
                )
                logger.info(f"Connected to Key Vault: {self.key_vault_url}")
            except Exception as e:
                logger.warning(f"Failed to connect to Key Vault: {e}. Will use environment variables.")

    def get_secret(self, secret_name: str, default: Optional[str] = None) -> str:
        """
        Get secret from Key Vault with fallback to environment variables

        Args:
            secret_name: Name of the secret
            default: Default value if secret not found

        Returns:
            Secret value
        """
        # Check cache first
        if secret_name in self._cache:
            return self._cache[secret_name]

        # Try Key Vault
        if self.secret_client:
            try:
                secret = self.secret_client.get_secret(secret_name)
                self._cache[secret_name] = secret.value
                return secret.value
            except Exception as e:
                logger.debug(f"Secret '{secret_name}' not found in Key Vault: {e}")

        # Fallback to environment variable
        env_name = secret_name.upper().replace("-", "_")
        value = os.getenv(env_name, default)

        if value:
            self._cache[secret_name] = value
            return value

        raise ValueError(f"Secret '{secret_name}' not found in Key Vault or environment variables")

    def load_azure_config(self) -> AzureConfig:
        """Load Azure infrastructure configuration"""
        return AzureConfig(
            subscription_id=self.get_secret("azure-subscription-id", os.getenv("AZURE_SUBSCRIPTION_ID", "")),
            resource_group=self.get_secret("azure-resource-group", os.getenv("AZURE_RESOURCE_GROUP", "")),
            location=self.get_secret("azure-location", os.getenv("AZURE_LOCATION", "eastus")),
            vnet_name=self.get_secret("azure-vnet-name", os.getenv("AZURE_VNET_NAME", "")),
            test_vm_subnet_id=self.get_secret("azure-test-vm-subnet-id", os.getenv("AZURE_TEST_VM_SUBNET_ID", "")),
            storage_account_name=self.get_secret("azure-storage-account-name", os.getenv("AZURE_STORAGE_ACCOUNT_NAME", "")),
            storage_account_key=self.get_secret("azure-storage-account-key", os.getenv("AZURE_STORAGE_ACCOUNT_KEY", "")),
            key_vault_url=self.key_vault_url,
            sql_server=self.get_secret("sql-server", os.getenv("SQL_SERVER", "")),
            sql_database=self.get_secret("sql-database", os.getenv("SQL_DATABASE", "cdr-metrics")),
            sql_username=self.get_secret("sql-admin-username", os.getenv("SQL_ADMIN_USERNAME", "")),
            sql_password=self.get_secret("sql-admin-password", os.getenv("SQL_ADMIN_PASSWORD", ""))
        )

    def load_wazuh_config(self) -> WazuhConfig:
        """Load Wazuh SIEM configuration"""
        manager_ip = self.get_secret("wazuh-manager-ip", os.getenv("WAZUH_MANAGER_IP", ""))
        indexer_ip = self.get_secret("wazuh-indexer-ip", os.getenv("WAZUH_INDEXER_IP", ""))

        return WazuhConfig(
            manager_ip=manager_ip,
            api_url=f"https://{manager_ip}:55000",
            api_username=self.get_secret("wazuh-api-username", "wazuh"),
            api_password=self.get_secret("wazuh-api-password", "wazuh"),
            indexer_ip=indexer_ip,
            indexer_url=f"https://{indexer_ip}:9200"
        )

    def load_edr_config(self) -> EDRConfig:
        """Load EDR solutions configuration"""
        return EDRConfig(
            crowdstrike_client_id=self.get_secret("crowdstrike-client-id", ""),
            crowdstrike_client_secret=self.get_secret("crowdstrike-client-secret", ""),
            crowdstrike_base_url=self.get_secret("crowdstrike-base-url", "https://api.crowdstrike.com"),
            sentinelone_api_token=self.get_secret("sentinelone-api-token", ""),
            sentinelone_console_url=self.get_secret("sentinelone-console-url", ""),
            sophos_api_key=self.get_secret("sophos-api-key", ""),
            sophos_api_url=self.get_secret("sophos-api-url", "https://api.central.sophos.com")
        )

    def load_av_config(self) -> AVConfig:
        """Load AV scanners configuration"""
        return AVConfig(
            defender_enabled=True,
            clamav_enabled=True,
            commercial_av_api_key=self.get_secret("commercial-av-api-key", ""),
            commercial_av_api_url=self.get_secret("commercial-av-api-url", "https://www.virustotal.com/api/v3")
        )

    def load_cdr_config(self) -> CDRConfig:
        """Load CDR solution configuration"""
        return CDRConfig(
            glasswall_api_key=self.get_secret("glasswall-api-key", ""),
            glasswall_api_url=self.get_secret("glasswall-api-url", "https://api.glasswall.com/v1"),
            timeout_seconds=int(self.get_secret("cdr-timeout-seconds", "300"))
        )

    def load_vm_config(self) -> VMConfig:
        """Load VM configuration"""
        return VMConfig(
            vm_size=self.get_secret("test-vm-size", "Standard_D4s_v3"),
            os_disk_size_gb=int(self.get_secret("test-vm-disk-size", "128")),
            use_spot_instances=self.get_secret("use-spot-instances", "true").lower() == "true",
            spot_max_price=float(self.get_secret("spot-max-price", "-1.0")),
            admin_username=self.get_secret("test-vm-admin-username", "vmadmin"),
            admin_password=self.get_secret("test-vm-admin-password", "")
        )

    def load_test_config(self) -> TestConfig:
        """Load test execution configuration"""
        return TestConfig(
            interaction_duration_seconds=int(self.get_secret("interaction-duration-seconds", "180")),
            enable_user_simulation=self.get_secret("enable-user-simulation", "true").lower() == "true",
            auto_enable_macros=self.get_secret("auto-enable-macros", "true").lower() == "true",
            max_retries=int(self.get_secret("max-retries", "3")),
            timeout_seconds=int(self.get_secret("timeout-seconds", "600"))
        )

    def get_all_configs(self) -> Dict[str, Any]:
        """Load all configurations"""
        return {
            "azure": self.load_azure_config(),
            "wazuh": self.load_wazuh_config(),
            "edr": self.load_edr_config(),
            "av": self.load_av_config(),
            "cdr": self.load_cdr_config(),
            "vm": self.load_vm_config(),
            "test": self.load_test_config()
        }


# Singleton instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager(key_vault_url: Optional[str] = None) -> ConfigManager:
    """Get or create singleton configuration manager"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager(key_vault_url)
    return _config_manager
