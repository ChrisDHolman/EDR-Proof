"""
EDR Telemetry Parser
Extracts detailed alert information from EDR console responses
"""

import logging
from typing import List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class EDRTelemetryParser:
    """
    Parses raw EDR API responses into structured telemetry data

    Each EDR has different API formats - this normalizes them
    """

    @staticmethod
    def parse_crowdstrike_alerts(alerts_response: List[Dict]) -> Dict[str, Any]:
        """
        Parse CrowdStrike Falcon alerts

        CrowdStrike API reference: https://falcon.crowdstrike.com/documentation
        """
        telemetry = {
            'total_alerts': len(alerts_response),
            'high_severity_alerts': 0,
            'medium_severity_alerts': 0,
            'low_severity_alerts': 0,
            'informational_alerts': 0,
            'malware_alerts': 0,
            'suspicious_behavior_alerts': 0,
            'network_alerts': 0,
            'file_system_alerts': 0,
            'registry_alerts': 0,
            'process_alerts': 0,
            'signature_based_detections': 0,
            'behavioral_detections': 0,
            'machine_learning_detections': 0,
            'alerts': []
        }

        for alert in alerts_response:
            # Parse severity
            severity = alert.get('severity', 'unknown').lower()
            if severity in ['critical', 'high']:
                telemetry['high_severity_alerts'] += 1
            elif severity == 'medium':
                telemetry['medium_severity_alerts'] += 1
            elif severity == 'low':
                telemetry['low_severity_alerts'] += 1
            else:
                telemetry['informational_alerts'] += 1

            # Parse alert type
            alert_type = alert.get('type', '').lower()
            if 'malware' in alert_type:
                telemetry['malware_alerts'] += 1
            elif 'behavioral' in alert_type or 'suspicious' in alert_type:
                telemetry['suspicious_behavior_alerts'] += 1
            elif 'network' in alert_type:
                telemetry['network_alerts'] += 1
            elif 'file' in alert_type:
                telemetry['file_system_alerts'] += 1
            elif 'registry' in alert_type:
                telemetry['registry_alerts'] += 1
            elif 'process' in alert_type:
                telemetry['process_alerts'] += 1

            # Parse detection method
            detection_method = alert.get('detection_method', '').lower()
            if 'signature' in detection_method or 'ioc' in detection_method:
                telemetry['signature_based_detections'] += 1
            elif 'behavioral' in detection_method or 'ioa' in detection_method:
                telemetry['behavioral_detections'] += 1
            elif 'ml' in detection_method or 'machine' in detection_method:
                telemetry['machine_learning_detections'] += 1

            # Normalize alert for storage
            normalized_alert = {
                'alert_external_id': alert.get('id'),
                'alert_name': alert.get('name') or alert.get('tactic'),
                'alert_type': alert.get('type'),
                'alert_category': alert.get('category'),
                'severity': severity,
                'confidence_level': alert.get('confidence', 0),
                'risk_score': alert.get('severity_number', 0),
                'detection_method': alert.get('detection_method'),
                'technique': alert.get('technique'),  # MITRE ATT&CK
                'tactic': alert.get('tactic'),
                'process_name': alert.get('process', {}).get('file_name'),
                'process_path': alert.get('process', {}).get('file_path'),
                'process_command_line': alert.get('process', {}).get('command_line'),
                'process_hash': alert.get('process', {}).get('sha256'),
                'parent_process_name': alert.get('parent_process', {}).get('file_name'),
                'affected_file_path': alert.get('file', {}).get('file_path'),
                'affected_file_hash': alert.get('file', {}).get('sha256'),
                'file_operation': alert.get('file_operation'),
                'remote_ip': alert.get('network', {}).get('remote_ip'),
                'remote_port': alert.get('network', {}).get('remote_port'),
                'remote_domain': alert.get('network', {}).get('domain'),
                'network_protocol': alert.get('network', {}).get('protocol'),
                'registry_key': alert.get('registry', {}).get('key_name'),
                'registry_value': alert.get('registry', {}).get('value_name'),
                'registry_operation': alert.get('registry_operation'),
                'alert_timestamp': alert.get('timestamp') or datetime.now(),
                'first_seen': alert.get('first_behavior'),
                'last_seen': alert.get('last_behavior'),
                'description': alert.get('description'),
                'remediation_action': alert.get('status'),
                'false_positive_likely': alert.get('ioc_value') == 'false_positive',
                'raw_alert_json': str(alert)  # Store full JSON
            }

            telemetry['alerts'].append(normalized_alert)

        return telemetry

    @staticmethod
    def parse_sentinelone_alerts(alerts_response: List[Dict]) -> Dict[str, Any]:
        """
        Parse SentinelOne alerts

        SentinelOne API reference: https://usea1-partners.sentinelone.net/api-doc
        """
        telemetry = {
            'total_alerts': len(alerts_response),
            'high_severity_alerts': 0,
            'medium_severity_alerts': 0,
            'low_severity_alerts': 0,
            'informational_alerts': 0,
            'malware_alerts': 0,
            'suspicious_behavior_alerts': 0,
            'network_alerts': 0,
            'file_system_alerts': 0,
            'registry_alerts': 0,
            'process_alerts': 0,
            'signature_based_detections': 0,
            'behavioral_detections': 0,
            'machine_learning_detections': 0,
            'alerts': []
        }

        for alert in alerts_response:
            # Parse threat info
            threat_info = alert.get('threatInfo', {})

            # Severity mapping
            confidence_level = threat_info.get('confidenceLevel', 'unknown').lower()
            if confidence_level in ['malicious', 'high']:
                telemetry['high_severity_alerts'] += 1
            elif confidence_level == 'suspicious':
                telemetry['medium_severity_alerts'] += 1
            else:
                telemetry['low_severity_alerts'] += 1

            # Classification
            classification = threat_info.get('classification', '').lower()
            if 'malware' in classification:
                telemetry['malware_alerts'] += 1
            elif 'pua' in classification or 'suspicious' in classification:
                telemetry['suspicious_behavior_alerts'] += 1

            # Detection engines used
            engines = threat_info.get('engines', [])
            if any('static' in e.lower() or 'reputation' in e.lower() for e in engines):
                telemetry['signature_based_detections'] += 1
            if any('behavioral' in e.lower() for e in engines):
                telemetry['behavioral_detections'] += 1

            # Normalize alert
            normalized_alert = {
                'alert_external_id': alert.get('id'),
                'alert_name': threat_info.get('threatName'),
                'alert_type': threat_info.get('classification'),
                'alert_category': threat_info.get('classificationType'),
                'severity': confidence_level,
                'confidence_level': threat_info.get('confidenceLevel'),
                'risk_score': threat_info.get('threatScore', 0),
                'detection_method': ', '.join(engines),
                'technique': threat_info.get('mitreTechnique'),
                'tactic': threat_info.get('mitreTactic'),
                'process_name': threat_info.get('processUser'),
                'process_path': threat_info.get('filePath'),
                'process_hash': threat_info.get('sha256'),
                'affected_file_path': threat_info.get('filePath'),
                'affected_file_hash': threat_info.get('sha256'),
                'alert_timestamp': alert.get('createdAt') or datetime.now(),
                'description': threat_info.get('description'),
                'remediation_action': alert.get('mitigationStatus'),
                'raw_alert_json': str(alert)
            }

            telemetry['alerts'].append(normalized_alert)

        return telemetry

    @staticmethod
    def parse_sophos_alerts(alerts_response: List[Dict]) -> Dict[str, Any]:
        """
        Parse Sophos Central alerts

        Sophos API reference: https://api.central.sophos.com/api-docs
        """
        telemetry = {
            'total_alerts': len(alerts_response),
            'high_severity_alerts': 0,
            'medium_severity_alerts': 0,
            'low_severity_alerts': 0,
            'informational_alerts': 0,
            'malware_alerts': 0,
            'suspicious_behavior_alerts': 0,
            'network_alerts': 0,
            'file_system_alerts': 0,
            'registry_alerts': 0,
            'process_alerts': 0,
            'signature_based_detections': 0,
            'behavioral_detections': 0,
            'machine_learning_detections': 0,
            'alerts': []
        }

        for alert in alerts_response:
            # Parse severity
            severity = str(alert.get('severity', 'low')).lower()
            if severity in ['high', 'critical']:
                telemetry['high_severity_alerts'] += 1
            elif severity == 'medium':
                telemetry['medium_severity_alerts'] += 1
            else:
                telemetry['low_severity_alerts'] += 1

            # Parse type
            alert_type = alert.get('type', '').lower()
            if 'malware' in alert_type or 'virus' in alert_type:
                telemetry['malware_alerts'] += 1
                telemetry['signature_based_detections'] += 1
            elif 'runtime' in alert_type or 'behavioral' in alert_type:
                telemetry['suspicious_behavior_alerts'] += 1
                telemetry['behavioral_detections'] += 1
            elif 'web' in alert_type or 'network' in alert_type:
                telemetry['network_alerts'] += 1

            # Normalize alert
            normalized_alert = {
                'alert_external_id': alert.get('id'),
                'alert_name': alert.get('description'),
                'alert_type': alert.get('type'),
                'alert_category': alert.get('category'),
                'severity': severity,
                'risk_score': alert.get('riskScore', 0),
                'detection_method': alert.get('detectionType'),
                'process_name': alert.get('data', {}).get('processName'),
                'process_path': alert.get('data', {}).get('processPath'),
                'affected_file_path': alert.get('data', {}).get('filePath'),
                'remote_ip': alert.get('data', {}).get('remoteIp'),
                'remote_domain': alert.get('data', {}).get('url'),
                'alert_timestamp': alert.get('when') or datetime.now(),
                'description': alert.get('description'),
                'raw_alert_json': str(alert)
            }

            telemetry['alerts'].append(normalized_alert)

        return telemetry
