"""
EDR Integration Modules
"""
from .base import EDRClient, EDRAlert, EDRDeploymentInfo
from .crowdstrike import CrowdStrikeClient
from .sentinelone import SentinelOneClient
from .sophos import SophosClient

__all__ = [
    'EDRClient',
    'EDRAlert',
    'EDRDeploymentInfo',
    'CrowdStrikeClient',
    'SentinelOneClient',
    'SophosClient'
]
