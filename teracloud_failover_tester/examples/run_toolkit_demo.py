#!/usr/bin/env python3
"""
Demonstration script for the Cross-DC Failover Toolkit integration.

This script shows how to use the CrossDCToolkitClient directly for monitoring
failover events without running a full test scenario.
"""

import os
import sys
import json
import time
import logging
import argparse
from typing import Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from streams_client.api_client import StreamsApiClient
from streams_client.crossdc_toolkit_client import CrossDCToolkitClient


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("toolkit_demo")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Cross-DC Failover Toolkit Demo"
    )
    parser.add_argument(
        "--primary-url",
        required=True,
        help="Primary DC API URL"
    )
    parser.add_argument(
        "--secondary-url",
        required=True,
        help="Secondary DC API URL"
    )
    parser.add_argument(
        "--auth-token",
        required=True,
        help="Authentication token for both DCs"
    )
    parser.add_argument(
        "--instance-id",
        required=True,
        help="Streams instance ID"
    )
    parser.add_argument(
        "--job-id",
        required=True,
        help="Streams job ID with toolkit integration"
    )
    parser.add_argument(
        "--monitor-time",
        type=int,
        default=300,
        help="Time to monitor failover status (seconds)"
    )
    parser.add_argument(
        "--output",
        default="toolkit_demo_output.json",
        help="File to save results to"
    )
    
    return parser.parse_args()


def monitor_toolkit_status(args):
    """Monitor toolkit status for the specified time."""
    logger.info("Initializing API clients")
    
    # Create API clients
    primary_api_client = StreamsApiClient(
        base_url=args.primary_url,
        auth_token=args.auth_token
    )
    
    secondary_api_client = StreamsApiClient(
        base_url=args.secondary_url,
        auth_token=args.auth_token
    )
    
    # Create toolkit client
    toolkit_config = {
        "instance_id": args.instance_id,
        "job_id": args.job_id,
        "status_check_interval_seconds": 5,
        "local_dc_name": "primary-dc",
        "remote_dc_name": "secondary-dc"
    }
    
    toolkit_client = CrossDCToolkitClient(
        primary_api_client=primary_api_client,
        secondary_api_client=secondary_api_client,
        config=toolkit_config
    )
    
    # Get initial status
    logger.info("Getting initial toolkit status")
    try:
        initial_status = toolkit_client.get_failover_status()
        logger.info(f"Initial status: {json.dumps(initial_status, indent=2)}")
    except Exception as e:
        logger.error(f"Error getting initial status: {str(e)}")
        return
    
    # Monitor for failover events
    logger.info(f"Monitoring failover status for {args.monitor_time} seconds")
    try:
        result = toolkit_client.monitor_failover_status(timeout_seconds=args.monitor_time)
        
        # Get service availability
        availability = toolkit_client.get_service_availability()
        result["service_availability"] = availability
        
        # Get toolkit metrics
        metrics = toolkit_client.get_toolkit_metrics()
        result["toolkit_metrics"] = metrics
        
        # Save results to file
        with open(args.output, 'w') as f:
            json.dump(result, f, indent=2)
        
        # Display summary
        logger.info("Monitoring completed:")
        logger.info(f"- Failover detected: {result.get('failover_detected', False)}")
        logger.info(f"- Monitoring duration: {result.get('monitoring_duration', 0):.2f} seconds")
        logger.info(f"- Primary DC status: {result.get('final_status', {}).get('primary_dc_status', 'unknown')}")
        logger.info(f"- Secondary DC status: {result.get('final_status', {}).get('secondary_dc_status', 'unknown')}")
        logger.info(f"- Results saved to: {args.output}")
        
    except Exception as e:
        logger.error(f"Error monitoring failover status: {str(e)}")


def main():
    """Main entry point."""
    args = parse_args()
    logger.info("Starting Cross-DC Failover Toolkit Demo")
    monitor_toolkit_status(args)
    logger.info("Demo completed")


if __name__ == "__main__":
    main()