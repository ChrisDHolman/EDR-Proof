#!/usr/bin/env python3
"""
Simple CLI tool to run CDR validation tests
"""

import sys
import os
import argparse
import json
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.utils.config import get_config_manager
from src.utils.logger import setup_logging
from src.orchestrator.pipeline import TestOrchestrator


def print_banner():
    """Print welcome banner"""
    print("\n" + "="*80)
    print(" CDR VALIDATION PIPELINE")
    print(" Automated EDR/AV Alert Reduction Testing")
    print("="*80 + "\n")


def print_results(results: dict):
    """Pretty print test results"""
    print("\n" + "="*80)
    print(" TEST RESULTS")
    print("="*80)

    print(f"\nTest Run ID: {results['test_run_id']}")
    print(f"Status: {results['status'].upper()}")

    if results['status'] == 'error':
        print(f"\n❌ Error: {results.get('error', 'Unknown error')}")
        return

    if results['status'] != 'completed':
        print(f"\n⚠️  Test did not complete successfully")
        return

    print(f"File: {results['file_name']}")
    print(f"Hash: {results['file_hash'][:16]}...")

    # Pre-CDR results
    if 'pre_cdr' in results and results['pre_cdr']:
        pre = results['pre_cdr']
        print("\n" + "-"*80)
        print(" PRE-CDR RESULTS (Original File)")
        print("-"*80)
        print(f"  Total EDR Alerts:      {pre['total_edr_alerts']}")
        print(f"    • CrowdStrike:       {pre['edr_alerts_crowdstrike']}")
        print(f"    • SentinelOne:       {pre['edr_alerts_sentinelone']}")
        print(f"    • Sophos:            {pre['edr_alerts_sophos']}")
        print(f"  Total AV Detections:   {pre['total_av_detections']}")
        print(f"  Wazuh Total Alerts:    {pre['wazuh_total_alerts']}")
        print(f"  Duration:              {pre['duration_seconds']:.1f}s")

    # CDR processing
    if 'cdr_processing' in results:
        cdr = results['cdr_processing']
        print("\n" + "-"*80)
        print(" CDR PROCESSING (Glasswall)")
        print("-"*80)
        if cdr['success']:
            print(f"  Status:                ✅ Success")
            print(f"  Processing Time:       {cdr['processing_time_seconds']:.1f}s")
            size_reduction = ((cdr['file_size_before'] - cdr.get('file_size_after', 0)) / cdr['file_size_before'] * 100)
            print(f"  File Size:             {cdr['file_size_before']:,} → {cdr.get('file_size_after', 0):,} bytes ({size_reduction:.1f}% reduction)")
        else:
            print(f"  Status:                ❌ Failed")
            print(f"  Error:                 {cdr.get('error_message', 'Unknown')}")

    # Post-CDR results
    if 'post_cdr' in results and results['post_cdr']:
        post = results['post_cdr']
        print("\n" + "-"*80)
        print(" POST-CDR RESULTS (Sanitized File)")
        print("-"*80)
        print(f"  Total EDR Alerts:      {post['total_edr_alerts']}")
        print(f"    • CrowdStrike:       {post['edr_alerts_crowdstrike']}")
        print(f"    • SentinelOne:       {post['edr_alerts_sentinelone']}")
        print(f"    • Sophos:            {post['edr_alerts_sophos']}")
        print(f"  Total AV Detections:   {post['total_av_detections']}")
        print(f"  Wazuh Total Alerts:    {post['wazuh_total_alerts']}")
        print(f"  Duration:              {post['duration_seconds']:.1f}s")

    # Comparison
    if 'comparison' in results:
        comp = results['comparison']
        print("\n" + "-"*80)
        print(" COMPARISON & ROI")
        print("-"*80)
        print(f"  EDR Alert Reduction:   {comp['edr_alerts_pre']} → {comp['edr_alerts_post']}  ({comp['edr_reduction_percentage']:.1f}% reduction)")
        print(f"  AV Detection Reduction: {comp['av_detections_pre']} → {comp['av_detections_post']}  ({comp['av_reduction_percentage']:.1f}% reduction)")
        print(f"  Wazuh Alert Reduction: {comp['wazuh_alerts_pre']} → {comp['wazuh_alerts_post']}  ({comp['wazuh_reduction_percentage']:.1f}% reduction)")

        if comp['overall_success']:
            print(f"\n  ✅ CDR VALIDATION SUCCESSFUL - Alert noise reduced!")
        else:
            print(f"\n  ⚠️  No alert reduction detected")

    print("\n" + "="*80 + "\n")


def save_results(results: dict, output_file: str):
    """Save results to JSON file"""
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"Results saved to: {output_file}")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='Run CDR validation test on a file',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run full test on a file
  python scripts/run_test.py --file samples/suspicious-doc.pdf

  # Test with custom output file
  python scripts/run_test.py --file malware.exe --output results.json

  # Use specific Key Vault
  python scripts/run_test.py --file doc.docx --keyvault https://my-kv.vault.azure.net/
        """
    )

    parser.add_argument(
        '--file',
        required=True,
        help='Path to file to test'
    )

    parser.add_argument(
        '--output',
        default=None,
        help='Output file for results (JSON)'
    )

    parser.add_argument(
        '--keyvault',
        default=None,
        help='Azure Key Vault URL for secrets'
    )

    parser.add_argument(
        '--log-level',
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Logging level'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Validate configuration without running test'
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(level=args.log_level)

    # Print banner
    print_banner()

    # Check file exists
    if not os.path.exists(args.file):
        print(f"❌ Error: File not found: {args.file}")
        sys.exit(1)

    print(f"File to test: {args.file}")
    print(f"File size: {os.path.getsize(args.file):,} bytes")

    # Initialize configuration
    print("\nInitializing configuration...")
    try:
        config_mgr = get_config_manager(args.keyvault)
        print("✅ Configuration loaded")
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        sys.exit(1)

    if args.dry_run:
        print("\n✅ Dry run successful - configuration valid")
        print("\nRemove --dry-run flag to execute the test.")
        sys.exit(0)

    # Initialize orchestrator
    print("\nInitializing test orchestrator...")
    try:
        orchestrator = TestOrchestrator(config_mgr)
        print("✅ Orchestrator initialized")
    except Exception as e:
        print(f"❌ Orchestrator initialization error: {e}")
        sys.exit(1)

    # Run test
    print("\n" + "="*80)
    print(" STARTING TEST PIPELINE")
    print("="*80)
    print("\n⚠️  This will provision Azure VMs and incur costs (~$0.05-0.10 per test)")
    print("⏱️  Estimated time: 20-25 minutes\n")

    input("Press Enter to continue or Ctrl+C to cancel...")

    print("\nRunning test...")
    start_time = datetime.now()

    try:
        results = orchestrator.run_full_test(args.file)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    # Print results
    print_results(results)
    print(f"Total execution time: {duration:.1f}s ({duration/60:.1f} minutes)")

    # Save results
    if args.output:
        output_file = args.output
    else:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = f"results_{timestamp}.json"

    save_results(results, output_file)

    # Exit with appropriate code
    if results['status'] == 'completed':
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()
