"""
JMX Metrics Collector - Collects JVM metrics via JMX.
"""

import logging
import time
from typing import Dict, List, Any, Optional

from monitoring.metrics_collector import BaseMetricsCollector


class JMXError(Exception):
    """Base exception for JMX collection errors."""
    pass


class JMXMetricsCollector(BaseMetricsCollector):
    """
    Collects JVM metrics from JMX endpoints.
    
    Note: This collector requires py4j for JMX connection functionality.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the JMX metrics collector.
        
        Args:
            config: Configuration dictionary for JMX
        """
        self.config = config
        self.logger = logging.getLogger("jmx_metrics")
        
        # Verify py4j is available
        try:
            from py4j.java_gateway import JavaGateway, GatewayParameters
            self.JavaGateway = JavaGateway
            self.GatewayParameters = GatewayParameters
        except ImportError:
            self.logger.error("py4j module not available, JMX metrics collection will not function")
            self.JavaGateway = None
            self.GatewayParameters = None
        
        # Required configuration
        self.primary_host = config.get("primary_host")
        self.primary_port = config.get("primary_port", 9999)
        self.secondary_host = config.get("secondary_host")
        self.secondary_port = config.get("secondary_port", 9999)
        
        if not self.primary_host:
            self.logger.warning("Primary JMX host not configured")
        
        if not self.secondary_host:
            self.logger.warning("Secondary JMX host not configured")
        
        # MBean patterns to collect (default to some standard beans)
        self.mbean_patterns = config.get("mbean_patterns", [
            "java.lang:type=Memory",
            "java.lang:type=Threading",
            "java.lang:type=OperatingSystem",
            "java.lang:type=Runtime",
            # Streams-specific beans (if available)
            "com.teracloud.streams:*"
        ])
        
        # Active gateway connections
        self.gateways = {}
    
    def collect_metrics(self, dc_type: str) -> Dict[str, Any]:
        """
        Collect metrics from JMX.
        
        Args:
            dc_type: Data center type ("primary" or "secondary")
            
        Returns:
            Dictionary of collected metrics
        """
        if not self.JavaGateway:
            self.logger.warning("py4j not available, JMX collection skipped")
            return {}
        
        # Select the appropriate host and port
        if dc_type.lower() == "primary":
            host = self.primary_host
            port = self.primary_port
        elif dc_type.lower() == "secondary":
            host = self.secondary_host
            port = self.secondary_port
        else:
            raise ValueError(f"Invalid DC type: {dc_type}. Must be 'primary' or 'secondary'.")
        
        if not host:
            self.logger.warning(f"JMX host not configured for {dc_type} DC")
            return {}
        
        # Initialize metrics dictionary
        jmx_metrics = {
            "source": "jmx",
            "dc_type": dc_type,
            "timestamp": time.time()
        }
        
        try:
            # Get or create gateway connection
            gateway = self._get_gateway(dc_type, host, port)
            
            # Get MBean server connection
            mbs = gateway.entry_point.getMBeanServerConnection()
            
            # Collect metrics from each MBean pattern
            for pattern in self.mbean_patterns:
                mbean_metrics = self._collect_mbean_metrics(mbs, pattern)
                if mbean_metrics:
                    # Use simple name as key
                    if ":" in pattern:
                        domain, rest = pattern.split(":", 1)
                        key = domain.split(".")[-1]
                    else:
                        key = pattern.split(".")[-1]
                    
                    jmx_metrics[key] = mbean_metrics
            
            # Add JVM memory metrics
            memory_metrics = self._collect_memory_metrics(mbs)
            if memory_metrics:
                jmx_metrics["memory"] = memory_metrics
            
            # Add JVM thread metrics
            thread_metrics = self._collect_thread_metrics(mbs)
            if thread_metrics:
                jmx_metrics["threads"] = thread_metrics
            
        except Exception as e:
            self.logger.error(f"Failed to collect JMX metrics: {str(e)}", exc_info=True)
            # Close the gateway on error
            self._close_gateway(dc_type)
        
        return jmx_metrics
    
    def _get_gateway(self, dc_type: str, host: str, port: int):
        """
        Get or create a py4j gateway to the JMX service.
        
        Args:
            dc_type: Data center type
            host: JMX host
            port: JMX port
            
        Returns:
            Py4j JavaGateway instance
            
        Raises:
            JMXError: If gateway creation fails
        """
        gateway_key = f"{dc_type}_{host}_{port}"
        
        if gateway_key in self.gateways:
            return self.gateways[gateway_key]
        
        try:
            # Create a new gateway
            gateway_params = self.GatewayParameters(host=host, port=port)
            gateway = self.JavaGateway(gateway_parameters=gateway_params)
            
            # Test the connection
            gateway.jvm.System.currentTimeMillis()
            
            # Store the gateway
            self.gateways[gateway_key] = gateway
            self.logger.info(f"Connected to JMX service at {host}:{port}")
            
            return gateway
            
        except Exception as e:
            self.logger.error(f"Failed to connect to JMX service at {host}:{port}: {str(e)}")
            raise JMXError(f"JMX connection failed: {str(e)}")
    
    def _close_gateway(self, dc_type: str):
        """
        Close the py4j gateway for the specified data center.
        
        Args:
            dc_type: Data center type
        """
        keys_to_remove = []
        
        for key, gateway in self.gateways.items():
            if key.startswith(f"{dc_type}_"):
                try:
                    gateway.close()
                    self.logger.info(f"Closed JMX gateway: {key}")
                    keys_to_remove.append(key)
                except Exception as e:
                    self.logger.warning(f"Error closing JMX gateway {key}: {str(e)}")
        
        # Remove closed gateways
        for key in keys_to_remove:
            self.gateways.pop(key, None)
    
    def _collect_mbean_metrics(self, mbs, pattern: str) -> Dict[str, Any]:
        """
        Collect metrics from MBeans matching the pattern.
        
        Args:
            mbs: MBeanServer connection
            pattern: MBean name pattern
            
        Returns:
            Dictionary of metrics
        """
        metrics = {}
        
        try:
            # Query for matching MBeans
            object_names = mbs.queryNames(pattern, None)
            
            # Iterate through each MBean
            for object_name in object_names:
                bean_name = object_name.toString()
                bean_metrics = {}
                
                try:
                    # Get MBean information
                    info = mbs.getMBeanInfo(object_name)
                    
                    # Collect attribute values
                    for attribute in info.getAttributes():
                        attr_name = attribute.getName()
                        
                        try:
                            # Skip attributes that might cause problems
                            if attr_name in ["ObjectName", "Class"]:
                                continue
                                
                            value = mbs.getAttribute(object_name, attr_name)
                            
                            # Convert complex objects to string
                            if hasattr(value, "toString"):
                                value = value.toString()
                            
                            # Store the attribute value
                            bean_metrics[attr_name] = value
                            
                        except Exception as attr_error:
                            # Skip attributes that can't be accessed
                            pass
                    
                    # Add bean metrics if any were collected
                    if bean_metrics:
                        # Use simple name as key
                        simple_name = bean_name.split("=")[-1].split(",")[0]
                        metrics[simple_name] = bean_metrics
                        
                except Exception as bean_error:
                    self.logger.warning(f"Error collecting metrics from {bean_name}: {str(bean_error)}")
            
        except Exception as e:
            self.logger.error(f"Error querying MBeans with pattern {pattern}: {str(e)}")
        
        return metrics
    
    def _collect_memory_metrics(self, mbs) -> Dict[str, Any]:
        """
        Collect detailed memory metrics.
        
        Args:
            mbs: MBeanServer connection
            
        Returns:
            Dictionary of memory metrics
        """
        memory_metrics = {}
        
        try:
            # Get memory MBean
            memory_bean = "java.lang:type=Memory"
            heap_memory = mbs.getAttribute(memory_bean, "HeapMemoryUsage")
            non_heap_memory = mbs.getAttribute(memory_bean, "NonHeapMemoryUsage")
            
            # Extract memory usage values
            memory_metrics["heap"] = {
                "init": heap_memory.getInit(),
                "used": heap_memory.getUsed(),
                "committed": heap_memory.getCommitted(),
                "max": heap_memory.getMax()
            }
            
            memory_metrics["non_heap"] = {
                "init": non_heap_memory.getInit(),
                "used": non_heap_memory.getUsed(),
                "committed": non_heap_memory.getCommitted(),
                "max": non_heap_memory.getMax()
            }
            
            # Calculate usage percentages
            if heap_memory.getMax() > 0:
                memory_metrics["heap_usage_percent"] = (heap_memory.getUsed() / heap_memory.getMax()) * 100.0
            
            if non_heap_memory.getMax() > 0:
                memory_metrics["non_heap_usage_percent"] = (non_heap_memory.getUsed() / non_heap_memory.getMax()) * 100.0
            
        except Exception as e:
            self.logger.warning(f"Error collecting memory metrics: {str(e)}")
        
        return memory_metrics
    
    def _collect_thread_metrics(self, mbs) -> Dict[str, Any]:
        """
        Collect detailed thread metrics.
        
        Args:
            mbs: MBeanServer connection
            
        Returns:
            Dictionary of thread metrics
        """
        thread_metrics = {}
        
        try:
            # Get threading MBean
            threading_bean = "java.lang:type=Threading"
            
            # Collect key thread metrics
            thread_metrics["thread_count"] = mbs.getAttribute(threading_bean, "ThreadCount")
            thread_metrics["daemon_thread_count"] = mbs.getAttribute(threading_bean, "DaemonThreadCount")
            thread_metrics["peak_thread_count"] = mbs.getAttribute(threading_bean, "PeakThreadCount")
            thread_metrics["total_started_thread_count"] = mbs.getAttribute(threading_bean, "TotalStartedThreadCount")
            
            # Get thread state counts
            thread_metrics["states"] = {}
            for state in ["NEW", "RUNNABLE", "BLOCKED", "WAITING", "TIMED_WAITING", "TERMINATED"]:
                try:
                    count = mbs.invoke(
                        threading_bean,
                        "getThreadCount",
                        [state],
                        ["java.lang.String"]
                    )
                    thread_metrics["states"][state.lower()] = count
                except:
                    pass
            
        except Exception as e:
            self.logger.warning(f"Error collecting thread metrics: {str(e)}")
        
        return thread_metrics