# EDR/AV CDR Effectiveness Validation Pipeline

## Overview

Automated pipeline to validate the effectiveness of Content Disarm and Reconstruction (CDR) in reducing EDR and AV alert noise. This system processes files through multiple security solutions before and after CDR processing to prove ROI.

## Architecture

```
Azure Storage → Azure DevOps Pipeline → [Pre-CDR Testing] → Glasswall CDR → [Post-CDR Testing] → Analytics
                                              ↓                                      ↓
                                        Wazuh SIEM ← EDR/AV Agents ← Test VMs (Isolated)
                                              ↓
                                        Azure SQL Database → Metrics & Reporting
```

## Components

### Security Solutions
- **EDR**: CrowdStrike Falcon, SentinelOne, Sophos
- **AV**: Windows Defender, ClamAV, Commercial AV APIs
- **CDR**: Glasswall
- **SIEM**: Wazuh (self-hosted on Azure VMs)

### Infrastructure
- **Cloud**: Azure (Fresh subscription)
- **Compute**: Azure VMs (Spot instances for cost optimization)
- **Storage**: Azure Storage Account (Blob)
- **Database**: Azure SQL Database
- **Orchestration**: Azure DevOps Pipelines
- **IaC**: Terraform

## Project Structure

```
edr-proof/
├── infrastructure/          # Infrastructure as Code
│   ├── terraform/          # Azure resource definitions
│   └── scripts/            # Deployment and configuration scripts
├── pipelines/              # Azure DevOps pipeline definitions
├── src/                    # Source code
│   ├── orchestrator/       # Main pipeline orchestration
│   ├── integrations/       # EDR, AV, CDR, SIEM integrations
│   ├── file_interaction/   # File execution and user simulation
│   ├── metrics/            # Data collection and analysis
│   └── utils/              # Shared utilities
├── tests/                  # Unit and integration tests
└── docs/                   # Documentation

```

## Key Features

- **Automated File Interaction**: Smart file handling based on type (executables, Office docs, PDFs, archives)
- **User Behavior Simulation**: Realistic mouse/keyboard interactions to trigger behavioral analysis
- **Isolated Sandboxing**: Azure VMs with automatic provisioning and teardown
- **Comprehensive Metrics**: EDR alerts, AV detections, false positives, processing time
- **Cost-Optimized**: Spot VMs, sequential processing, rapid teardown
- **Before/After Comparison**: Statistical proof of CDR effectiveness

## Workflow

1. **File Upload**: Files placed in Azure Storage Account
2. **Pre-CDR Testing**:
   - Provision isolated Azure VM
   - Deploy EDR agents (3x) + AV scanners (3x) + Wazuh agent
   - Execute/open file with user simulation (2-5 min)
   - Collect metrics from EDR/AV/Wazuh
   - Teardown VM
3. **CDR Processing**: Glasswall sanitizes the file
4. **Post-CDR Testing**: Repeat step 2 with sanitized file
5. **Analytics**: Compare metrics, calculate noise reduction, generate report

## Metrics Tracked

- EDR alert count and severity (pre vs post)
- AV detection count and false positives (pre vs post)
- Alert noise reduction percentage
- Processing time and cost per file
- Clean file rate post-CDR

## Getting Started

### Prerequisites

- Azure subscription with Owner/Contributor access
- Azure DevOps organization and project
- Service Connection configured in Azure DevOps
- API credentials for:
  - CrowdStrike Falcon
  - SentinelOne
  - Sophos
  - Glasswall CDR
  - Commercial AV vendors
- Terraform CLI installed
- Azure CLI installed
- Python 3.11+

### Quick Start

1. **Clone and Setup**:
   ```bash
   git clone <repo-url>
   cd edr-proof
   python -m venv venv
   source venv/bin/activate  # or venv\Scripts\activate on Windows
   pip install -r requirements.txt
   ```

2. **Configure Secrets**:
   ```bash
   # Create terraform.tfvars from template
   cp infrastructure/terraform/terraform.tfvars.example infrastructure/terraform/terraform.tfvars
   # Edit and add your API keys and credentials
   ```

3. **Deploy Infrastructure**:
   ```bash
   cd infrastructure/terraform
   terraform init
   terraform plan
   terraform apply
   ```

4. **Configure Wazuh**:
   ```bash
   cd ../scripts
   ./deploy-wazuh.sh
   ./configure-wazuh.sh
   ```

5. **Setup Azure DevOps Pipeline**:
   - Import `pipelines/azure-pipelines.yml`
   - Configure service connection
   - Add pipeline variables (from Key Vault)

6. **Run Pipeline**:
   - Upload test files to Azure Storage
   - Trigger pipeline manually
   - Monitor execution in Azure DevOps
   - View results in Azure SQL or dashboard

## Documentation

- [Architecture Design](docs/architecture.md)
- [Setup Guide](docs/setup-guide.md)
- [API Documentation](docs/api-documentation.md)

## Security Considerations

- All test VMs are isolated in dedicated VNet with NSG restrictions
- No internet egress during file testing
- Automatic quarantine of detected malware
- VM snapshots before file execution
- Audit logging to Azure Monitor
- Secrets stored in Azure Key Vault

## Cost Optimization

- Azure Spot VMs for test instances (70-90% savings)
- Sequential processing (1 file at a time)
- Rapid VM teardown (<5 min per test)
- Reserved instances for persistent Wazuh VMs
- Storage lifecycle policies (auto-delete old logs)

## License

Proprietary - Internal Use Only

## Support

For issues and questions, contact the DevOps/Security team.
