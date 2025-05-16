"""
Prometheus Metrics Collector - Collects metrics from Prometheus servers.
"""

import logging
import time
from typing import Dict, List, Any, Optional, Union
import json

import requests
from requests.auth import HTTPBasicAuth

from monitoring.metrics_collector import BaseMetricsCollector


class PrometheusError(Exception):
    """Base exception for Prometheus collection errors."""
    pass


class PrometheusMetricsCollector(BaseMetricsCollector):
    """
    Collects metrics from Prometheus servers in the primary and secondary datacenters.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the Prometheus metrics collector.
        
        Args:
            config: Configuration dictionary for Prometheus
        """
        self.config = config
        self.logger = logging.getLogger("prometheus_metrics")
        
        # Required configuration
        self.primary_url = config.get("primary_url")
        self.secondary_url = config.get("secondary_url")
        
        if not self.primary_url:
            self.logger.warning("Primary Prometheus URL not configured")
        
        if not self.secondary_url:
            self.logger.warning("Secondary Prometheus URL not configured")
        
        # Authentication
        self.username = config.get("username")
        self.password = config.get("password")
        self.verify_ssl = config.get("verify_ssl", True)
        
        # Metrics to collect (default to some standard metrics)
        self.metrics_to_collect = config.get("metrics", [
            # General system metrics
            "up",
            "process_cpu_seconds_total",
            "process_resident_memory_bytes",
            
            # Streams-specific metrics (may need customization)
            "streams_job_healthy",
            "streams_job_nTuplesProcessed",
            "streams_job_nTuplesSubmitted",
            "streams_instance_status",
            
            # JVM metrics (if available)
            "jvm_memory_bytes_used",
            "jvm_threads_current"
        ])
        
        # Connection timeout
        self.timeout = config.get("timeout_seconds", 10)
        
        # Create session for requests
        self.session = requests.Session()
        if self.username and self.password:
            self.session.auth = HTTPBasicAuth(self.username, self.password)
    
    def collect_metrics(self, dc_type: str) -> Dict[str, Any]:
        """
        Collect metrics from Prometheus.
        
        Args:
            dc_type: Data center type ("primary" or "secondary")
            
        Returns:
            Dictionary of collected metrics
        """
        # Select the appropriate URL
        if dc_type.lower() == "primary":
            prometheus_url = self.primary_url
        elif dc_type.lower() == "secondary":
            prometheus_url = self.secondary_url
        else:
            raise ValueError(f"Invalid DC type: {dc_type}. Must be 'primary' or 'secondary'.")
        
        if not prometheus_url:
            self.logger.warning(f"Prometheus URL not configured for {dc_type} DC")
            return {}
        
        # Initialize metrics dictionary
        prometheus_metrics = {
            "source": "prometheus",
            "dc_type": dc_type,
            "timestamp": time.time()
        }
        
        # Collect each configured metric
        for metric_name in self.metrics_to_collect:
            try:
                value = self._query_prometheus(prometheus_url, metric_name)
                if value is not None:
                    prometheus_metrics[metric_name] = value
            except Exception as e:
                self.logger.warning(f"Failed to collect metric {metric_name}: {str(e)}")
        
        # Collect key metric groupings
        try:
            job_id = self.config.get("job_id", "")
            instance_id = self.config.get("instance_id", "")
            
            if job_id:
                # Query job-specific metrics
                job_metrics = self._query_job_metrics(prometheus_url, job_id)
                prometheus_metrics["job"] = job_metrics
            
            if instance_id:
                # Query instance-specific metrics
                instance_metrics = self._query_instance_metrics(prometheus_url, instance_id)
                prometheus_metrics["instance"] = instance_metrics
            
        except Exception as e:
            self.logger.warning(f"Failed to collect grouped metrics: {str(e)}")
        
        return prometheus_metrics
    
    def _query_prometheus(self, base_url: str, query: str) -> Optional[Union[float, Dict[str, Any]]]:
        """
        Query Prometheus API for a metric.
        
        Args:
            base_url: Base URL of the Prometheus server
            query: Query string (metric name or PromQL expression)
            
        Returns:
            Metric value or dictionary of values, or None if not found
            
        Raises:
            PrometheusError: If the query fails
        """
        # Build the query URL
        url = f"{base_url.rstrip('/')}/api/v1/query"
        
        try:
            # Make the request
            response = self.session.get(
                url,
                params={"query": query},
                timeout=self.timeout,
                verify=self.verify_ssl
            )
            
            # Check for errors
            response.raise_for_status()
            
            # Parse the response
            data = response.json()
            
            if data.get("status") != "success":
                error = data.get("error", "Unknown error")
                self.logger.warning(f"Prometheus query failed: {error}")
                return None
            
            # Extract results
            result = data.get("data", {}).get("result", [])
            
            if not result:
                # No data points returned
                return None
            
            # Handle different result types
            if len(result) == 1:
                # Single value
                entry = result[0]
                value = entry.get("value", [None, None])[1]
                if value is not None:
                    try:
                        return float(value)
                    except ValueError:
                        return value
            else:
                # Multiple values, return as dictionary
                values = {}
                for entry in result:
                    metric = entry.get("metric", {})
                    value = entry.get("value", [None, None])[1]
                    
                    # Try to find a good key
                    key = None
                    for possible_key in ["__name__", "job", "instance", "name"]:
                        if possible_key in metric:
                            key = metric[possible_key]
                            break
                    
                    if key is None:
                        # Use a concatenation of labels
                        key = "_".join(f"{k}:{v}" for k, v in metric.items())
                    
                    if value is not None:
                        try:
                            values[key] = float(value)
                        except ValueError:
                            values[key] = value
                
                return values
            
        except requests.RequestException as e:
            self.logger.error(f"Request to Prometheus failed: {str(e)}")
            raise PrometheusError(f"Prometheus query failed: {str(e)}")
        
        return None
    
    def _query_job_metrics(self, base_url: str, job_id: str) -> Dict[str, Any]:
        """
        Query Prometheus for job-specific metrics.
        
        Args:
            base_url: Base URL of the Prometheus server
            job_id: ID of the Streams job
            
        Returns:
            Dictionary of job metrics
        """
        job_metrics = {}
        
        # List of metrics to query for the job
        job_metric_queries = [
            f'streams_job_healthy{{job_id="{job_id}"}}',
            f'streams_job_nTuplesProcessed{{job_id="{job_id}"}}',
            f'streams_job_nTuplesSubmitted{{job_id="{job_id}"}}',
            f'streams_job_nTuplesDropped{{job_id="{job_id}"}}'
        ]
        
        for query in job_metric_queries:
            try:
                value = self._query_prometheus(base_url, query)
                if value is not None:
                    # Extract metric name from query
                    metric_name = query.split("{")[0]
                    job_metrics[metric_name] = value
            except Exception as e:
                self.logger.warning(f"Failed to collect job metric {query}: {str(e)}")
        
        return job_metrics
    
    def _query_instance_metrics(self, base_url: str, instance_id: str) -> Dict[str, Any]:
        """
        Query Prometheus for instance-specific metrics.
        
        Args:
            base_url: Base URL of the Prometheus server
            instance_id: ID of the Streams instance
            
        Returns:
            Dictionary of instance metrics
        """
        instance_metrics = {}
        
        # List of metrics to query for the instance
        instance_metric_queries = [
            f'streams_instance_status{{instance_id="{instance_id}"}}',
            f'streams_instance_job_count{{instance_id="{instance_id}"}}',
            f'streams_instance_cpu_usage{{instance_id="{instance_id}"}}'
        ]
        
        for query in instance_metric_queries:
            try:
                value = self._query_prometheus(base_url, query)
                if value is not None:
                    # Extract metric name from query
                    metric_name = query.split("{")[0]
                    instance_metrics[metric_name] = value
            except Exception as e:
                self.logger.warning(f"Failed to collect instance metric {query}: {str(e)}")
        
        return instance_metrics