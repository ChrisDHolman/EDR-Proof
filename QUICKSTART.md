# Quick Start Guide - CDR Validation Pipeline

## What You Have Now

A complete DevOps automation pipeline for validating CDR (Content Disarm and Reconstruction) effectiveness across multiple EDR and AV solutions.

## Project Status

✅ **Completed (Phase 1 - Foundation)**:
- Complete Azure infrastructure as code (Terraform)
- Network architecture with isolated test environments
- Wazuh SIEM deployment automation
- Azure SQL database schema for metrics
- Python orchestration framework
- Configuration management with Key Vault integration
- Logging and monitoring utilities

🔨 **Next Steps (Phase 2 - Implementation)**:
- EDR integration modules (CrowdStrike, SentinelOne, Sophos)
- AV scanner modules (Defender, ClamAV, VirusTotal)
- File interaction engine
- CDR integration (Glasswall)
- VM lifecycle automation
- Azure DevOps pipeline definitions
- Metrics collection and analytics
- Reporting dashboard

## Quick Deploy (15 minutes)

### 1. Configure Credentials

```bash
cd infrastructure/terraform
cp terraform.tfvars.example terraform.tfvars
nano terraform.tfvars  # Add your API keys and passwords
```

**Minimum Required**:
- Azure subscription ID
- Wazuh admin password
- SQL admin password
- Your IP address (for firewall rules)

### 2. Deploy Infrastructure

```bash
terraform init
terraform apply
# Type 'yes' when prompted
```

**This will create**:
- Virtual Network with 3 subnets (Wazuh, Test VMs, Management)
- 2 Wazuh VMs (Manager + Indexer)
- Azure SQL Database
- Storage Account (4 containers)
- Key Vault with secrets
- Network Security Groups
- Log Analytics Workspace

### 3. Access Wazuh Dashboard

```bash
# Get the URL
terraform output wazuh_dashboard_url

# Default login: wazuh / wazuh
# CHANGE PASSWORD IMMEDIATELY!
```

### 4. Initialize Database

```bash
cd ../../src/metrics

# Get SQL server FQDN
SQL_SERVER=$(terraform -chdir=../../infrastructure/terraform output -raw sql_server_fqdn)

# Apply schema (requires sqlcmd)
sqlcmd -S $SQL_SERVER -U sqladmin -d cdr-metrics -i sql_schema.sql
```

## Architecture At a Glance

```
┌─────────────────────────────────────────────────────┐
│                  AZURE SUBSCRIPTION                 │
│                                                     │
│  ┌──────────────┐        ┌──────────────────┐     │
│  │   Storage    │        │  Wazuh VMs       │     │
│  │   Account    │◄──────►│  - Manager       │     │
│  │  (Blobs)     │        │  - Indexer       │     │
│  └──────┬───────┘        └────────▲─────────┘     │
│         │                         │                │
│  ┌──────▼─────────────────────────┴──────────┐    │
│  │     Azure DevOps Pipeline                 │    │
│  │  Pre-CDR → CDR → Post-CDR → Analytics     │    │
│  └────────────────┬──────────────────────────┘    │
│                   │                                │
│  ┌────────────────▼──────────────────────────┐    │
│  │  Test VMs (Isolated, Spot Instances)      │    │
│  │  - EDR Agents (CrowdStrike, S1, Sophos)   │    │
│  │  - AV Scanners (Defender, ClamAV)         │    │
│  │  - File Interaction Engine                │    │
│  └────────────────┬──────────────────────────┘    │
│                   │                                │
│  ┌────────────────▼──────────────────────────┐    │
│  │  Azure SQL Database (Metrics & Results)   │    │
│  └────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

## File Structure

```
edr-proof/
├── infrastructure/
│   ├── terraform/              # Azure IaC
│   │   ├── main.tf            # Core resources
│   │   ├── network.tf         # VNet, NSGs, subnets
│   │   ├── wazuh.tf          # Wazuh VMs
│   │   ├── database.tf        # SQL Database
│   │   ├── variables.tf       # Input variables
│   │   └── outputs.tf         # Export values
│   └── scripts/
│       ├── wazuh-manager-init.sh   # Wazuh Manager bootstrap
│       └── wazuh-indexer-init.sh   # Wazuh Indexer bootstrap
│
├── src/
│   ├── orchestrator/          # [TODO] Main pipeline controller
│   ├── integrations/          # [TODO] EDR, AV, CDR, SIEM clients
│   ├── file_interaction/      # [TODO] File execution engine
│   ├── metrics/
│   │   └── sql_schema.sql     # Database schema
│   └── utils/
│       ├── config.py          # Configuration management
│       ├── logger.py          # Logging utilities
│       └── helpers.py         # Helper functions
│
├── pipelines/                  # [TODO] Azure DevOps YAML
├── tests/                      # [TODO] Unit & integration tests
├── docs/
│   └── setup-guide.md         # Detailed setup instructions
│
├── README.md                   # Project overview
├── QUICKSTART.md              # This file
├── requirements.txt           # Python dependencies
└── .gitignore
```

## What Happens in a Test Run

1. **File Upload**: Place file in `input-files` blob container
2. **Pre-CDR Testing**:
   - Provision isolated Azure VM
   - Install EDR agents (CrowdStrike, SentinelOne, Sophos)
   - Deploy AV scanners (Defender, ClamAV, VirusTotal)
   - Deploy Wazuh agent
   - Copy file to VM
   - Execute/open file with user simulation (2-5 min)
   - Collect EDR alerts from Wazuh
   - Collect AV scan results
   - Store metrics in SQL
   - Teardown VM
3. **CDR Processing**: Send file to Glasswall API for sanitization
4. **Post-CDR Testing**: Repeat step 2 with sanitized file
5. **Analytics**: Compare pre vs post metrics, calculate ROI

## Key Metrics Tracked

- **EDR Alerts**: Count, severity, types (pre vs post)
- **AV Detections**: Threats found, false positives (pre vs post)
- **Alert Reduction**: Percentage decrease in noise
- **Processing Time**: Duration per file
- **Cost**: Azure VM costs per test
- **ROI Score**: Cost vs benefit analysis

## Common Commands

```bash
# Deploy/update infrastructure
cd infrastructure/terraform
terraform apply

# Destroy infrastructure (CAUTION!)
terraform destroy

# SSH to Wazuh Manager
terraform output wazuh_manager_public_ip
ssh wazuhadmin@<ip>

# Query test results
sqlcmd -S <sql-server> -U sqladmin -d cdr-metrics \
  -Q "SELECT * FROM vw_test_run_summary"

# Upload test file
az storage blob upload \
  --account-name <storage-account> \
  --container-name input-files \
  --name sample.pdf \
  --file sample.pdf

# Check logs
az monitor log-analytics query \
  --workspace <workspace-id> \
  --analytics-query "AzureActivity | take 10"
```

## Cost Optimization

**Current Setup** (~$350-450/month):
- Wazuh VMs: ~$300-400 (always on)
- SQL Database: ~$15
- Storage: ~$20
- Test VMs: ~$5-10 (Spot instances)

**To Reduce Costs**:
1. Auto-shutdown Wazuh VMs when not testing
2. Use Azure Reserved Instances (save 30-50%)
3. Lower SQL tier (Basic instead of Standard)
4. Process files in batches
5. Use managed Wazuh cloud instead of self-hosted

## Security Checklist

- [ ] Change default Wazuh password (wazuh/wazuh)
- [ ] Change SQL admin password
- [ ] Update `allowed_ip_ranges` to your IP only
- [ ] Enable Azure Key Vault audit logging
- [ ] Rotate API keys monthly
- [ ] Review NSG rules
- [ ] Enable SQL Advanced Threat Protection
- [ ] Configure Azure Cost Alerts
- [ ] Backup Wazuh configuration

## Troubleshooting

**Terraform fails with "name already exists"**
- Storage, Key Vault, SQL names must be globally unique
- Add random suffix in terraform.tfvars

**Cannot access Wazuh dashboard**
- Check NSG allows your IP
- Verify VM is running: `az vm list -g <resource-group>`
- Check Wazuh services: SSH in and run `systemctl status wazuh-*`

**Pipeline not working**
- Verify service connection in Azure DevOps
- Check Key Vault access policies
- Review pipeline logs

**High costs**
- Check for orphaned resources
- Ensure VMs are using Spot pricing
- Review Storage lifecycle policies

## Next Development Steps

To continue building out the pipeline:

1. **EDR Integrations**: Implement `src/integrations/edr/`
   - CrowdStrike Falcon API client
   - SentinelOne API client
   - Sophos Central API client

2. **AV Modules**: Implement `src/integrations/av/`
   - Windows Defender PowerShell wrapper
   - ClamAV CLI wrapper
   - VirusTotal API client

3. **File Interaction**: Implement `src/file_interaction/`
   - Smart file executor (based on file type)
   - Office macro enabler
   - User behavior simulator (mouse/keyboard)

4. **CDR Integration**: Implement `src/integrations/cdr/`
   - Glasswall API client
   - File upload/download handlers

5. **VM Automation**: Implement `src/orchestrator/vm_manager.py`
   - VM provisioning with Azure SDK
   - Snapshot management
   - Automatic teardown

6. **Pipeline**: Create `pipelines/azure-pipelines.yml`
   - Define stages and jobs
   - Add service connection
   - Configure variables

## Resources

- **Azure Terraform**: https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs
- **Wazuh Docs**: https://documentation.wazuh.com
- **CrowdStrike API**: https://falcon.crowdstrike.com/documentation
- **SentinelOne API**: https://usea1-partners.sentinelone.net/api-doc/overview
- **Glasswall CDR**: https://docs.glasswall.com

## Support

Check the detailed setup guide: `docs/setup-guide.md`

For issues:
1. Check Azure Activity Log
2. Review Wazuh logs: `/var/ossec/logs/ossec.log`
3. Check Azure DevOps pipeline logs
4. Review SQL database for test run status

## License

Proprietary - Internal Use Only
