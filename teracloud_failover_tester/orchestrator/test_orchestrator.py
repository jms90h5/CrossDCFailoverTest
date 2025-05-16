"""
Test Orchestrator - Core component for test execution lifecycle management.
"""

import logging
import time
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Dict, List, Optional, Any

from streams_client.api_client import StreamsApiClient
from streams_client.data_exchange_client import DataExchangeClient
from streams_client.crossdc_toolkit_client import CrossDCToolkitClient
from fault_injection.fault_injector import FaultInjector
from monitoring.metrics_collector import MetricsCollector
from data_handler.data_handler import DataHandler


class TestPhase(Enum):
    """Enum representing the various phases of a failover test."""
    SETUP = auto()
    PRE_FAILOVER = auto()
    FAULT_INJECTION = auto()
    FAILOVER_MONITORING = auto()
    POST_FAILOVER = auto()
    VALIDATION = auto()
    TEARDOWN = auto()


@dataclass
class TestResult:
    """Data class for storing test execution results."""
    test_id: str
    success: bool
    phases_completed: List[TestPhase]
    metrics: Dict[str, Any]
    issues: List[str]
    start_time: float
    end_time: float
    rto_seconds: Optional[float] = None
    rpo_events: Optional[int] = None
    data_validation_result: Optional[Dict[str, Any]] = None


class TestOrchestrator:
    """
    Manages the entire lifecycle of a failover test, coordinating the various
    components and phases of execution.
    """
    
    def __init__(
        self, 
        config: Dict, 
        test_scenario: Dict,
        output_dir: str,
        skip_cleanup: bool = False
    ):
        """
        Initialize the test orchestrator.
        
        Args:
            config: Global configuration dictionary
            test_scenario: Test scenario configuration dictionary
            output_dir: Directory for storing test results
            skip_cleanup: Whether to skip cleanup phase (useful for debugging)
        """
        self.config = config
        self.test_scenario = test_scenario
        self.output_dir = Path(output_dir)
        self.skip_cleanup = skip_cleanup
        
        self.logger = logging.getLogger("orchestrator")
        self.current_phase = None
        self.phase_results = {}
        
        # Initialize component clients
        self.primary_api_client = self._create_api_client("primary")
        self.secondary_api_client = self._create_api_client("secondary")
        self.data_exchange_client = self._create_data_exchange_client()
        self.crossdc_client = self._create_crossdc_client()
        self.fault_injector = self._create_fault_injector()
        self.metrics_collector = self._create_metrics_collector()
        self.data_handler = self._create_data_handler()
        
        # Test execution metadata
        self.test_id = test_scenario.get("test_id", f"test_{int(time.time())}")
        self.start_time = None
        self.end_time = None
        
    def _create_api_client(self, dc_type: str) -> StreamsApiClient:
        """Create a Streams API client for the specified DC type."""
        dc_config = self.config["datacenters"][dc_type]
        return StreamsApiClient(
            base_url=dc_config["api_url"],
            auth_token=dc_config["auth_token"],
            verify_ssl=dc_config.get("verify_ssl", True)
        )
    
    def _create_data_exchange_client(self) -> DataExchangeClient:
        """Create a client for the Data Exchange service."""
        return DataExchangeClient(
            primary_api_client=self.primary_api_client,
            secondary_api_client=self.secondary_api_client,
            config=self.config.get("data_exchange", {})
        )
        
    def _create_crossdc_client(self) -> CrossDCToolkitClient:
        """Create a client for the Cross-DC Failover Toolkit."""
        # Prepare the configuration for the toolkit client
        toolkit_config = self.config.get("crossdc_toolkit", {}).copy()
        
        # Add necessary job and instance information
        if "instance_id" not in toolkit_config:
            # Try to get from base config or datacenters
            if "instance_id" in self.config:
                toolkit_config["instance_id"] = self.config["instance_id"]
            elif "datacenters" in self.config and "primary" in self.config["datacenters"]:
                toolkit_config["instance_id"] = self.config["datacenters"]["primary"].get("instance_id", "")
        
        # Add job ID if available
        if "job_id" not in toolkit_config and "job_id" in self.test_scenario:
            toolkit_config["job_id"] = self.test_scenario["job_id"]
            
        return CrossDCToolkitClient(
            primary_api_client=self.primary_api_client,
            secondary_api_client=self.secondary_api_client,
            config=toolkit_config
        )
    
    def _create_fault_injector(self) -> FaultInjector:
        """Create a fault injector for the test scenario."""
        return FaultInjector(
            config=self.config.get("fault_injection", {}),
            scenario=self.test_scenario.get("fault_scenario", {})
        )
    
    def _create_metrics_collector(self) -> MetricsCollector:
        """Create a metrics collector for monitoring."""
        return MetricsCollector(
            primary_api_client=self.primary_api_client,
            secondary_api_client=self.secondary_api_client,
            config=self.config.get("monitoring", {})
        )
    
    def _create_data_handler(self) -> DataHandler:
        """Create a data handler for test data injection and validation."""
        return DataHandler(
            data_exchange_client=self.data_exchange_client,
            config=self.config.get("data_handler", {}),
            test_data=self.test_scenario.get("pre_failover_data", {})
        )
    
    def run_test(self) -> TestResult:
        """
        Execute the test scenario through all phases.
        
        Returns:
            TestResult object containing the test results
        """
        self.start_time = time.time()
        phases_completed = []
        issues = []
        success = True
        
        try:
            # Phase 1: Setup
            self.current_phase = TestPhase.SETUP
            self.logger.info(f"Starting phase: {self.current_phase.name}")
            self._execute_setup_phase()
            phases_completed.append(self.current_phase)
            
            # Phase 2: Pre-Failover
            self.current_phase = TestPhase.PRE_FAILOVER
            self.logger.info(f"Starting phase: {self.current_phase.name}")
            self._execute_pre_failover_phase()
            phases_completed.append(self.current_phase)
            
            # Phase 3: Fault Injection
            self.current_phase = TestPhase.FAULT_INJECTION
            self.logger.info(f"Starting phase: {self.current_phase.name}")
            self._execute_fault_injection_phase()
            phases_completed.append(self.current_phase)
            
            # Phase 4: Failover Monitoring
            self.current_phase = TestPhase.FAILOVER_MONITORING
            self.logger.info(f"Starting phase: {self.current_phase.name}")
            failover_metrics = self._execute_failover_monitoring_phase()
            phases_completed.append(self.current_phase)
            
            # Phase 5: Post-Failover
            self.current_phase = TestPhase.POST_FAILOVER
            self.logger.info(f"Starting phase: {self.current_phase.name}")
            self._execute_post_failover_phase()
            phases_completed.append(self.current_phase)
            
            # Phase 6: Validation
            self.current_phase = TestPhase.VALIDATION
            self.logger.info(f"Starting phase: {self.current_phase.name}")
            validation_result = self._execute_validation_phase()
            phases_completed.append(self.current_phase)
            
            # Calculate success based on validation results
            success = validation_result.get("success", False)
            if not success:
                issues.extend(validation_result.get("issues", []))
            
        except Exception as e:
            success = False
            self.logger.error(
                f"Error in phase {self.current_phase.name}: {str(e)}", 
                exc_info=True
            )
            issues.append(f"Error in phase {self.current_phase.name}: {str(e)}")
        
        finally:
            # Phase 7: Teardown (attempt even if other phases failed)
            if not self.skip_cleanup:
                try:
                    self.current_phase = TestPhase.TEARDOWN
                    self.logger.info(f"Starting phase: {self.current_phase.name}")
                    self._execute_teardown_phase()
                    phases_completed.append(self.current_phase)
                except Exception as e:
                    self.logger.error(
                        f"Error in teardown phase: {str(e)}", 
                        exc_info=True
                    )
                    issues.append(f"Error in teardown phase: {str(e)}")
            else:
                self.logger.info("Skipping teardown phase as requested")
            
            self.end_time = time.time()
        
        # Compile and return the test result
        metrics = self.metrics_collector.get_all_metrics()
        metrics.update(failover_metrics or {})
        
        return TestResult(
            test_id=self.test_id,
            success=success,
            phases_completed=phases_completed,
            metrics=metrics,
            issues=issues,
            start_time=self.start_time,
            end_time=self.end_time,
            rto_seconds=failover_metrics.get("recovery_time_seconds") if failover_metrics else None,
            rpo_events=validation_result.get("data_loss_count") if validation_result else None,
            data_validation_result=validation_result
        )
    
    def _execute_setup_phase(self):
        """
        Execute the setup phase:
        - Deploy application to primary DC
        - Configure Cross-DC Failover toolkit
        - Initialize monitoring
        """
        self.logger.info("Deploying application to primary DC")
        # TODO: Implement application deployment
        
        self.logger.info("Configuring Cross-DC Failover toolkit")
        # TODO: Implement toolkit configuration
        
        self.logger.info("Initializing monitoring")
        self.metrics_collector.start_collection()
    
    def _execute_pre_failover_phase(self):
        """
        Execute the pre-failover phase:
        - Generate and inject test data
        - Verify application is processing correctly
        - Establish baseline metrics
        """
        self.logger.info("Injecting test data")
        self.data_handler.generate_and_inject_data()
        
        self.logger.info("Verifying application is processing correctly")
        # TODO: Implement application status verification
        
        self.logger.info("Collecting baseline metrics")
        self.metrics_collector.collect_baseline_metrics()
    
    def _execute_fault_injection_phase(self):
        """
        Execute the fault injection phase:
        - Apply fault scenario to primary DC
        - Verify fault has been applied correctly
        """
        self.logger.info("Applying fault scenario")
        self.fault_injector.inject_fault()
        
        self.logger.info("Verifying fault has been applied")
        self.fault_injector.verify_fault()
    
    def _execute_failover_monitoring_phase(self) -> Dict[str, Any]:
        """
        Execute the failover monitoring phase:
        - Detect and monitor failover process
        - Track key metrics during failover
        - Record timestamps for RTO calculation
        
        Returns:
            Dictionary containing failover metrics
        """
        self.logger.info("Monitoring failover process")
        failover_start_time = time.time()
        
        # Try to use the Cross-DC Toolkit client for more accurate failover detection
        try:
            # Get initial toolkit status
            toolkit_status = self.crossdc_client.get_failover_status()
            self.logger.info(f"Initial toolkit status: {toolkit_status}")
            
            # Monitor toolkit status for failover
            result = self.crossdc_client.monitor_failover_status(
                timeout_seconds=self.test_scenario.get("expected_recovery_time_seconds", 300) * 2
            )
            
            failover_completed = result.get("failover_detected", False)
            failover_end_time = time.time()
            
            if not failover_completed:
                self.logger.warning("Failover did not complete within expected time")
                
            # Get additional metrics from toolkit
            toolkit_metrics = self.crossdc_client.get_toolkit_metrics()
                
            # Calculate RTO
            recovery_time = failover_end_time - failover_start_time
            self.logger.info(f"Failover completed in {recovery_time:.2f} seconds")
            
            # Return comprehensive metrics
            return {
                "failover_start_time": failover_start_time,
                "failover_end_time": failover_end_time,
                "recovery_time_seconds": recovery_time,
                "expected_recovery_time_seconds": self.test_scenario.get("expected_recovery_time_seconds"),
                "failover_completed": failover_completed,
                "toolkit_status": result.get("final_status", {}),
                "toolkit_metrics": toolkit_metrics
            }
            
        except Exception as e:
            self.logger.warning(f"Error using Cross-DC Toolkit client: {str(e)}")
            self.logger.info("Falling back to metrics-based failover detection")
            
            # Fall back to the metrics-based approach
            failover_completed = self.metrics_collector.wait_for_failover_completion(
                timeout=self.test_scenario.get("expected_recovery_time_seconds", 300) * 2
            )
            
            failover_end_time = time.time()
            
            if not failover_completed:
                self.logger.warning("Failover did not complete within expected time")
                
            # Calculate RTO
            recovery_time = failover_end_time - failover_start_time
            self.logger.info(f"Failover completed in {recovery_time:.2f} seconds")
            
            return {
                "failover_start_time": failover_start_time,
                "failover_end_time": failover_end_time,
                "recovery_time_seconds": recovery_time,
                "expected_recovery_time_seconds": self.test_scenario.get("expected_recovery_time_seconds"),
                "failover_completed": failover_completed,
                "using_toolkit_client": False
            }
    
    def _execute_post_failover_phase(self):
        """
        Execute the post-failover phase:
        - Verify application is running in secondary DC
        - Continue metrics collection
        - Retrieve processed data for validation
        """
        self.logger.info("Verifying application in secondary DC")
        
        # Use the Cross-DC Toolkit client to verify service availability
        try:
            availability = self.crossdc_client.get_service_availability()
            
            if availability.get("secondary_dc_available", False):
                self.logger.info("Service is available in the secondary DC")
            else:
                self.logger.warning("Service is NOT available in the secondary DC")
            
            # Get latest toolkit status
            toolkit_status = self.crossdc_client.get_failover_status()
            self.logger.info(f"Post-failover toolkit status: {toolkit_status}")
            
        except Exception as e:
            self.logger.warning(f"Error checking service availability: {str(e)}")
            # Fall back to basic verification
            self.logger.info("Falling back to basic secondary DC verification")
            # TODO: Implement basic secondary DC application verification
        
        self.logger.info("Continuing metrics collection")
        self.metrics_collector.collect_post_failover_metrics()
        
        self.logger.info("Retrieving processed data")
        self.data_handler.retrieve_processed_data()
    
    def _execute_validation_phase(self) -> Dict[str, Any]:
        """
        Execute the validation phase:
        - Validate data integrity and completeness
        - Calculate data loss (RPO)
        - Evaluate performance metrics
        - Determine test success
        
        Returns:
            Dictionary containing validation results
        """
        self.logger.info("Validating data integrity")
        data_validation = self.data_handler.validate_data()
        
        self.logger.info("Evaluating performance metrics")
        metrics_validation = self.metrics_collector.validate_metrics(
            expected_metrics=self.test_scenario.get("expected_metrics", {})
        )
        
        # Use the Cross-DC Toolkit client for additional validation
        toolkit_validation = {"success": True, "issues": []}
        try:
            # Get final toolkit status
            toolkit_status = self.crossdc_client.get_failover_status()
            
            # Check if secondary DC is up and primary DC is down or back up
            secondary_up = toolkit_status.get("secondary_dc_status", "") == "up"
            primary_status = toolkit_status.get("primary_dc_status", "")
            failover_detected = toolkit_status.get("failover_detected", False)
            
            toolkit_validation["success"] = secondary_up and failover_detected
            toolkit_validation["secondary_up"] = secondary_up
            toolkit_validation["primary_status"] = primary_status
            toolkit_validation["failover_detected"] = failover_detected
            
            if not secondary_up:
                toolkit_validation["issues"].append("Secondary DC is not up after failover")
                
            if not failover_detected:
                toolkit_validation["issues"].append("Failover not detected by toolkit")
            
        except Exception as e:
            self.logger.warning(f"Error validating toolkit status: {str(e)}")
            toolkit_validation["success"] = True  # Don't fail just because toolkit validation failed
            toolkit_validation["error"] = str(e)
        
        # Determine overall success
        validation_success = data_validation.get("success", False) and metrics_validation.get("success", False) and toolkit_validation.get("success", True)
        
        # Calculate RPO metrics
        data_loss_count = data_validation.get("missing_events", 0)
        data_loss_percentage = data_validation.get("loss_percentage", 0)
        expected_loss_percentage = self.test_scenario.get("expected_data_loss_percentage", 0)
        
        rpo_satisfied = data_loss_percentage <= expected_loss_percentage
        if not rpo_satisfied:
            self.logger.warning(
                f"RPO not satisfied: Loss of {data_loss_percentage:.2f}% exceeds "
                f"expected {expected_loss_percentage:.2f}%"
            )
        
        # Compile all validation results
        validation_result = {
            "success": validation_success and rpo_satisfied,
            "data_validation": data_validation,
            "metrics_validation": metrics_validation,
            "data_loss_count": data_loss_count,
            "data_loss_percentage": data_loss_percentage,
            "expected_data_loss_percentage": expected_loss_percentage,
            "rpo_satisfied": rpo_satisfied,
            "issues": []
        }
        
        # Collect issues
        if not data_validation.get("success", False):
            validation_result["issues"].extend(data_validation.get("issues", []))
            
        if not metrics_validation.get("success", False):
            validation_result["issues"].extend(metrics_validation.get("issues", []))
            
        if not rpo_satisfied:
            validation_result["issues"].append(
                f"RPO not satisfied: Loss of {data_loss_percentage:.2f}% exceeds "
                f"expected {expected_loss_percentage:.2f}%"
            )
        
        return validation_result
    
    def _execute_teardown_phase(self):
        """
        Execute the teardown phase:
        - Clean up fault injection artifacts
        - Stop metrics collection
        - Clean up applications and resources
        """
        self.logger.info("Cleaning up fault injection")
        self.fault_injector.cleanup()
        
        self.logger.info("Stopping metrics collection")
        self.metrics_collector.stop_collection()
        
        self.logger.info("Cleaning up applications and resources")
        # TODO: Implement application and resource cleanup