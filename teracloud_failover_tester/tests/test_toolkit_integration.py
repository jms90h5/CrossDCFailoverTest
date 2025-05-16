#!/usr/bin/env python3
"""
Test script for the Cross-DC Failover Toolkit integration.
"""

import os
import sys
import json
import time
import logging
import unittest
from unittest.mock import MagicMock, patch

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from streams_client.api_client import StreamsApiClient
from streams_client.crossdc_toolkit_client import CrossDCToolkitClient
from orchestrator.test_orchestrator import TestOrchestrator
from config.config_manager import ConfigManager


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TestToolkitIntegration(unittest.TestCase):
    """Tests for the Cross-DC Failover Toolkit integration."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock API clients
        self.primary_api_client = MagicMock(spec=StreamsApiClient)
        self.secondary_api_client = MagicMock(spec=StreamsApiClient)
        
        # Define configuration
        self.config = {
            "crossdc_toolkit": {
                "instance_id": "test-instance",
                "job_id": "test-job-123",
                "status_check_interval_seconds": 1,
                "local_dc_name": "dc1",
                "remote_dc_name": "dc2",
                "operation_mode": 1
            }
        }

    def test_toolkit_client_initialization(self):
        """Test that the toolkit client initializes correctly."""
        client = CrossDCToolkitClient(
            primary_api_client=self.primary_api_client,
            secondary_api_client=self.secondary_api_client,
            config=self.config["crossdc_toolkit"]
        )
        
        self.assertEqual(client.instance_id, "test-instance")
        self.assertEqual(client.job_id, "test-job-123")
        self.assertEqual(client.local_dc_name, "dc1")
        self.assertEqual(client.remote_dc_name, "dc2")
        self.assertEqual(client.operation_mode, 1)

    def test_get_failover_status(self):
        """Test getting failover status."""
        # Mock API responses
        self.primary_api_client.get_instance.return_value = {
            "id": "test-instance",
            "status": "running",
            "health": "healthy"
        }
        self.primary_api_client.get_job.return_value = {
            "id": "test-job-123",
            "status": "running",
            "health": "healthy"
        }
        self.secondary_api_client.get_instance.return_value = {
            "id": "test-instance",
            "status": "running",
            "health": "healthy"
        }
        self.secondary_api_client.get_job.return_value = {
            "id": "test-job-123",
            "status": "running",
            "health": "degraded"
        }
        
        # Create client and get status
        client = CrossDCToolkitClient(
            primary_api_client=self.primary_api_client,
            secondary_api_client=self.secondary_api_client,
            config=self.config["crossdc_toolkit"]
        )
        
        status = client.get_failover_status()
        
        # Verify status
        self.assertEqual(status["primary_dc_status"], "up")
        self.assertEqual(status["secondary_dc_status"], "degraded")
        self.assertFalse(status["failover_detected"])

    def test_failover_detection(self):
        """Test that failover is detected correctly."""
        # Mock API responses to simulate primary DC failure
        self.primary_api_client.get_instance.side_effect = Exception("Connection failed")
        
        self.secondary_api_client.get_instance.return_value = {
            "id": "test-instance",
            "status": "running",
            "health": "healthy"
        }
        self.secondary_api_client.get_job.return_value = {
            "id": "test-job-123",
            "status": "running",
            "health": "healthy"
        }
        
        # Create client and get status
        client = CrossDCToolkitClient(
            primary_api_client=self.primary_api_client,
            secondary_api_client=self.secondary_api_client,
            config=self.config["crossdc_toolkit"]
        )
        
        # First check should detect primary DC failure
        status = client.get_failover_status()
        
        # Verify status
        self.assertEqual(status["primary_dc_status"], "down")
        self.assertEqual(status["secondary_dc_status"], "up")
        self.assertTrue(status["failover_detected"])
        self.assertIsNotNone(status["failover_time"])

    @patch('streams_client.api_client.StreamsApiClient')
    @patch('config.config_manager.ConfigManager.load_config')
    def test_orchestrator_integration(self, mock_load_config, mock_api_client):
        """Test integration with the test orchestrator."""
        # Mock configuration and scenario
        mock_load_config.return_value = {
            "datacenters": {
                "primary": {
                    "api_url": "https://primary-dc-api.example.com",
                    "auth_token": "test-token",
                    "instance_id": "test-instance"
                },
                "secondary": {
                    "api_url": "https://secondary-dc-api.example.com",
                    "auth_token": "test-token",
                    "instance_id": "test-instance"
                }
            },
            "crossdc_toolkit": self.config["crossdc_toolkit"],
            "fault_injection": {},
            "monitoring": {}
        }
        
        # Mock test scenario
        test_scenario = {
            "test_id": "toolkit_test",
            "job_id": "test-job-123",
            "expected_recovery_time_seconds": 60
        }
        
        # Create and setup mock API clients
        mock_primary_api = MagicMock()
        mock_secondary_api = MagicMock()
        mock_api_client.side_effect = [mock_primary_api, mock_secondary_api]
        
        # Configure mocks for get_failover_status
        mock_primary_api.get_instance.return_value = {"status": "running", "health": "healthy"}
        mock_primary_api.get_job.return_value = {"status": "running", "health": "healthy"}
        mock_secondary_api.get_instance.return_value = {"status": "running", "health": "healthy"}
        mock_secondary_api.get_job.return_value = {"status": "running", "health": "healthy"}
        
        # Create test orchestrator
        config = ConfigManager.load_config()
        orchestrator = TestOrchestrator(
            config=config,
            test_scenario=test_scenario,
            output_dir="/tmp/test_output",
            skip_cleanup=True
        )
        
        # Verify CrossDCToolkitClient was initialized correctly
        self.assertIsNotNone(orchestrator.crossdc_client)
        self.assertEqual(orchestrator.crossdc_client.instance_id, "test-instance")
        self.assertEqual(orchestrator.crossdc_client.job_id, "test-job-123")

    @patch('streams_client.api_client.StreamsApiClient')
    def test_monitor_failover_status(self, mock_api_client):
        """Test monitoring failover status over time."""
        # Create mocks for API clients
        mock_primary_api = MagicMock()
        mock_secondary_api = MagicMock()
        mock_api_client.side_effect = [mock_primary_api, mock_secondary_api]
        
        # First call - normal operation
        mock_primary_api.get_instance.return_value = {"status": "running", "health": "healthy"}
        mock_primary_api.get_job.return_value = {"status": "running", "health": "healthy"}
        mock_secondary_api.get_instance.return_value = {"status": "running", "health": "healthy"}
        mock_secondary_api.get_job.return_value = {"status": "running", "health": "healthy"}
        
        # Create client
        client = CrossDCToolkitClient(
            primary_api_client=mock_primary_api,
            secondary_api_client=mock_secondary_api,
            config=self.config["crossdc_toolkit"]
        )
        
        # Start monitoring in a separate thread
        import threading
        monitor_results = []
        
        def monitor_thread():
            result = client.monitor_failover_status(timeout_seconds=3)
            monitor_results.append(result)
        
        thread = threading.Thread(target=monitor_thread)
        thread.start()
        
        # Let the monitoring start
        time.sleep(0.5)
        
        # Now simulate primary DC failure
        mock_primary_api.get_instance.side_effect = Exception("Connection failed")
        
        # Wait for monitoring to complete
        thread.join(timeout=5)
        
        # Check results
        self.assertTrue(len(monitor_results) > 0)
        result = monitor_results[0]
        self.assertTrue(result["failover_detected"])
        self.assertLess(result["monitoring_duration"], 3)  # Should finish before timeout


if __name__ == '__main__':
    unittest.main()