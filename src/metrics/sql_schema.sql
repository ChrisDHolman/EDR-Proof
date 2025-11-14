-- CDR Validation Metrics Database Schema
-- Azure SQL Database

-- Test Runs table (parent table for all tests)
CREATE TABLE test_runs (
    test_run_id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    run_timestamp DATETIME2 DEFAULT GETUTCDATE(),
    file_name NVARCHAR(500) NOT NULL,
    file_path NVARCHAR(1000) NOT NULL,
    file_hash_sha256 NVARCHAR(64) NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    file_type NVARCHAR(50),
    test_status NVARCHAR(50) DEFAULT 'in_progress', -- in_progress, completed, failed
    total_processing_time_seconds FLOAT,
    total_cost_usd DECIMAL(10, 4),
    created_by NVARCHAR(200) DEFAULT SYSTEM_USER,
    notes NVARCHAR(MAX),
    INDEX idx_test_runs_timestamp (run_timestamp DESC),
    INDEX idx_test_runs_file_hash (file_hash_sha256),
    INDEX idx_test_runs_status (test_status)
);

-- EDR Alerts table
CREATE TABLE edr_alerts (
    alert_id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    test_run_id UNIQUEIDENTIFIER NOT NULL FOREIGN KEY REFERENCES test_runs(test_run_id) ON DELETE CASCADE,
    phase NVARCHAR(20) NOT NULL CHECK (phase IN ('pre_cdr', 'post_cdr')),
    edr_vendor NVARCHAR(100) NOT NULL, -- CrowdStrike, SentinelOne, Sophos
    alert_timestamp DATETIME2 DEFAULT GETUTCDATE(),
    alert_count INT NOT NULL DEFAULT 0,
    alert_severity NVARCHAR(50), -- critical, high, medium, low, info
    alert_type NVARCHAR(200), -- malware, suspicious_behavior, policy_violation, etc.
    alert_details NVARCHAR(MAX), -- JSON with full alert details
    threat_detected BIT DEFAULT 0,
    false_positive BIT DEFAULT 0,
    processing_time_seconds FLOAT,
    vm_name NVARCHAR(200),
    INDEX idx_edr_alerts_test_run (test_run_id, phase),
    INDEX idx_edr_alerts_vendor (edr_vendor),
    INDEX idx_edr_alerts_severity (alert_severity)
);

-- AV Detections table
CREATE TABLE av_detections (
    detection_id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    test_run_id UNIQUEIDENTIFIER NOT NULL FOREIGN KEY REFERENCES test_runs(test_run_id) ON DELETE CASCADE,
    phase NVARCHAR(20) NOT NULL CHECK (phase IN ('pre_cdr', 'post_cdr')),
    av_vendor NVARCHAR(100) NOT NULL, -- Windows Defender, ClamAV, VirusTotal, etc.
    scan_timestamp DATETIME2 DEFAULT GETUTCDATE(),
    threats_found INT NOT NULL DEFAULT 0,
    threat_names NVARCHAR(MAX), -- Comma-separated or JSON array
    threat_categories NVARCHAR(MAX), -- malware, adware, pua, etc.
    scan_result NVARCHAR(50), -- clean, infected, suspicious, error
    scan_details NVARCHAR(MAX), -- JSON with full scan results
    quarantined BIT DEFAULT 0,
    false_positive BIT DEFAULT 0,
    scan_duration_seconds FLOAT,
    vm_name NVARCHAR(200),
    INDEX idx_av_detections_test_run (test_run_id, phase),
    INDEX idx_av_detections_vendor (av_vendor),
    INDEX idx_av_detections_result (scan_result)
);

-- CDR Processing table
CREATE TABLE cdr_processing (
    cdr_id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    test_run_id UNIQUEIDENTIFIER NOT NULL FOREIGN KEY REFERENCES test_runs(test_run_id) ON DELETE CASCADE,
    processing_timestamp DATETIME2 DEFAULT GETUTCDATE(),
    cdr_vendor NVARCHAR(100) DEFAULT 'Glasswall',
    input_file_hash NVARCHAR(64) NOT NULL,
    output_file_hash NVARCHAR(64),
    output_file_path NVARCHAR(1000),
    processing_status NVARCHAR(50), -- success, failed, partial
    threats_removed INT DEFAULT 0,
    macros_removed BIT DEFAULT 0,
    embedded_objects_removed INT DEFAULT 0,
    file_reconstructed BIT DEFAULT 1,
    processing_time_seconds FLOAT,
    error_message NVARCHAR(MAX),
    cdr_report NVARCHAR(MAX), -- JSON with detailed CDR report
    INDEX idx_cdr_test_run (test_run_id)
);

-- File Interactions table (track what was done with each file)
CREATE TABLE file_interactions (
    interaction_id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    test_run_id UNIQUEIDENTIFIER NOT NULL FOREIGN KEY REFERENCES test_runs(test_run_id) ON DELETE CASCADE,
    phase NVARCHAR(20) NOT NULL CHECK (phase IN ('pre_cdr', 'post_cdr')),
    interaction_timestamp DATETIME2 DEFAULT GETUTCDATE(),
    interaction_type NVARCHAR(100), -- execute, open_document, extract_archive, simulate_user
    interaction_status NVARCHAR(50), -- success, failed, crashed, timeout
    duration_seconds FLOAT,
    vm_name NVARCHAR(200),
    error_message NVARCHAR(MAX),
    interaction_log NVARCHAR(MAX), -- Detailed interaction log
    INDEX idx_interactions_test_run (test_run_id, phase)
);

-- VM Lifecycle table (track VM provisioning and teardown)
CREATE TABLE vm_lifecycle (
    vm_lifecycle_id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    test_run_id UNIQUEIDENTIFIER NOT NULL FOREIGN KEY REFERENCES test_runs(test_run_id) ON DELETE CASCADE,
    phase NVARCHAR(20) NOT NULL CHECK (phase IN ('pre_cdr', 'post_cdr')),
    vm_name NVARCHAR(200) NOT NULL,
    vm_id NVARCHAR(500), -- Azure VM resource ID
    vm_size NVARCHAR(50),
    provision_timestamp DATETIME2,
    teardown_timestamp DATETIME2,
    lifecycle_duration_seconds FLOAT,
    provision_status NVARCHAR(50), -- provisioned, failed
    teardown_status NVARCHAR(50), -- torn_down, failed
    cost_usd DECIMAL(10, 4),
    spot_instance BIT DEFAULT 1,
    INDEX idx_vm_lifecycle_test_run (test_run_id, phase),
    INDEX idx_vm_lifecycle_name (vm_name)
);

-- Wazuh Logs table (aggregated from Wazuh SIEM)
CREATE TABLE wazuh_logs (
    log_id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    test_run_id UNIQUEIDENTIFIER NOT NULL FOREIGN KEY REFERENCES test_runs(test_run_id) ON DELETE CASCADE,
    phase NVARCHAR(20) NOT NULL CHECK (phase IN ('pre_cdr', 'post_cdr')),
    log_timestamp DATETIME2 DEFAULT GETUTCDATE(),
    agent_name NVARCHAR(200),
    rule_id INT,
    rule_level INT,
    rule_description NVARCHAR(500),
    log_source NVARCHAR(200), -- edr, av, system
    log_data NVARCHAR(MAX), -- Full JSON log
    INDEX idx_wazuh_logs_test_run (test_run_id, phase),
    INDEX idx_wazuh_logs_level (rule_level)
);

-- Comparison Summary table (pre vs post CDR comparison)
CREATE TABLE comparison_summary (
    comparison_id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    test_run_id UNIQUEIDENTIFIER NOT NULL FOREIGN KEY REFERENCES test_runs(test_run_id) ON DELETE CASCADE,
    calculation_timestamp DATETIME2 DEFAULT GETUTCDATE(),

    -- EDR Metrics
    total_edr_alerts_pre INT DEFAULT 0,
    total_edr_alerts_post INT DEFAULT 0,
    edr_alert_reduction_count INT DEFAULT 0,
    edr_alert_reduction_percent DECIMAL(5, 2) DEFAULT 0,

    -- AV Metrics
    total_av_detections_pre INT DEFAULT 0,
    total_av_detections_post INT DEFAULT 0,
    av_detection_reduction_count INT DEFAULT 0,
    av_detection_reduction_percent DECIMAL(5, 2) DEFAULT 0,

    -- False Positives
    false_positives_pre INT DEFAULT 0,
    false_positives_post INT DEFAULT 0,
    false_positive_reduction_percent DECIMAL(5, 2) DEFAULT 0,

    -- Overall Metrics
    file_clean_post_cdr BIT DEFAULT 0,
    noise_reduction_score DECIMAL(5, 2) DEFAULT 0, -- Combined score 0-100

    -- Performance
    total_processing_time_seconds FLOAT,
    total_cost_usd DECIMAL(10, 4),
    roi_score DECIMAL(10, 2), -- Cost vs benefit analysis

    INDEX idx_comparison_test_run (test_run_id)
);

-- Create view for easy reporting
GO
CREATE VIEW vw_test_run_summary AS
SELECT
    tr.test_run_id,
    tr.run_timestamp,
    tr.file_name,
    tr.file_type,
    tr.file_hash_sha256,
    tr.test_status,
    tr.total_processing_time_seconds,
    tr.total_cost_usd,

    -- Pre-CDR EDR
    (SELECT COUNT(*) FROM edr_alerts WHERE test_run_id = tr.test_run_id AND phase = 'pre_cdr') as edr_alerts_pre,

    -- Post-CDR EDR
    (SELECT COUNT(*) FROM edr_alerts WHERE test_run_id = tr.test_run_id AND phase = 'post_cdr') as edr_alerts_post,

    -- Pre-CDR AV
    (SELECT SUM(threats_found) FROM av_detections WHERE test_run_id = tr.test_run_id AND phase = 'pre_cdr') as av_threats_pre,

    -- Post-CDR AV
    (SELECT SUM(threats_found) FROM av_detections WHERE test_run_id = tr.test_run_id AND phase = 'post_cdr') as av_threats_post,

    -- CDR Status
    (SELECT processing_status FROM cdr_processing WHERE test_run_id = tr.test_run_id) as cdr_status,

    -- Comparison
    cs.edr_alert_reduction_percent,
    cs.av_detection_reduction_percent,
    cs.noise_reduction_score,
    cs.file_clean_post_cdr

FROM test_runs tr
LEFT JOIN comparison_summary cs ON tr.test_run_id = cs.test_run_id;
GO

-- Stored procedure to calculate comparison metrics
CREATE PROCEDURE sp_calculate_comparison
    @test_run_id UNIQUEIDENTIFIER
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @edr_pre INT, @edr_post INT, @edr_reduction INT, @edr_reduction_pct DECIMAL(5,2);
    DECLARE @av_pre INT, @av_post INT, @av_reduction INT, @av_reduction_pct DECIMAL(5,2);
    DECLARE @fp_pre INT, @fp_post INT, @fp_reduction_pct DECIMAL(5,2);
    DECLARE @clean_post BIT, @noise_score DECIMAL(5,2);
    DECLARE @total_time FLOAT, @total_cost DECIMAL(10,4);

    -- Calculate EDR metrics
    SELECT @edr_pre = COALESCE(SUM(alert_count), 0)
    FROM edr_alerts
    WHERE test_run_id = @test_run_id AND phase = 'pre_cdr';

    SELECT @edr_post = COALESCE(SUM(alert_count), 0)
    FROM edr_alerts
    WHERE test_run_id = @test_run_id AND phase = 'post_cdr';

    SET @edr_reduction = @edr_pre - @edr_post;
    SET @edr_reduction_pct = CASE WHEN @edr_pre > 0 THEN (@edr_reduction * 100.0 / @edr_pre) ELSE 0 END;

    -- Calculate AV metrics
    SELECT @av_pre = COALESCE(SUM(threats_found), 0)
    FROM av_detections
    WHERE test_run_id = @test_run_id AND phase = 'pre_cdr';

    SELECT @av_post = COALESCE(SUM(threats_found), 0)
    FROM av_detections
    WHERE test_run_id = @test_run_id AND phase = 'post_cdr';

    SET @av_reduction = @av_pre - @av_post;
    SET @av_reduction_pct = CASE WHEN @av_pre > 0 THEN (@av_reduction * 100.0 / @av_pre) ELSE 0 END;

    -- Calculate false positives
    SELECT @fp_pre = COUNT(*)
    FROM (
        SELECT * FROM edr_alerts WHERE test_run_id = @test_run_id AND phase = 'pre_cdr' AND false_positive = 1
        UNION ALL
        SELECT * FROM av_detections WHERE test_run_id = @test_run_id AND phase = 'pre_cdr' AND false_positive = 1
    ) AS fp;

    SELECT @fp_post = COUNT(*)
    FROM (
        SELECT * FROM edr_alerts WHERE test_run_id = @test_run_id AND phase = 'post_cdr' AND false_positive = 1
        UNION ALL
        SELECT * FROM av_detections WHERE test_run_id = @test_run_id AND phase = 'post_cdr' AND false_positive = 1
    ) AS fp;

    SET @fp_reduction_pct = CASE WHEN @fp_pre > 0 THEN ((@fp_pre - @fp_post) * 100.0 / @fp_pre) ELSE 0 END;

    -- Check if file is clean post-CDR
    SET @clean_post = CASE WHEN @edr_post = 0 AND @av_post = 0 THEN 1 ELSE 0 END;

    -- Calculate noise reduction score (weighted average)
    SET @noise_score = (@edr_reduction_pct * 0.5) + (@av_reduction_pct * 0.5);

    -- Get performance metrics
    SELECT @total_time = total_processing_time_seconds, @total_cost = total_cost_usd
    FROM test_runs
    WHERE test_run_id = @test_run_id;

    -- Insert or update comparison summary
    MERGE comparison_summary AS target
    USING (SELECT @test_run_id AS test_run_id) AS source
    ON target.test_run_id = source.test_run_id
    WHEN MATCHED THEN
        UPDATE SET
            calculation_timestamp = GETUTCDATE(),
            total_edr_alerts_pre = @edr_pre,
            total_edr_alerts_post = @edr_post,
            edr_alert_reduction_count = @edr_reduction,
            edr_alert_reduction_percent = @edr_reduction_pct,
            total_av_detections_pre = @av_pre,
            total_av_detections_post = @av_post,
            av_detection_reduction_count = @av_reduction,
            av_detection_reduction_percent = @av_reduction_pct,
            false_positives_pre = @fp_pre,
            false_positives_post = @fp_post,
            false_positive_reduction_percent = @fp_reduction_pct,
            file_clean_post_cdr = @clean_post,
            noise_reduction_score = @noise_score,
            total_processing_time_seconds = @total_time,
            total_cost_usd = @total_cost
    WHEN NOT MATCHED THEN
        INSERT (test_run_id, total_edr_alerts_pre, total_edr_alerts_post, edr_alert_reduction_count,
                edr_alert_reduction_percent, total_av_detections_pre, total_av_detections_post,
                av_detection_reduction_count, av_detection_reduction_percent, false_positives_pre,
                false_positives_post, false_positive_reduction_percent, file_clean_post_cdr,
                noise_reduction_score, total_processing_time_seconds, total_cost_usd)
        VALUES (@test_run_id, @edr_pre, @edr_post, @edr_reduction, @edr_reduction_pct,
                @av_pre, @av_post, @av_reduction, @av_reduction_pct, @fp_pre, @fp_post,
                @fp_reduction_pct, @clean_post, @noise_score, @total_time, @total_cost);

    -- Return the summary
    SELECT * FROM comparison_summary WHERE test_run_id = @test_run_id;
END;
GO

-- Stored procedure to get overall statistics
CREATE PROCEDURE sp_get_overall_statistics
AS
BEGIN
    SET NOCOUNT ON;

    SELECT
        COUNT(DISTINCT test_run_id) as total_tests,
        AVG(noise_reduction_score) as avg_noise_reduction,
        AVG(edr_alert_reduction_percent) as avg_edr_reduction,
        AVG(av_detection_reduction_percent) as avg_av_reduction,
        SUM(CASE WHEN file_clean_post_cdr = 1 THEN 1 ELSE 0 END) as files_clean_post_cdr,
        AVG(total_processing_time_seconds) as avg_processing_time,
        SUM(total_cost_usd) as total_cost
    FROM comparison_summary;
END;
GO

-- Create indexes for performance
CREATE INDEX idx_test_runs_created ON test_runs(run_timestamp DESC);
CREATE INDEX idx_edr_phase_vendor ON edr_alerts(phase, edr_vendor);
CREATE INDEX idx_av_phase_vendor ON av_detections(phase, av_vendor);

-- Grant permissions (adjust as needed for your Azure AD users/service principals)
-- GRANT SELECT, INSERT, UPDATE ON DATABASE::cdr-metrics TO [your-service-principal];
