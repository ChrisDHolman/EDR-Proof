#!/usr/bin/env python3
"""
Test all API connections before running full pipeline
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.utils.config import get_config_manager
from src.integrations.edr import CrowdStrikeClient, SentinelOneClient, SophosClient
from src.integrations.av import VirusTotalScanner
from src.integrations.cdr import GlasswallClient
from src.integrations.siem import WazuhClient
from azure.identity import DefaultAzureCredential
from azure.mgmt.compute import ComputeManagementClient

def test_azure_auth():
    """Test Azure authentication"""
    print("\n" + "="*60)
    print("Testing Azure Authentication...")
    print("="*60)

    try:
        config_mgr = get_config_manager()
        azure_config = config_mgr.load_azure_config()

        credential = DefaultAzureCredential()
        compute_client = ComputeManagementClient(
            credential=credential,
            subscription_id=azure_config.subscription_id
        )

        # Try to list VMs as a test
        vms = list(compute_client.virtual_machines.list(azure_config.resource_group))

        print(f"✅ Azure authentication successful")
        print(f"   Subscription: {azure_config.subscription_id}")
        print(f"   Resource Group: {azure_config.resource_group}")
        print(f"   VMs found: {len(vms)}")
        return True

    except Exception as e:
        print(f"❌ Azure authentication failed: {e}")
        return False


def test_wazuh():
    """Test Wazuh API connection"""
    print("\n" + "="*60)
    print("Testing Wazuh SIEM Connection...")
    print("="*60)

    try:
        config_mgr = get_config_manager()
        wazuh_config = config_mgr.load_wazuh_config()

        client = WazuhClient(wazuh_config)

        if client.test_connection():
            agents = client.get_agents()
            print(f"✅ Wazuh connection successful")
            print(f"   API URL: {wazuh_config.api_url}")
            print(f"   Agents registered: {len(agents)}")
            return True
        else:
            print(f"❌ Wazuh authentication failed")
            return False

    except Exception as e:
        print(f"❌ Wazuh connection failed: {e}")
        return False


def test_crowdstrike():
    """Test CrowdStrike API connection"""
    print("\n" + "="*60)
    print("Testing CrowdStrike Falcon API...")
    print("="*60)

    try:
        config_mgr = get_config_manager()
        edr_config = config_mgr.load_edr_config()

        if not edr_config.crowdstrike_client_id:
            print("⚠️  CrowdStrike credentials not configured, skipping")
            return None

        client = CrowdStrikeClient(edr_config)

        if client.test_connection():
            print(f"✅ CrowdStrike connection successful")
            print(f"   Base URL: {edr_config.crowdstrike_base_url}")
            return True
        else:
            print(f"❌ CrowdStrike authentication failed")
            return False

    except Exception as e:
        print(f"❌ CrowdStrike connection failed: {e}")
        return False


def test_sentinelone():
    """Test SentinelOne API connection"""
    print("\n" + "="*60)
    print("Testing SentinelOne API...")
    print("="*60)

    try:
        config_mgr = get_config_manager()
        edr_config = config_mgr.load_edr_config()

        if not edr_config.sentinelone_api_token:
            print("⚠️  SentinelOne credentials not configured, skipping")
            return None

        client = SentinelOneClient(edr_config)

        if client.test_connection():
            print(f"✅ SentinelOne connection successful")
            print(f"   Console URL: {edr_config.sentinelone_console_url}")
            return True
        else:
            print(f"❌ SentinelOne authentication failed")
            return False

    except Exception as e:
        print(f"❌ SentinelOne connection failed: {e}")
        return False


def test_sophos():
    """Test Sophos API connection"""
    print("\n" + "="*60)
    print("Testing Sophos Central API...")
    print("="*60)

    try:
        config_mgr = get_config_manager()
        edr_config = config_mgr.load_edr_config()

        if not edr_config.sophos_api_key:
            print("⚠️  Sophos credentials not configured, skipping")
            return None

        client = SophosClient(edr_config)

        if client.test_connection():
            print(f"✅ Sophos connection successful")
            print(f"   API URL: {edr_config.sophos_api_url}")
            return True
        else:
            print(f"❌ Sophos authentication failed")
            return False

    except Exception as e:
        print(f"❌ Sophos connection failed: {e}")
        return False


def test_glasswall():
    """Test Glasswall CDR API connection"""
    print("\n" + "="*60)
    print("Testing Glasswall CDR API...")
    print("="*60)

    try:
        config_mgr = get_config_manager()
        cdr_config = config_mgr.load_cdr_config()

        if not cdr_config.glasswall_api_key:
            print("⚠️  Glasswall credentials not configured, skipping")
            return None

        client = GlasswallClient(cdr_config)

        if client.test_connection():
            print(f"✅ Glasswall connection successful")
            print(f"   API URL: {cdr_config.glasswall_api_url}")
            print(f"   Supported file types: {len(client.get_supported_file_types())}")
            return True
        else:
            print(f"❌ Glasswall connection failed")
            return False

    except Exception as e:
        print(f"❌ Glasswall connection failed: {e}")
        return False


def test_virustotal():
    """Test VirusTotal API connection"""
    print("\n" + "="*60)
    print("Testing VirusTotal API...")
    print("="*60)

    try:
        config_mgr = get_config_manager()
        av_config = config_mgr.load_av_config()

        if not av_config.commercial_av_api_key:
            print("⚠️  VirusTotal API key not configured, skipping")
            return None

        scanner = VirusTotalScanner(av_config)

        if scanner.is_available():
            print(f"✅ VirusTotal connection successful")
            print(f"   API Version: {scanner.get_version()}")
            return True
        else:
            print(f"❌ VirusTotal authentication failed")
            return False

    except Exception as e:
        print(f"❌ VirusTotal connection failed: {e}")
        return False


def main():
    """Run all connection tests"""
    print("\n" + "="*60)
    print("CDR VALIDATION PIPELINE - CONNECTION TESTS")
    print("="*60)

    results = {
        'Azure': test_azure_auth(),
        'Wazuh': test_wazuh(),
        'CrowdStrike': test_crowdstrike(),
        'SentinelOne': test_sentinelone(),
        'Sophos': test_sophos(),
        'Glasswall CDR': test_glasswall(),
        'VirusTotal': test_virustotal()
    }

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)

    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    skipped = sum(1 for v in results.values() if v is None)

    for service, result in results.items():
        if result is True:
            status = "✅ PASS"
        elif result is False:
            status = "❌ FAIL"
        else:
            status = "⚠️  SKIPPED"

        print(f"{status:12} {service}")

    print(f"\nTotal: {passed} passed, {failed} failed, {skipped} skipped")

    if failed > 0:
        print("\n⚠️  Some connections failed. Check credentials and network connectivity.")
        sys.exit(1)
    elif passed == 0:
        print("\n⚠️  No connections configured. Please set up API credentials.")
        sys.exit(1)
    else:
        print("\n✅ All configured connections successful!")
        sys.exit(0)


if __name__ == '__main__':
    main()
