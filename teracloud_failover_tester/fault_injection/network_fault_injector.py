"""
Network Fault Injector - Simulates network failures using tc and iptables.
"""

import logging
import time
import ipaddress
from typing import Dict, Any, List, Optional, Tuple

import paramiko

from fault_injection.fault_injector import BaseFaultInjector


class NetworkFaultInjectionError(Exception):
    """Exception for network fault injection errors."""
    pass


class NetworkFaultInjector(BaseFaultInjector):
    """
    Simulates network failures such as partitions, latency, packet loss, and bandwidth constraints.
    
    Uses tc (Traffic Control) and iptables for network manipulation via SSH.
    """
    
    def __init__(self, config: Dict[str, Any], scenario: Dict[str, Any]):
        """
        Initialize the network fault injector.
        
        Args:
            config: Network fault configuration
            scenario: Test scenario with network fault details
        """
        super().__init__(config, scenario)
        
        # Validate configuration
        self._validate_config()
        
        # Set up SSH connections
        self.ssh_connections = {}
        self.commands_executed = []
    
    def inject_fault(self) -> Dict[str, Any]:
        """
        Inject the configured network fault.
        
        Returns:
            Dictionary with fault injection results
            
        Raises:
            NetworkFaultInjectionError: If fault injection fails
        """
        fault_type = self.scenario.get("type", "").lower()
        
        self.logger.info(f"Injecting network fault of type: {fault_type}")
        
        try:
            if fault_type == "network_partition":
                return self._inject_network_partition()
            elif fault_type == "network_latency":
                return self._inject_network_latency()
            elif fault_type == "network_packet_loss":
                return self._inject_packet_loss()
            elif fault_type == "network_bandwidth":
                return self._inject_bandwidth_limit()
            else:
                raise NetworkFaultInjectionError(f"Unsupported network fault type: {fault_type}")
        except Exception as e:
            self.logger.error(f"Network fault injection failed: {str(e)}", exc_info=True)
            # Attempt cleanup of any partial fault injection
            self.cleanup()
            raise NetworkFaultInjectionError(f"Failed to inject {fault_type}: {str(e)}")
    
    def verify_fault(self) -> Dict[str, Any]:
        """
        Verify that the network fault has been applied correctly.
        
        Returns:
            Dictionary with verification results
            
        Raises:
            NetworkFaultInjectionError: If fault verification fails
        """
        fault_type = self.scenario.get("type", "").lower()
        
        self.logger.info(f"Verifying network fault of type: {fault_type}")
        
        try:
            # Check if tc rules are in place
            if fault_type in ["network_latency", "network_packet_loss", "network_bandwidth"]:
                return self._verify_tc_rules()
            # Check if iptables rules are in place
            elif fault_type == "network_partition":
                return self._verify_iptables_rules()
            else:
                raise NetworkFaultInjectionError(f"Unsupported network fault type for verification: {fault_type}")
        except Exception as e:
            self.logger.error(f"Network fault verification failed: {str(e)}", exc_info=True)
            raise NetworkFaultInjectionError(f"Failed to verify {fault_type}: {str(e)}")
    
    def cleanup(self) -> Dict[str, Any]:
        """
        Clean up network fault injection by removing tc and iptables rules.
        
        Returns:
            Dictionary with cleanup results
        """
        self.logger.info("Cleaning up network fault injection")
        
        cleanup_results = {
            "tc_cleanup": None,
            "iptables_cleanup": None,
            "success": True
        }
        
        try:
            # Clean up tc rules
            tc_result = self._cleanup_tc_rules()
            cleanup_results["tc_cleanup"] = tc_result
            
            # Clean up iptables rules
            iptables_result = self._cleanup_iptables_rules()
            cleanup_results["iptables_cleanup"] = iptables_result
            
        except Exception as e:
            self.logger.error(f"Network fault cleanup failed: {str(e)}", exc_info=True)
            cleanup_results["success"] = False
            cleanup_results["error"] = str(e)
        
        # Close SSH connections
        for host, client in self.ssh_connections.items():
            try:
                client.close()
                self.logger.debug(f"Closed SSH connection to {host}")
            except:
                self.logger.warning(f"Failed to close SSH connection to {host}")
        
        self.ssh_connections = {}
        self.commands_executed = []
        return cleanup_results
    
    def _validate_config(self):
        """
        Validate the network fault configuration.
        
        Raises:
            ValueError: If the configuration is invalid
        """
        # Check if we have the necessary configuration
        if not self.config:
            raise ValueError("Network fault configuration is required")
        
        # Check if we have the host configuration for SSH
        if "hosts" not in self.config and "host" not in self.scenario:
            raise ValueError("Host configuration is required for network fault injection")
        
        # For network partition, check for source and target networks
        if self.scenario.get("type", "").lower() == "network_partition":
            if "primary_network" not in self.config and "target_network" not in self.scenario:
                raise ValueError("Primary/target network must be specified for network partition")
    
    def _get_ssh_connection(self, host_name: str) -> paramiko.SSHClient:
        """
        Get or create an SSH connection to the specified host.
        
        Args:
            host_name: Name of the host to connect to
            
        Returns:
            Paramiko SSH client for the host
            
        Raises:
            NetworkFaultInjectionError: If SSH connection fails
        """
        # Return existing connection if available
        if host_name in self.ssh_connections:
            return self.ssh_connections[host_name]
        
        # Get host configuration
        host_config = self.config.get("hosts", {}).get(host_name)
        
        if not host_config:
            # If host not found in config, check if it's specified in scenario
            if self.scenario.get("host") == host_name:
                # Use default SSH configuration with hostname from scenario
                host_config = {
                    "hostname": host_name,
                    "port": 22
                }
            else:
                raise NetworkFaultInjectionError(f"Host configuration not found for {host_name}")
        
        # Create SSH client
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Get connection details
        hostname = host_config["hostname"]
        port = host_config.get("port", 22)
        username = host_config.get("username") or self.config.get("username")
        password = host_config.get("password") or self.config.get("password")
        key_path = host_config.get("private_key_path") or self.config.get("private_key_path")
        
        if not username:
            raise NetworkFaultInjectionError(f"SSH username not specified for {host_name}")
        
        try:
            # Connect with private key if available
            if key_path:
                private_key = paramiko.RSAKey.from_private_key_file(key_path)
                client.connect(
                    hostname=hostname,
                    port=port,
                    username=username,
                    pkey=private_key,
                    timeout=self.config.get("connection_timeout", 30)
                )
            # Otherwise, connect with password
            elif password:
                client.connect(
                    hostname=hostname,
                    port=port,
                    username=username,
                    password=password,
                    timeout=self.config.get("connection_timeout", 30)
                )
            else:
                raise NetworkFaultInjectionError(f"No authentication method specified for {host_name}")
            
            self.logger.debug(f"Established SSH connection to {host_name}")
            
            # Store the connection
            self.ssh_connections[host_name] = client
            return client
            
        except Exception as e:
            self.logger.error(f"Failed to connect to {host_name}: {str(e)}")
            raise NetworkFaultInjectionError(f"SSH connection to {host_name} failed: {str(e)}")
    
    def _execute_command(self, host_name: str, command: str) -> Tuple[str, str, int]:
        """
        Execute a command on the specified host via SSH.
        
        Args:
            host_name: Name of the host to execute the command on
            command: Command to execute
            
        Returns:
            Tuple of (stdout, stderr, exit_code)
            
        Raises:
            NetworkFaultInjectionError: If command execution fails
        """
        self.logger.debug(f"Executing on {host_name}: {command}")
        
        try:
            client = self._get_ssh_connection(host_name)
            
            # Execute the command
            stdin, stdout, stderr = client.exec_command(command)
            exit_code = stdout.channel.recv_exit_status()
            
            # Get output
            stdout_text = stdout.read().decode("utf-8").strip()
            stderr_text = stderr.read().decode("utf-8").strip()
            
            # Log the result
            if exit_code != 0:
                self.logger.warning(
                    f"Command on {host_name} exited with code {exit_code}: {command}\n"
                    f"STDOUT: {stdout_text}\nSTDERR: {stderr_text}"
                )
            else:
                self.logger.debug(
                    f"Command on {host_name} succeeded: {command}\n"
                    f"STDOUT: {stdout_text}"
                )
            
            # Track executed commands for cleanup
            self.commands_executed.append({
                "host": host_name,
                "command": command,
                "exit_code": exit_code
            })
            
            return stdout_text, stderr_text, exit_code
            
        except Exception as e:
            self.logger.error(f"Failed to execute command on {host_name}: {str(e)}")
            raise NetworkFaultInjectionError(f"Command execution on {host_name} failed: {str(e)}")
    
    def _inject_network_partition(self) -> Dict[str, Any]:
        """
        Inject a network partition fault using iptables.
        
        Returns:
            Dictionary with network partition results
            
        Raises:
            NetworkFaultInjectionError: If network partition fails
        """
        host = self.scenario.get("host") or self.scenario.get("target")
        
        if not host:
            raise NetworkFaultInjectionError("Host must be specified for network partition")
            
        target_network = self.scenario.get("target_network") or self.config.get("primary_network")
        
        if not target_network:
            raise NetworkFaultInjectionError("Target network must be specified for network partition")
        
        # Validate network format
        try:
            ipaddress.ip_network(target_network)
        except ValueError:
            raise NetworkFaultInjectionError(f"Invalid target network format: {target_network}")
        
        # Create iptables DROP rule
        drop_command = (
            f"sudo iptables -A INPUT -s {target_network} -j DROP && "
            f"sudo iptables -A OUTPUT -d {target_network} -j DROP"
        )
        
        stdout, stderr, exit_code = self._execute_command(host, drop_command)
        
        if exit_code != 0:
            raise NetworkFaultInjectionError(
                f"Failed to create iptables rules: {stderr}"
            )
        
        self.logger.info(f"Successfully injected network partition on {host} for {target_network}")
        
        return {
            "success": True,
            "host": host,
            "target_network": target_network,
            "rules_added": True
        }
    
    def _inject_network_latency(self) -> Dict[str, Any]:
        """
        Inject network latency using tc (Traffic Control).
        
        Returns:
            Dictionary with network latency results
            
        Raises:
            NetworkFaultInjectionError: If latency injection fails
        """
        host = self.scenario.get("host") or self.scenario.get("target")
        
        if not host:
            raise NetworkFaultInjectionError("Host must be specified for network latency")
            
        interface = self.scenario.get("interface") or self._get_default_interface(host)
        latency_ms = self.scenario.get("latency_ms")
        
        if not latency_ms:
            raise NetworkFaultInjectionError("Latency (ms) must be specified for network latency")
        
        # Check if tc is available
        tc_check_command = "which tc"
        stdout, stderr, exit_code = self._execute_command(host, tc_check_command)
        
        if exit_code != 0:
            raise NetworkFaultInjectionError(
                f"tc (Traffic Control) not available on {host}"
            )
        
        # Create tc rules for latency
        # First, clear any existing rules
        clear_command = f"sudo tc qdisc del dev {interface} root"
        self._execute_command(host, clear_command)
        
        # Add latency rule
        latency_command = (
            f"sudo tc qdisc add dev {interface} root netem delay {latency_ms}ms"
        )
        
        stdout, stderr, exit_code = self._execute_command(host, latency_command)
        
        if exit_code != 0:
            raise NetworkFaultInjectionError(
                f"Failed to add latency rule: {stderr}"
            )
        
        self.logger.info(f"Successfully injected {latency_ms}ms latency on {host} ({interface})")
        
        return {
            "success": True,
            "host": host,
            "interface": interface,
            "latency_ms": latency_ms
        }
    
    def _inject_packet_loss(self) -> Dict[str, Any]:
        """
        Inject packet loss using tc (Traffic Control).
        
        Returns:
            Dictionary with packet loss results
            
        Raises:
            NetworkFaultInjectionError: If packet loss injection fails
        """
        host = self.scenario.get("host") or self.scenario.get("target")
        
        if not host:
            raise NetworkFaultInjectionError("Host must be specified for packet loss")
            
        interface = self.scenario.get("interface") or self._get_default_interface(host)
        packet_loss_percentage = self.scenario.get("packet_loss_percentage")
        
        if not packet_loss_percentage:
            raise NetworkFaultInjectionError("Packet loss percentage must be specified")
        
        # Check if tc is available
        tc_check_command = "which tc"
        stdout, stderr, exit_code = self._execute_command(host, tc_check_command)
        
        if exit_code != 0:
            raise NetworkFaultInjectionError(
                f"tc (Traffic Control) not available on {host}"
            )
        
        # Create tc rules for packet loss
        # First, clear any existing rules
        clear_command = f"sudo tc qdisc del dev {interface} root"
        self._execute_command(host, clear_command)
        
        # Add packet loss rule
        loss_command = (
            f"sudo tc qdisc add dev {interface} root netem loss {packet_loss_percentage}%"
        )
        
        stdout, stderr, exit_code = self._execute_command(host, loss_command)
        
        if exit_code != 0:
            raise NetworkFaultInjectionError(
                f"Failed to add packet loss rule: {stderr}"
            )
        
        self.logger.info(
            f"Successfully injected {packet_loss_percentage}% packet loss on {host} ({interface})"
        )
        
        return {
            "success": True,
            "host": host,
            "interface": interface,
            "packet_loss_percentage": packet_loss_percentage
        }
    
    def _inject_bandwidth_limit(self) -> Dict[str, Any]:
        """
        Inject bandwidth limitation using tc (Traffic Control).
        
        Returns:
            Dictionary with bandwidth limitation results
            
        Raises:
            NetworkFaultInjectionError: If bandwidth limitation fails
        """
        host = self.scenario.get("host") or self.scenario.get("target")
        
        if not host:
            raise NetworkFaultInjectionError("Host must be specified for bandwidth limitation")
            
        interface = self.scenario.get("interface") or self._get_default_interface(host)
        bandwidth_limit_kbps = self.scenario.get("bandwidth_limit_kbps")
        
        if not bandwidth_limit_kbps:
            raise NetworkFaultInjectionError("Bandwidth limit (kbps) must be specified")
        
        # Check if tc is available
        tc_check_command = "which tc"
        stdout, stderr, exit_code = self._execute_command(host, tc_check_command)
        
        if exit_code != 0:
            raise NetworkFaultInjectionError(
                f"tc (Traffic Control) not available on {host}"
            )
        
        # Create tc rules for bandwidth limitation
        # First, clear any existing rules
        clear_command = f"sudo tc qdisc del dev {interface} root"
        self._execute_command(host, clear_command)
        
        # Add bandwidth limit rule
        # Use Hierarchical Token Bucket (HTB) for bandwidth control
        bandwidth_command = (
            f"sudo tc qdisc add dev {interface} root handle 1: htb default 10 && "
            f"sudo tc class add dev {interface} parent 1: classid 1:10 htb rate {bandwidth_limit_kbps}kbit"
        )
        
        stdout, stderr, exit_code = self._execute_command(host, bandwidth_command)
        
        if exit_code != 0:
            raise NetworkFaultInjectionError(
                f"Failed to add bandwidth limit rule: {stderr}"
            )
        
        self.logger.info(
            f"Successfully limited bandwidth to {bandwidth_limit_kbps} kbps on {host} ({interface})"
        )
        
        return {
            "success": True,
            "host": host,
            "interface": interface,
            "bandwidth_limit_kbps": bandwidth_limit_kbps
        }
    
    def _get_default_interface(self, host: str) -> str:
        """
        Get the default network interface on the host.
        
        Args:
            host: Host to get the default interface for
            
        Returns:
            Name of the default interface
            
        Raises:
            NetworkFaultInjectionError: If default interface cannot be determined
        """
        # First check if interface is defined in config
        if "interfaces" in self.config and host in self.config["interfaces"]:
            return self.config["interfaces"][host]
        
        # If not, try to determine it from the default route
        command = "ip route | grep default | awk '{print $5}' | head -n 1"
        stdout, stderr, exit_code = self._execute_command(host, command)
        
        if exit_code != 0 or not stdout:
            raise NetworkFaultInjectionError(
                f"Failed to determine default interface on {host}: {stderr}"
            )
        
        return stdout.strip()
    
    def _verify_tc_rules(self) -> Dict[str, Any]:
        """
        Verify that TC rules are in place.
        
        Returns:
            Dictionary with verification results
            
        Raises:
            NetworkFaultInjectionError: If verification fails
        """
        host = self.scenario.get("host") or self.scenario.get("target")
        
        if not host:
            raise NetworkFaultInjectionError("Host must be specified for TC rule verification")
            
        interface = self.scenario.get("interface") or self._get_default_interface(host)
        
        # Check TC rules
        command = f"sudo tc qdisc show dev {interface}"
        stdout, stderr, exit_code = self._execute_command(host, command)
        
        if exit_code != 0:
            raise NetworkFaultInjectionError(
                f"Failed to verify TC rules on {host}: {stderr}"
            )
        
        # Check if netem or htb is in the output
        if "netem" not in stdout and "htb" not in stdout:
            self.logger.warning(f"TC rules not found on {host} ({interface})")
            return {
                "success": False,
                "host": host,
                "interface": interface,
                "rules_found": False,
                "output": stdout
            }
        
        self.logger.info(f"Successfully verified TC rules on {host} ({interface})")
        
        return {
            "success": True,
            "host": host,
            "interface": interface,
            "rules_found": True,
            "output": stdout
        }
    
    def _verify_iptables_rules(self) -> Dict[str, Any]:
        """
        Verify that iptables rules are in place.
        
        Returns:
            Dictionary with verification results
            
        Raises:
            NetworkFaultInjectionError: If verification fails
        """
        host = self.scenario.get("host") or self.scenario.get("target")
        
        if not host:
            raise NetworkFaultInjectionError("Host must be specified for iptables rule verification")
            
        target_network = self.scenario.get("target_network") or self.config.get("primary_network")
        
        if not target_network:
            raise NetworkFaultInjectionError("Target network must be specified for verification")
        
        # Check iptables rules
        command = "sudo iptables -L -n"
        stdout, stderr, exit_code = self._execute_command(host, command)
        
        if exit_code != 0:
            raise NetworkFaultInjectionError(
                f"Failed to verify iptables rules on {host}: {stderr}"
            )
        
        # Check if DROP rules are in the output
        if "DROP" not in stdout:
            self.logger.warning(f"iptables DROP rules not found on {host}")
            return {
                "success": False,
                "host": host,
                "rules_found": False,
                "output": stdout
            }
        
        self.logger.info(f"Successfully verified iptables rules on {host}")
        
        return {
            "success": True,
            "host": host,
            "rules_found": True,
            "output": stdout
        }
    
    def _cleanup_tc_rules(self) -> Dict[str, Any]:
        """
        Clean up TC rules.
        
        Returns:
            Dictionary with cleanup results
        """
        results = {}
        
        # Find hosts with TC commands
        tc_hosts = set()
        for cmd_info in self.commands_executed:
            if "tc qdisc add" in cmd_info["command"]:
                tc_hosts.add(cmd_info["host"])
        
        # Clean up TC rules on each host
        for host in tc_hosts:
            try:
                # Find interfaces from commands
                interfaces = set()
                for cmd_info in self.commands_executed:
                    if cmd_info["host"] == host and "tc qdisc add dev" in cmd_info["command"]:
                        # Extract interface name
                        parts = cmd_info["command"].split()
                        if "dev" in parts:
                            idx = parts.index("dev")
                            if idx + 1 < len(parts):
                                interfaces.add(parts[idx + 1])
                
                # If no interfaces found, try to get default
                if not interfaces:
                    try:
                        interfaces.add(self._get_default_interface(host))
                    except:
                        pass
                
                # Clear rules on each interface
                interface_results = {}
                for interface in interfaces:
                    command = f"sudo tc qdisc del dev {interface} root"
                    stdout, stderr, exit_code = self._execute_command(host, command)
                    
                    interface_results[interface] = {
                        "success": exit_code == 0,
                        "output": stdout if exit_code == 0 else stderr
                    }
                
                results[host] = {
                    "success": all(r["success"] for r in interface_results.values()),
                    "interfaces": interface_results
                }
                
            except Exception as e:
                self.logger.warning(f"Failed to clean up TC rules on {host}: {str(e)}")
                results[host] = {
                    "success": False,
                    "error": str(e)
                }
        
        return results
    
    def _cleanup_iptables_rules(self) -> Dict[str, Any]:
        """
        Clean up iptables rules.
        
        Returns:
            Dictionary with cleanup results
        """
        results = {}
        
        # Find hosts with iptables commands
        iptables_hosts = set()
        for cmd_info in self.commands_executed:
            if "iptables -A" in cmd_info["command"]:
                iptables_hosts.add(cmd_info["host"])
        
        # Clean up iptables rules on each host
        for host in iptables_hosts:
            try:
                # Flush iptables rules
                command = "sudo iptables -F"
                stdout, stderr, exit_code = self._execute_command(host, command)
                
                results[host] = {
                    "success": exit_code == 0,
                    "output": stdout if exit_code == 0 else stderr
                }
                
            except Exception as e:
                self.logger.warning(f"Failed to clean up iptables rules on {host}: {str(e)}")
                results[host] = {
                    "success": False,
                    "error": str(e)
                }
        
        return results