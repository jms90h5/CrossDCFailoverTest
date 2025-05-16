"""
Cross-DC Failover Toolkit Client - Monitors and interacts with the toolkit functionality.
"""

import json
import logging
import time
from typing import Dict, List, Any, Optional, Union

from streams_client.api_client import StreamsApiClient, APIError


class CrossDCToolkitError(Exception):
    """Base exception for Cross-DC Toolkit errors."""
    pass


class CrossDCToolkitClient:
    """
    Client for monitoring the Cross-DC Failover Toolkit.
    
    Since the toolkit does not expose a direct REST API, this client:
    1. Monitors the application's output streams via JMX metrics or logs
    2. Detects failover status changes by analyzing logs and metrics
    3. Uses the standard Streams REST Management API for application interaction
    """
    
    def __init__(
        self,
        primary_api_client: StreamsApiClient,
        secondary_api_client: StreamsApiClient,
        config: Dict[str, Any]
    ):
        """
        Initialize the Cross-DC Failover Toolkit client.
        
        Args:
            primary_api_client: API client for the primary data center
            secondary_api_client: API client for the secondary data center
            config: Configuration dictionary with toolkit-specific settings
        """
        self.primary_api_client = primary_api_client
        self.secondary_api_client = secondary_api_client
        self.config = config
        
        # Set up logger
        self.logger = logging.getLogger("crossdc_toolkit")
        
        # Get configuration values
        self.instance_id = config.get("instance_id", "")
        self.job_id = config.get("job_id", "")
        self.check_interval = config.get("status_check_interval_seconds", 10)
        
        # Toolkit-specific configuration
        self.local_dc_name = config.get("local_dc_name", "")
        self.remote_dc_name = config.get("remote_dc_name", "")
        self.operation_mode = config.get("operation_mode", 1)  # 1 = active, 0 = passive
        
        # Initialize state tracking
        self.last_known_status = None
        self.primary_datacenter_status = "unknown"
        self.secondary_datacenter_status = "unknown"
        self.failover_detected = False
        self.failover_time = None
    
    def get_failover_status(self) -> Dict[str, Any]:
        """
        Get the current failover status.
        
        Since the toolkit doesn't provide a direct API, this method:
        1. Checks the application logs for status information
        2. Monitors metrics that indicate failover status
        3. Infers the state based on application behavior
        
        Returns:
            Dictionary containing failover status information
            
        Raises:
            CrossDCToolkitError: If status retrieval fails
        """
        status = {
            "primary_dc_status": self.primary_datacenter_status,
            "secondary_dc_status": self.secondary_datacenter_status,
            "failover_detected": self.failover_detected,
            "failover_time": self.failover_time,
            "operation_mode": "active" if self.operation_mode == 1 else "passive",
            "local_dc_name": self.local_dc_name,
            "remote_dc_name": self.remote_dc_name
        }
        
        try:
            # Check if we have job and instance IDs
            if not self.instance_id or not self.job_id:
                self.logger.warning("Instance ID and/or Job ID not set, can't get detailed status")
                return status
            
            # Get primary DC status
            primary_status = self._check_datacenter_status(self.primary_api_client, "primary")
            
            # Get secondary DC status
            secondary_status = self._check_datacenter_status(self.secondary_api_client, "secondary")
            
            # Update status based on what we found
            status.update({
                "primary_dc_status": primary_status.get("status", self.primary_datacenter_status),
                "primary_dc_details": primary_status,
                "secondary_dc_status": secondary_status.get("status", self.secondary_datacenter_status),
                "secondary_dc_details": secondary_status
            })
            
            # Update internal state tracking
            self.primary_datacenter_status = status["primary_dc_status"]
            self.secondary_datacenter_status = status["secondary_dc_status"]
            
            # Check for failover condition
            if (self.primary_datacenter_status == "down" or self.primary_datacenter_status == "failed") and \
               self.secondary_datacenter_status == "up" and \
               not self.failover_detected:
                self.failover_detected = True
                self.failover_time = time.time()
                self.logger.info("Failover detected: Primary DC down, Secondary DC up")
            
            # Update status with failover detection
            status["failover_detected"] = self.failover_detected
            status["failover_time"] = self.failover_time
            
            return status
            
        except Exception as e:
            self.logger.error(f"Error getting failover status: {str(e)}", exc_info=True)
            raise CrossDCToolkitError(f"Failed to get failover status: {str(e)}")
    
    def monitor_failover_status(self, timeout_seconds: int = 300) -> Dict[str, Any]:
        """
        Monitor failover status for changes over time.
        
        Args:
            timeout_seconds: Maximum time to monitor in seconds
            
        Returns:
            Dictionary containing final status and state changes
            
        Raises:
            CrossDCToolkitError: If monitoring fails
        """
        self.logger.info(f"Monitoring failover status for {timeout_seconds} seconds")
        
        start_time = time.time()
        end_time = start_time + timeout_seconds
        status_history = []
        
        # Initialize with current status
        current_status = self.get_failover_status()
        status_history.append({
            "timestamp": start_time,
            "status": current_status
        })
        
        # Monitor until timeout
        while time.time() < end_time:
            time.sleep(self.check_interval)
            
            try:
                new_status = self.get_failover_status()
                
                # Check for state changes
                if self._status_changed(current_status, new_status):
                    self.logger.info(f"Failover status changed: {new_status}")
                    
                    # Record the change
                    status_history.append({
                        "timestamp": time.time(),
                        "status": new_status
                    })
                    
                    current_status = new_status
                
                # Check if we've detected failover completion
                if new_status.get("failover_detected", False):
                    # Allow some additional time for stabilization
                    time.sleep(self.check_interval * 2)
                    final_status = self.get_failover_status()
                    
                    status_history.append({
                        "timestamp": time.time(),
                        "status": final_status,
                        "event": "monitoring_complete_failover_detected"
                    })
                    
                    return {
                        "final_status": final_status,
                        "history": status_history,
                        "failover_detected": True,
                        "monitoring_duration": time.time() - start_time
                    }
                    
            except Exception as e:
                self.logger.warning(f"Error during status check: {str(e)}")
                
                # Record the error
                status_history.append({
                    "timestamp": time.time(),
                    "error": str(e)
                })
        
        # Timeout reached
        final_status = self.get_failover_status()
        status_history.append({
            "timestamp": time.time(),
            "status": final_status,
            "event": "monitoring_complete_timeout"
        })
        
        return {
            "final_status": final_status,
            "history": status_history,
            "failover_detected": final_status.get("failover_detected", False),
            "monitoring_duration": time.time() - start_time,
            "timeout_reached": True
        }
    
    def wait_for_failover_completion(self, timeout_seconds: int = 300) -> bool:
        """
        Wait for failover to complete.
        
        Args:
            timeout_seconds: Maximum time to wait in seconds
            
        Returns:
            True if failover completed successfully, False otherwise
            
        Raises:
            CrossDCToolkitError: If waiting fails
        """
        self.logger.info(f"Waiting for failover completion (timeout: {timeout_seconds}s)")
        
        result = self.monitor_failover_status(timeout_seconds)
        
        if result.get("failover_detected", False):
            self.logger.info(f"Failover completed in {result.get('monitoring_duration', 0):.2f} seconds")
            return True
        else:
            self.logger.warning(f"Failover did not complete within {timeout_seconds} seconds")
            return False
    
    def get_service_availability(self) -> Dict[str, Any]:
        """
        Check service availability across data centers.
        
        Returns:
            Dictionary with availability information
            
        Raises:
            CrossDCToolkitError: If availability check fails
        """
        try:
            # Check primary DC availability
            primary_available = self._check_service_availability(self.primary_api_client, "primary")
            
            # Check secondary DC availability
            secondary_available = self._check_service_availability(self.secondary_api_client, "secondary")
            
            return {
                "primary_dc_available": primary_available,
                "secondary_dc_available": secondary_available,
                "service_available": primary_available or secondary_available
            }
            
        except Exception as e:
            self.logger.error(f"Error checking service availability: {str(e)}", exc_info=True)
            raise CrossDCToolkitError(f"Failed to check service availability: {str(e)}")
    
    def get_toolkit_metrics(self) -> Dict[str, Any]:
        """
        Get toolkit-related metrics from both data centers.
        
        Returns:
            Dictionary with toolkit metrics
            
        Raises:
            CrossDCToolkitError: If metrics retrieval fails
        """
        try:
            metrics = {
                "primary_dc": {},
                "secondary_dc": {}
            }
            
            # Get primary DC metrics
            try:
                primary_metrics = self._get_dc_metrics(self.primary_api_client, "primary")
                metrics["primary_dc"] = primary_metrics
            except Exception as e:
                self.logger.warning(f"Failed to get primary DC metrics: {str(e)}")
            
            # Get secondary DC metrics
            try:
                secondary_metrics = self._get_dc_metrics(self.secondary_api_client, "secondary")
                metrics["secondary_dc"] = secondary_metrics
            except Exception as e:
                self.logger.warning(f"Failed to get secondary DC metrics: {str(e)}")
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Error getting toolkit metrics: {str(e)}", exc_info=True)
            raise CrossDCToolkitError(f"Failed to get toolkit metrics: {str(e)}")
    
    def _check_datacenter_status(self, api_client: StreamsApiClient, dc_type: str) -> Dict[str, Any]:
        """
        Check the status of a data center using the API client.
        
        Args:
            api_client: API client for the data center
            dc_type: Data center type ("primary" or "secondary")
            
        Returns:
            Dictionary with data center status information
        """
        status = {
            "type": dc_type,
            "status": "unknown"
        }
        
        try:
            # Check if instance exists
            try:
                instance = api_client.get_instance(self.instance_id)
                status["instance_exists"] = True
                status["instance_status"] = instance.get("status", "unknown")
            except APIError:
                status["instance_exists"] = False
                status["status"] = "down"
                return status
            
            # Check if job exists
            try:
                job = api_client.get_job(self.instance_id, self.job_id)
                status["job_exists"] = True
                status["job_status"] = job.get("status", "unknown")
                status["job_health"] = job.get("health", "unknown")
                
                # Determine overall status based on job health
                if job.get("health", "").lower() == "healthy":
                    status["status"] = "up"
                elif job.get("status", "").lower() == "running":
                    status["status"] = "degraded"
                else:
                    status["status"] = "down"
                
            except APIError:
                status["job_exists"] = False
                status["status"] = "down"
            
            # Check for toolkit-specific logs
            try:
                # This is just a placeholder, as we don't have direct access to RemoteDataCenterStatus stream
                # In a real implementation, you might need to analyze logs or expose this as a metric
                pass
            except:
                pass
                
            return status
            
        except Exception as e:
            self.logger.warning(f"Error checking {dc_type} datacenter status: {str(e)}")
            status["error"] = str(e)
            status["status"] = "unknown"
            return status
    
    def _check_service_availability(self, api_client: StreamsApiClient, dc_type: str) -> bool:
        """
        Check if the service is available in a data center.
        
        Args:
            api_client: API client for the data center
            dc_type: Data center type ("primary" or "secondary")
            
        Returns:
            True if service is available, False otherwise
        """
        try:
            # Try to get the job
            job = api_client.get_job(self.instance_id, self.job_id)
            
            # Check if job is running and healthy
            if job.get("status", "").lower() == "running" and job.get("health", "").lower() == "healthy":
                return True
                
            return False
            
        except Exception as e:
            self.logger.debug(f"Service in {dc_type} DC is not available: {str(e)}")
            return False
    
    def _get_dc_metrics(self, api_client: StreamsApiClient, dc_type: str) -> Dict[str, Any]:
        """
        Get metrics for a data center.
        
        Args:
            api_client: API client for the data center
            dc_type: Data center type ("primary" or "secondary")
            
        Returns:
            Dictionary with metrics
        """
        metrics = {}
        
        try:
            # Get metrics from the job
            job_metrics = api_client.get_metrics(self.instance_id, "jobs", self.job_id)
            
            if "metrics" in job_metrics:
                # Extract relevant metrics
                for metric in job_metrics["metrics"]:
                    name = metric.get("name", "")
                    value = metric.get("value", 0)
                    
                    # Look for toolkit-related metrics
                    if "crossdc" in name.lower() or "failover" in name.lower():
                        metrics[name] = value
            
            # Also check PE metrics for the operator
            try:
                pes = api_client.get_pes(self.instance_id, self.job_id)
                
                for pe in pes:
                    # Look for CrossDCFailover operator PEs
                    pe_id = pe.get("id", "")
                    if not pe_id:
                        continue
                        
                    pe_metrics = api_client.get_metrics(self.instance_id, "pes", pe_id)
                    
                    if "metrics" in pe_metrics:
                        for metric in pe_metrics["metrics"]:
                            name = metric.get("name", "")
                            value = metric.get("value", 0)
                            
                            # Look for toolkit-related metrics
                            if "crossdc" in name.lower() or "failover" in name.lower():
                                metrics[f"pe_{pe_id}_{name}"] = value
            except Exception as pe_error:
                self.logger.debug(f"Error getting PE metrics: {str(pe_error)}")
            
            return metrics
            
        except Exception as e:
            self.logger.warning(f"Error getting metrics for {dc_type} DC: {str(e)}")
            return {"error": str(e)}
    
    def _status_changed(self, old_status: Dict[str, Any], new_status: Dict[str, Any]) -> bool:
        """
        Check if the failover status has changed.
        
        Args:
            old_status: Previous status
            new_status: Current status
            
        Returns:
            True if status has changed, False otherwise
        """
        # Check for failover detection change
        if old_status.get("failover_detected", False) != new_status.get("failover_detected", False):
            return True
        
        # Check for data center status changes
        if old_status.get("primary_dc_status") != new_status.get("primary_dc_status"):
            return True
            
        if old_status.get("secondary_dc_status") != new_status.get("secondary_dc_status"):
            return True
        
        return False