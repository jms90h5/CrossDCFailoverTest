"""
Metrics Collector - Central component for collecting, storing, and evaluating metrics.
"""

import logging
import time
import threading
from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Any, Optional, Set, Tuple, Union

from streams_client.api_client import StreamsApiClient, APIError


class MetricsCollectionError(Exception):
    """Base exception for metrics collection errors."""
    pass


class MetricsCollector:
    """
    Collects and processes metrics from various sources during failover tests.
    
    This class coordinates metrics collection from multiple sources:
    - Teracloud Streams REST API
    - Prometheus
    - JMX (if enabled)
    - System metrics from hosts
    """
    
    def __init__(
        self,
        primary_api_client: StreamsApiClient,
        secondary_api_client: StreamsApiClient,
        config: Dict[str, Any]
    ):
        """
        Initialize the metrics collector.
        
        Args:
            primary_api_client: API client for the primary data center
            secondary_api_client: API client for the secondary data center
            config: Configuration dictionary for metrics collection
        """
        self.primary_api_client = primary_api_client
        self.secondary_api_client = secondary_api_client
        self.config = config
        
        # Get configuration settings
        self.collection_interval = config.get("metrics_collection_interval_seconds", 5)
        
        # Set up logger
        self.logger = logging.getLogger("metrics_collector")
        
        # Initialize metrics storage
        self.metrics = defaultdict(dict)
        self.baseline_metrics = {}
        self.post_failover_metrics = {}
        
        # Initialize time series for metrics
        self.time_series = defaultdict(dict)
        
        # Set up collectors based on configuration
        self.collectors = []
        
        # Always add the Streams API collector
        self.collectors.append(StreamsAPIMetricsCollector(
            primary_api_client=primary_api_client,
            secondary_api_client=secondary_api_client,
            config=config
        ))
        
        # Add Prometheus collector if configured
        if "prometheus" in config:
            try:
                from monitoring.prometheus_collector import PrometheusMetricsCollector
                self.collectors.append(PrometheusMetricsCollector(
                    config=config.get("prometheus", {})
                ))
                self.logger.info("Prometheus metrics collector initialized")
            except ImportError:
                self.logger.warning(
                    "prometheus-api-client not installed, Prometheus metrics collection disabled"
                )
        
        # Add JMX collector if enabled
        if config.get("jmx", {}).get("enabled", False):
            try:
                from monitoring.jmx_collector import JMXMetricsCollector
                self.collectors.append(JMXMetricsCollector(
                    config=config.get("jmx", {})
                ))
                self.logger.info("JMX metrics collector initialized")
            except ImportError:
                self.logger.warning(
                    "py4j not installed, JMX metrics collection disabled"
                )
        
        # Flag to control the collection thread
        self.collecting = False
        self.collection_thread = None
    
    def start_collection(self) -> None:
        """
        Start metrics collection in a background thread.
        """
        if self.collecting:
            self.logger.warning("Metrics collection already running")
            return
        
        self.collecting = True
        self.collection_thread = threading.Thread(
            target=self._collection_loop,
            daemon=True
        )
        self.collection_thread.start()
        self.logger.info(f"Started metrics collection (interval: {self.collection_interval}s)")
    
    def stop_collection(self) -> None:
        """
        Stop the metrics collection background thread.
        """
        if not self.collecting:
            self.logger.warning("Metrics collection not running")
            return
        
        self.collecting = False
        if self.collection_thread:
            self.collection_thread.join(timeout=self.collection_interval * 2)
            if self.collection_thread.is_alive():
                self.logger.warning("Collection thread did not terminate gracefully")
            
        self.logger.info("Stopped metrics collection")
    
    def collect_baseline_metrics(self) -> Dict[str, Any]:
        """
        Collect baseline metrics before failover.
        
        Returns:
            Dictionary of baseline metrics
        """
        self.logger.info("Collecting baseline metrics")
        
        baseline = {}
        
        # Collect from all collectors
        for collector in self.collectors:
            try:
                metrics = collector.collect_metrics("primary")
                baseline.update(metrics)
            except Exception as e:
                self.logger.error(
                    f"Error collecting baseline metrics from {collector.__class__.__name__}: {str(e)}",
                    exc_info=True
                )
        
        # Store the baseline for comparison
        self.baseline_metrics = baseline
        
        self.logger.debug(f"Baseline metrics: {baseline}")
        return baseline
    
    def collect_post_failover_metrics(self) -> Dict[str, Any]:
        """
        Collect metrics after failover has completed.
        
        Returns:
            Dictionary of post-failover metrics
        """
        self.logger.info("Collecting post-failover metrics")
        
        post_failover = {}
        
        # Collect from all collectors, but now from secondary DC
        for collector in self.collectors:
            try:
                metrics = collector.collect_metrics("secondary")
                post_failover.update(metrics)
            except Exception as e:
                self.logger.error(
                    f"Error collecting post-failover metrics from {collector.__class__.__name__}: {str(e)}",
                    exc_info=True
                )
        
        # Store the post-failover metrics for comparison
        self.post_failover_metrics = post_failover
        
        self.logger.debug(f"Post-failover metrics: {post_failover}")
        return post_failover
    
    def wait_for_failover_completion(self, timeout: int = 300) -> bool:
        """
        Wait for failover to complete by monitoring metrics.
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Returns:
            True if failover completed successfully, False otherwise
        """
        self.logger.info(f"Waiting for failover to complete (timeout: {timeout}s)")
        
        start_time = time.time()
        failover_detected = False
        failover_completed = False
        
        # Record failover start time in time series
        self.time_series["failover"]["start_time"] = start_time
        
        # Poll for failover status
        while time.time() - start_time < timeout and not failover_completed:
            # Check primary DC for failure
            if not failover_detected:
                try:
                    primary_status = self._check_primary_failure()
                    if primary_status.get("failed", False):
                        self.logger.info("Primary DC failure detected")
                        failover_detected = True
                except Exception as e:
                    self.logger.warning(f"Error checking primary DC status: {str(e)}")
                    # Assume failure if we can't check primary
                    self.logger.info("Assuming primary DC failure due to connection error")
                    failover_detected = True
            
            # Check secondary DC for activation
            if failover_detected and not failover_completed:
                try:
                    secondary_status = self._check_secondary_activation()
                    if secondary_status.get("activated", False):
                        self.logger.info("Secondary DC activation detected")
                        failover_completed = True
                        
                        # Record failover completion time in time series
                        end_time = time.time()
                        self.time_series["failover"]["end_time"] = end_time
                        
                        # Calculate and store recovery time
                        recovery_time = end_time - start_time
                        self.time_series["failover"]["recovery_time"] = recovery_time
                        self.logger.info(f"Failover completed in {recovery_time:.2f} seconds")
                except Exception as e:
                    self.logger.warning(f"Error checking secondary DC status: {str(e)}")
            
            # Sleep before checking again
            if not failover_completed:
                time.sleep(min(5, self.collection_interval))
        
        if not failover_completed:
            self.logger.warning(f"Failover did not complete within {timeout} seconds")
        
        return failover_completed
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """
        Get all collected metrics.
        
        Returns:
            Dictionary containing all metrics
        """
        result = {
            "current": self.metrics,
            "baseline": self.baseline_metrics,
            "post_failover": self.post_failover_metrics,
            "time_series": self.time_series
        }
        
        return result
    
    def validate_metrics(self, expected_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate metrics against expected values.
        
        Args:
            expected_metrics: Dictionary of expected metrics and thresholds
            
        Returns:
            Dictionary with validation results
        """
        self.logger.info("Validating metrics against expected values")
        
        validation_result = {
            "success": True,
            "metrics_evaluated": 0,
            "metrics_passed": 0,
            "results": {},
            "issues": []
        }
        
        # Get current metrics
        all_metrics = self.get_all_metrics()
        current = all_metrics["current"]
        post_failover = all_metrics["post_failover"]
        
        # Use post-failover metrics if available, otherwise use current
        metrics_to_validate = post_failover if post_failover else current
        
        # Validate each expected metric
        for metric_name, expected in expected_metrics.items():
            validation_result["metrics_evaluated"] += 1
            
            # Find the metric in our collected data
            metric_value = self._find_metric_value(metrics_to_validate, metric_name)
            
            if metric_value is None:
                validation_result["success"] = False
                issue = f"Metric '{metric_name}' not found in collected data"
                validation_result["issues"].append(issue)
                validation_result["results"][metric_name] = {
                    "success": False,
                    "issue": "Metric not found"
                }
                continue
            
            # Validate based on expected conditions
            metric_passed = True
            metric_issues = []
            
            # Check minimum threshold
            if "min" in expected and metric_value < expected["min"]:
                metric_passed = False
                issue = (
                    f"Metric '{metric_name}' value {metric_value} "
                    f"is below minimum threshold {expected['min']}"
                )
                metric_issues.append(issue)
            
            # Check maximum threshold
            if "max" in expected and metric_value > expected["max"]:
                metric_passed = False
                issue = (
                    f"Metric '{metric_name}' value {metric_value} "
                    f"exceeds maximum threshold {expected['max']}"
                )
                metric_issues.append(issue)
            
            # Check exact value
            if "equals" in expected and metric_value != expected["equals"]:
                metric_passed = False
                issue = (
                    f"Metric '{metric_name}' value {metric_value} "
                    f"does not equal expected value {expected['equals']}"
                )
                metric_issues.append(issue)
            
            # Store result
            validation_result["results"][metric_name] = {
                "success": metric_passed,
                "expected": expected,
                "actual": metric_value,
                "issues": metric_issues
            }
            
            # Update overall success
            if metric_passed:
                validation_result["metrics_passed"] += 1
            else:
                validation_result["success"] = False
                validation_result["issues"].extend(metric_issues)
        
        self.logger.info(
            f"Metrics validation: {validation_result['metrics_passed']}/{validation_result['metrics_evaluated']} "
            f"metrics passed, overall success: {validation_result['success']}"
        )
        
        return validation_result
    
    def _collection_loop(self) -> None:
        """
        Background thread loop for periodic metrics collection.
        """
        while self.collecting:
            try:
                # Determine which DC to collect from (primary or secondary)
                # If we've detected failover, collect from secondary
                dc_type = "secondary" if self.time_series.get("failover", {}).get("end_time") else "primary"
                
                # Collect metrics from all sources
                current_metrics = {}
                for collector in self.collectors:
                    try:
                        metrics = collector.collect_metrics(dc_type)
                        current_metrics.update(metrics)
                    except Exception as e:
                        self.logger.warning(
                            f"Error collecting metrics from {collector.__class__.__name__}: {str(e)}"
                        )
                
                # Update current metrics
                self.metrics.update(current_metrics)
                
                # Add to time series with current timestamp
                timestamp = time.time()
                for key, value in current_metrics.items():
                    if isinstance(value, (int, float)):
                        self.time_series.setdefault(key, {})[str(timestamp)] = value
                
            except Exception as e:
                self.logger.error(f"Error in metrics collection loop: {str(e)}", exc_info=True)
            
            # Sleep until next collection
            time.sleep(self.collection_interval)
    
    def _check_primary_failure(self) -> Dict[str, Any]:
        """
        Check if the primary DC has failed.
        
        Returns:
            Dictionary with primary DC status
        """
        result = {"failed": False}
        
        # Try to get instance status from primary DC
        try:
            # Get instance and check status
            instance_id = self.config.get("primary_instance_id", "")
            if not instance_id:
                # Find it from the datacenter config
                dc_config = self.config.get("datacenters", {}).get("primary", {})
                instance_id = dc_config.get("instance_id", "")
            
            if instance_id:
                instance = self.primary_api_client.get_instance(instance_id)
                status = instance.get("status", "").lower()
                
                result["status"] = status
                result["failed"] = status not in ["running", "healthy"]
            else:
                # If we don't have an instance ID, check general connectivity
                instances = self.primary_api_client.get_instances()
                result["connected"] = True
                result["failed"] = False
                
        except APIError as e:
            self.logger.warning(f"API error checking primary DC: {str(e)}")
            result["error"] = str(e)
            result["failed"] = True
        except Exception as e:
            self.logger.error(f"Error checking primary DC: {str(e)}")
            result["error"] = str(e)
            result["failed"] = True
        
        return result
    
    def _check_secondary_activation(self) -> Dict[str, Any]:
        """
        Check if the secondary DC has been activated.
        
        Returns:
            Dictionary with secondary DC activation status
        """
        result = {"activated": False}
        
        # Find job ID from config
        job_id = self.config.get("job_id", "")
        instance_id = self.config.get("secondary_instance_id", "")
        
        # Find it from the datacenter config if not set directly
        if not instance_id:
            dc_config = self.config.get("datacenters", {}).get("secondary", {})
            instance_id = dc_config.get("instance_id", "")
        
        if not job_id or not instance_id:
            self.logger.warning("Job ID or instance ID not found in config, can't check secondary activation")
            return result
        
        try:
            # Get job status from secondary DC
            job = self.secondary_api_client.get_job(instance_id, job_id)
            state = job.get("state", "").lower()
            health = job.get("health", "").lower()
            
            result["state"] = state
            result["health"] = health
            
            # Check if job is running and healthy
            result["activated"] = state == "running" and health == "healthy"
            
        except APIError as e:
            self.logger.warning(f"API error checking secondary DC: {str(e)}")
            result["error"] = str(e)
        except Exception as e:
            self.logger.error(f"Error checking secondary DC: {str(e)}")
            result["error"] = str(e)
        
        return result
    
    def _find_metric_value(self, metrics: Dict[str, Any], metric_name: str) -> Optional[Any]:
        """
        Find a metric value in the metrics dictionary, handling nested structures.
        
        Args:
            metrics: Dictionary of metrics
            metric_name: Name of the metric to find
            
        Returns:
            The metric value, or None if not found
        """
        # Direct match
        if metric_name in metrics:
            return metrics[metric_name]
        
        # Handle dot notation for nested metrics
        if "." in metric_name:
            parts = metric_name.split(".")
            value = metrics
            for part in parts:
                if isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    return None
            return value
        
        # Search in one level of nesting
        for category, values in metrics.items():
            if isinstance(values, dict) and metric_name in values:
                return values[metric_name]
        
        return None


class BaseMetricsCollector(ABC):
    """
    Abstract base class for metrics collectors.
    
    All specific metrics collectors should inherit from this class.
    """
    
    @abstractmethod
    def collect_metrics(self, dc_type: str) -> Dict[str, Any]:
        """
        Collect metrics from the source.
        
        Args:
            dc_type: Data center type ("primary" or "secondary")
            
        Returns:
            Dictionary of collected metrics
        """
        pass


class StreamsAPIMetricsCollector(BaseMetricsCollector):
    """
    Collects metrics from the Teracloud Streams REST Management API.
    """
    
    def __init__(
        self,
        primary_api_client: StreamsApiClient,
        secondary_api_client: StreamsApiClient,
        config: Dict[str, Any]
    ):
        """
        Initialize the Streams API metrics collector.
        
        Args:
            primary_api_client: API client for the primary data center
            secondary_api_client: API client for the secondary data center
            config: Configuration dictionary
        """
        self.primary_api_client = primary_api_client
        self.secondary_api_client = secondary_api_client
        self.config = config
        self.logger = logging.getLogger("streams_api_metrics")
    
    def collect_metrics(self, dc_type: str) -> Dict[str, Any]:
        """
        Collect metrics from the Streams REST API.
        
        Args:
            dc_type: Data center type ("primary" or "secondary")
            
        Returns:
            Dictionary of collected metrics
        """
        # Select the appropriate client
        if dc_type.lower() == "primary":
            api_client = self.primary_api_client
        elif dc_type.lower() == "secondary":
            api_client = self.secondary_api_client
        else:
            raise ValueError(f"Invalid DC type: {dc_type}. Must be 'primary' or 'secondary'.")
        
        # Find instance and job IDs from configuration
        instance_id = self._get_instance_id(dc_type)
        job_id = self.config.get("job_id", "")
        
        if not instance_id:
            self.logger.warning(f"Instance ID for {dc_type} DC not found in configuration")
            return {}
        
        metrics = {
            "dc_type": dc_type,
            "timestamp": time.time(),
            "instance": {},
            "job": {},
            "processing_elements": {}
        }
        
        # Collect instance metrics
        try:
            instance = api_client.get_instance(instance_id)
            metrics["instance"] = {
                "id": instance.get("id", ""),
                "status": instance.get("status", ""),
                "health": instance.get("health", ""),
                "jobs_count": len(instance.get("jobs", [])) if "jobs" in instance else 0
            }
        except Exception as e:
            self.logger.warning(f"Failed to collect instance metrics: {str(e)}")
        
        # Collect job metrics if job ID is provided
        if job_id:
            try:
                job = api_client.get_job(instance_id, job_id)
                metrics["job"] = {
                    "id": job.get("id", ""),
                    "name": job.get("name", ""),
                    "state": job.get("state", ""),
                    "health": job.get("health", ""),
                    "submission_time": job.get("submissionTime", ""),
                    "pe_count": job.get("peCount", 0)
                }
                
                # Calculate health percentage
                if "health" in job:
                    health = job["health"].lower()
                    if health == "healthy":
                        metrics["health_percentage"] = 100.0
                    elif health == "partially healthy":
                        metrics["health_percentage"] = 75.0
                    elif health == "unhealthy":
                        metrics["health_percentage"] = 0.0
                    else:
                        metrics["health_percentage"] = 50.0
                
                # Collect detailed job metrics if available
                try:
                    job_metrics = api_client.get_metrics(instance_id, "jobs", job_id)
                    if "metrics" in job_metrics:
                        for metric in job_metrics["metrics"]:
                            name = metric.get("name", "")
                            value = metric.get("value", 0)
                            if name and name != "health":
                                metrics["job"][name] = value
                                
                                # Store some important metrics at the top level
                                if name in ["nTuplesProcessed", "nTuplesSubmitted"]:
                                    metrics[name] = value
                
                except Exception as e:
                    self.logger.warning(f"Failed to collect job metrics: {str(e)}")
                
                # Collect processing element metrics
                try:
                    pes = api_client.get_pes(instance_id, job_id)
                    metrics["processing_elements"]["count"] = len(pes)
                    
                    healthy_pes = 0
                    for pe in pes:
                        pe_id = pe.get("id", "")
                        pe_health = pe.get("health", "").lower()
                        
                        if pe_health == "healthy":
                            healthy_pes += 1
                        
                        # Store key PE metrics
                        if pe_id:
                            metrics["processing_elements"][pe_id] = {
                                "health": pe_health,
                                "status": pe.get("status", ""),
                                "launchCount": pe.get("launchCount", 0)
                            }
                    
                    # Calculate PE health percentage
                    if pes:
                        metrics["pe_health_percentage"] = (healthy_pes / len(pes)) * 100.0
                
                except Exception as e:
                    self.logger.warning(f"Failed to collect PE metrics: {str(e)}")
            
            except Exception as e:
                self.logger.warning(f"Failed to collect job information: {str(e)}")
        
        return metrics
    
    def _get_instance_id(self, dc_type: str) -> str:
        """
        Get the instance ID for the specified data center type.
        
        Args:
            dc_type: Data center type ("primary" or "secondary")
            
        Returns:
            Instance ID or empty string if not found
        """
        # Check for direct setting in metrics config
        direct_key = f"{dc_type.lower()}_instance_id"
        if direct_key in self.config:
            return self.config[direct_key]
        
        # Check in datacenters section
        datacenters = self.config.get("datacenters", {})
        dc_config = datacenters.get(dc_type.lower(), {})
        
        return dc_config.get("instance_id", "")