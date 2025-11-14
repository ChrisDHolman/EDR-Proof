# CDR Validation Pipeline - Setup Guide

## Overview

This guide will walk you through setting up the complete CDR validation infrastructure on Azure.

## Prerequisites

Before you begin, ensure you have:

1. **Azure Account**
   - Active Azure subscription with Owner or Contributor access
   - Azure CLI installed (`az --version`)
   - Logged in: `az login`

2. **Development Tools**
   - Terraform >= 1.5.0
   - Python >= 3.11
   - Git

3. **API Credentials**
   - CrowdStrike Falcon API credentials
   - SentinelOne API token
   - Sophos Central API key
   - Glasswall CDR API key
   - VirusTotal or other commercial AV API key (optional)

4. **Azure DevOps**
   - Azure DevOps organization
   - Project created
   - Service connection to Azure subscription

## Step 1: Clone and Prepare Repository

```bash
# Clone the repository
git clone <repository-url>
cd edr-proof

# Create Python virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt
```

## Step 2: Configure Terraform Variables

```bash
cd infrastructure/terraform

# Copy example variables file
cp terraform.tfvars.example terraform.tfvars

# Edit terraform.tfvars with your values
nano terraform.tfvars
```

### Required Variables

Update the following in `terraform.tfvars`:

```hcl
# Basic Configuration
environment         = "prod"
location            = "eastus"  # or your preferred region
resource_group_name = "rg-cdr-validation"

# Admin Credentials (CHANGE THESE!)
wazuh_admin_username = "wazuhadmin"
wazuh_admin_password = "YourStrongPasswordHere123!"

sql_admin_username = "sqladmin"
sql_admin_password = "YourStrongPasswordHere456!"

# API Credentials
crowdstrike_client_id     = "your_client_id"
crowdstrike_client_secret = "your_client_secret"
sentinelone_api_token     = "your_api_token"
sophos_api_key            = "your_api_key"
glasswall_api_key         = "your_api_key"
commercial_av_api_key     = "your_virustotal_key"

# Azure DevOps
devops_service_principal_object_id = "your_sp_object_id"

# Network Security (IMPORTANT: Change this to your IP)
allowed_ip_ranges = [
  "YOUR_IP_ADDRESS/32"  # Replace with your actual IP
]

# Storage & SQL (must be globally unique)
storage_account_name = "stcdrvalidationunique123"
key_vault_name       = "kv-cdr-validation-xyz"
sql_server_name      = "sql-cdr-validation-abc"
```

## Step 3: Deploy Infrastructure

```bash
# Initialize Terraform
terraform init

# Preview changes
terraform plan

# Deploy infrastructure (will take 15-20 minutes)
terraform apply

# Save outputs
terraform output > ../outputs.txt
```

### Important Outputs

After deployment, note these values:

- `wazuh_manager_public_ip`: For accessing Wazuh dashboard
- `wazuh_dashboard_url`: Direct URL to Wazuh UI
- `sql_server_fqdn`: For database connections
- `storage_account_name`: For file uploads
- `key_vault_name`: For secrets management

## Step 4: Configure Wazuh

### 4.1 Access Wazuh Dashboard

```bash
# Get Wazuh dashboard URL
terraform output wazuh_dashboard_url

# Default credentials:
# Username: wazuh
# Password: wazuh
```

**IMPORTANT**: Change default credentials immediately!

### 4.2 Run Wazuh Configuration Script

```bash
cd ../../infrastructure/scripts

# SSH into Wazuh Manager
WAZUH_IP=$(terraform output -raw wazuh_manager_public_ip)
ssh wazuhadmin@$WAZUH_IP

# On Wazuh Manager VM, check installation status
cat /root/wazuh-info.txt

# Verify services
sudo systemctl status wazuh-manager
sudo systemctl status wazuh-dashboard
```

### 4.3 Configure EDR Integrations

```bash
# Create custom integration scripts for each EDR
cd /var/ossec/integrations/custom

# CrowdStrike integration
sudo nano crowdstrike_integration.py
# (Implementation provided in src/integrations/edr/)

# SentinelOne integration
sudo nano sentinelone_integration.py

# Sophos integration
sudo nano sophos_integration.py

# Make executable
sudo chmod +x *.py
```

## Step 5: Initialize SQL Database

```bash
# From your local machine
cd src/metrics

# Install SQL command-line tools
# Linux: sudo apt-get install mssql-tools
# Mac: brew install msodbcsql17 mssql-tools
# Windows: Already included

# Get SQL connection details
SQL_SERVER=$(cd ../../infrastructure/terraform && terraform output -raw sql_server_fqdn)
SQL_ADMIN=$(cd ../../infrastructure/terraform && terraform output -raw sql_admin_username)

# Run schema creation
sqlcmd -S $SQL_SERVER -U $SQL_ADMIN -d cdr-metrics -i sql_schema.sql

# Verify tables created
sqlcmd -S $SQL_SERVER -U $SQL_ADMIN -d cdr-metrics -Q "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES"
```

## Step 6: Configure Azure DevOps Pipeline

### 6.1 Create Service Connection

1. Go to Azure DevOps Project Settings → Service Connections
2. Create new Azure Resource Manager connection
3. Use Service Principal authentication
4. Select your subscription and resource group
5. Name it: `azure-cdr-validation`

### 6.2 Add Pipeline Variables

In Azure DevOps, go to Pipelines → Library → Create Variable Group:

**Variable Group Name**: `cdr-validation-config`

Add these variables (link to Key Vault):
- `AZURE_KEY_VAULT_URL`
- `AZURE_SUBSCRIPTION_ID`
- `AZURE_RESOURCE_GROUP`
- `WAZUH_MANAGER_IP`
- `SQL_SERVER`
- `SQL_DATABASE`
- `STORAGE_ACCOUNT_NAME`

### 6.3 Import Pipeline

```bash
# In Azure DevOps
# Pipelines → New Pipeline → Azure Repos Git → Select repository
# Choose: Existing Azure Pipelines YAML file
# Path: /pipelines/azure-pipelines.yml
```

## Step 7: Test the Setup

### 7.1 Upload Test File

```bash
# Install Azure Storage tools
pip install azure-storage-blob

# Upload a test file
az storage blob upload \
  --account-name $(terraform output -raw storage_account_name) \
  --container-name input-files \
  --name test-file.pdf \
  --file /path/to/test-file.pdf
```

### 7.2 Run Pipeline Manually

1. Go to Azure DevOps Pipelines
2. Select the CDR validation pipeline
3. Click "Run pipeline"
4. Monitor execution

### 7.3 Verify Results

```bash
# Check SQL database for results
sqlcmd -S $SQL_SERVER -U $SQL_ADMIN -d cdr-metrics -Q "SELECT * FROM vw_test_run_summary"

# Check Wazuh for logs
# Access Wazuh Dashboard → Security Events

# Check storage for processed files
az storage blob list \
  --account-name $(terraform output -raw storage_account_name) \
  --container-name cdr-processed
```

## Step 8: Install EDR Agents

### CrowdStrike Falcon

```bash
# Download installer from CrowdStrike console
# Windows:
falcon-sensor-installer.exe /install /quiet CID=YOUR_CID

# Linux:
sudo dpkg -i falcon-sensor.deb
sudo /opt/CrowdStrike/falconctl -s -f --cid=YOUR_CID
sudo systemctl start falcon-sensor
```

### SentinelOne

```bash
# Download installer from SentinelOne console
# Windows:
SentinelInstaller.exe /q /site_token=YOUR_TOKEN

# Linux:
sudo dpkg -i sentinelone.deb
sudo sentinelctl management token set YOUR_TOKEN
sudo systemctl start sentinelone
```

### Sophos

```bash
# Download installer from Sophos Central
# Follow vendor-specific instructions
```

## Troubleshooting

### Terraform Deployment Issues

**Error: Name already exists**
- Storage account, Key Vault, and SQL server names must be globally unique
- Modify the names in `terraform.tfvars`

**Error: Insufficient permissions**
- Ensure your Azure account has Owner or Contributor role
- Service Principal needs proper RBAC assignments

### Wazuh Connection Issues

**Cannot access dashboard**
- Check NSG rules allow your IP
- Verify Wazuh services are running: `sudo systemctl status wazuh-*`
- Check firewall: `sudo ufw status`

**Agents not connecting**
- Verify agent can reach Wazuh Manager IP
- Check ports 1514, 1515 are open
- Review agent logs: `/var/ossec/logs/ossec.log`

### SQL Database Issues

**Cannot connect**
- Add your IP to SQL firewall rules
- Verify connection string
- Check if VNet rules are configured

**Schema creation fails**
- Ensure you're connected to correct database
- Check user permissions
- Review syntax for Azure SQL compatibility

### Pipeline Failures

**Authentication errors**
- Verify service connection is configured
- Check Key Vault access policies
- Ensure managed identity has permissions

**VM provisioning fails**
- Check subscription quotas
- Verify subnet has available IPs
- Review Azure Activity Log for errors

## Security Best Practices

1. **Change Default Passwords**
   - Wazuh (wazuh/wazuh)
   - SQL admin password
   - VM admin passwords

2. **Restrict Network Access**
   - Update `allowed_ip_ranges` to your specific IPs
   - Use VPN or Bastion for management access
   - Never expose Wazuh/SQL to 0.0.0.0/0

3. **Rotate Secrets**
   - Regularly rotate API keys
   - Use Key Vault for all secrets
   - Enable Key Vault audit logging

4. **Monitor Costs**
   - Set up Azure Cost Alerts
   - Review VM usage
   - Use Spot instances for test VMs
   - Delete unused resources

5. **Backup**
   - Enable SQL automated backups
   - Export important configurations
   - Document custom integrations

## Next Steps

1. **Customize File Interactions**: Edit `src/file_interaction/` scripts
2. **Add Custom Rules**: Configure Wazuh rules for your environment
3. **Scale Testing**: Increase parallel processing
4. **Build Dashboard**: Create Power BI reports from SQL data
5. **Automate**: Schedule regular test runs

## Support

- Check logs in Azure Monitor
- Review Wazuh documentation: https://documentation.wazuh.com
- Consult vendor documentation for EDR/AV/CDR products
- Review Azure DevOps pipeline logs

## Costs Estimate

Approximate monthly costs (eastus region):

- Wazuh VMs (D4 + D8, reserved): ~$300-400
- SQL Database (S1): ~$15
- Storage (1TB): ~$20
- Test VMs (Spot, <1 hour/day): ~$5-10
- Network egress: ~$5-10

**Total**: ~$350-450/month

To reduce costs:
- Use smaller VM sizes for Wazuh
- Auto-shutdown Wazuh VMs when not in use
- Use lower SQL tier (Basic)
- Process files in batches
