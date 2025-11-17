# Terraform Outputs

output "resource_group_name" {
  description = "Name of the resource group"
  value       = azurerm_resource_group.main.name
}

output "resource_group_location" {
  description = "Location of the resource group"
  value       = azurerm_resource_group.main.location
}

output "vnet_name" {
  description = "Name of the virtual network"
  value       = azurerm_virtual_network.main.name
}

output "vnet_id" {
  description = "ID of the virtual network"
  value       = azurerm_virtual_network.main.id
}

output "test_vm_subnet_id" {
  description = "Subnet ID for test VMs"
  value       = azurerm_subnet.test_vms.id
}

output "storage_account_name" {
  description = "Name of the storage account"
  value       = azurerm_storage_account.main.name
}

output "storage_account_primary_key" {
  description = "Primary access key for storage account"
  value       = azurerm_storage_account.main.primary_access_key
  sensitive   = true
}

output "storage_account_connection_string" {
  description = "Connection string for storage account"
  value       = azurerm_storage_account.main.primary_connection_string
  sensitive   = true
}

output "input_container_name" {
  description = "Name of the input files container"
  value       = azurerm_storage_container.input_files.name
}

output "output_container_name" {
  description = "Name of the output files container"
  value       = azurerm_storage_container.output_files.name
}

output "cdr_processed_container_name" {
  description = "Name of the CDR processed files container"
  value       = azurerm_storage_container.cdr_processed.name
}

output "key_vault_name" {
  description = "Name of the Key Vault"
  value       = azurerm_key_vault.main.name
}

output "key_vault_uri" {
  description = "URI of the Key Vault"
  value       = azurerm_key_vault.main.vault_uri
}

output "wazuh_manager_public_ip" {
  description = "Public IP address of Wazuh Manager"
  value       = azurerm_public_ip.wazuh_manager.ip_address
}

output "wazuh_manager_private_ip" {
  description = "Private IP address of Wazuh Manager"
  value       = azurerm_network_interface.wazuh_manager.private_ip_address
}

output "wazuh_indexer_public_ip" {
  description = "Public IP address of Wazuh Indexer"
  value       = azurerm_public_ip.wazuh_indexer.ip_address
}

output "wazuh_indexer_private_ip" {
  description = "Private IP address of Wazuh Indexer"
  value       = azurerm_network_interface.wazuh_indexer.private_ip_address
}

output "wazuh_dashboard_url" {
  description = "URL to access Wazuh Dashboard"
  value       = "https://${azurerm_public_ip.wazuh_manager.ip_address}"
}

output "sql_server_fqdn" {
  description = "Fully qualified domain name of SQL Server"
  value       = azurerm_mssql_server.main.fully_qualified_domain_name
}

output "sql_database_name" {
  description = "Name of the SQL Database"
  value       = azurerm_mssql_database.main.name
}

output "sql_connection_string" {
  description = "SQL Server connection string (without password)"
  value       = "Server=tcp:${azurerm_mssql_server.main.fully_qualified_domain_name},1433;Initial Catalog=${azurerm_mssql_database.main.name};User ID=${var.sql_admin_username};"
  sensitive   = true
}

output "log_analytics_workspace_id" {
  description = "ID of Log Analytics Workspace"
  value       = azurerm_log_analytics_workspace.main.workspace_id
}

output "wazuh_vm_ids" {
  description = "Virtual machine IDs for Wazuh infrastructure"
  value = {
    manager = azurerm_linux_virtual_machine.wazuh_manager.id
    indexer = azurerm_linux_virtual_machine.wazuh_indexer.id
  }
}

output "network_security_group_ids" {
  description = "Network Security Group IDs"
  value = {
    wazuh      = azurerm_network_security_group.wazuh.id
    test_vms   = azurerm_network_security_group.test_vms.id
    management = azurerm_network_security_group.management.id
  }
}

output "deployment_summary" {
  description = "Summary of deployed resources"
  value = {
    resource_group      = azurerm_resource_group.main.name
    location            = azurerm_resource_group.main.location
    wazuh_dashboard_url = "https://${azurerm_public_ip.wazuh_manager.ip_address}"
    wazuh_manager_ip    = azurerm_public_ip.wazuh_manager.ip_address
    storage_account     = azurerm_storage_account.main.name
    sql_server          = azurerm_mssql_server.main.name
    key_vault           = azurerm_key_vault.main.name
  }
}
