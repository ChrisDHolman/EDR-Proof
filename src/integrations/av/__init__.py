"""
AV Scanner Integration Modules
"""
from .base import AVScanner, AVScanResult
from .defender import WindowsDefenderScanner
from .clamav import ClamAVScanner
from .virustotal import VirusTotalScanner

__all__ = [
    'AVScanner',
    'AVScanResult',
    'WindowsDefenderScanner',
    'ClamAVScanner',
    'VirusTotalScanner'
]
