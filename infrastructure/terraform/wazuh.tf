# Wazuh SIEM Infrastructure

# Public IP for Wazuh Manager (for dashboard access)
resource "azurerm_public_ip" "wazuh_manager" {
  name                = "pip-wazuh-manager-${var.environment}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  allocation_method   = "Static"
  sku                 = "Standard"
  tags                = var.project_tags
}

# Public IP for Wazuh Indexer
resource "azurerm_public_ip" "wazuh_indexer" {
  name                = "pip-wazuh-indexer-${var.environment}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  allocation_method   = "Static"
  sku                 = "Standard"
  tags                = var.project_tags
}

# Network Interface for Wazuh Manager
resource "azurerm_network_interface" "wazuh_manager" {
  name                = "nic-wazuh-manager-${var.environment}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name

  ip_configuration {
    name                          = "internal"
    subnet_id                     = azurerm_subnet.wazuh.id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.wazuh_manager.id
  }

  tags = var.project_tags
}

# Network Interface for Wazuh Indexer
resource "azurerm_network_interface" "wazuh_indexer" {
  name                = "nic-wazuh-indexer-${var.environment}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name

  ip_configuration {
    name                          = "internal"
    subnet_id                     = azurerm_subnet.wazuh.id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.wazuh_indexer.id
  }

  tags = var.project_tags
}

# Wazuh Manager VM
resource "azurerm_linux_virtual_machine" "wazuh_manager" {
  name                            = "vm-wazuh-manager-${var.environment}"
  location                        = azurerm_resource_group.main.location
  resource_group_name             = azurerm_resource_group.main.name
  size                            = var.wazuh_manager_vm_size
  admin_username                  = var.wazuh_admin_username
  disable_password_authentication = false
  admin_password                  = var.wazuh_admin_password
  network_interface_ids = [
    azurerm_network_interface.wazuh_manager.id
  ]

  os_disk {
    name                 = "osdisk-wazuh-manager"
    caching              = "ReadWrite"
    storage_account_type = "Premium_LRS"
    disk_size_gb         = 128
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "0001-com-ubuntu-server-jammy"
    sku       = "22_04-lts-gen2"
    version   = "latest"
  }

  # Custom data to bootstrap Wazuh installation
  custom_data = base64encode(templatefile("${path.module}/../scripts/wazuh-manager-init.sh", {
    wazuh_version  = "4.7.0"
    indexer_ip     = azurerm_network_interface.wazuh_indexer.private_ip_address
    storage_account = azurerm_storage_account.main.name
  }))

  boot_diagnostics {
    storage_account_uri = azurerm_storage_account.main.primary_blob_endpoint
  }

  identity {
    type = "SystemAssigned"
  }

  tags = merge(var.project_tags, {
    Role = "SIEM-Manager"
  })
}

# Wazuh Indexer VM (Elasticsearch-based)
resource "azurerm_linux_virtual_machine" "wazuh_indexer" {
  name                            = "vm-wazuh-indexer-${var.environment}"
  location                        = azurerm_resource_group.main.location
  resource_group_name             = azurerm_resource_group.main.name
  size                            = var.wazuh_indexer_vm_size
  admin_username                  = var.wazuh_admin_username
  disable_password_authentication = false
  admin_password                  = var.wazuh_admin_password
  network_interface_ids = [
    azurerm_network_interface.wazuh_indexer.id
  ]

  os_disk {
    name                 = "osdisk-wazuh-indexer"
    caching              = "ReadWrite"
    storage_account_type = "Premium_LRS"
    disk_size_gb         = 256 # Larger disk for Elasticsearch data
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "0001-com-ubuntu-server-jammy"
    sku       = "22_04-lts-gen2"
    version   = "latest"
  }

  # Custom data to bootstrap Wazuh Indexer installation
  custom_data = base64encode(templatefile("${path.module}/../scripts/wazuh-indexer-init.sh", {
    wazuh_version = "4.7.0"
    manager_ip    = azurerm_network_interface.wazuh_manager.private_ip_address
  }))

  boot_diagnostics {
    storage_account_uri = azurerm_storage_account.main.primary_blob_endpoint
  }

  identity {
    type = "SystemAssigned"
  }

  tags = merge(var.project_tags, {
    Role = "SIEM-Indexer"
  })
}

# Managed disk for Wazuh Indexer data (separate for performance)
resource "azurerm_managed_disk" "wazuh_indexer_data" {
  name                 = "disk-wazuh-indexer-data-${var.environment}"
  location             = azurerm_resource_group.main.location
  resource_group_name  = azurerm_resource_group.main.name
  storage_account_type = "Premium_LRS"
  create_option        = "Empty"
  disk_size_gb         = 512
  tags                 = var.project_tags
}

# Attach data disk to Indexer VM
resource "azurerm_virtual_machine_data_disk_attachment" "wazuh_indexer" {
  managed_disk_id    = azurerm_managed_disk.wazuh_indexer_data.id
  virtual_machine_id = azurerm_linux_virtual_machine.wazuh_indexer.id
  lun                = 0
  caching            = "ReadWrite"
}

# Azure Monitor VM Insights extension for Wazuh Manager
resource "azurerm_virtual_machine_extension" "wazuh_manager_monitor" {
  name                       = "AzureMonitorLinuxAgent"
  virtual_machine_id         = azurerm_linux_virtual_machine.wazuh_manager.id
  publisher                  = "Microsoft.Azure.Monitor"
  type                       = "AzureMonitorLinuxAgent"
  type_handler_version       = "1.0"
  auto_upgrade_minor_version = true
}

# Azure Monitor VM Insights extension for Wazuh Indexer
resource "azurerm_virtual_machine_extension" "wazuh_indexer_monitor" {
  name                       = "AzureMonitorLinuxAgent"
  virtual_machine_id         = azurerm_linux_virtual_machine.wazuh_indexer.id
  publisher                  = "Microsoft.Azure.Monitor"
  type                       = "AzureMonitorLinuxAgent"
  type_handler_version       = "1.0"
  auto_upgrade_minor_version = true
}

# Auto-shutdown schedule for cost optimization (optional, can be disabled)
resource "azurerm_dev_test_global_vm_shutdown_schedule" "wazuh_manager" {
  virtual_machine_id = azurerm_linux_virtual_machine.wazuh_manager.id
  location           = azurerm_resource_group.main.location
  enabled            = false # Set to true if you want auto-shutdown

  daily_recurrence_time = var.auto_shutdown_time
  timezone              = "Eastern Standard Time"

  notification_settings {
    enabled = false
  }
}

resource "azurerm_dev_test_global_vm_shutdown_schedule" "wazuh_indexer" {
  virtual_machine_id = azurerm_linux_virtual_machine.wazuh_indexer.id
  location           = azurerm_resource_group.main.location
  enabled            = false # Set to true if you want auto-shutdown

  daily_recurrence_time = var.auto_shutdown_time
  timezone              = "Eastern Standard Time"

  notification_settings {
    enabled = false
  }
}
