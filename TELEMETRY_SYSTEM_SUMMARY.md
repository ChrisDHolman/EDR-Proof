# Comprehensive Telemetry & Results System

## What I Built

A **complete results storage and analysis system** that captures **every piece of telemetry** from Phase 2 (AV) and Phase 3 (EDR) to prove CDR ROI through noise reduction.

---

## 🎯 Core Capabilities

### 1. **Structured Results Database** (`src/database/`)

**File:** `schema.sql` - Complete SQLite/PostgreSQL schema

**Tables:**
- `av_scan_results` - Every AV detection (pre/post CDR)
- `edr_telemetry` - EDR alert summaries
- **`edr_alerts`** - EVERY individual alert/log (critical!)
- `noise_reduction_analysis` - ROI calculations

**Why This Matters:**
- Stores every detection, every alert, every detail
- Enables pre vs post CDR comparison
- Proves noise reduction with hard data
- Queryable for reports and analysis

### 2. **EDR Telemetry Parser** (`src/analytics/telemetry_parser.py`)

**Normalizes different EDR formats:**
- CrowdStrike Falcon API → Normalized format
- SentinelOne API → Normalized format
- Sophos Central API → Normalized format

**Extracts:**
- Alert name, type, category, severity
- Process details (name, path, command line, hash)
- File operations (create, modify, delete, execute)
- Network activity (IP, port, domain, protocol)
- Registry changes (key, value, operation)
- MITRE ATT&CK techniques and tactics
- Detection methods (signature, behavioral, ML)

**Why This Matters:**
- Different EDR vendors have different APIs
- Parser converts all to unified format
- Enables cross-EDR comparison
- Captures **all the noise** we're trying to reduce

### 3. **Database Manager** (`src/database/db_manager.py`)

**Key Methods:**

```python
# Phase 2: Store AV results
db.insert_av_scan_result({
    'is_malicious': True,
    'threat_name': 'Trojan.Generic',
    'confidence': 95.0,
    'severity': 'high',
    'version': 'pre-cdr'  # or 'post-cdr'
})

# Phase 3: Store EDR telemetry
telemetry_id = db.insert_edr_telemetry({
    'total_alerts': 47,
    'high_severity_alerts': 12,
    'malware_alerts': 8,
    'version': 'pre-cdr'
})

# Store individual alerts
for alert in alerts:
    db.insert_edr_alert({
        'telemetry_id': telemetry_id,
        'alert_name': 'Suspicious Process Creation',
        'severity': 'high',
        'process_name': 'powershell.exe',
        'process_command_line': 'powershell -enc ...',
        'technique': 'T1059.001',  # MITRE ATT&CK
        'raw_alert_json': json.dumps(alert)
    })

# Calculate ROI
analysis = db.calculate_noise_reduction(job_id, file_id, 'glasswall')
# Returns:
# {
#   'edr_alert_reduction_pct': 87.3,
#   'cdr_effectiveness_rating': 'excellent',
#   'analyst_time_saved_hours': 3.8,
#   'estimated_cost_savings_usd': 190.00
# }
```

**Why This Matters:**
- Single API for all database operations
- Automatic ROI calculations
- Pre vs post comparison built-in
- Export capabilities for reporting

---

## 📊 What Gets Captured

### Phase 2: AV Detection Data

**For Each Scan:**
- ✅ Is file detected as malicious?
- ✅ Threat name (if detected)
- ✅ Threat type (trojan, ransomware, PUA, etc.)
- ✅ Threat family (Emotet, TrickBot, etc.)
- ✅ Confidence level (0-100)
- ✅ Severity (critical, high, medium, low)
- ✅ Detection methods (static, heuristic, behavioral)
- ✅ File reputation (known_good, known_bad, unknown)

**Comparison:**
```
Pre-CDR:  OPSWAT: Malicious (Trojan.Generic, 95% confidence)
          ReversingLabs: Malicious (Win32.Trojan, 89% confidence)

Post-CDR: OPSWAT: Clean (0% confidence)
          ReversingLabs: Clean (0% confidence)

Result: 100% detection reduction
```

### Phase 3: EDR Telemetry (THE CRITICAL PART!)

**For Each File Execution:**

**Summary Metrics:**
- Total alerts generated
- High/Medium/Low severity breakdown
- Alert categories (malware, behavioral, network, file system, registry, process)
- Detection methods (signature-based, behavioral, ML)

**Individual Alert Details (EVERY SINGLE ALERT):**
- Alert name and description
- Alert type and category
- Severity and confidence level
- Risk score
- Detection method
- MITRE ATT&CK technique and tactic

**Process Information:**
- Process name, path, command line, hash
- Parent process details

**File Operations:**
- File path, hash
- Operation type (create, modify, delete, execute)

**Network Activity:**
- Remote IP, port, domain
- Protocol

**Registry Operations:**
- Registry key, value
- Operation type

**Full Raw JSON:**
- Complete alert from EDR console (for deep analysis)

**Example Alert:**
```json
{
  "alert_name": "Suspicious PowerShell Execution",
  "severity": "high",
  "confidence_level": 92,
  "technique": "T1059.001",  # MITRE ATT&CK
  "tactic": "Execution",
  "process_name": "powershell.exe",
  "process_command_line": "powershell.exe -EncodedCommand ...",
  "process_hash": "abc123...",
  "affected_file_path": "C:\\malware.exe",
  "detection_method": "behavioral"
}
```

**Comparison:**
```
Pre-CDR (malware.exe):
  - 47 total alerts
  - 12 high severity
  - 8 malware alerts
  - 19 behavioral detections
  - Alerts: Suspicious process, registry mod, network connection, etc.

Post-CDR (malware_sanitized.exe):
  - 6 total alerts
  - 0 high severity
  - 0 malware alerts
  - 6 informational (file execution only)

Result: 87.3% noise reduction!
```

---

## 🔍 Query Examples

### Get Job Summary
```python
db = DatabaseManager()
summary = db.get_job_summary(job_id)

print(f"Total files: {summary['total_files']}")
print(f"Avg alert reduction: {summary['avg_alert_reduction_pct']}%")
print(f"Pre-CDR alerts: {summary['edr_pre_alerts']}")
print(f"Post-CDR alerts: {summary['edr_post_alerts']}")
```

### Find Noisiest Files (Best ROI Candidates)
```python
noisy_files = db.get_noisiest_files(job_id, limit=10)

for file in noisy_files:
    print(f"{file['file_name']}: {file['total_alerts']} alerts")
    print(f"  - Critical: {file['critical_alerts']}")
    print(f"  - High: {file['high_alerts']}")
```

### Compare Pre vs Post for Specific File
```python
av_comparison = db.get_av_detection_comparison(job_id, file_id)
edr_comparison = db.get_edr_alert_comparison(job_id, file_id)

print(f"AV Detection Reduction: {av_comparison['detection_reduction_pct']}%")
print(f"EDR Alert Reduction: {edr_comparison['alert_reduction_pct']}%")
print(f"High Severity Reduction: {edr_comparison['high_severity_reduction']}")
```

### Analyze Alert Categories
```python
pre_alerts = db.get_edr_alerts_by_category(job_id, file_id, 'pre-cdr')
post_alerts = db.get_edr_alerts_by_category(job_id, file_id, 'post-cdr')

# Shows which alert types CDR eliminates
for pre_cat in pre_alerts:
    post_cat = next((p for p in post_alerts if p['alert_category'] == pre_cat['alert_category']), None)
    reduction = pre_cat['count'] - (post_cat['count'] if post_cat else 0)
    print(f"{pre_cat['alert_category']}: {reduction} alerts eliminated")
```

---

## 📈 ROI Calculation

The `calculate_noise_reduction()` method provides:

```python
analysis = db.calculate_noise_reduction(job_id, file_id, 'glasswall')

{
    # Phase 2 Metrics
    'av_pre_cdr_detections': 2,
    'av_post_cdr_detections': 0,
    'av_detection_reduction_pct': 100.0,

    # Phase 3 Metrics
    'edr_pre_cdr_total_alerts': 47,
    'edr_post_cdr_total_alerts': 6,
    'edr_alert_reduction': 41,
    'edr_alert_reduction_pct': 87.3,

    # Severity Breakdown
    'edr_pre_cdr_high_severity': 12,
    'edr_post_cdr_high_severity': 0,
    'edr_high_severity_reduction': 12,

    # Overall Metrics
    'total_noise_reduction_score': 91.1,  # 0-100 scale
    'cdr_effectiveness_rating': 'excellent',  # excellent, good, fair, poor
    'recommended_for_production': True,

    # Business Value
    'analyst_time_saved_hours': 3.8,  # @5min per high severity alert
    'estimated_cost_savings_usd': 190.00  # @$50/hour analyst time
}
```

**Scoring:**
- 30% weight: AV detection reduction
- 70% weight: EDR alert reduction (the real noise!)

**Rating Scale:**
- Excellent: 80%+ reduction
- Good: 60-79% reduction
- Fair: 40-59% reduction
- Poor: <40% reduction

---

## 📊 Dashboard Integration

Add these endpoints to `app.py`:

```python
from src.database.db_manager import DatabaseManager

db = DatabaseManager()

@app.get("/api/jobs/{job_id}/metrics")
async def get_job_metrics(job_id: str):
    """Real-time metrics for dashboard"""
    return {
        'summary': db.get_job_summary(job_id),
        'noisiest_files': db.get_noisiest_files(job_id, 10),
        'overall_roi': db.get_overall_roi(job_id)
    }

@app.get("/api/files/{file_id}/alerts/comparison")
async def compare_alerts(file_id: int, job_id: str):
    """Alert comparison chart data"""
    pre_alerts = db.get_edr_alerts_by_category(job_id, file_id, 'pre-cdr')
    post_alerts = db.get_edr_alerts_by_category(job_id, file_id, 'post-cdr')
    return {'pre': pre_alerts, 'post': post_alerts}

@app.get("/api/jobs/{job_id}/export/csv")
async def export_csv(job_id: str):
    """Export results as CSV"""
    # ... implementation
```

---

## 🎯 Key Benefits

1. **Every Alert Captured** - Nothing is lost, full forensic detail
2. **Automatic Comparison** - Database handles pre vs post automatically
3. **ROI Calculations** - Noise reduction, time savings, cost savings
4. **Queryable** - SQL queries for custom reports
5. **Exportable** - CSV, JSON, PDF for stakeholders
6. **Vendor Agnostic** - Works with any EDR/AV (with parser)

---

## 🚀 Integration Steps

1. **Update Phase 2 Tasks** - Add `db.insert_av_scan_result()` calls
2. **Update Phase 3 Tasks** - Add EDR telemetry parsing and storage
3. **Add API Endpoints** - Query results via REST API
4. **Build Dashboard** - Visualize noise reduction
5. **Generate Reports** - Export for executives

See `RESULTS_STORAGE_GUIDE.md` for complete integration code examples.

---

## 📁 Files Created

```
src/database/
├── schema.sql                      # Complete database schema
└── db_manager.py                   # Database operations API

src/analytics/
├── __init__.py
└── telemetry_parser.py            # EDR API format parsers

RESULTS_STORAGE_GUIDE.md           # Integration guide with code examples
TELEMETRY_SYSTEM_SUMMARY.md        # This file
```

---

## 💡 Example Use Case

**Scenario:** 200 potentially malicious files need CDR validation

**Process:**
1. Phase 1: Process through 3 CDR engines → 600 sanitized files
2. Phase 2: AV scan all files (200 pre + 600 post) → Database stores results
3. Phase 3: Execute on VMs with EDR → **Capture all alerts to database**
4. Analysis: Calculate noise reduction → **Prove CDR ROI**

**Results in Database:**
- 1,600 AV scan results
- 2,400 EDR telemetry summaries
- **~50,000+ individual EDR alerts** (varies by file noisiness)
- 600 noise reduction analyses (one per CDR engine x file)

**Executive Summary:**
```
200 malware samples processed through Glasswall CDR:

Phase 2 (AV):
- Pre-CDR:  187 files detected as malicious (93.5%)
- Post-CDR: 12 files detected as malicious (6.0%)
- Detection Reduction: 93.6%

Phase 3 (EDR):
- Pre-CDR:  9,847 total alerts (avg 49 per file)
  - 2,341 high severity alerts
  - 1,982 malware alerts
- Post-CDR: 1,203 total alerts (avg 6 per file)
  - 47 high severity alerts
  - 0 malware alerts
- Alert Reduction: 87.8%

ROI:
- Analyst time saved: 382 hours
- Cost savings: $19,100
- Average noise reduction score: 89.2/100
- Recommended for production: Yes

Top noisiest files that benefit most from CDR:
1. invoice.docx - 247 alerts → 3 alerts (98.8% reduction)
2. report.pdf - 189 alerts → 5 alerts (97.4% reduction)
3. contract.exe - 156 alerts → 0 alerts (100% reduction)
```

---

**This is the data that proves CDR works and justifies the investment!** 🎯

The database captures **everything** - every detection, every alert, every detail needed to prove noise reduction and calculate ROI.