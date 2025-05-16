#!/usr/bin/env python3
"""
Teracloud Streams Automated Cross-DC Failover Tester
Main entry point for the framework
"""

import argparse
import logging
import os
import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from config.config_manager import ConfigManager
from orchestrator.test_orchestrator import TestOrchestrator
from reporting.report_generator import ReportGenerator
from utils.logging_utils import setup_logging


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Teracloud Streams Automated Cross-DC Failover Tester"
    )
    
    parser.add_argument(
        "--scenario", 
        required=True,
        help="Path to the test scenario YAML file"
    )
    
    parser.add_argument(
        "--config", 
        default=os.path.join("config", "config.yaml"),
        help="Path to the configuration file (default: config/config.yaml)"
    )
    
    parser.add_argument(
        "--report",
        choices=["junit", "html", "both", "none"],
        default="junit",
        help="Report format to generate (default: junit)"
    )
    
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set the logging level (default: INFO)"
    )
    
    parser.add_argument(
        "--output-dir",
        default="results",
        help="Directory to store test results and reports (default: results)"
    )
    
    parser.add_argument(
        "--skip-cleanup",
        action="store_true",
        help="Skip cleanup phase after test completion (useful for debugging)"
    )
    
    return parser.parse_args()


def main():
    """Main entry point for the failover testing framework."""
    # Parse command-line arguments
    args = parse_arguments()
    
    # Set up logging
    log_file = os.path.join(args.output_dir, "test_run.log")
    setup_logging(args.log_level, log_file)
    
    logger = logging.getLogger("main")
    logger.info("Starting Teracloud Streams Automated Cross-DC Failover Tester")
    
    try:
        # Ensure output directory exists
        os.makedirs(args.output_dir, exist_ok=True)
        
        # Load configuration
        logger.info(f"Loading configuration from {args.config}")
        config_manager = ConfigManager(args.config)
        config = config_manager.load_config()
        
        # Load test scenario
        logger.info(f"Loading test scenario from {args.scenario}")
        test_scenario = config_manager.load_scenario(args.scenario)
        
        # Initialize and run test orchestrator
        logger.info(f"Initializing test orchestrator")
        orchestrator = TestOrchestrator(
            config, 
            test_scenario,
            args.output_dir,
            skip_cleanup=args.skip_cleanup
        )
        
        # Run the test
        logger.info(f"Starting test execution")
        result = orchestrator.run_test()
        
        # Generate reports
        if args.report != "none":
            logger.info(f"Generating {args.report} reports")
            report_generator = ReportGenerator(args.output_dir)
            
            if args.report in ["junit", "both"]:
                report_generator.generate_junit_report(result)
                
            if args.report in ["html", "both"]:
                report_generator.generate_html_report(result)
        
        # Output final result
        status = "PASSED" if result.success else "FAILED"
        logger.info(f"Test execution {status}")
        print(f"\nTest execution {status}. See {log_file} for details.")
        print(f"Results and reports available in: {args.output_dir}")
        
        # Exit with appropriate status code
        sys.exit(0 if result.success else 1)
        
    except Exception as e:
        logger.error(f"Error during test execution: {str(e)}", exc_info=True)
        print(f"\nTest execution FAILED with error: {str(e)}")
        print(f"See {log_file} for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()