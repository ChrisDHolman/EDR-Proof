# Variables for Azure CDR Validation Infrastructure

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "prod"
}

variable "location" {
  description = "Azure region for resources"
  type        = string
  default     = "eastus"
}

variable "resource_group_name" {
  description = "Resource group name"
  type        = string
  default     = "rg-cdr-validation"
}

variable "project_tags" {
  description = "Common tags for all resources"
  type        = map(string)
  default = {
    Project     = "CDR-Validation"
    ManagedBy   = "Terraform"
    CostCenter  = "Security"
    Environment = "Production"
  }
}

# Network Configuration
variable "vnet_address_space" {
  description = "Address space for the virtual network"
  type        = list(string)
  default     = ["10.0.0.0/16"]
}

variable "wazuh_subnet_prefix" {
  description = "Subnet prefix for Wazuh infrastructure"
  type        = string
  default     = "10.0.1.0/24"
}

variable "test_vm_subnet_prefix" {
  description = "Subnet prefix for test VMs"
  type        = string
  default     = "10.0.2.0/24"
}

variable "management_subnet_prefix" {
  description = "Subnet prefix for management/bastion"
  type        = string
  default     = "10.0.3.0/24"
}

# Wazuh VM Configuration
variable "wazuh_manager_vm_size" {
  description = "VM size for Wazuh Manager"
  type        = string
  default     = "Standard_D4s_v3" # 4 vCPU, 16 GB RAM
}

variable "wazuh_indexer_vm_size" {
  description = "VM size for Wazuh Indexer"
  type        = string
  default     = "Standard_D8s_v3" # 8 vCPU, 32 GB RAM (Elasticsearch needs memory)
}

variable "wazuh_admin_username" {
  description = "Admin username for Wazuh VMs"
  type        = string
  default     = "wazuhadmin"
  sensitive   = true
}

variable "wazuh_admin_password" {
  description = "Admin password for Wazuh VMs"
  type        = string
  sensitive   = true
}

# Test VM Configuration
variable "test_vm_size" {
  description = "VM size for test VMs (Spot instances)"
  type        = string
  default     = "Standard_D4s_v3" # 4 vCPU, 16 GB RAM
}

variable "test_vm_os_disk_size" {
  description = "OS disk size in GB for test VMs"
  type        = number
  default     = 128
}

variable "test_vm_image" {
  description = "OS image for test VMs"
  type = object({
    publisher = string
    offer     = string
    sku       = string
    version   = string
  })
  default = {
    publisher = "MicrosoftWindowsServer"
    offer     = "WindowsServer"
    sku       = "2022-datacenter"
    version   = "latest"
  }
}

# Storage Account Configuration
variable "storage_account_name" {
  description = "Name for the storage account (must be globally unique)"
  type        = string
  default     = "stcdrvalidation"
}

variable "storage_account_tier" {
  description = "Storage account tier"
  type        = string
  default     = "Standard"
}

variable "storage_account_replication" {
  description = "Storage account replication type"
  type        = string
  default     = "LRS" # Locally Redundant Storage (cost-optimized)
}

# SQL Database Configuration
variable "sql_server_name" {
  description = "Name for Azure SQL Server"
  type        = string
  default     = "sql-cdr-validation"
}

variable "sql_database_name" {
  description = "Name for Azure SQL Database"
  type        = string
  default     = "cdr-metrics"
}

variable "sql_admin_username" {
  description = "SQL Server admin username"
  type        = string
  default     = "sqladmin"
  sensitive   = true
}

variable "sql_admin_password" {
  description = "SQL Server admin password"
  type        = string
  sensitive   = true
}

variable "sql_sku" {
  description = "SQL Database SKU"
  type        = string
  default     = "S1" # Standard tier (cost-optimized)
}

# Key Vault Configuration
variable "key_vault_name" {
  description = "Name for Azure Key Vault"
  type        = string
  default     = "kv-cdr-validation"
}

variable "key_vault_sku" {
  description = "Key Vault SKU"
  type        = string
  default     = "standard"
}

# API Credentials (stored in Key Vault)
variable "crowdstrike_client_id" {
  description = "CrowdStrike Falcon API Client ID"
  type        = string
  sensitive   = true
  default     = ""
}

variable "crowdstrike_client_secret" {
  description = "CrowdStrike Falcon API Client Secret"
  type        = string
  sensitive   = true
  default     = ""
}

variable "sentinelone_api_token" {
  description = "SentinelOne API Token"
  type        = string
  sensitive   = true
  default     = ""
}

variable "sophos_api_key" {
  description = "Sophos API Key"
  type        = string
  sensitive   = true
  default     = ""
}

variable "glasswall_api_key" {
  description = "Glasswall CDR API Key"
  type        = string
  sensitive   = true
  default     = ""
}

variable "glasswall_api_url" {
  description = "Glasswall CDR API URL"
  type        = string
  default     = "https://api.glasswall.com/v1"
}

variable "commercial_av_api_key" {
  description = "Commercial AV API Key (e.g., VirusTotal)"
  type        = string
  sensitive   = true
  default     = ""
}

# Cost Optimization
variable "enable_spot_instances" {
  description = "Use Spot instances for test VMs"
  type        = bool
  default     = true
}

variable "spot_max_price" {
  description = "Maximum price for Spot instances (-1 for pay-as-you-go)"
  type        = number
  default     = -1
}

variable "auto_shutdown_time" {
  description = "Auto-shutdown time for VMs (HHmm format, e.g., 1900 for 7 PM)"
  type        = string
  default     = "1900"
}

# Monitoring and Logging
variable "log_analytics_workspace_name" {
  description = "Name for Log Analytics Workspace"
  type        = string
  default     = "log-cdr-validation"
}

variable "log_retention_days" {
  description = "Log retention in days"
  type        = number
  default     = 30
}

# DevOps Configuration
variable "devops_service_principal_object_id" {
  description = "Azure DevOps Service Principal Object ID for Key Vault access"
  type        = string
  default     = ""
}

variable "allowed_ip_ranges" {
  description = "Allowed IP ranges for accessing resources (e.g., your office IP)"
  type        = list(string)
  default     = ["0.0.0.0/0"] # CHANGE THIS IN PRODUCTION
}
