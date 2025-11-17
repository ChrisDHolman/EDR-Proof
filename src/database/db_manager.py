"""
Database Manager for EDR-PROOF Results Storage
Handles all database operations for Phase 2 (AV) and Phase 3 (EDR) results
"""

import sqlite3
import logging
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
from contextlib import contextmanager
import json

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages SQLite database for storing and querying test results

    This is critical for:
    - Storing AV detection results (Phase 2)
    - Storing EDR telemetry and alerts (Phase 3)
    - Calculating noise reduction metrics
    - Generating reports and analytics
    """

    def __init__(self, db_path: str = None):
        """
        Initialize database manager

        Args:
            db_path: Path to SQLite database file (default: ./data/edr_proof.db)
        """
        if db_path is None:
            db_path = os.path.join(os.getcwd(), 'data', 'edr_proof.db')

        self.db_path = db_path

        # Ensure data directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        # Initialize database schema
        self._init_schema()

        logger.info(f"DatabaseManager initialized: {db_path}")

    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}", exc_info=True)
            raise
        finally:
            conn.close()

    def _init_schema(self):
        """Initialize database schema from SQL file"""
        schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')

        with open(schema_path, 'r') as f:
            schema_sql = f.read()

        with self.get_connection() as conn:
            conn.executescript(schema_sql)

        logger.info("Database schema initialized")

    # ==================== File Operations ====================

    def insert_file(self, job_id: str, file_path: str, file_hash: str,
                   file_size: int, file_type: str) -> int:
        """Insert a file record"""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO files (job_id, file_path, file_name, file_hash,
                                 file_size, file_type, uploaded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                job_id,
                file_path,
                os.path.basename(file_path),
                file_hash,
                file_size,
                file_type,
                datetime.now()
            ))
            return cursor.lastrowid

    # ==================== Phase 2: AV Results ====================

    def insert_av_scan_result(self, scan_data: Dict[str, Any]) -> int:
        """
        Insert AV scan result (Phase 2)

        This is CRITICAL for detection rate analysis
        """
        with self.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO av_scan_results (
                    job_id, file_id, av_engine, version, cdr_engine,
                    is_malicious, threat_name, threat_type, threat_family,
                    confidence, severity, engine_version, signature_version,
                    scan_time_ms, detection_methods, indicators_of_compromise,
                    file_reputation, scanned_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                scan_data['job_id'],
                scan_data['file_id'],
                scan_data['av_engine'],
                scan_data['version'],  # 'pre-cdr' or 'post-cdr'
                scan_data.get('cdr_engine'),
                scan_data['is_malicious'],
                scan_data.get('threat_name'),
                scan_data.get('threat_type'),
                scan_data.get('threat_family'),
                scan_data.get('confidence'),
                scan_data.get('severity'),
                scan_data.get('engine_version'),
                scan_data.get('signature_version'),
                scan_data.get('scan_time_ms'),
                json.dumps(scan_data.get('detection_methods', [])),
                json.dumps(scan_data.get('indicators_of_compromise', [])),
                scan_data.get('file_reputation'),
                datetime.now()
            ))
            return cursor.lastrowid

    def get_av_detection_comparison(self, job_id: str, file_id: int) -> Dict[str, Any]:
        """
        Compare AV detections pre vs post CDR for a specific file

        Returns detection rate reduction metrics
        """
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT
                    version,
                    COUNT(*) as scan_count,
                    SUM(CASE WHEN is_malicious THEN 1 ELSE 0 END) as detections,
                    AVG(confidence) as avg_confidence,
                    GROUP_CONCAT(DISTINCT threat_name) as threat_names
                FROM av_scan_results
                WHERE job_id = ? AND file_id = ?
                GROUP BY version
            """, (job_id, file_id))

            results = {row['version']: dict(row) for row in cursor.fetchall()}

            # Calculate reduction
            pre = results.get('pre-cdr', {'detections': 0})
            post = results.get('post-cdr', {'detections': 0})

            reduction = pre['detections'] - post['detections']
            reduction_pct = (reduction / pre['detections'] * 100) if pre['detections'] > 0 else 0

            return {
                'pre_cdr': pre,
                'post_cdr': post,
                'detection_reduction': reduction,
                'detection_reduction_pct': round(reduction_pct, 2)
            }

    # ==================== Phase 3: EDR Telemetry ====================

    def insert_edr_telemetry(self, telemetry_data: Dict[str, Any]) -> int:
        """
        Insert EDR telemetry summary (Phase 3)

        This captures the high-level alert counts from EDR console
        """
        with self.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO edr_telemetry (
                    job_id, file_id, edr_solution, version, cdr_engine,
                    vm_name, execution_started_at, execution_ended_at,
                    execution_duration_sec, execution_success,
                    total_alerts, high_severity_alerts, medium_severity_alerts,
                    low_severity_alerts, informational_alerts,
                    malware_alerts, suspicious_behavior_alerts, network_alerts,
                    file_system_alerts, registry_alerts, process_alerts,
                    signature_based_detections, behavioral_detections,
                    machine_learning_detections, tested_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                telemetry_data['job_id'],
                telemetry_data['file_id'],
                telemetry_data['edr_solution'],
                telemetry_data['version'],  # 'pre-cdr' or 'post-cdr'
                telemetry_data.get('cdr_engine'),
                telemetry_data['vm_name'],
                telemetry_data['execution_started_at'],
                telemetry_data['execution_ended_at'],
                telemetry_data.get('execution_duration_sec'),
                telemetry_data.get('execution_success', True),
                telemetry_data.get('total_alerts', 0),
                telemetry_data.get('high_severity_alerts', 0),
                telemetry_data.get('medium_severity_alerts', 0),
                telemetry_data.get('low_severity_alerts', 0),
                telemetry_data.get('informational_alerts', 0),
                telemetry_data.get('malware_alerts', 0),
                telemetry_data.get('suspicious_behavior_alerts', 0),
                telemetry_data.get('network_alerts', 0),
                telemetry_data.get('file_system_alerts', 0),
                telemetry_data.get('registry_alerts', 0),
                telemetry_data.get('process_alerts', 0),
                telemetry_data.get('signature_based_detections', 0),
                telemetry_data.get('behavioral_detections', 0),
                telemetry_data.get('machine_learning_detections', 0),
                datetime.now()
            ))
            return cursor.lastrowid

    def insert_edr_alert(self, alert_data: Dict[str, Any]) -> int:
        """
        Insert individual EDR alert (Phase 3)

        This is CRITICAL - stores every single alert/log entry from EDR console
        These are the "noise" we're trying to reduce with CDR
        """
        with self.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO edr_alerts (
                    telemetry_id, job_id, file_id, edr_solution,
                    alert_external_id, alert_name, alert_type, alert_category,
                    severity, confidence_level, risk_score,
                    detection_method, technique, tactic,
                    process_name, process_path, process_command_line, process_hash,
                    parent_process_name, affected_file_path, affected_file_hash,
                    file_operation, remote_ip, remote_port, remote_domain,
                    network_protocol, registry_key, registry_value, registry_operation,
                    alert_timestamp, first_seen, last_seen,
                    description, remediation_action, false_positive_likely,
                    raw_alert_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                alert_data['telemetry_id'],
                alert_data['job_id'],
                alert_data['file_id'],
                alert_data['edr_solution'],
                alert_data.get('alert_external_id'),
                alert_data['alert_name'],
                alert_data.get('alert_type'),
                alert_data.get('alert_category'),
                alert_data['severity'],
                alert_data.get('confidence_level'),
                alert_data.get('risk_score'),
                alert_data.get('detection_method'),
                alert_data.get('technique'),  # MITRE ATT&CK
                alert_data.get('tactic'),
                alert_data.get('process_name'),
                alert_data.get('process_path'),
                alert_data.get('process_command_line'),
                alert_data.get('process_hash'),
                alert_data.get('parent_process_name'),
                alert_data.get('affected_file_path'),
                alert_data.get('affected_file_hash'),
                alert_data.get('file_operation'),
                alert_data.get('remote_ip'),
                alert_data.get('remote_port'),
                alert_data.get('remote_domain'),
                alert_data.get('network_protocol'),
                alert_data.get('registry_key'),
                alert_data.get('registry_value'),
                alert_data.get('registry_operation'),
                alert_data['alert_timestamp'],
                alert_data.get('first_seen'),
                alert_data.get('last_seen'),
                alert_data.get('description'),
                alert_data.get('remediation_action'),
                alert_data.get('false_positive_likely', False),
                alert_data.get('raw_alert_json'),  # Store full JSON for deep analysis
                datetime.now()
            ))
            return cursor.lastrowid

    def get_edr_alert_comparison(self, job_id: str, file_id: int) -> Dict[str, Any]:
        """
        Compare EDR alerts pre vs post CDR for a specific file

        This is the KEY metric - shows noise reduction
        """
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT
                    version,
                    SUM(total_alerts) as total_alerts,
                    SUM(high_severity_alerts) as high_severity,
                    SUM(medium_severity_alerts) as medium_severity,
                    SUM(malware_alerts) as malware_alerts,
                    SUM(behavioral_detections) as behavioral
                FROM edr_telemetry
                WHERE job_id = ? AND file_id = ?
                GROUP BY version
            """, (job_id, file_id))

            results = {row['version']: dict(row) for row in cursor.fetchall()}

            pre = results.get('pre-cdr', {'total_alerts': 0})
            post = results.get('post-cdr', {'total_alerts': 0})

            reduction = pre['total_alerts'] - post['total_alerts']
            reduction_pct = (reduction / pre['total_alerts'] * 100) if pre['total_alerts'] > 0 else 0

            return {
                'pre_cdr': pre,
                'post_cdr': post,
                'alert_reduction': reduction,
                'alert_reduction_pct': round(reduction_pct, 2),
                'high_severity_reduction': pre.get('high_severity', 0) - post.get('high_severity', 0)
            }

    def get_edr_alerts_by_category(self, job_id: str, file_id: int, version: str) -> Dict[str, List]:
        """
        Get EDR alerts grouped by category for analysis

        Helps understand what types of alerts CDR eliminates
        """
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT
                    ea.alert_category,
                    ea.alert_type,
                    ea.severity,
                    COUNT(*) as count,
                    GROUP_CONCAT(DISTINCT ea.alert_name) as alert_names
                FROM edr_alerts ea
                JOIN edr_telemetry et ON ea.telemetry_id = et.telemetry_id
                WHERE ea.job_id = ? AND ea.file_id = ? AND et.version = ?
                GROUP BY ea.alert_category, ea.alert_type, ea.severity
                ORDER BY count DESC
            """, (job_id, file_id, version))

            return [dict(row) for row in cursor.fetchall()]

    # ==================== Noise Reduction Analysis ====================

    def calculate_noise_reduction(self, job_id: str, file_id: int, cdr_engine: str) -> Dict[str, Any]:
        """
        Calculate comprehensive noise reduction metrics

        This is the FINAL ROI calculation that proves CDR effectiveness
        """
        # Get AV comparison
        av_comparison = self.get_av_detection_comparison(job_id, file_id)

        # Get EDR comparison
        edr_comparison = self.get_edr_alert_comparison(job_id, file_id)

        # Calculate overall noise reduction score (0-100)
        av_weight = 0.3  # 30% weight for AV detection reduction
        edr_weight = 0.7  # 70% weight for EDR alert reduction

        noise_reduction_score = (
            av_comparison['detection_reduction_pct'] * av_weight +
            edr_comparison['alert_reduction_pct'] * edr_weight
        )

        # Determine effectiveness rating
        if noise_reduction_score >= 80:
            rating = 'excellent'
        elif noise_reduction_score >= 60:
            rating = 'good'
        elif noise_reduction_score >= 40:
            rating = 'fair'
        else:
            rating = 'poor'

        # Estimate analyst time saved (assuming 5 min per high severity alert)
        time_saved_hours = edr_comparison['high_severity_reduction'] * 5 / 60

        # Estimate cost savings ($50/hour for analyst time)
        cost_savings = time_saved_hours * 50

        analysis = {
            'job_id': job_id,
            'file_id': file_id,
            'cdr_engine': cdr_engine,
            'av_pre_cdr_detections': av_comparison['pre_cdr']['detections'],
            'av_post_cdr_detections': av_comparison['post_cdr']['detections'],
            'av_detection_reduction': av_comparison['detection_reduction'],
            'av_detection_reduction_pct': av_comparison['detection_reduction_pct'],
            'edr_pre_cdr_total_alerts': edr_comparison['pre_cdr']['total_alerts'],
            'edr_post_cdr_total_alerts': edr_comparison['post_cdr']['total_alerts'],
            'edr_alert_reduction': edr_comparison['alert_reduction'],
            'edr_alert_reduction_pct': edr_comparison['alert_reduction_pct'],
            'edr_pre_cdr_high_severity': edr_comparison['pre_cdr'].get('high_severity', 0),
            'edr_post_cdr_high_severity': edr_comparison['post_cdr'].get('high_severity', 0),
            'edr_high_severity_reduction': edr_comparison['high_severity_reduction'],
            'total_noise_reduction_score': round(noise_reduction_score, 2),
            'cdr_effectiveness_rating': rating,
            'recommended_for_production': noise_reduction_score >= 60,
            'analyst_time_saved_hours': round(time_saved_hours, 2),
            'estimated_cost_savings_usd': round(cost_savings, 2),
            'analyzed_at': datetime.now()
        }

        # Store analysis in database
        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO noise_reduction_analysis (
                    job_id, file_id, cdr_engine,
                    av_pre_cdr_detections, av_post_cdr_detections,
                    av_detection_reduction, av_detection_reduction_pct,
                    edr_pre_cdr_total_alerts, edr_post_cdr_total_alerts,
                    edr_alert_reduction, edr_alert_reduction_pct,
                    edr_pre_cdr_high_severity, edr_post_cdr_high_severity,
                    edr_high_severity_reduction,
                    total_noise_reduction_score, cdr_effectiveness_rating,
                    recommended_for_production, analyst_time_saved_hours,
                    estimated_cost_savings_usd, analyzed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, tuple(analysis.values()))

        return analysis

    # ==================== Query Methods ====================

    def get_job_summary(self, job_id: str) -> Dict[str, Any]:
        """Get comprehensive job summary with all metrics"""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM vw_job_summary WHERE job_id = ?
            """, (job_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_noisiest_files(self, job_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get files that generated the most EDR alerts (pre-CDR)

        These are the best candidates to show CDR ROI
        """
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT
                    f.file_name,
                    f.file_hash,
                    COUNT(DISTINCT ea.alert_id) as total_alerts,
                    SUM(CASE WHEN ea.severity = 'critical' THEN 1 ELSE 0 END) as critical_alerts,
                    SUM(CASE WHEN ea.severity = 'high' THEN 1 ELSE 0 END) as high_alerts
                FROM files f
                JOIN edr_telemetry edr ON f.file_id = edr.file_id AND edr.version = 'pre-cdr'
                JOIN edr_alerts ea ON edr.telemetry_id = ea.telemetry_id
                WHERE f.job_id = ?
                GROUP BY f.file_name, f.file_hash
                ORDER BY total_alerts DESC
                LIMIT ?
            """, (job_id, limit))
            return [dict(row) for row in cursor.fetchall()]

    def export_results_json(self, job_id: str) -> Dict[str, Any]:
        """Export complete job results as JSON for reporting"""
        summary = self.get_job_summary(job_id)

        with self.get_connection() as conn:
            # Get all files
            cursor = conn.execute("SELECT * FROM files WHERE job_id = ?", (job_id,))
            files = [dict(row) for row in cursor.fetchall()]

            # Get noise reduction analysis
            cursor = conn.execute("SELECT * FROM noise_reduction_analysis WHERE job_id = ?", (job_id,))
            analyses = [dict(row) for row in cursor.fetchall()]

        return {
            'job_summary': summary,
            'files': files,
            'noise_reduction_analyses': analyses,
            'export_timestamp': datetime.now().isoformat()
        }
