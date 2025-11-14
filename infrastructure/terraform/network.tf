# Network Infrastructure for CDR Validation

# Virtual Network
resource "azurerm_virtual_network" "main" {
  name                = "vnet-cdr-${var.environment}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  address_space       = var.vnet_address_space
  tags                = var.project_tags
}

# Wazuh Subnet (persistent infrastructure)
resource "azurerm_subnet" "wazuh" {
  name                 = "snet-wazuh"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = [var.wazuh_subnet_prefix]

  # Service endpoints for secure access to Azure services
  service_endpoints = [
    "Microsoft.Storage",
    "Microsoft.Sql",
    "Microsoft.KeyVault"
  ]
}

# Test VM Subnet (ephemeral, isolated for malware testing)
resource "azurerm_subnet" "test_vms" {
  name                 = "snet-test-vms"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = [var.test_vm_subnet_prefix]

  # Service endpoints
  service_endpoints = [
    "Microsoft.Storage"
  ]
}

# Management Subnet (for DevOps agents, bastion, etc.)
resource "azurerm_subnet" "management" {
  name                 = "snet-management"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = [var.management_subnet_prefix]

  service_endpoints = [
    "Microsoft.Storage",
    "Microsoft.Sql",
    "Microsoft.KeyVault"
  ]
}

# Network Security Group for Wazuh Subnet
resource "azurerm_network_security_group" "wazuh" {
  name                = "nsg-wazuh-${var.environment}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = var.project_tags

  # Wazuh Agent Communication (from test VMs)
  security_rule {
    name                       = "Allow-Wazuh-Agent"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "1514-1515"
    source_address_prefix      = var.test_vm_subnet_prefix
    destination_address_prefix = "*"
  }

  # Wazuh API (from management subnet)
  security_rule {
    name                       = "Allow-Wazuh-API"
    priority                   = 110
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "55000"
    source_address_prefix      = var.management_subnet_prefix
    destination_address_prefix = "*"
  }

  # Wazuh Dashboard (from allowed IPs)
  security_rule {
    name                       = "Allow-Wazuh-Dashboard"
    priority                   = 120
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "443"
    source_address_prefixes    = var.allowed_ip_ranges
    destination_address_prefix = "*"
  }

  # SSH for management
  security_rule {
    name                       = "Allow-SSH"
    priority                   = 130
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "22"
    source_address_prefixes    = var.allowed_ip_ranges
    destination_address_prefix = "*"
  }

  # Deny all other inbound
  security_rule {
    name                       = "Deny-All-Inbound"
    priority                   = 1000
    direction                  = "Inbound"
    access                     = "Deny"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }

  # Allow outbound to test VMs (for agent management)
  security_rule {
    name                       = "Allow-Test-VMs-Outbound"
    priority                   = 100
    direction                  = "Outbound"
    access                     = "Allow"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = "*"
    destination_address_prefix = var.test_vm_subnet_prefix
  }

  # Allow outbound to Azure services
  security_rule {
    name                       = "Allow-Azure-Services"
    priority                   = 110
    direction                  = "Outbound"
    access                     = "Allow"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = "*"
    destination_address_prefix = "AzureCloud"
  }

  # Allow outbound for updates and package management
  security_rule {
    name                       = "Allow-Internet-Outbound"
    priority                   = 120
    direction                  = "Outbound"
    access                     = "Allow"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = "*"
    destination_address_prefix = "Internet"
  }
}

# Network Security Group for Test VMs (highly restricted)
resource "azurerm_network_security_group" "test_vms" {
  name                = "nsg-test-vms-${var.environment}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = var.project_tags

  # Allow Wazuh agent communication to Wazuh subnet
  security_rule {
    name                       = "Allow-Wazuh-Outbound"
    priority                   = 100
    direction                  = "Outbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_ranges    = ["1514", "1515", "55000"]
    source_address_prefix      = "*"
    destination_address_prefix = var.wazuh_subnet_prefix
  }

  # Allow Azure Storage access (for file retrieval)
  security_rule {
    name                       = "Allow-Storage-Outbound"
    priority                   = 110
    direction                  = "Outbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "443"
    source_address_prefix      = "*"
    destination_address_prefix = "Storage"
  }

  # Allow management from management subnet
  security_rule {
    name                       = "Allow-Management-Inbound"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = var.management_subnet_prefix
    destination_address_prefix = "*"
  }

  # DENY ALL INTERNET ACCESS (critical for malware containment)
  security_rule {
    name                       = "Deny-Internet-Outbound"
    priority                   = 1000
    direction                  = "Outbound"
    access                     = "Deny"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = "*"
    destination_address_prefix = "Internet"
  }

  # Deny all other inbound
  security_rule {
    name                       = "Deny-All-Inbound"
    priority                   = 1000
    direction                  = "Inbound"
    access                     = "Deny"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }
}

# Network Security Group for Management Subnet
resource "azurerm_network_security_group" "management" {
  name                = "nsg-management-${var.environment}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = var.project_tags

  # Allow RDP/SSH from allowed IPs
  security_rule {
    name                       = "Allow-RDP"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "3389"
    source_address_prefixes    = var.allowed_ip_ranges
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "Allow-SSH"
    priority                   = 110
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "22"
    source_address_prefixes    = var.allowed_ip_ranges
    destination_address_prefix = "*"
  }

  # Allow all outbound (management needs full access)
  security_rule {
    name                       = "Allow-All-Outbound"
    priority                   = 100
    direction                  = "Outbound"
    access                     = "Allow"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }
}

# Associate NSGs with Subnets
resource "azurerm_subnet_network_security_group_association" "wazuh" {
  subnet_id                 = azurerm_subnet.wazuh.id
  network_security_group_id = azurerm_network_security_group.wazuh.id
}

resource "azurerm_subnet_network_security_group_association" "test_vms" {
  subnet_id                 = azurerm_subnet.test_vms.id
  network_security_group_id = azurerm_network_security_group.test_vms.id
}

resource "azurerm_subnet_network_security_group_association" "management" {
  subnet_id                 = azurerm_subnet.management.id
  network_security_group_id = azurerm_network_security_group.management.id
}

# Network Watcher (for traffic analytics and diagnostics)
resource "azurerm_network_watcher" "main" {
  name                = "nw-cdr-${var.environment}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = var.project_tags
}

# NSG Flow Logs for security monitoring
resource "azurerm_network_watcher_flow_log" "test_vms" {
  name                 = "fl-test-vms-${var.environment}"
  network_watcher_name = azurerm_network_watcher.main.name
  resource_group_name  = azurerm_resource_group.main.name

  network_security_group_id = azurerm_network_security_group.test_vms.id
  storage_account_id        = azurerm_storage_account.main.id
  enabled                   = true
  retention_policy {
    enabled = true
    days    = var.log_retention_days
  }

  traffic_analytics {
    enabled               = true
    workspace_id          = azurerm_log_analytics_workspace.main.workspace_id
    workspace_region      = azurerm_log_analytics_workspace.main.location
    workspace_resource_id = azurerm_log_analytics_workspace.main.id
    interval_in_minutes   = 10
  }

  tags = var.project_tags
}
