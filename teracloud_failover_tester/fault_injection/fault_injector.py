"""
Fault Injector - Core component for simulating failures in Teracloud Streams environments.
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple

from fault_injection.network_fault_injector import NetworkFaultInjector
from fault_injection.process_fault_injector import ProcessFaultInjector
from fault_injection.api_fault_injector import APIFaultInjector


class FaultInjectionError(Exception):
    """Base exception for fault injection errors."""
    pass


class FaultInjector:
    """
    Coordinates fault injection across different mechanisms (network, process, API).
    
    This class is responsible for selecting and coordinating the appropriate
    fault injection strategy based on the test scenario.
    """
    
    def __init__(self, config: Dict[str, Any], scenario: Dict[str, Any]):
        """
        Initialize the fault injector.
        
        Args:
            config: Configuration dictionary for fault injection
            scenario: Test scenario with fault details
        """
        self.config = config
        self.scenario = scenario
        self.logger = logging.getLogger("fault_injector")
        
        # Track active fault injectors
        self.active_injectors = []
        
        # Initialize based on fault type
        self.fault_type = scenario.get("type", "").lower()
        
        # Validate fault type
        if not self.fault_type:
            raise ValueError("Fault type must be specified in scenario")
            
        # Create appropriate injectors based on fault type
        if self.fault_type in ["network_partition", "network_latency", "network_packet_loss", "network_bandwidth"]:
            self.injectors = [NetworkFaultInjector(config.get("network", {}), scenario)]
        elif self.fault_type in ["process_kill", "process_hang", "resource_exhaustion"]:
            self.injectors = [ProcessFaultInjector(config.get("ssh", {}), scenario)]
        elif self.fault_type in ["api_initiated"]:
            self.injectors = [APIFaultInjector(config, scenario)]
        elif self.fault_type == "combined":
            # For combined faults, create multiple injectors
            injectors = []
            
            if "network_faults" in scenario:
                injectors.append(NetworkFaultInjector(
                    config.get("network", {}), 
                    scenario.get("network_faults", {})
                ))
            
            if "process_faults" in scenario:
                injectors.append(ProcessFaultInjector(
                    config.get("ssh", {}), 
                    scenario.get("process_faults", {})
                ))
            
            if "api_faults" in scenario:
                injectors.append(APIFaultInjector(
                    config, 
                    scenario.get("api_faults", {})
                ))
            
            self.injectors = injectors
        else:
            raise ValueError(f"Unsupported fault type: {self.fault_type}")
    
    def inject_fault(self) -> Dict[str, Any]:
        """
        Inject the configured fault.
        
        Returns:
            Dictionary with fault injection results
            
        Raises:
            FaultInjectionError: If fault injection fails
        """
        if not self.injectors:
            raise FaultInjectionError("No fault injectors configured")
        
        results = {}
        errors = []
        
        # Inject faults using all configured injectors
        for injector in self.injectors:
            try:
                self.logger.info(f"Injecting fault using {injector.__class__.__name__}")
                
                result = injector.inject_fault()
                results[injector.__class__.__name__] = result
                
                # Track active injectors
                self.active_injectors.append(injector)
                
            except Exception as e:
                self.logger.error(f"Failed to inject fault: {str(e)}", exc_info=True)
                errors.append(str(e))
        
        if errors:
            raise FaultInjectionError(f"Fault injection failed: {', '.join(errors)}")
        
        return results
    
    def verify_fault(self) -> Dict[str, Any]:
        """
        Verify that the fault has been applied correctly.
        
        Returns:
            Dictionary with verification results
            
        Raises:
            FaultInjectionError: If fault verification fails
        """
        if not self.active_injectors:
            raise FaultInjectionError("No active fault injectors to verify")
        
        results = {}
        errors = []
        
        # Verify faults using all active injectors
        for injector in self.active_injectors:
            try:
                self.logger.info(f"Verifying fault using {injector.__class__.__name__}")
                
                result = injector.verify_fault()
                results[injector.__class__.__name__] = result
                
            except Exception as e:
                self.logger.error(f"Failed to verify fault: {str(e)}", exc_info=True)
                errors.append(str(e))
        
        if errors:
            raise FaultInjectionError(f"Fault verification failed: {', '.join(errors)}")
        
        return results
    
    def cleanup(self) -> Dict[str, Any]:
        """
        Clean up after fault injection.
        
        Returns:
            Dictionary with cleanup results
        """
        results = {}
        errors = []
        
        # Clean up using all active injectors
        for injector in self.active_injectors:
            try:
                self.logger.info(f"Cleaning up after {injector.__class__.__name__}")
                
                result = injector.cleanup()
                results[injector.__class__.__name__] = result
                
            except Exception as e:
                self.logger.error(f"Failed to clean up fault: {str(e)}", exc_info=True)
                errors.append(str(e))
        
        # Clear active injectors
        self.active_injectors = []
        
        if errors:
            self.logger.warning(f"Some fault cleanup operations failed: {', '.join(errors)}")
        
        return results


class BaseFaultInjector(ABC):
    """
    Abstract base class for fault injectors.
    
    All specific fault injectors should inherit from this class.
    """
    
    def __init__(self, config: Dict[str, Any], scenario: Dict[str, Any]):
        """
        Initialize the base fault injector.
        
        Args:
            config: Configuration dictionary
            scenario: Test scenario with fault details
        """
        self.config = config
        self.scenario = scenario
        self.logger = logging.getLogger(self.__class__.__name__)
        self.active_faults = []
    
    @abstractmethod
    def inject_fault(self) -> Dict[str, Any]:
        """
        Inject the configured fault.
        
        Returns:
            Dictionary with fault injection results
        """
        pass
    
    @abstractmethod
    def verify_fault(self) -> Dict[str, Any]:
        """
        Verify that the fault has been applied correctly.
        
        Returns:
            Dictionary with verification results
        """
        pass
    
    @abstractmethod
    def cleanup(self) -> Dict[str, Any]:
        """
        Clean up after fault injection.
        
        Returns:
            Dictionary with cleanup results
        """
        pass