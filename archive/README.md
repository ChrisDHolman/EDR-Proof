# Archive - Old Azure DevOps Pipeline Approach

This directory contains the original Azure DevOps Pipeline-based implementation for reference.

## What's Archived

### Code
- `orchestrator/` - Old pipeline orchestration (replaced by `tasks/` Celery workers)
- `infrastructure/` - Terraform for Azure resources (optional for new hybrid system)
- `pipelines/` - Azure DevOps YAML pipelines (no longer used)

### Documentation
- `GETTING_STARTED.md` - Old setup guide
- `IMPLEMENTATION_STATUS.md` - Old progress tracking
- `QUICKSTART_COMMANDS.md` - Old command reference
- `START_HERE.md` - Old onboarding doc
- `QUICKSTART-OLD.md` - Previous quick start

## Why Archived?

The project has been **modernized** with a hybrid FastAPI + Celery approach that provides:

✅ **4-5x faster** processing (parallel vs sequential)
✅ **Real-time dashboard** (live progress tracking)
✅ **Better debugging** (Python stack traces vs YAML)
✅ **Lower cost** ($2-5/batch vs $50-100/month)
✅ **No vendor lock-in** (run anywhere)

## Current System

See the root directory for the new hybrid system:
- `app.py` - FastAPI web application
- `tasks/` - Celery task workers
- `docker-compose.yml` - Container orchestration
- `README.md` - New documentation
- `IMPLEMENTATION_SUMMARY.md` - Complete technical guide

## Should You Use This Archive?

**Use the old approach if:**
- You're already invested in Azure DevOps
- You prefer YAML-based pipelines
- You want Terraform-managed infrastructure
- You need the Wazuh SIEM integration

**Use the new hybrid approach if:**
- You want faster processing (4-5x speedup)
- You prefer Python over YAML
- You want a web dashboard
- You need flexibility to run anywhere
- You want lower costs

## Infrastructure Note

The Terraform code in `infrastructure/` can still be useful for:
- Setting up Azure VNet for VM isolation
- Creating Azure Storage Account
- Provisioning Azure SQL Database (if you want to store results there)

However, the new hybrid system **doesn't require** most of this infrastructure:
- ❌ No Wazuh SIEM (EDR consoles queried directly)
- ❌ No Azure SQL (Redis used for state)
- ❌ No Azure DevOps pipeline agents
- ✅ Just needs: Azure Storage + VMs for Phase 3

## Migration Notes

If you have existing Azure DevOps pipelines running:

1. Both systems can coexist (use different storage containers)
2. The new system reads from Azure Blob Storage (same as old)
3. VM base images work with both approaches
4. EDR/AV/CDR API credentials are the same

## Reference Only

This archive is kept for:
- Historical reference
- Understanding original design decisions
- Terraform modules that might be useful
- Comparison with new approach

**For new deployments, use the hybrid system in the root directory.**

---

Last updated: 2025-01-17
Archived during migration to FastAPI + Celery hybrid approach
