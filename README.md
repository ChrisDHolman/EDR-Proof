# EDR-PROOF: Hybrid CDR Validation System

> **Modern automation platform** for validating Content Disarm & Reconstruction (CDR) effectiveness across EDR/AV solutions

## 🚀 Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start Redis
docker run -d -p 6379:6379 redis:7-alpine

# 3. Configure credentials
cp .env.example .env
nano .env  # Add your API keys

# 4. Start system
./start.sh

# 5. Open dashboard
http://localhost:8000
```

**Or use Docker:**
```bash
docker-compose up -d
```

---

## 📖 What This Does

Automates large-scale validation of CDR technology by processing files through:

**Phase 1:** CDR Processing (3 engines in parallel)
- Glasswall
- OPSWAT MetaDefender
- Votiro

**Phase 2:** AV Scanning (2 engines in parallel)
- OPSWAT MetaDefender AV
- ReversingLabs AP

**Phase 3:** EDR Testing (3 solutions with VM pool)
- CrowdStrike Falcon
- SentinelOne
- Sophos

**Result:** Proves CDR ROI by comparing alert volumes before/after sanitization

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────┐
│     Web Dashboard (http://localhost:8000)   │
│     - Submit jobs                           │
│     - Real-time progress                    │
│     - View results                          │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│         FastAPI + Celery Workers            │
│  ┌──────────┐ ┌──────────┐ ┌─────────────┐ │
│  │ Phase 1  │ │ Phase 2  │ │  Phase 3    │ │
│  │ (CDR)    │ │ (AV)     │ │  (EDR+VMs)  │ │
│  │ 10 work. │ │ 10 work. │ │  5 workers  │ │
│  └──────────┘ └──────────┘ └──────┬──────┘ │
└─────────────────────────────────────┼────────┘
                                      │
                           ┌──────────▼────────┐
                           │ Azure VM Pool     │
                           │ 15 VMs (5 per EDR)│
                           │ Pre-installed EDR │
                           └───────────────────┘
```

---

## 📁 Project Structure

```
edr-proof/
├── app.py                   # FastAPI web application
├── docker-compose.yml       # Container orchestration
├── start.sh / stop.sh       # Easy startup scripts
├── .env.example             # Configuration template
│
├── tasks/                   # Celery task definitions
│   ├── celery_app.py       # Celery configuration
│   ├── job_manager.py      # Job state management
│   ├── vm_pool_manager.py  # VM orchestration
│   ├── phase1_cdr.py       # CDR processing
│   ├── phase2_av.py        # AV scanning
│   └── phase3_edr.py       # EDR testing
│
├── src/
│   ├── integrations/       # CDR/AV/EDR API clients
│   │   ├── cdr/           # Glasswall, OPSWAT, Votiro
│   │   ├── av/            # OPSWAT AV, ReversingLabs
│   │   └── edr/           # CrowdStrike, SentinelOne, Sophos
│   ├── file_interaction/   # File execution engine
│   └── utils/             # Azure Storage, config, logging
│
├── archive/                # Old Azure DevOps approach (reference)
└── IMPLEMENTATION_SUMMARY.md  # Complete technical documentation
```

---

## 🎯 Key Features

✅ **4-5x Faster** - Parallel processing vs sequential pipelines
✅ **Real-Time Dashboard** - Live progress tracking
✅ **VM Pool Management** - Intelligent VM allocation for Phase 3
✅ **Cost Optimized** - Spot VMs, pay per batch (~$2-5)
✅ **No Vendor Lock-In** - Run locally, Docker, or any cloud
✅ **Flexible** - Easy to add new CDR/AV/EDR engines

---

## 📊 Performance

| Metric | Value |
|--------|-------|
| **200 files × 3 phases** | 8-10 hours |
| **Phase 1 (CDR)** | 30-60 min (10 parallel workers) |
| **Phase 2 (AV)** | 45-90 min (10 parallel workers) |
| **Phase 3 (EDR)** | 6-8 hours (15 VMs) |
| **Cost per batch** | $2-5 (Spot VMs) |

---

## 🛠️ Prerequisites

### Required
- Python 3.11+
- Redis (for Celery)
- Azure Storage Account
- Azure subscription (for Phase 3 VMs)

### API Credentials Needed
- **CDR Engines:** Glasswall, OPSWAT, Votiro
- **AV Engines:** OPSWAT MetaDefender, ReversingLabs
- **EDR Consoles:** CrowdStrike, SentinelOne, Sophos

### Critical for Phase 3
**VM Base Images** with EDR agents pre-installed:
- `crowdstrike-base-image`
- `sentinelone-base-image`
- `sophos-base-image`

See `IMPLEMENTATION_SUMMARY.md` for image creation instructions.

---

## 🎨 Dashboard

Access **http://localhost:8000** to see:

- 📤 Job submission form
- 📊 Real-time progress bars
- 📈 Phase-by-phase statistics
- 🎯 ROI metrics (alert reduction %)
- 🔄 Auto-refresh every 5 seconds

**Monitoring UI:** http://localhost:5555 (Celery Flower)

---

## 📚 Documentation

| File | Description |
|------|-------------|
| **IMPLEMENTATION_SUMMARY.md** | **START HERE** - Complete technical guide |
| `.env.example` | Configuration template |
| `README.md` | This file - quick overview |
| `archive/` | Old Azure DevOps approach (reference) |

---

## 🔧 Configuration

Edit `.env` with your credentials:

```env
# Azure Storage
AZURE_STORAGE_ACCOUNT_URL=https://your-account.blob.core.windows.net
AZURE_STORAGE_ACCOUNT_KEY=your-key

# CDR Engines
GLASSWALL_API_KEY=your-key
OPSWAT_CDR_API_KEY=your-key
VOTIRO_API_KEY=your-key

# AV Engines
OPSWAT_AV_API_KEY=your-key
REVERSINGLABS_API_KEY=your-key

# EDR Consoles
CROWDSTRIKE_CLIENT_ID=your-id
CROWDSTRIKE_CLIENT_SECRET=your-secret
SENTINELONE_API_TOKEN=your-token
SOPHOS_CLIENT_ID=your-id

# Azure VM Images (for Phase 3)
CROWDSTRIKE_IMAGE_ID=/subscriptions/.../images/crowdstrike-base-image
SENTINELONE_IMAGE_ID=/subscriptions/.../images/sentinelone-base-image
SOPHOS_IMAGE_ID=/subscriptions/.../images/sophos-base-image
```

---

## 🚀 Usage

### Start a Job

**Via Dashboard:**
1. Go to http://localhost:8000
2. Enter container name (e.g., `test-files`)
3. Select phases (1, 2, 3)
4. Click "Start Batch Job"

**Via API:**
```bash
curl -X POST http://localhost:8000/api/jobs/batch \
  -H "Content-Type: application/json" \
  -d '{
    "container_name": "test-files",
    "phases": [1, 2, 3],
    "priority": "normal"
  }'
```

### Monitor Progress

- **Dashboard:** http://localhost:8000
- **Flower:** http://localhost:5555
- **Logs:** `tail -f logs/*.log`

### Get Results

```bash
# List all jobs
curl http://localhost:8000/api/jobs

# Get job status
curl http://localhost:8000/api/jobs/{job_id}

# Get detailed results
curl http://localhost:8000/api/jobs/{job_id}/results
```

---

## 🔍 System Components

### FastAPI Application (`app.py`)
- REST API for job management
- HTML dashboard with real-time updates
- Job submission, monitoring, results

### Celery Workers (`tasks/`)
- **Phase 1:** CDR processing (parallel)
- **Phase 2:** AV scanning (parallel)
- **Phase 3:** EDR testing (VM pool)

### VM Pool Manager (`tasks/vm_pool_manager.py`)
- Maintains 15 VMs (5 per EDR)
- Thread-safe allocation
- Auto-recycling after 20 uses
- Cleanup between tests

### Job Manager (`tasks/job_manager.py`)
- Redis-based state tracking
- Real-time progress calculation
- Result aggregation

---

## 🐛 Troubleshooting

**Redis not running:**
```bash
docker run -d -p 6379:6379 redis:7-alpine
# or
sudo systemctl start redis
```

**Workers not processing:**
```bash
# Check worker status
celery -A tasks.celery_app inspect active

# Restart workers
./stop.sh && ./start.sh
```

**No VMs available:**
```python
# Initialize VM pool
from tasks.vm_pool_manager import VMPoolManager
from src.utils.config import ConfigManager

VMPoolManager(ConfigManager()).initialize_pools()
```

**See logs:**
```bash
tail -f logs/fastapi.log
tail -f logs/celery-phase3.log
```

---

## 💰 Cost Breakdown

| Component | Cost |
|-----------|------|
| **Phase 1 (CDR)** | API costs only |
| **Phase 2 (AV)** | API costs only |
| **Phase 3 (VMs)** | 15 VMs × 8hrs × $0.02/hr = **~$2.40** |
| **Storage** | 2GB × $0.02/GB = **<$0.10** |
| **Total per batch** | **~$2-5** |

Much cheaper than Azure DevOps agent costs ($50-100/month).

---

## 🔒 Security

- VMs isolated in dedicated VNet
- No internet egress during testing
- Automatic VM cleanup after tests
- Secrets in `.env` (never commit!)
- Azure Spot VMs for cost savings

---

## 📞 Support

**Read first:**
- `IMPLEMENTATION_SUMMARY.md` - Complete technical guide
- Check logs in `logs/` directory
- Review Flower UI at http://localhost:5555

**Common issues:**
- Redis connection → Start Redis
- No VMs → Initialize pool
- API errors → Check credentials in `.env`

---

## 🎓 Next Steps

1. ✅ Read `IMPLEMENTATION_SUMMARY.md`
2. ✅ Configure `.env` with real credentials
3. ✅ Create VM base images (Phase 3 requirement)
4. ✅ Upload test files to Azure Blob
5. ✅ Initialize VM pool
6. ✅ Run your first batch job!

---

## 📝 License

Proprietary - Internal Use Only

---

## 🏆 Why This Approach?

**Before (Azure DevOps Pipelines):**
- ❌ Sequential processing (slow)
- ❌ Complex YAML debugging
- ❌ Limited scalability
- ❌ Fixed monthly costs
- ❌ Vendor lock-in

**After (FastAPI + Celery):**
- ✅ Parallel processing (4-5x faster)
- ✅ Python debugging (stack traces)
- ✅ Infinite scalability (add workers)
- ✅ Pay per batch
- ✅ Run anywhere

---

**Ready to validate CDR at scale!** 🚀

For detailed technical documentation, see: **`IMPLEMENTATION_SUMMARY.md`**
