"""
API Fault Injector - Simulates failures using Teracloud Streams REST Management API.
"""

import logging
import time
from typing import Dict, Any, List, Optional, Tuple

from fault_injection.fault_injector import BaseFaultInjector
from streams_client.api_client import StreamsApiClient, APIError


class APIFaultInjectionError(Exception):
    """Exception for API fault injection errors."""
    pass


class APIFaultInjector(BaseFaultInjector):
    """
    Simulates failures by interacting with the Teracloud Streams REST Management API.
    
    This injector can stop jobs, terminate instances, or otherwise cause failures
    by calling the appropriate API endpoints.
    """
    
    def __init__(self, config: Dict[str, Any], scenario: Dict[str, Any]):
        """
        Initialize the API fault injector.
        
        Args:
            config: Global configuration including API client info
            scenario: Test scenario with API fault details
        """
        super().__init__(config, scenario)
        
        # Validate configuration
        self._validate_config()
        
        # Initialize API clients
        self.primary_api_client = self._create_api_client("primary")
        self.secondary_api_client = self._create_api_client("secondary")
        
        # Track injected faults
        self.injected_faults = []
    
    def inject_fault(self) -> Dict[str, Any]:
        """
        Inject the configured API fault.
        
        Returns:
            Dictionary with fault injection results
            
        Raises:
            APIFaultInjectionError: If fault injection fails
        """
        operation = self.scenario.get("api_operation", "").lower()
        
        self.logger.info(f"Injecting API fault with operation: {operation}")
        
        try:
            if operation == "stop_job":
                return self._stop_job()
            elif operation == "pause_job":
                return self._pause_job()
            elif operation == "terminate_instance":
                return self._terminate_instance()
            elif operation == "disable_operator":
                return self._disable_operator()
            elif operation == "trigger_failover":
                return self._trigger_failover()
            else:
                raise APIFaultInjectionError(f"Unsupported API operation: {operation}")
        except Exception as e:
            self.logger.error(f"API fault injection failed: {str(e)}", exc_info=True)
            raise APIFaultInjectionError(f"Failed to inject fault with operation {operation}: {str(e)}")
    
    def verify_fault(self) -> Dict[str, Any]:
        """
        Verify that the API fault has been applied correctly.
        
        Returns:
            Dictionary with verification results
            
        Raises:
            APIFaultInjectionError: If fault verification fails
        """
        operation = self.scenario.get("api_operation", "").lower()
        
        self.logger.info(f"Verifying API fault with operation: {operation}")
        
        try:
            if operation == "stop_job":
                return self._verify_job_stopped()
            elif operation == "pause_job":
                return self._verify_job_paused()
            elif operation == "terminate_instance":
                return self._verify_instance_terminated()
            elif operation == "disable_operator":
                return self._verify_operator_disabled()
            elif operation == "trigger_failover":
                return self._verify_failover_triggered()
            else:
                raise APIFaultInjectionError(f"Unsupported API operation for verification: {operation}")
        except Exception as e:
            self.logger.error(f"API fault verification failed: {str(e)}", exc_info=True)
            raise APIFaultInjectionError(f"Failed to verify fault with operation {operation}: {str(e)}")
    
    def cleanup(self) -> Dict[str, Any]:
        """
        Clean up API fault injection (not always applicable).
        
        Returns:
            Dictionary with cleanup results
        """
        self.logger.info("Cleaning up API fault injection (if applicable)")
        
        # Not all API operations can be undone
        operation = self.scenario.get("api_operation", "").lower()
        
        cleanup_results = {
            "success": True,
            "operation": operation,
            "actions_taken": []
        }
        
        # Most API faults can't be undone (like stopping a job or terminating an instance)
        # They will require manual intervention or system recovery
        
        self.injected_faults = []
        return cleanup_results
    
    def _validate_config(self):
        """
        Validate the API fault configuration.
        
        Raises:
            ValueError: If the configuration is invalid
        """
        # Check if we have the necessary configuration
        if not self.config or "datacenters" not in self.config:
            raise ValueError("Datacenter configuration is required for API fault injection")
        
        # Check for primary datacenter config
        if "primary" not in self.config["datacenters"]:
            raise ValueError("Primary datacenter configuration is required")
        
        # Check for required scenario parameters
        if "api_operation" not in self.scenario:
            raise ValueError("API operation must be specified")
            
        # Check operation-specific requirements
        operation = self.scenario.get("api_operation", "").lower()
        
        if operation in ["stop_job", "pause_job"]:
            if not self.scenario.get("instance_id") or not self.scenario.get("job_id"):
                raise ValueError("Instance ID and Job ID must be specified for job operations")
        elif operation == "terminate_instance":
            if not self.scenario.get("instance_id"):
                raise ValueError("Instance ID must be specified for terminate_instance operation")
        elif operation == "disable_operator":
            if not self.scenario.get("instance_id") or not self.scenario.get("job_id") or not self.scenario.get("operator_id"):
                raise ValueError("Instance ID, Job ID, and Operator ID must be specified for disable_operator operation")
    
    def _create_api_client(self, dc_type: str) -> StreamsApiClient:
        """
        Create an API client for the specified datacenter.
        
        Args:
            dc_type: Datacenter type ("primary" or "secondary")
            
        Returns:
            StreamsApiClient instance
            
        Raises:
            ValueError: If datacenter configuration is missing
        """
        dc_config = self.config.get("datacenters", {}).get(dc_type)
        
        if not dc_config:
            raise ValueError(f"{dc_type.capitalize()} datacenter configuration is required")
        
        return StreamsApiClient(
            base_url=dc_config["api_url"],
            auth_token=dc_config["auth_token"],
            verify_ssl=dc_config.get("verify_ssl", True)
        )
    
    def _stop_job(self) -> Dict[str, Any]:
        """
        Stop a job using the REST Management API.
        
        Returns:
            Dictionary with stop job results
            
        Raises:
            APIFaultInjectionError: If stopping the job fails
        """
        instance_id = self.scenario["instance_id"]
        job_id = self.scenario["job_id"]
        
        self.logger.info(f"Stopping job {job_id} in instance {instance_id}")
        
        try:
            # Use the appropriate client (usually primary)
            api_client = self.primary_api_client
            
            # Cancel the job
            result = api_client.cancel_job(instance_id, job_id)
            
            self.logger.info(f"Successfully stopped job {job_id}")
            
            # Track the injected fault
            self.injected_faults.append({
                "type": "stop_job",
                "instance_id": instance_id,
                "job_id": job_id,
                "timestamp": time.time()
            })
            
            return {
                "success": True,
                "operation": "stop_job",
                "instance_id": instance_id,
                "job_id": job_id,
                "api_result": result
            }
            
        except APIError as e:
            self.logger.error(f"Failed to stop job: {str(e)}")
            raise APIFaultInjectionError(f"Failed to stop job {job_id}: {str(e)}")
    
    def _pause_job(self) -> Dict[str, Any]:
        """
        Pause a job using the REST Management API.
        
        Returns:
            Dictionary with pause job results
            
        Raises:
            APIFaultInjectionError: If pausing the job fails
        """
        instance_id = self.scenario["instance_id"]
        job_id = self.scenario["job_id"]
        
        self.logger.info(f"Pausing job {job_id} in instance {instance_id}")
        
        try:
            # Use the appropriate client (usually primary)
            api_client = self.primary_api_client
            
            # Pause the job (implementation depends on API version)
            # Note: Check if the pause endpoint exists in your API version
            try:
                # Try with dedicated pause endpoint (if available)
                result = api_client._make_request(
                    "PUT", 
                    f"instances/{instance_id}/jobs/{job_id}/pause"
                )
            except APIError as e:
                # Fallback to updating job state if dedicated endpoint doesn't exist
                if "not found" in str(e).lower():
                    result = api_client._make_request(
                        "PATCH", 
                        f"instances/{instance_id}/jobs/{job_id}",
                        data={"state": "paused"}
                    )
                else:
                    raise
            
            self.logger.info(f"Successfully paused job {job_id}")
            
            # Track the injected fault
            self.injected_faults.append({
                "type": "pause_job",
                "instance_id": instance_id,
                "job_id": job_id,
                "timestamp": time.time()
            })
            
            return {
                "success": True,
                "operation": "pause_job",
                "instance_id": instance_id,
                "job_id": job_id,
                "api_result": result
            }
            
        except APIError as e:
            self.logger.error(f"Failed to pause job: {str(e)}")
            raise APIFaultInjectionError(f"Failed to pause job {job_id}: {str(e)}")
    
    def _terminate_instance(self) -> Dict[str, Any]:
        """
        Terminate a Streams instance using the REST Management API.
        
        Returns:
            Dictionary with terminate instance results
            
        Raises:
            APIFaultInjectionError: If terminating the instance fails
        """
        instance_id = self.scenario["instance_id"]
        
        self.logger.info(f"Terminating instance {instance_id}")
        
        try:
            # Use the appropriate client (usually primary)
            api_client = self.primary_api_client
            
            # Terminate the instance
            result = api_client._make_request(
                "DELETE", 
                f"instances/{instance_id}"
            )
            
            self.logger.info(f"Successfully initiated termination of instance {instance_id}")
            
            # Track the injected fault
            self.injected_faults.append({
                "type": "terminate_instance",
                "instance_id": instance_id,
                "timestamp": time.time()
            })
            
            return {
                "success": True,
                "operation": "terminate_instance",
                "instance_id": instance_id,
                "api_result": result
            }
            
        except APIError as e:
            self.logger.error(f"Failed to terminate instance: {str(e)}")
            raise APIFaultInjectionError(f"Failed to terminate instance {instance_id}: {str(e)}")
    
    def _disable_operator(self) -> Dict[str, Any]:
        """
        Disable an operator in a job using the REST Management API.
        
        Returns:
            Dictionary with disable operator results
            
        Raises:
            APIFaultInjectionError: If disabling the operator fails
        """
        instance_id = self.scenario["instance_id"]
        job_id = self.scenario["job_id"]
        operator_id = self.scenario["operator_id"]
        
        self.logger.info(f"Disabling operator {operator_id} in job {job_id}")
        
        try:
            # Use the appropriate client (usually primary)
            api_client = self.primary_api_client
            
            # Disable the operator
            # Note: The exact endpoint depends on the API version
            result = api_client._make_request(
                "PATCH", 
                f"instances/{instance_id}/jobs/{job_id}/operators/{operator_id}",
                data={"enabled": False}
            )
            
            self.logger.info(f"Successfully disabled operator {operator_id}")
            
            # Track the injected fault
            self.injected_faults.append({
                "type": "disable_operator",
                "instance_id": instance_id,
                "job_id": job_id,
                "operator_id": operator_id,
                "timestamp": time.time()
            })
            
            return {
                "success": True,
                "operation": "disable_operator",
                "instance_id": instance_id,
                "job_id": job_id,
                "operator_id": operator_id,
                "api_result": result
            }
            
        except APIError as e:
            self.logger.error(f"Failed to disable operator: {str(e)}")
            raise APIFaultInjectionError(f"Failed to disable operator {operator_id}: {str(e)}")
    
    def _trigger_failover(self) -> Dict[str, Any]:
        """
        Trigger a failover using the Cross-DC Failover Toolkit API.
        
        Returns:
            Dictionary with trigger failover results
            
        Raises:
            APIFaultInjectionError: If triggering failover fails
        """
        instance_id = self.scenario.get("instance_id")
        job_id = self.scenario.get("job_id")
        
        self.logger.info(f"Triggering failover for job {job_id} in instance {instance_id}")
        
        try:
            # Use the appropriate client (usually primary)
            api_client = self.primary_api_client
            
            # The failover trigger endpoint depends on the specific API
            # exposed by the Cross-DC Failover Toolkit
            
            # Note: This is a placeholder. The actual endpoint depends on the
            # Cross-DC Failover Toolkit implementation
            result = api_client._make_request(
                "POST", 
                f"instances/{instance_id}/jobs/{job_id}/failover/trigger"
            )
            
            self.logger.info(f"Successfully triggered failover for job {job_id}")
            
            # Track the injected fault
            self.injected_faults.append({
                "type": "trigger_failover",
                "instance_id": instance_id,
                "job_id": job_id,
                "timestamp": time.time()
            })
            
            return {
                "success": True,
                "operation": "trigger_failover",
                "instance_id": instance_id,
                "job_id": job_id,
                "api_result": result
            }
            
        except APIError as e:
            self.logger.error(f"Failed to trigger failover: {str(e)}")
            raise APIFaultInjectionError(f"Failed to trigger failover for job {job_id}: {str(e)}")
    
    def _verify_job_stopped(self) -> Dict[str, Any]:
        """
        Verify that a job has been stopped.
        
        Returns:
            Dictionary with verification results
            
        Raises:
            APIFaultInjectionError: If verification fails
        """
        instance_id = self.scenario["instance_id"]
        job_id = self.scenario["job_id"]
        
        self.logger.info(f"Verifying job {job_id} is stopped")
        
        try:
            # Use the appropriate client (usually primary)
            api_client = self.primary_api_client
            
            # Check job status
            try:
                job = api_client.get_job(instance_id, job_id)
                job_state = job.get("state", "").lower()
                
                # Check if job is cancelled/stopped
                is_stopped = job_state in ["canceled", "cancelled", "stopped"]
                
                if is_stopped:
                    self.logger.info(f"Job {job_id} is confirmed stopped (state: {job_state})")
                else:
                    self.logger.warning(f"Job {job_id} is not stopped (state: {job_state})")
                
                return {
                    "success": is_stopped,
                    "instance_id": instance_id,
                    "job_id": job_id,
                    "job_state": job_state,
                    "expected_state": "canceled/stopped"
                }
            except APIError as e:
                # If the job is not found, it could be considered stopped
                if "not found" in str(e).lower():
                    self.logger.info(f"Job {job_id} not found, considering it stopped")
                    return {
                        "success": True,
                        "instance_id": instance_id,
                        "job_id": job_id,
                        "job_state": "not_found",
                        "expected_state": "canceled/stopped"
                    }
                else:
                    raise
                
        except APIError as e:
            self.logger.error(f"Failed to verify job stopped: {str(e)}")
            raise APIFaultInjectionError(f"Failed to verify job {job_id} stopped: {str(e)}")
    
    def _verify_job_paused(self) -> Dict[str, Any]:
        """
        Verify that a job has been paused.
        
        Returns:
            Dictionary with verification results
            
        Raises:
            APIFaultInjectionError: If verification fails
        """
        instance_id = self.scenario["instance_id"]
        job_id = self.scenario["job_id"]
        
        self.logger.info(f"Verifying job {job_id} is paused")
        
        try:
            # Use the appropriate client (usually primary)
            api_client = self.primary_api_client
            
            # Check job status
            job = api_client.get_job(instance_id, job_id)
            job_state = job.get("state", "").lower()
            
            # Check if job is paused
            is_paused = job_state == "paused"
            
            if is_paused:
                self.logger.info(f"Job {job_id} is confirmed paused")
            else:
                self.logger.warning(f"Job {job_id} is not paused (state: {job_state})")
            
            return {
                "success": is_paused,
                "instance_id": instance_id,
                "job_id": job_id,
                "job_state": job_state,
                "expected_state": "paused"
            }
                
        except APIError as e:
            self.logger.error(f"Failed to verify job paused: {str(e)}")
            raise APIFaultInjectionError(f"Failed to verify job {job_id} paused: {str(e)}")
    
    def _verify_instance_terminated(self) -> Dict[str, Any]:
        """
        Verify that an instance has been terminated.
        
        Returns:
            Dictionary with verification results
            
        Raises:
            APIFaultInjectionError: If verification fails
        """
        instance_id = self.scenario["instance_id"]
        
        self.logger.info(f"Verifying instance {instance_id} is terminated")
        
        try:
            # Use the appropriate client (usually primary)
            api_client = self.primary_api_client
            
            # Check instance status
            try:
                instance = api_client.get_instance(instance_id)
                instance_status = instance.get("status", "").lower()
                
                # Check if instance is terminated/stopping
                is_terminated = instance_status in ["stopped", "terminated", "stopping"]
                
                if is_terminated:
                    self.logger.info(f"Instance {instance_id} is confirmed terminated (status: {instance_status})")
                else:
                    self.logger.warning(f"Instance {instance_id} is not terminated (status: {instance_status})")
                
                return {
                    "success": is_terminated,
                    "instance_id": instance_id,
                    "instance_status": instance_status,
                    "expected_status": "stopped/terminated"
                }
            except APIError as e:
                # If the instance is not found, it is considered terminated
                if "not found" in str(e).lower():
                    self.logger.info(f"Instance {instance_id} not found, considering it terminated")
                    return {
                        "success": True,
                        "instance_id": instance_id,
                        "instance_status": "not_found",
                        "expected_status": "stopped/terminated"
                    }
                else:
                    raise
                
        except APIError as e:
            self.logger.error(f"Failed to verify instance terminated: {str(e)}")
            raise APIFaultInjectionError(f"Failed to verify instance {instance_id} terminated: {str(e)}")
    
    def _verify_operator_disabled(self) -> Dict[str, Any]:
        """
        Verify that an operator has been disabled.
        
        Returns:
            Dictionary with verification results
            
        Raises:
            APIFaultInjectionError: If verification fails
        """
        instance_id = self.scenario["instance_id"]
        job_id = self.scenario["job_id"]
        operator_id = self.scenario["operator_id"]
        
        self.logger.info(f"Verifying operator {operator_id} is disabled")
        
        try:
            # Use the appropriate client (usually primary)
            api_client = self.primary_api_client
            
            # Check operator status
            result = api_client._make_request(
                "GET", 
                f"instances/{instance_id}/jobs/{job_id}/operators/{operator_id}"
            )
            
            # Check if operator is disabled
            # Note: The exact field depends on the API
            is_disabled = not result.get("enabled", True)
            
            if is_disabled:
                self.logger.info(f"Operator {operator_id} is confirmed disabled")
            else:
                self.logger.warning(f"Operator {operator_id} is not disabled")
            
            return {
                "success": is_disabled,
                "instance_id": instance_id,
                "job_id": job_id,
                "operator_id": operator_id,
                "operator_enabled": not is_disabled,
                "expected_enabled": False
            }
                
        except APIError as e:
            self.logger.error(f"Failed to verify operator disabled: {str(e)}")
            raise APIFaultInjectionError(f"Failed to verify operator {operator_id} disabled: {str(e)}")
    
    def _verify_failover_triggered(self) -> Dict[str, Any]:
        """
        Verify that a failover has been triggered.
        
        Returns:
            Dictionary with verification results
            
        Raises:
            APIFaultInjectionError: If verification fails
        """
        instance_id = self.scenario.get("instance_id")
        job_id = self.scenario.get("job_id")
        
        self.logger.info(f"Verifying failover triggered for job {job_id}")
        
        try:
            # Use the secondary client to verify the job is running there
            api_client = self.secondary_api_client
            
            # Check job status on secondary
            try:
                job = api_client.get_job(instance_id, job_id)
                job_state = job.get("state", "").lower()
                job_health = job.get("health", "").lower()
                
                # Check if job is running in secondary DC
                is_running = job_state == "running" and job_health == "healthy"
                
                if is_running:
                    self.logger.info(f"Job {job_id} is confirmed running in secondary DC")
                else:
                    self.logger.warning(
                        f"Job {job_id} is not properly running in secondary DC "
                        f"(state: {job_state}, health: {job_health})"
                    )
                
                return {
                    "success": is_running,
                    "instance_id": instance_id,
                    "job_id": job_id,
                    "secondary_job_state": job_state,
                    "secondary_job_health": job_health,
                    "expected_state": "running",
                    "expected_health": "healthy"
                }
            except APIError as e:
                # If the job is not found in secondary, failover didn't work
                self.logger.warning(f"Job {job_id} not found in secondary DC, failover failed")
                return {
                    "success": False,
                    "instance_id": instance_id,
                    "job_id": job_id,
                    "error": "Job not found in secondary DC"
                }
                
        except APIError as e:
            self.logger.error(f"Failed to verify failover: {str(e)}")
            raise APIFaultInjectionError(f"Failed to verify failover for job {job_id}: {str(e)}")