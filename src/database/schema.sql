-- EDR-PROOF Results Database Schema
-- Stores all Phase 2 (AV) and Phase 3 (EDR) results for analysis

-- Jobs table (tracks batch jobs)
CREATE TABLE IF NOT EXISTS jobs (
    job_id VARCHAR(36) PRIMARY KEY,
    container_name VARCHAR(255) NOT NULL,
    phases TEXT NOT NULL,  -- JSON array [1,2,3]
    priority VARCHAR(20) DEFAULT 'normal',
    status VARCHAR(20) NOT NULL,  -- pending, running, completed, failed
    created_at TIMESTAMP NOT NULL,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    total_files INTEGER DEFAULT 0,
    processed_files INTEGER DEFAULT 0,
    failed_files INTEGER DEFAULT 0,
    progress_percentage FLOAT DEFAULT 0.0,
    error_message TEXT
);

-- Files table (tracks individual files)
CREATE TABLE IF NOT EXISTS files (
    file_id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id VARCHAR(36) NOT NULL,
    file_path TEXT NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_hash VARCHAR(64),
    file_size INTEGER,
    file_type VARCHAR(50),
    uploaded_at TIMESTAMP NOT NULL,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
);

-- CDR Processing Results (Phase 1)
CREATE TABLE IF NOT EXISTS cdr_results (
    cdr_result_id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id VARCHAR(36) NOT NULL,
    file_id INTEGER NOT NULL,
    cdr_engine VARCHAR(50) NOT NULL,  -- glasswall, opswat, votiro
    success BOOLEAN NOT NULL,
    processing_time_ms INTEGER,
    original_size INTEGER,
    sanitized_size INTEGER,
    size_reduction_bytes INTEGER,
    size_reduction_pct FLOAT,
    threats_found INTEGER DEFAULT 0,
    threats_removed TEXT,  -- JSON array of threat names
    sanitized_file_path TEXT,
    error_message TEXT,
    processed_at TIMESTAMP NOT NULL,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id),
    FOREIGN KEY (file_id) REFERENCES files(file_id)
);

-- AV Scan Results (Phase 2) - CRITICAL FOR DETECTION ANALYSIS
CREATE TABLE IF NOT EXISTS av_scan_results (
    scan_id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id VARCHAR(36) NOT NULL,
    file_id INTEGER NOT NULL,
    av_engine VARCHAR(50) NOT NULL,  -- opswat, reversinglabs
    version VARCHAR(20) NOT NULL,  -- 'pre-cdr' or 'post-cdr'
    cdr_engine VARCHAR(50),  -- NULL for pre-cdr, engine name for post-cdr

    -- Detection Results
    is_malicious BOOLEAN NOT NULL,
    threat_name VARCHAR(255),
    threat_type VARCHAR(100),  -- trojan, ransomware, pua, etc.
    threat_family VARCHAR(100),  -- emotet, trickbot, etc.
    confidence FLOAT,  -- 0-100
    severity VARCHAR(20),  -- low, medium, high, critical

    -- Engine Details
    engine_version VARCHAR(50),
    signature_version VARCHAR(50),
    scan_time_ms INTEGER,

    -- Additional Detection Info
    detection_methods TEXT,  -- JSON array: [static, heuristic, behavioral]
    indicators_of_compromise TEXT,  -- JSON array of IOCs
    file_reputation VARCHAR(50),  -- known_good, known_bad, unknown, suspicious

    scanned_at TIMESTAMP NOT NULL,

    FOREIGN KEY (job_id) REFERENCES jobs(job_id),
    FOREIGN KEY (file_id) REFERENCES files(file_id)
);

-- EDR Telemetry (Phase 3) - CRITICAL FOR NOISE ANALYSIS
CREATE TABLE IF NOT EXISTS edr_telemetry (
    telemetry_id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id VARCHAR(36) NOT NULL,
    file_id INTEGER NOT NULL,
    edr_solution VARCHAR(50) NOT NULL,  -- crowdstrike, sentinelone, sophos
    version VARCHAR(20) NOT NULL,  -- 'pre-cdr' or 'post-cdr'
    cdr_engine VARCHAR(50),  -- NULL for pre-cdr, engine name for post-cdr

    -- VM Execution Details
    vm_name VARCHAR(100) NOT NULL,
    execution_started_at TIMESTAMP NOT NULL,
    execution_ended_at TIMESTAMP NOT NULL,
    execution_duration_sec INTEGER,
    execution_success BOOLEAN,

    -- Alert Summary
    total_alerts INTEGER DEFAULT 0,
    high_severity_alerts INTEGER DEFAULT 0,
    medium_severity_alerts INTEGER DEFAULT 0,
    low_severity_alerts INTEGER DEFAULT 0,
    informational_alerts INTEGER DEFAULT 0,

    -- Alert Categories
    malware_alerts INTEGER DEFAULT 0,
    suspicious_behavior_alerts INTEGER DEFAULT 0,
    network_alerts INTEGER DEFAULT 0,
    file_system_alerts INTEGER DEFAULT 0,
    registry_alerts INTEGER DEFAULT 0,
    process_alerts INTEGER DEFAULT 0,

    -- Detection Methods
    signature_based_detections INTEGER DEFAULT 0,
    behavioral_detections INTEGER DEFAULT 0,
    machine_learning_detections INTEGER DEFAULT 0,

    tested_at TIMESTAMP NOT NULL,

    FOREIGN KEY (job_id) REFERENCES jobs(job_id),
    FOREIGN KEY (file_id) REFERENCES files(file_id)
);

-- EDR Alert Details (Individual alerts from EDR consoles)
CREATE TABLE IF NOT EXISTS edr_alerts (
    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
    telemetry_id INTEGER NOT NULL,
    job_id VARCHAR(36) NOT NULL,
    file_id INTEGER NOT NULL,
    edr_solution VARCHAR(50) NOT NULL,

    -- Alert Identification
    alert_external_id VARCHAR(100),  -- ID from EDR console
    alert_name VARCHAR(255) NOT NULL,
    alert_type VARCHAR(100),  -- malware, exploit, suspicious_behavior
    alert_category VARCHAR(100),  -- malware_detection, behavioral_analysis

    -- Severity and Confidence
    severity VARCHAR(20) NOT NULL,  -- critical, high, medium, low, info
    confidence_level FLOAT,  -- 0-100
    risk_score INTEGER,  -- 0-100

    -- Detection Details
    detection_method VARCHAR(100),  -- signature, heuristic, ml, behavioral
    technique VARCHAR(255),  -- MITRE ATT&CK technique
    tactic VARCHAR(255),  -- MITRE ATT&CK tactic

    -- Process Information
    process_name VARCHAR(255),
    process_path TEXT,
    process_command_line TEXT,
    process_hash VARCHAR(64),
    parent_process_name VARCHAR(255),

    -- File Information (if file-based alert)
    affected_file_path TEXT,
    affected_file_hash VARCHAR(64),
    file_operation VARCHAR(50),  -- create, modify, delete, execute

    -- Network Information (if network alert)
    remote_ip VARCHAR(45),
    remote_port INTEGER,
    remote_domain VARCHAR(255),
    network_protocol VARCHAR(20),

    -- Registry Information (if registry alert)
    registry_key TEXT,
    registry_value TEXT,
    registry_operation VARCHAR(50),  -- create, modify, delete

    -- Timeline
    alert_timestamp TIMESTAMP NOT NULL,
    first_seen TIMESTAMP,
    last_seen TIMESTAMP,

    -- Additional Context
    description TEXT,
    remediation_action VARCHAR(100),  -- quarantined, blocked, allowed, monitored
    false_positive_likely BOOLEAN DEFAULT FALSE,
    raw_alert_json TEXT,  -- Full JSON from EDR console

    created_at TIMESTAMP NOT NULL,

    FOREIGN KEY (telemetry_id) REFERENCES edr_telemetry(telemetry_id),
    FOREIGN KEY (job_id) REFERENCES jobs(job_id),
    FOREIGN KEY (file_id) REFERENCES files(file_id)
);

-- Noise Reduction Analysis (Comparison results)
CREATE TABLE IF NOT EXISTS noise_reduction_analysis (
    analysis_id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id VARCHAR(36) NOT NULL,
    file_id INTEGER NOT NULL,
    cdr_engine VARCHAR(50) NOT NULL,

    -- Phase 2 Analysis (AV Detection Reduction)
    av_pre_cdr_detections INTEGER DEFAULT 0,
    av_post_cdr_detections INTEGER DEFAULT 0,
    av_detection_reduction INTEGER DEFAULT 0,
    av_detection_reduction_pct FLOAT DEFAULT 0.0,

    -- Phase 3 Analysis (EDR Alert Reduction)
    edr_pre_cdr_total_alerts INTEGER DEFAULT 0,
    edr_post_cdr_total_alerts INTEGER DEFAULT 0,
    edr_alert_reduction INTEGER DEFAULT 0,
    edr_alert_reduction_pct FLOAT DEFAULT 0.0,

    edr_pre_cdr_high_severity INTEGER DEFAULT 0,
    edr_post_cdr_high_severity INTEGER DEFAULT 0,
    edr_high_severity_reduction INTEGER DEFAULT 0,

    edr_pre_cdr_malware_alerts INTEGER DEFAULT 0,
    edr_post_cdr_malware_alerts INTEGER DEFAULT 0,
    edr_malware_alert_reduction INTEGER DEFAULT 0,

    -- Overall ROI Metrics
    total_noise_reduction_score FLOAT,  -- 0-100
    cdr_effectiveness_rating VARCHAR(20),  -- excellent, good, fair, poor
    recommended_for_production BOOLEAN,

    -- Cost Analysis
    analyst_time_saved_hours FLOAT,
    estimated_cost_savings_usd FLOAT,

    analyzed_at TIMESTAMP NOT NULL,

    FOREIGN KEY (job_id) REFERENCES jobs(job_id),
    FOREIGN KEY (file_id) REFERENCES files(file_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at);
CREATE INDEX IF NOT EXISTS idx_files_job ON files(job_id);
CREATE INDEX IF NOT EXISTS idx_files_hash ON files(file_hash);
CREATE INDEX IF NOT EXISTS idx_av_scans_job_version ON av_scan_results(job_id, version);
CREATE INDEX IF NOT EXISTS idx_av_scans_malicious ON av_scan_results(is_malicious);
CREATE INDEX IF NOT EXISTS idx_edr_telemetry_job_version ON edr_telemetry(job_id, version);
CREATE INDEX IF NOT EXISTS idx_edr_alerts_severity ON edr_alerts(severity);
CREATE INDEX IF NOT EXISTS idx_edr_alerts_telemetry ON edr_alerts(telemetry_id);
CREATE INDEX IF NOT EXISTS idx_noise_analysis_job ON noise_reduction_analysis(job_id);

-- Views for easy querying

-- View: Job Summary with all metrics
CREATE VIEW IF NOT EXISTS vw_job_summary AS
SELECT
    j.job_id,
    j.status,
    j.created_at,
    j.completed_at,
    j.total_files,
    j.processed_files,
    COUNT(DISTINCT f.file_id) as unique_files,
    -- Phase 2 metrics
    SUM(CASE WHEN av.version = 'pre-cdr' AND av.is_malicious THEN 1 ELSE 0 END) as av_pre_detections,
    SUM(CASE WHEN av.version = 'post-cdr' AND av.is_malicious THEN 1 ELSE 0 END) as av_post_detections,
    -- Phase 3 metrics
    SUM(CASE WHEN edr.version = 'pre-cdr' THEN edr.total_alerts ELSE 0 END) as edr_pre_alerts,
    SUM(CASE WHEN edr.version = 'post-cdr' THEN edr.total_alerts ELSE 0 END) as edr_post_alerts,
    -- Overall reduction
    AVG(na.edr_alert_reduction_pct) as avg_alert_reduction_pct,
    AVG(na.total_noise_reduction_score) as avg_noise_reduction_score
FROM jobs j
LEFT JOIN files f ON j.job_id = f.job_id
LEFT JOIN av_scan_results av ON j.job_id = av.job_id
LEFT JOIN edr_telemetry edr ON j.job_id = edr.job_id
LEFT JOIN noise_reduction_analysis na ON j.job_id = na.job_id
GROUP BY j.job_id;

-- View: File-level comparison (pre vs post CDR)
CREATE VIEW IF NOT EXISTS vw_file_comparison AS
SELECT
    f.file_id,
    f.file_name,
    f.file_hash,
    f.job_id,
    -- AV detections
    SUM(CASE WHEN av.version = 'pre-cdr' AND av.is_malicious THEN 1 ELSE 0 END) as av_pre_detections,
    SUM(CASE WHEN av.version = 'post-cdr' AND av.is_malicious THEN 1 ELSE 0 END) as av_post_detections,
    -- EDR alerts
    SUM(CASE WHEN edr.version = 'pre-cdr' THEN edr.total_alerts ELSE 0 END) as edr_pre_alerts,
    SUM(CASE WHEN edr.version = 'post-cdr' THEN edr.total_alerts ELSE 0 END) as edr_post_alerts,
    -- Noise reduction
    MAX(na.edr_alert_reduction_pct) as alert_reduction_pct,
    MAX(na.cdr_effectiveness_rating) as effectiveness_rating
FROM files f
LEFT JOIN av_scan_results av ON f.file_id = av.file_id
LEFT JOIN edr_telemetry edr ON f.file_id = edr.file_id
LEFT JOIN noise_reduction_analysis na ON f.file_id = na.file_id
GROUP BY f.file_id;

-- View: Most noisy files (pre-CDR)
CREATE VIEW IF NOT EXISTS vw_noisiest_files AS
SELECT
    f.file_name,
    f.file_hash,
    COUNT(DISTINCT ea.alert_id) as total_alerts,
    SUM(CASE WHEN ea.severity = 'critical' THEN 1 ELSE 0 END) as critical_alerts,
    SUM(CASE WHEN ea.severity = 'high' THEN 1 ELSE 0 END) as high_alerts,
    STRING_AGG(DISTINCT ea.alert_name, ', ') as alert_types
FROM files f
JOIN edr_telemetry edr ON f.file_id = edr.file_id AND edr.version = 'pre-cdr'
JOIN edr_alerts ea ON edr.telemetry_id = ea.telemetry_id
GROUP BY f.file_name, f.file_hash
ORDER BY total_alerts DESC;
