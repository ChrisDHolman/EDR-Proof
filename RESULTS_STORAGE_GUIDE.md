```

# Results Storage & Analysis Guide

## Overview

This guide shows how Phase 2 (AV) and Phase 3 (EDR) results are captured, stored, and analyzed to prove CDR ROI through noise reduction metrics.

---

## Database Schema

### Key Tables

**`av_scan_results`** - Phase 2 AV detection data
- Stores every AV scan (pre-CDR and post-CDR)
- Captures: threat name, type, family, confidence, severity
- Enables detection rate comparison

**`edr_telemetry`** - Phase 3 EDR summary data
- Stores alert counts by severity and category
- Tracks execution details (VM, duration)
- Summarizes total noise per file

**`edr_alerts`** - Phase 3 individual alert details (CRITICAL!)
- **Every single alert/log from EDR console**
- Process details, file operations, network activity
- MITRE ATT&CK techniques
- **This is the "noise" we're measuring**

**`noise_reduction_analysis`** - Final ROI calculations
- Pre vs post CDR comparison
- Alert reduction percentage
- Cost savings estimates
- Effectiveness ratings

---

## How It Works

### Phase 2: AV Detection Storage

```python
from src.database.db_manager import DatabaseManager

db = DatabaseManager()

# After AV scan completes
scan_result = av_client.scan_file(file_path)

# Store with enhanced details
db.insert_av_scan_result({
    'job_id': job_id,
    'file_id': file_id,
    'av_engine': 'opswat',
    'version': 'pre-cdr',  # or 'post-cdr'
    'cdr_engine': None,  # or 'glasswall'
    'is_malicious': scan_result.is_malicious,
    'threat_name': scan_result.threat_name,
    'threat_type': 'trojan',  # Categorize: trojan, ransomware, pua
    'threat_family': 'emotet',  # If identifiable
    'confidence': scan_result.confidence,
    'severity': 'high',  # critical, high, medium, low
    'engine_version': scan_result.engine_version,
    'scan_time_ms': scan_result.scan_time_ms,
    'detection_methods': ['static', 'heuristic'],  # Array
    'indicators_of_compromise': ['suspicious_api_calls'],
    'file_reputation': 'known_bad'
})

# Compare pre vs post
comparison = db.get_av_detection_comparison(job_id, file_id)
print(f"AV detection reduction: {comparison['detection_reduction_pct']}%")
```

### Phase 3: EDR Telemetry Storage

```python
from src.analytics.telemetry_parser import EDRTelemetryParser

# After file execution on VM with EDR
execution_result = vm_pool_manager.execute_file_on_vm(vm, file_path)

# Query EDR console for alerts
raw_alerts = crowdstrike_client.get_alerts(
    host_name=vm['vm_name'],
    start_time=execution_start,
    end_time=execution_end
)

# Parse EDR-specific format into normalized telemetry
telemetry = EDRTelemetryParser.parse_crowdstrike_alerts(raw_alerts)

# Store telemetry summary
telemetry_id = db.insert_edr_telemetry({
    'job_id': job_id,
    'file_id': file_id,
    'edr_solution': 'crowdstrike',
    'version': 'pre-cdr',  # or 'post-cdr'
    'cdr_engine': None,  # or 'glasswall'
    'vm_name': vm['vm_name'],
    'execution_started_at': execution_start,
    'execution_ended_at': execution_end,
    'execution_duration_sec': 300,
    'execution_success': True,

    # Alert counts (from parser)
    'total_alerts': telemetry['total_alerts'],
    'high_severity_alerts': telemetry['high_severity_alerts'],
    'medium_severity_alerts': telemetry['medium_severity_alerts'],
    'low_severity_alerts': telemetry['low_severity_alerts'],

    # Alert categories
    'malware_alerts': telemetry['malware_alerts'],
    'suspicious_behavior_alerts': telemetry['suspicious_behavior_alerts'],
    'network_alerts': telemetry['network_alerts'],
    'file_system_alerts': telemetry['file_system_alerts'],
    'registry_alerts': telemetry['registry_alerts'],
    'process_alerts': telemetry['process_alerts'],

    # Detection methods
    'signature_based_detections': telemetry['signature_based_detections'],
    'behavioral_detections': telemetry['behavioral_detections'],
    'machine_learning_detections': telemetry['machine_learning_detections']
})

# Store EVERY individual alert (critical for analysis!)
for alert in telemetry['alerts']:
    alert['telemetry_id'] = telemetry_id
    alert['job_id'] = job_id
    alert['file_id'] = file_id
    alert['edr_solution'] = 'crowdstrike'

    db.insert_edr_alert(alert)

# Compare pre vs post
comparison = db.get_edr_alert_comparison(job_id, file_id)
print(f"EDR alert reduction: {comparison['alert_reduction_pct']}%")
print(f"High severity reduction: {comparison['high_severity_reduction']}")
```

### ROI Calculation

```python
# After both pre-CDR and post-CDR tests complete
analysis = db.calculate_noise_reduction(job_id, file_id, cdr_engine='glasswall')

print(f"Noise Reduction Score: {analysis['total_noise_reduction_score']}/100")
print(f"CDR Effectiveness: {analysis['cdr_effectiveness_rating']}")
print(f"Alert Reduction: {analysis['edr_alert_reduction_pct']}%")
print(f"Analyst Time Saved: {analysis['analyst_time_saved_hours']} hours")
print(f"Cost Savings: ${analysis['estimated_cost_savings_usd']}")
print(f"Recommended: {analysis['recommended_for_production']}")
```

---

## Integration with Celery Tasks

### Update Phase 2 Task (tasks/phase2_av.py)

```python
from src.database.db_manager import DatabaseManager

db = DatabaseManager()

@celery_app.task
def scan_single_file_av(job_id, container_name, file_info, av_engine_name):
    # ... existing code ...

    # After scan completes
    scan_result = av_client.scan_file(local_file_path)

    # Get or create file_id
    file_hash = calculate_file_hash(local_file_path)
    file_id = db.insert_file(job_id, file_path, file_hash, file_size, file_type)

    # Store scan result in database
    db.insert_av_scan_result({
        'job_id': job_id,
        'file_id': file_id,
        'av_engine': av_engine_name,
        'version': file_info['version'],  # 'pre-cdr' or 'post-cdr'
        'cdr_engine': file_info.get('cdr_engine'),
        'is_malicious': scan_result.is_malicious,
        'threat_name': scan_result.threat_name,
        'threat_type': classify_threat_type(scan_result.threat_name),
        'confidence': scan_result.confidence,
        'severity': map_severity(scan_result.confidence),
        'engine_version': scan_result.engine_version,
        'scan_time_ms': scan_result.scan_time_ms,
        'detection_methods': extract_detection_methods(scan_result),
        'file_reputation': 'known_bad' if scan_result.is_malicious else 'clean'
    })

    return result
```

### Update Phase 3 Task (tasks/phase3_edr.py)

```python
from src.database.db_manager import DatabaseManager
from src.analytics.telemetry_parser import EDRTelemetryParser

db = DatabaseManager()

@celery_app.task
def test_single_file_edr(job_id, container_name, file_info, edr_solution_name):
    # ... existing VM acquisition and file execution ...

    # After file execution, query EDR console
    edr_client = edr_clients[edr_solution_name]

    raw_alerts = edr_client.get_alerts(
        host_name=vm['vm_name'],
        start_time=execution_start,
        end_time=execution_end
    )

    # Parse alerts based on EDR solution
    if edr_solution_name == 'crowdstrike':
        telemetry = EDRTelemetryParser.parse_crowdstrike_alerts(raw_alerts)
    elif edr_solution_name == 'sentinelone':
        telemetry = EDRTelemetryParser.parse_sentinelone_alerts(raw_alerts)
    elif edr_solution_name == 'sophos':
        telemetry = EDRTelemetryParser.parse_sophos_alerts(raw_alerts)

    # Get or create file_id
    file_hash = calculate_file_hash(local_file_path)
    file_id = db.insert_file(job_id, file_path, file_hash, file_size, file_type)

    # Store telemetry summary
    telemetry_id = db.insert_edr_telemetry({
        'job_id': job_id,
        'file_id': file_id,
        'edr_solution': edr_solution_name,
        'version': file_info['version'],  # 'pre-cdr' or 'post-cdr'
        'cdr_engine': file_info.get('cdr_engine'),
        'vm_name': vm['vm_name'],
        'execution_started_at': execution_start,
        'execution_ended_at': execution_end,
        'execution_duration_sec': int((execution_end - execution_start).total_seconds()),
        'execution_success': True,
        **telemetry  # Unpack all telemetry metrics
    })

    # Store EVERY individual alert
    for alert in telemetry['alerts']:
        alert.update({
            'telemetry_id': telemetry_id,
            'job_id': job_id,
            'file_id': file_id,
            'edr_solution': edr_solution_name
        })
        db.insert_edr_alert(alert)

    logger.info(
        f"[Job {job_id}] {file_path} ({file_info['version']}) on {edr_solution_name}: "
        f"{telemetry['total_alerts']} alerts ({telemetry['high_severity_alerts']} high severity)"
    )

    return result
```

### Calculate ROI After Both Phases

```python
@celery_app.task
def on_edr_batch_complete(results, job_id):
    """After all EDR tests complete, calculate noise reduction"""

    db = DatabaseManager()

    # Get all unique file IDs
    file_ids = db.get_file_ids_for_job(job_id)

    # Calculate noise reduction for each file x CDR engine
    for file_id in file_ids:
        for cdr_engine in ['glasswall', 'opswat', 'votiro']:
            analysis = db.calculate_noise_reduction(job_id, file_id, cdr_engine)

            logger.info(
                f"[Job {job_id}] File {file_id} with {cdr_engine}: "
                f"{analysis['edr_alert_reduction_pct']}% noise reduction, "
                f"rating: {analysis['cdr_effectiveness_rating']}"
            )

    # Update job with final summary
    job_summary = db.get_job_summary(job_id)
    job_manager.update_job(job_id, {
        'status': 'completed',
        'completed_at': datetime.now(),
        'final_results': job_summary
    })
```

---

## Querying Results

### Via Database Manager

```python
db = DatabaseManager()

# Get job summary
summary = db.get_job_summary(job_id)

# Get noisiest files (best candidates for showing ROI)
noisy_files = db.get_noisiest_files(job_id, limit=10)

# Get detailed alert breakdown by category
pre_alerts = db.get_edr_alerts_by_category(job_id, file_id, 'pre-cdr')
post_alerts = db.get_edr_alerts_by_category(job_id, file_id, 'post-cdr')

# Export full results
json_export = db.export_results_json(job_id)
```

### Via SQL (Direct Queries)

```sql
-- Top 10 files with best noise reduction
SELECT
    f.file_name,
    na.edr_alert_reduction_pct,
    na.edr_pre_cdr_total_alerts,
    na.edr_post_cdr_total_alerts
FROM noise_reduction_analysis na
JOIN files f ON na.file_id = f.file_id
WHERE na.job_id = 'your-job-id'
ORDER BY na.edr_alert_reduction_pct DESC
LIMIT 10;

-- Alert types eliminated by CDR
SELECT
    pre.alert_category,
    pre.count as pre_cdr_count,
    COALESCE(post.count, 0) as post_cdr_count,
    pre.count - COALESCE(post.count, 0) as reduction
FROM (
    SELECT alert_category, COUNT(*) as count
    FROM edr_alerts ea
    JOIN edr_telemetry et ON ea.telemetry_id = et.telemetry_id
    WHERE et.version = 'pre-cdr' AND et.job_id = 'your-job-id'
    GROUP BY alert_category
) pre
LEFT JOIN (
    SELECT alert_category, COUNT(*) as count
    FROM edr_alerts ea
    JOIN edr_telemetry et ON ea.telemetry_id = et.telemetry_id
    WHERE et.version = 'post-cdr' AND et.job_id = 'your-job-id'
    GROUP BY alert_category
) post ON pre.alert_category = post.alert_category
ORDER BY reduction DESC;

-- Cost savings across entire job
SELECT
    SUM(analyst_time_saved_hours) as total_hours_saved,
    SUM(estimated_cost_savings_usd) as total_cost_savings,
    AVG(total_noise_reduction_score) as avg_noise_reduction,
    COUNT(CASE WHEN recommended_for_production THEN 1 END) as recommended_count
FROM noise_reduction_analysis
WHERE job_id = 'your-job-id';
```

---

## API Endpoints (Add to app.py)

```python
@app.get("/api/jobs/{job_id}/results/summary")
async def get_job_results_summary(job_id: str):
    """Get comprehensive job results"""
    db = DatabaseManager()
    return db.get_job_summary(job_id)

@app.get("/api/jobs/{job_id}/results/noisiest-files")
async def get_noisiest_files(job_id: str, limit: int = 10):
    """Get files generating most alerts (best ROI candidates)"""
    db = DatabaseManager()
    return db.get_noisiest_files(job_id, limit)

@app.get("/api/jobs/{job_id}/results/export")
async def export_job_results(job_id: str):
    """Export complete results as JSON"""
    db = DatabaseManager()
    return db.export_results_json(job_id)

@app.get("/api/files/{file_id}/comparison")
async def get_file_comparison(file_id: int, job_id: str):
    """Compare pre vs post CDR for specific file"""
    db = DatabaseManager()
    av_comparison = db.get_av_detection_comparison(job_id, file_id)
    edr_comparison = db.get_edr_alert_comparison(job_id, file_id)

    return {
        'av_comparison': av_comparison,
        'edr_comparison': edr_comparison
    }

@app.get("/api/alerts/by-category")
async def get_alerts_by_category(job_id: str, file_id: int, version: str):
    """Get EDR alerts grouped by category"""
    db = DatabaseManager()
    return db.get_edr_alerts_by_category(job_id, file_id, version)
```

---

## Export Formats

### CSV Export

```python
import csv

def export_to_csv(job_id: str, output_path: str):
    """Export results to CSV for Excel analysis"""
    db = DatabaseManager()

    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)

        # Header
        writer.writerow([
            'File Name', 'File Hash',
            'AV Pre Detections', 'AV Post Detections', 'AV Reduction %',
            'EDR Pre Alerts', 'EDR Post Alerts', 'EDR Reduction %',
            'High Severity Reduction', 'Noise Score', 'Effectiveness',
            'Time Saved (hrs)', 'Cost Savings ($)'
        ])

        # Get all analyses
        analyses = db.get_all_analyses(job_id)

        for analysis in analyses:
            writer.writerow([
                analysis['file_name'],
                analysis['file_hash'],
                analysis['av_pre_cdr_detections'],
                analysis['av_post_cdr_detections'],
                analysis['av_detection_reduction_pct'],
                analysis['edr_pre_cdr_total_alerts'],
                analysis['edr_post_cdr_total_alerts'],
                analysis['edr_alert_reduction_pct'],
                analysis['edr_high_severity_reduction'],
                analysis['total_noise_reduction_score'],
                analysis['cdr_effectiveness_rating'],
                analysis['analyst_time_saved_hours'],
                analysis['estimated_cost_savings_usd']
            ])
```

### PDF Report (using reportlab)

```python
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, Paragraph

def generate_pdf_report(job_id: str, output_path: str):
    """Generate executive summary PDF"""
    db = DatabaseManager()
    summary = db.get_job_summary(job_id)

    doc = SimpleDocTemplate(output_path, pagesize=letter)
    elements = []

    # Title
    elements.append(Paragraph(f"CDR Validation Report - Job {job_id}"))

    # Summary stats
    data = [
        ['Metric', 'Value'],
        ['Total Files', summary['total_files']],
        ['Avg Alert Reduction', f"{summary['avg_alert_reduction_pct']}%"],
        ['Avg Noise Score', f"{summary['avg_noise_reduction_score']}/100"],
        ['Pre-CDR Alerts', summary['edr_pre_alerts']],
        ['Post-CDR Alerts', summary['edr_post_alerts']]
    ]

    elements.append(Table(data))
    doc.build(elements)
```

---

## Key Points

1. **Store EVERYTHING** - Every alert, every detection, every detail
2. **Pre vs Post comparison** is automatic via database queries
3. **Noise reduction** is the primary metric for ROI
4. **Individual alerts** show exactly what CDR eliminates
5. **Export capabilities** enable executive reporting

---

## Next Steps

1. Update Phase 2/3 tasks to use DatabaseManager
2. Add API endpoints to app.py for querying results
3. Create export functions (CSV, PDF, JSON)
4. Build dashboard visualizations
5. Generate executive summary reports

See `src/database/db_manager.py` for complete API reference.
```