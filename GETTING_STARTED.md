# Getting Started - CDR Validation Pipeline

This guide will walk you through setting up and running your first CDR validation test.

---

## Prerequisites Checklist

Before starting, ensure you have:

- [ ] Azure subscription with Contributor/Owner access
- [ ] Azure CLI installed and authenticated (`az login`)
- [ ] Terraform CLI installed (v1.0+)
- [ ] Python 3.11+ installed
- [ ] API credentials for:
  - [ ] CrowdStrike Falcon (Client ID + Secret)
  - [ ] SentinelOne (API Token + Console URL)
  - [ ] Sophos Central (API Key)
  - [ ] Glasswall CDR (API Key)
  - [ ] VirusTotal (API Key) - optional

---

## Step 1: Deploy Azure Infrastructure

### 1.1 Configure Terraform Variables

```bash
cd infrastructure/terraform

# Copy the example variables file
cp terraform.tfvars.example terraform.tfvars

# Edit with your values
nano terraform.tfvars
```

**Minimum required values:**
```hcl
# terraform.tfvars
subscription_id      = "your-azure-subscription-id"
location            = "eastus"
resource_group_name = "rg-cdr-validation"

# Security
sql_admin_password       = "YourSecurePassword123!"
wazuh_admin_password     = "YourSecurePassword456!"
test_vm_admin_password   = "YourSecurePassword789!"

# Your public IP for firewall rules
allowed_ip_ranges = ["YOUR.PUBLIC.IP.HERE/32"]

# Unique names (must be globally unique)
storage_account_name = "stcdrvalid12345"  # Must be unique
key_vault_name      = "kv-cdr-valid-12345" # Must be unique
sql_server_name     = "sql-cdr-valid-12345" # Must be unique
```

### 1.2 Deploy Infrastructure

```bash
# Initialize Terraform
terraform init

# Preview changes
terraform plan

# Deploy (takes ~10-15 minutes)
terraform apply -auto-approve
```

**What gets created:**
- Virtual Network with 3 subnets
- 2 Wazuh VMs (Manager + Indexer)
- Azure SQL Database
- Storage Account with 4 containers
- Key Vault for secrets
- Network Security Groups
- Log Analytics Workspace

### 1.3 Get Infrastructure Outputs

```bash
# Save important values
terraform output > ../outputs.txt

# Get Wazuh dashboard URL
terraform output wazuh_dashboard_url

# Get SQL server name
terraform output sql_server_fqdn
```

---

## Step 2: Configure Secrets

You have two options for storing secrets:

### Option A: Azure Key Vault (Recommended)

```bash
# Get Key Vault name
KV_NAME=$(terraform output -raw key_vault_name)

# Add EDR secrets
az keyvault secret set --vault-name $KV_NAME --name crowdstrike-client-id --value "YOUR_CS_CLIENT_ID"
az keyvault secret set --vault-name $KV_NAME --name crowdstrike-client-secret --value "YOUR_CS_SECRET"
az keyvault secret set --vault-name $KV_NAME --name crowdstrike-base-url --value "https://api.crowdstrike.com"

az keyvault secret set --vault-name $KV_NAME --name sentinelone-api-token --value "YOUR_S1_TOKEN"
az keyvault secret set --vault-name $KV_NAME --name sentinelone-console-url --value "https://your-console.sentinelone.net"

az keyvault secret set --vault-name $KV_NAME --name sophos-api-key --value "YOUR_SOPHOS_KEY"
az keyvault secret set --vault-name $KV_NAME --name sophos-api-url --value "https://api.central.sophos.com"

# Add CDR secrets
az keyvault secret set --vault-name $KV_NAME --name glasswall-api-key --value "YOUR_GLASSWALL_KEY"
az keyvault secret set --vault-name $KV_NAME --name glasswall-api-url --value "https://api.glasswall.com/v1"

# Add AV secrets
az keyvault secret set --vault-name $KV_NAME --name commercial-av-api-key --value "YOUR_VIRUSTOTAL_KEY"

# Add Wazuh secrets
az keyvault secret set --vault-name $KV_NAME --name wazuh-manager-ip --value "$(terraform output -raw wazuh_manager_private_ip)"
az keyvault secret set --vault-name $KV_NAME --name wazuh-indexer-ip --value "$(terraform output -raw wazuh_indexer_private_ip)"
az keyvault secret set --vault-name $KV_NAME --name wazuh-api-password --value "YOUR_WAZUH_PASSWORD"

# Add Azure config
az keyvault secret set --vault-name $KV_NAME --name azure-subscription-id --value "$(az account show --query id -o tsv)"
az keyvault secret set --vault-name $KV_NAME --name azure-resource-group --value "rg-cdr-validation"
az keyvault secret set --vault-name $KV_NAME --name azure-location --value "eastus"
```

### Option B: Environment Variables

```bash
# Create .env file
cat > .env <<EOF
# Azure
AZURE_SUBSCRIPTION_ID=$(az account show --query id -o tsv)
AZURE_RESOURCE_GROUP=rg-cdr-validation
AZURE_LOCATION=eastus
AZURE_KEY_VAULT_URL=https://${KV_NAME}.vault.azure.net/

# EDR
CROWDSTRIKE_CLIENT_ID=your_client_id
CROWDSTRIKE_CLIENT_SECRET=your_secret
CROWDSTRIKE_BASE_URL=https://api.crowdstrike.com

SENTINELONE_API_TOKEN=your_token
SENTINELONE_CONSOLE_URL=https://your-console.sentinelone.net

SOPHOS_API_KEY=your_key
SOPHOS_API_URL=https://api.central.sophos.com

# CDR
GLASSWALL_API_KEY=your_key
GLASSWALL_API_URL=https://api.glasswall.com/v1

# AV
COMMERCIAL_AV_API_KEY=your_virustotal_key

# Wazuh
WAZUH_MANAGER_IP=<from terraform output>
WAZUH_INDEXER_IP=<from terraform output>
WAZUH_API_PASSWORD=wazuh

# VM
TEST_VM_ADMIN_PASSWORD=YourSecurePassword789!
EOF

# Load environment
source .env
```

---

## Step 3: Install Python Dependencies

```bash
cd ../..  # Back to project root

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

---

## Step 4: Test Individual Components

Let me create a test script for you:

```bash
# Test each component individually
python scripts/test_connections.py
```

This will test:
- ✅ Azure authentication
- ✅ Wazuh API connection
- ✅ CrowdStrike API
- ✅ SentinelOne API
- ✅ Sophos API
- ✅ Glasswall CDR API
- ✅ VirusTotal API

---

## Step 5: Run Your First Test

### 5.1 Simple Test (Without VM)

Test the CDR and AV components without full VM provisioning:

```bash
# Test CDR on a clean file
python -m src.test_cdr_only --file samples/clean-document.pdf

# Test AV scanners
python -m src.test_av_only --file samples/eicar.txt
```

### 5.2 Full End-to-End Test

**⚠️ This will provision an Azure VM and incur costs ($0.05-0.10 per test)**

```bash
# Run full pipeline on a test file
python -m src.run_test --file samples/test-document.docx
```

**What happens:**
1. Provisions Azure VM (~3 min)
2. Deploys EDR agents (~5 min)
3. Copies file to VM
4. Executes file with user simulation (~3 min)
5. Collects alerts from Wazuh/EDR consoles
6. Processes file through Glasswall CDR
7. Repeats steps 1-5 with sanitized file
8. Compares results and shows alert reduction
9. Cleans up VM

**Total time:** ~20-25 minutes per test

---

## Step 6: View Results

### Console Output
Results are printed to console:

```
================================================================================
CDR VALIDATION TEST RESULTS
================================================================================
Test Run ID: 550e8400-e29b-41d4-a716-446655440000
File: suspicious-document.docx (sha256: abc123...)

PRE-CDR RESULTS:
  - Total EDR Alerts: 23
    • CrowdStrike: 8
    • SentinelOne: 10
    • Sophos: 5
  - Total AV Detections: 3
  - Wazuh Alerts: 35

CDR PROCESSING:
  - Status: Success
  - Processing Time: 12.3s
  - File Size: 245KB → 198KB (19% reduction)

POST-CDR RESULTS:
  - Total EDR Alerts: 2
    • CrowdStrike: 1
    • SentinelOne: 1
    • Sophos: 0
  - Total AV Detections: 0
  - Wazuh Alerts: 3

COMPARISON:
  ✅ EDR Alert Reduction: 91.30% (23 → 2)
  ✅ AV Detection Reduction: 100.00% (3 → 0)
  ✅ Wazuh Alert Reduction: 91.43% (35 → 3)

💰 Cost: $0.08 (Spot VM: 23 mins)
================================================================================
```

### Database
Results are also stored in Azure SQL:

```bash
# Query results
sqlcmd -S $(terraform output -raw sql_server_fqdn) \
       -U sqladmin \
       -d cdr-metrics \
       -Q "SELECT * FROM test_runs ORDER BY start_time DESC"
```

---

## Common Issues & Troubleshooting

### Issue: Terraform fails with "name already exists"

**Solution:** Storage, Key Vault, and SQL names must be globally unique. Add a random suffix:

```hcl
storage_account_name = "stcdrvalid${random.integer.value}"
```

### Issue: Can't access Wazuh dashboard

**Solutions:**
1. Check your IP is in allowed_ip_ranges
2. Verify Wazuh VM is running: `az vm list -g rg-cdr-validation -o table`
3. SSH to Wazuh and check services: `systemctl status wazuh-manager`

### Issue: EDR API authentication fails

**Solutions:**
1. Verify API credentials are correct
2. Check Key Vault access policies: `az keyvault show --name $KV_NAME`
3. Test manually: `curl -H "x-api-key: YOUR_KEY" https://api.example.com/test`

### Issue: Python import errors

**Solution:** Make sure you're in the virtual environment and installed all dependencies:

```bash
source venv/bin/activate
pip install -r requirements.txt --upgrade
```

### Issue: VM provisioning fails

**Solutions:**
1. Check Azure quota: `az vm list-usage --location eastus -o table`
2. Try different VM size: Edit `TEST_VM_SIZE` env var
3. Disable Spot instances: Set `USE_SPOT_INSTANCES=false`

---

## Cost Optimization Tips

**Current costs (~$350-450/month):**
- Wazuh VMs: $300-400 (always-on)
- SQL Database: $15
- Storage: $20
- Test VMs: $5-10/month (Spot instances, sequential)

**To reduce costs:**

1. **Auto-shutdown Wazuh VMs when not testing:**
   ```bash
   # Stop VMs
   az vm deallocate -g rg-cdr-validation -n wazuh-manager
   az vm deallocate -g rg-cdr-validation -n wazuh-indexer

   # Start when needed
   az vm start -g rg-cdr-validation -n wazuh-manager
   az vm start -g rg-cdr-validation -n wazuh-indexer
   ```

2. **Use lower SQL tier:**
   - Basic tier: $5/month
   - Change in Terraform: `sku_name = "Basic"`

3. **Process files in batches:**
   - Sequential processing keeps only 1 VM running at a time

4. **Use Azure Reserved Instances:**
   - 30-50% savings for Wazuh VMs if running 24/7

---

## Next Steps

Once basic tests work:

1. **Create sample test files:**
   ```bash
   mkdir samples
   # Add test files (PDFs, Office docs, executables)
   ```

2. **Set up Azure DevOps pipeline:**
   - Trigger on blob upload to `input-files` container
   - Automatically run test pipeline
   - Store results in SQL

3. **Create dashboard:**
   - Power BI or Grafana
   - Visualize alert reduction trends
   - Track CDR effectiveness over time

4. **Scale up:**
   - Process multiple files in parallel
   - Add more EDR vendors
   - Expand file type coverage

---

## Support & Documentation

- **Implementation Details:** See `IMPLEMENTATION_STATUS.md`
- **Architecture:** See `README.md`
- **Terraform Docs:** See `infrastructure/terraform/README.md` (if exists)
- **API Docs:** See `docs/api-documentation.md` (if exists)

For issues, check logs:
```bash
# Application logs
tail -f logs/cdr-pipeline.log

# Azure Activity Log
az monitor activity-log list -g rg-cdr-validation --offset 1h

# Wazuh logs
ssh wazuhadmin@<wazuh-ip>
tail -f /var/ossec/logs/ossec.log
```

---

## Quick Command Reference

```bash
# Deploy infrastructure
cd infrastructure/terraform && terraform apply

# Run test
python -m src.run_test --file myfile.pdf

# Check Wazuh status
curl -k -u wazuh:wazuh https://<wazuh-ip>:55000/

# List test VMs
az vm list -g rg-cdr-validation --query "[?tags.purpose=='cdr-testing']" -o table

# Delete all test VMs
az vm delete -g rg-cdr-validation --ids $(az vm list -g rg-cdr-validation --query "[?tags.purpose=='cdr-testing'].id" -o tsv) -y

# Query test results
sqlcmd -S <sql-server>.database.windows.net -U sqladmin -d cdr-metrics -Q "SELECT * FROM vw_test_run_summary"

# Check costs
az consumption usage list --start-date 2025-11-01 --end-date 2025-11-14
```

---

## Ready to Start!

You're all set! Start with Step 1 (Deploy Infrastructure) if you haven't already, then work through each step sequentially.

**Recommended First Test:**
- Use a clean PDF file for your first run
- This ensures everything works before testing with actual malware
- Example: Any normal PDF document from your computer
