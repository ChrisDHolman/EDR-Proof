# Quick Start Commands

Copy-paste these commands to get started quickly.

---

## 1. Deploy Infrastructure (First Time Only)

```bash
cd infrastructure/terraform

# Configure your values
cp terraform.tfvars.example terraform.tfvars
nano terraform.tfvars  # Edit with your Azure subscription details

# Deploy (~10-15 minutes)
terraform init
terraform apply -auto-approve

# Save outputs for later
terraform output > ../outputs.txt
```

---

## 2. Configure Secrets

### Option A: Quick Setup with Key Vault

```bash
# Get Key Vault name from Terraform
export KV_NAME=$(terraform output -raw key_vault_name)

# Set EDR secrets (replace with your actual values)
az keyvault secret set --vault-name $KV_NAME --name crowdstrike-client-id --value "YOUR_VALUE_HERE"
az keyvault secret set --vault-name $KV_NAME --name crowdstrike-client-secret --value "YOUR_VALUE_HERE"
az keyvault secret set --vault-name $KV_NAME --name sentinelone-api-token --value "YOUR_VALUE_HERE"
az keyvault secret set --vault-name $KV_NAME --name sentinelone-console-url --value "YOUR_VALUE_HERE"
az keyvault secret set --vault-name $KV_NAME --name sophos-api-key --value "YOUR_VALUE_HERE"

# Set CDR secret
az keyvault secret set --vault-name $KV_NAME --name glasswall-api-key --value "YOUR_VALUE_HERE"

# Set AV secret (optional)
az keyvault secret set --vault-name $KV_NAME --name commercial-av-api-key --value "YOUR_VIRUSTOTAL_KEY"

# Set Wazuh secrets
az keyvault secret set --vault-name $KV_NAME --name wazuh-manager-ip --value "$(terraform output -raw wazuh_manager_private_ip)"
az keyvault secret set --vault-name $KV_NAME --name wazuh-api-password --value "wazuh"

# Set Azure config
az keyvault secret set --vault-name $KV_NAME --name azure-subscription-id --value "$(az account show --query id -o tsv)"
az keyvault secret set --vault-name $KV_NAME --name azure-resource-group --value "rg-cdr-validation"
```

### Option B: Quick Setup with .env File

```bash
cd ../..  # Back to project root

cat > .env <<'EOF'
# Azure
export AZURE_SUBSCRIPTION_ID=$(az account show --query id -o tsv)
export AZURE_RESOURCE_GROUP=rg-cdr-validation
export AZURE_LOCATION=eastus

# EDR - REPLACE WITH YOUR VALUES
export CROWDSTRIKE_CLIENT_ID=your_client_id
export CROWDSTRIKE_CLIENT_SECRET=your_secret
export SENTINELONE_API_TOKEN=your_token
export SENTINELONE_CONSOLE_URL=https://your-console.sentinelone.net
export SOPHOS_API_KEY=your_key

# CDR - REPLACE WITH YOUR VALUES
export GLASSWALL_API_KEY=your_glasswall_key

# AV (optional)
export COMMERCIAL_AV_API_KEY=your_virustotal_key

# Wazuh (get from terraform output)
export WAZUH_MANAGER_IP=10.0.1.4
export WAZUH_API_PASSWORD=wazuh

# VM
export TEST_VM_ADMIN_PASSWORD=YourSecurePassword789!
EOF

# Edit the file with your actual values
nano .env

# Load variables
source .env
```

---

## 3. Install Python Dependencies

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies (~2-3 minutes)
pip install -r requirements.txt
```

---

## 4. Test Connections

```bash
# Test all API connections
python scripts/test_connections.py
```

**Expected output:**
```
✅ PASS       Azure
✅ PASS       Wazuh
✅ PASS       CrowdStrike
✅ PASS       SentinelOne
✅ PASS       Sophos
✅ PASS       Glasswall CDR
✅ PASS       VirusTotal

Total: 7 passed, 0 failed, 0 skipped
```

---

## 5. Run Your First Test

### Create a test file

```bash
# Create samples directory
mkdir -p samples

# Download a clean PDF for testing
curl -o samples/test.pdf https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf

# Or create a simple text file
echo "This is a test file" > samples/test.txt
```

### Run the test

```bash
# Dry run (validates configuration without running)
python scripts/run_test.py --file samples/test.pdf --dry-run

# Full test (provisions VMs, costs ~$0.05-0.10)
python scripts/run_test.py --file samples/test.pdf
```

---

## Common Commands

### Check infrastructure status
```bash
cd infrastructure/terraform

# List all resources
terraform state list

# Show specific resource
terraform show

# Get outputs
terraform output
```

### Check Wazuh
```bash
# Get Wazuh IP
WAZUH_IP=$(terraform output -raw wazuh_manager_public_ip 2>/dev/null || terraform output -raw wazuh_manager_private_ip)

# Check Wazuh API
curl -k -u wazuh:wazuh https://$WAZUH_IP:55000/

# SSH to Wazuh (if public IP exists)
ssh wazuhadmin@$WAZUH_IP

# Check Wazuh services (from SSH)
sudo systemctl status wazuh-manager
sudo systemctl status wazuh-indexer
```

### Check test VMs
```bash
# List all VMs
az vm list -g rg-cdr-validation -o table

# List only test VMs
az vm list -g rg-cdr-validation \
  --query "[?tags.purpose=='cdr-testing'].{Name:name,Status:provisioningState,Created:tags.created}" \
  -o table

# Delete all test VMs (cleanup)
az vm delete -g rg-cdr-validation \
  --ids $(az vm list -g rg-cdr-validation \
    --query "[?tags.purpose=='cdr-testing'].id" -o tsv) \
  -y --no-wait
```

### Check costs
```bash
# Current month costs
az consumption usage list \
  --start-date $(date -d "$(date +%Y-%m-01)" +%Y-%m-%d) \
  --end-date $(date +%Y-%m-%d) \
  --query "[?contains(instanceName, 'cdr')].{Resource:instanceName,Cost:pretaxCost}" \
  -o table

# Or use Azure Portal
echo "View costs: https://portal.azure.com/#view/Microsoft_Azure_CostManagement/Menu/~/costanalysis"
```

### Query results database
```bash
# Get SQL server name
SQL_SERVER=$(terraform output -raw sql_server_fqdn)

# Query recent test runs
sqlcmd -S $SQL_SERVER -U sqladmin -d cdr-metrics \
  -Q "SELECT TOP 10 test_run_id, file_name, phase, total_edr_alerts, total_av_detections FROM test_runs ORDER BY start_time DESC"

# Get summary stats
sqlcmd -S $SQL_SERVER -U sqladmin -d cdr-metrics \
  -Q "SELECT * FROM vw_test_run_summary"
```

---

## Cleanup Commands

### Stop Wazuh VMs (save costs when not testing)
```bash
cd infrastructure/terraform

# Stop VMs
az vm deallocate -g rg-cdr-validation -n wazuh-manager --no-wait
az vm deallocate -g rg-cdr-validation -n wazuh-indexer --no-wait

# Start when needed
az vm start -g rg-cdr-validation -n wazuh-manager --no-wait
az vm start -g rg-cdr-validation -n wazuh-indexer --no-wait
```

### Destroy everything (⚠️ IRREVERSIBLE)
```bash
cd infrastructure/terraform

# Destroy all infrastructure
terraform destroy -auto-approve
```

---

## Troubleshooting Commands

### Check Python environment
```bash
# Verify virtual environment is active
which python

# Should show: /path/to/edr-proof/venv/bin/python

# Check installed packages
pip list | grep -E "(azure|falconpy|requests)"

# Reinstall if needed
pip install -r requirements.txt --upgrade --force-reinstall
```

### Check Azure authentication
```bash
# Check current account
az account show

# Login if needed
az login

# Set subscription
az account set --subscription "your-subscription-id"
```

### Check logs
```bash
# Application logs (if logging to file)
tail -f logs/cdr-pipeline.log

# Azure activity log
az monitor activity-log list \
  -g rg-cdr-validation \
  --offset 1h \
  --query "[].{Time:eventTimestamp,Operation:operationName.localizedValue,Status:status.localizedValue}" \
  -o table

# Wazuh logs (from SSH)
ssh wazuhadmin@$WAZUH_IP
sudo tail -f /var/ossec/logs/ossec.log
sudo tail -f /var/ossec/logs/api.log
```

### Reset everything and start fresh
```bash
# 1. Destroy infrastructure
cd infrastructure/terraform
terraform destroy -auto-approve

# 2. Clean Python environment
cd ../..
deactivate
rm -rf venv

# 3. Start over from Step 1
```

---

## Next Steps After First Successful Test

1. **Add more test files:**
   ```bash
   # Add various file types to samples/
   cp /path/to/your/files/* samples/
   ```

2. **Batch testing:**
   ```bash
   # Test multiple files
   for file in samples/*; do
     python scripts/run_test.py --file "$file"
   done
   ```

3. **Set up Azure DevOps:**
   - Create pipeline from `pipelines/azure-pipelines.yml` (when created)
   - Trigger on blob upload to storage account

4. **View results:**
   - Query SQL database for trends
   - Create Power BI dashboard
   - Export to Excel

---

## Support

- **Detailed Setup:** See `GETTING_STARTED.md`
- **Implementation Details:** See `IMPLEMENTATION_STATUS.md`
- **Project Overview:** See `README.md`

For issues:
1. Check logs (commands above)
2. Verify all secrets are configured
3. Test individual components with `test_connections.py`
4. Check Azure portal for resource status
