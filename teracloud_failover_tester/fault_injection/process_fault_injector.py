"""
Process Fault Injector - Simulates process failures such as kills, hangs, and resource exhaustion.
"""

import logging
import time
import re
from typing import Dict, Any, List, Optional, Tuple

import paramiko

from fault_injection.fault_injector import BaseFaultInjector


class ProcessFaultInjectionError(Exception):
    """Exception for process fault injection errors."""
    pass


class ProcessFaultInjector(BaseFaultInjector):
    """
    Simulates process failures such as kills, hangs, and resource exhaustion.
    
    Uses SSH to execute commands on target hosts for process manipulation.
    """
    
    def __init__(self, config: Dict[str, Any], scenario: Dict[str, Any]):
        """
        Initialize the process fault injector.
        
        Args:
            config: SSH configuration for process fault injection
            scenario: Test scenario with process fault details
        """
        super().__init__(config, scenario)
        
        # Validate configuration
        self._validate_config()
        
        # Set up SSH connections
        self.ssh_connections = {}
        self.commands_executed = []
        self.killed_processes = []
    
    def inject_fault(self) -> Dict[str, Any]:
        """
        Inject the configured process fault.
        
        Returns:
            Dictionary with fault injection results
            
        Raises:
            ProcessFaultInjectionError: If fault injection fails
        """
        fault_type = self.scenario.get("type", "").lower()
        
        self.logger.info(f"Injecting process fault of type: {fault_type}")
        
        try:
            if fault_type == "process_kill":
                return self._inject_process_kill()
            elif fault_type == "process_hang":
                return self._inject_process_hang()
            elif fault_type == "resource_exhaustion":
                return self._inject_resource_exhaustion()
            else:
                raise ProcessFaultInjectionError(f"Unsupported process fault type: {fault_type}")
        except Exception as e:
            self.logger.error(f"Process fault injection failed: {str(e)}", exc_info=True)
            # Attempt cleanup of any partial fault injection
            self.cleanup()
            raise ProcessFaultInjectionError(f"Failed to inject {fault_type}: {str(e)}")
    
    def verify_fault(self) -> Dict[str, Any]:
        """
        Verify that the process fault has been applied correctly.
        
        Returns:
            Dictionary with verification results
            
        Raises:
            ProcessFaultInjectionError: If fault verification fails
        """
        fault_type = self.scenario.get("type", "").lower()
        
        self.logger.info(f"Verifying process fault of type: {fault_type}")
        
        try:
            if fault_type == "process_kill":
                return self._verify_process_kill()
            elif fault_type == "process_hang":
                return self._verify_process_hang()
            elif fault_type == "resource_exhaustion":
                return self._verify_resource_exhaustion()
            else:
                raise ProcessFaultInjectionError(f"Unsupported process fault type for verification: {fault_type}")
        except Exception as e:
            self.logger.error(f"Process fault verification failed: {str(e)}", exc_info=True)
            raise ProcessFaultInjectionError(f"Failed to verify {fault_type}: {str(e)}")
    
    def cleanup(self) -> Dict[str, Any]:
        """
        Clean up after process fault injection.
        
        Returns:
            Dictionary with cleanup results
        """
        self.logger.info("Cleaning up process fault injection")
        
        cleanup_results = {
            "success": True
        }
        
        try:
            # Clean up based on fault type
            fault_type = self.scenario.get("type", "").lower()
            
            if fault_type == "process_kill":
                # Nothing to clean up for process kill
                cleanup_results["process_kill_cleanup"] = {"success": True}
            elif fault_type == "process_hang":
                # Kill any hanging processes
                hang_cleanup = self._cleanup_process_hang()
                cleanup_results["process_hang_cleanup"] = hang_cleanup
            elif fault_type == "resource_exhaustion":
                # Stop resource exhaustion processes
                exhaustion_cleanup = self._cleanup_resource_exhaustion()
                cleanup_results["resource_exhaustion_cleanup"] = exhaustion_cleanup
            
        except Exception as e:
            self.logger.error(f"Process fault cleanup failed: {str(e)}", exc_info=True)
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
        Validate the process fault configuration.
        
        Raises:
            ValueError: If the configuration is invalid
        """
        # Check if we have the necessary configuration
        if not self.config:
            raise ValueError("SSH configuration is required for process fault injection")
        
        # Check if we have the host configuration
        if "host" not in self.scenario:
            raise ValueError("Host must be specified for process fault injection")
        
        # Check process identification parameters
        fault_type = self.scenario.get("type", "").lower()
        if fault_type in ["process_kill", "process_hang"]:
            if not self.scenario.get("process_name") and not self.scenario.get("process_pattern"):
                raise ValueError("Process name or pattern must be specified")
    
    def _get_ssh_connection(self, host_name: str) -> paramiko.SSHClient:
        """
        Get or create an SSH connection to the specified host.
        
        Args:
            host_name: Name of the host to connect to
            
        Returns:
            Paramiko SSH client for the host
            
        Raises:
            ProcessFaultInjectionError: If SSH connection fails
        """
        # Return existing connection if available
        if host_name in self.ssh_connections:
            return self.ssh_connections[host_name]
        
        # Get host configuration
        host_config = self.config.get("hosts", {}).get(host_name)
        
        if not host_config:
            # If host not found in config, use default SSH configuration
            # with hostname from scenario
            host_config = {
                "hostname": host_name,
                "port": 22
            }
        
        # Create SSH client
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Get connection details
        hostname = host_config.get("hostname", host_name)
        port = host_config.get("port", 22)
        username = host_config.get("username") or self.config.get("username")
        password = host_config.get("password") or self.config.get("password")
        key_path = host_config.get("private_key_path") or self.config.get("private_key_path")
        
        if not username:
            raise ProcessFaultInjectionError(f"SSH username not specified for {host_name}")
        
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
                raise ProcessFaultInjectionError(f"No authentication method specified for {host_name}")
            
            self.logger.debug(f"Established SSH connection to {host_name}")
            
            # Store the connection
            self.ssh_connections[host_name] = client
            return client
            
        except Exception as e:
            self.logger.error(f"Failed to connect to {host_name}: {str(e)}")
            raise ProcessFaultInjectionError(f"SSH connection to {host_name} failed: {str(e)}")
    
    def _execute_command(self, host_name: str, command: str) -> Tuple[str, str, int]:
        """
        Execute a command on the specified host via SSH.
        
        Args:
            host_name: Name of the host to execute the command on
            command: Command to execute
            
        Returns:
            Tuple of (stdout, stderr, exit_code)
            
        Raises:
            ProcessFaultInjectionError: If command execution fails
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
            raise ProcessFaultInjectionError(f"Command execution on {host_name} failed: {str(e)}")
    
    def _find_processes(self, host: str) -> List[Dict[str, Any]]:
        """
        Find processes matching the configured process name or pattern.
        
        Args:
            host: Host to find processes on
            
        Returns:
            List of dictionaries with process information
            
        Raises:
            ProcessFaultInjectionError: If process search fails
        """
        process_name = self.scenario.get("process_name")
        process_pattern = self.scenario.get("process_pattern")
        
        if not process_name and not process_pattern:
            raise ProcessFaultInjectionError("Process name or pattern must be specified")
        
        # Build the ps command based on the criteria
        if process_name:
            # Search by exact process name
            ps_command = f"ps -eo pid,ppid,user,cmd | grep -v grep | grep -w '{process_name}'"
        else:
            # Search by process pattern
            ps_command = f"ps -eo pid,ppid,user,cmd | grep -v grep | grep '{process_pattern}'"
        
        stdout, stderr, exit_code = self._execute_command(host, ps_command)
        
        # exit_code 1 from grep means no matches, which is not an error
        if exit_code > 1:
            raise ProcessFaultInjectionError(f"Failed to search for processes: {stderr}")
        
        # Parse the ps output
        processes = []
        for line in stdout.splitlines():
            if not line.strip():
                continue
                
            parts = line.strip().split(None, 3)
            if len(parts) >= 4:
                processes.append({
                    "pid": parts[0],
                    "ppid": parts[1],
                    "user": parts[2],
                    "cmd": parts[3]
                })
        
        return processes
    
    def _inject_process_kill(self) -> Dict[str, Any]:
        """
        Kill processes matching the configured criteria.
        
        Returns:
            Dictionary with process kill results
            
        Raises:
            ProcessFaultInjectionError: If process kill fails
        """
        host = self.scenario.get("host")
        
        if not host:
            raise ProcessFaultInjectionError("Host must be specified for process kill")
        
        # Find matching processes
        processes = self._find_processes(host)
        
        if not processes:
            raise ProcessFaultInjectionError("No matching processes found")
        
        # Kill each process
        killed_processes = []
        for process in processes:
            pid = process["pid"]
            cmd = process["cmd"]
            
            # Use SIGKILL for immediate termination
            kill_command = f"sudo kill -9 {pid}"
            stdout, stderr, exit_code = self._execute_command(host, kill_command)
            
            if exit_code != 0:
                self.logger.warning(f"Failed to kill process {pid} on {host}: {stderr}")
            else:
                self.logger.info(f"Successfully killed process {pid} ({cmd}) on {host}")
                killed_processes.append(process)
        
        if not killed_processes:
            raise ProcessFaultInjectionError("Failed to kill any processes")
        
        # Track killed processes for verification
        self.killed_processes = killed_processes
        
        return {
            "success": True,
            "host": host,
            "processes_killed": len(killed_processes),
            "killed_processes": killed_processes
        }
    
    def _inject_process_hang(self) -> Dict[str, Any]:
        """
        Cause processes to hang by sending SIGSTOP signal.
        
        Returns:
            Dictionary with process hang results
            
        Raises:
            ProcessFaultInjectionError: If process hang fails
        """
        host = self.scenario.get("host")
        
        if not host:
            raise ProcessFaultInjectionError("Host must be specified for process hang")
        
        # Find matching processes
        processes = self._find_processes(host)
        
        if not processes:
            raise ProcessFaultInjectionError("No matching processes found")
        
        # Send SIGSTOP to each process
        stopped_processes = []
        for process in processes:
            pid = process["pid"]
            cmd = process["cmd"]
            
            # Use SIGSTOP to pause the process
            stop_command = f"sudo kill -STOP {pid}"
            stdout, stderr, exit_code = self._execute_command(host, stop_command)
            
            if exit_code != 0:
                self.logger.warning(f"Failed to stop process {pid} on {host}: {stderr}")
            else:
                self.logger.info(f"Successfully stopped process {pid} ({cmd}) on {host}")
                stopped_processes.append(process)
        
        if not stopped_processes:
            raise ProcessFaultInjectionError("Failed to stop any processes")
        
        # Track stopped processes for cleanup
        self.killed_processes = stopped_processes
        
        return {
            "success": True,
            "host": host,
            "processes_stopped": len(stopped_processes),
            "stopped_processes": stopped_processes
        }
    
    def _inject_resource_exhaustion(self) -> Dict[str, Any]:
        """
        Cause resource exhaustion by consuming CPU, memory, or I/O resources.
        
        Returns:
            Dictionary with resource exhaustion results
            
        Raises:
            ProcessFaultInjectionError: If resource exhaustion fails
        """
        host = self.scenario.get("host")
        resource_type = self.scenario.get("resource_type", "cpu").lower()
        duration_seconds = self.scenario.get("duration_seconds", 60)
        
        if not host:
            raise ProcessFaultInjectionError("Host must be specified for resource exhaustion")
        
        # Execute appropriate stress command based on resource type
        stress_command = ""
        
        if resource_type == "cpu":
            # CPU stress - use all available CPUs
            cpu_count_command = "nproc"
            stdout, stderr, exit_code = self._execute_command(host, cpu_count_command)
            
            if exit_code != 0 or not stdout.strip():
                cpu_count = 1  # Default to 1 if command fails
            else:
                try:
                    cpu_count = int(stdout.strip())
                except ValueError:
                    cpu_count = 1
            
            # Use stress-ng if available, fallback to dd
            stress_check_command = "which stress-ng || which stress || echo not_available"
            stdout, stderr, exit_code = self._execute_command(host, stress_check_command)
            
            if "not_available" in stdout:
                # Use dd as a fallback
                stress_command = (
                    f"for i in $(seq 1 {cpu_count}); do "
                    f"dd if=/dev/zero of=/dev/null bs=1M count=10000 & "
                    f"done; sleep {duration_seconds}; "
                    f"pkill -f 'dd if=/dev/zero'"
                )
            elif "stress-ng" in stdout:
                # Use stress-ng
                stress_command = (
                    f"stress-ng --cpu {cpu_count} --timeout {duration_seconds}s --background"
                )
            else:
                # Use stress
                stress_command = (
                    f"stress --cpu {cpu_count} --timeout {duration_seconds}s &"
                )
                
        elif resource_type == "memory":
            # Memory stress - use a percentage of available memory
            mem_percentage = self.scenario.get("resource_percentage", 80)
            
            # Get available memory
            mem_command = "free -m | grep Mem | awk '{print $2}'"
            stdout, stderr, exit_code = self._execute_command(host, mem_command)
            
            if exit_code != 0 or not stdout.strip():
                total_memory = 1024  # Default to 1GB if command fails
            else:
                try:
                    total_memory = int(stdout.strip())
                except ValueError:
                    total_memory = 1024
            
            # Calculate memory to consume
            target_memory = int(total_memory * mem_percentage / 100)
            
            # Use stress-ng if available, fallback to Python
            stress_check_command = "which stress-ng || which stress || echo not_available"
            stdout, stderr, exit_code = self._execute_command(host, stress_check_command)
            
            if "not_available" in stdout:
                # Use Python as a fallback
                stress_command = (
                    f"python3 -c '"
                    f"import time; "
                    f"data = bytearray({target_memory} * 1024 * 1024); "
                    f"time.sleep({duration_seconds})"
                    f"' &"
                )
            elif "stress-ng" in stdout:
                # Use stress-ng
                stress_command = (
                    f"stress-ng --vm 1 --vm-bytes {target_memory}M "
                    f"--timeout {duration_seconds}s --background"
                )
            else:
                # Use stress
                stress_command = (
                    f"stress --vm 1 --vm-bytes {target_memory}M "
                    f"--timeout {duration_seconds}s &"
                )
                
        elif resource_type == "io":
            # I/O stress - write to a temporary file
            io_path = self.scenario.get("io_path", "/tmp/stress_io_test")
            
            # Use stress-ng if available, fallback to dd
            stress_check_command = "which stress-ng || which stress || echo not_available"
            stdout, stderr, exit_code = self._execute_command(host, stress_check_command)
            
            if "not_available" in stdout:
                # Use dd as a fallback
                stress_command = (
                    f"dd if=/dev/zero of={io_path} bs=1M count=1000 oflag=direct & "
                    f"sleep {duration_seconds}; "
                    f"pkill -f 'dd if=/dev/zero'; "
                    f"rm -f {io_path}"
                )
            elif "stress-ng" in stdout:
                # Use stress-ng
                stress_command = (
                    f"stress-ng --io 4 --timeout {duration_seconds}s --background"
                )
            else:
                # Use stress
                stress_command = (
                    f"stress --io 4 --timeout {duration_seconds}s &"
                )
        else:
            raise ProcessFaultInjectionError(f"Unsupported resource type: {resource_type}")
        
        # Execute the stress command
        stdout, stderr, exit_code = self._execute_command(host, stress_command)
        
        if exit_code != 0:
            raise ProcessFaultInjectionError(
                f"Failed to start resource exhaustion: {stderr}"
            )
        
        self.logger.info(
            f"Successfully started {resource_type} exhaustion on {host} "
            f"for {duration_seconds} seconds"
        )
        
        return {
            "success": True,
            "host": host,
            "resource_type": resource_type,
            "duration_seconds": duration_seconds,
            "command": stress_command
        }
    
    def _verify_process_kill(self) -> Dict[str, Any]:
        """
        Verify that processes are no longer running.
        
        Returns:
            Dictionary with verification results
            
        Raises:
            ProcessFaultInjectionError: If verification fails
        """
        host = self.scenario.get("host")
        
        if not host:
            raise ProcessFaultInjectionError("Host must be specified for verification")
        
        if not self.killed_processes:
            # If we don't have a list of killed processes, re-run the search
            # and check that no processes match
            processes = self._find_processes(host)
            
            return {
                "success": len(processes) == 0,
                "host": host,
                "processes_found": len(processes),
                "expected": 0
            }
        
        # Check each process that was killed
        still_running = []
        for process in self.killed_processes:
            pid = process["pid"]
            
            # Check if process exists
            ps_command = f"ps -p {pid} -o pid= || echo 'Process not found'"
            stdout, stderr, exit_code = self._execute_command(host, ps_command)
            
            if "Process not found" not in stdout and stdout.strip():
                # Process is still running
                still_running.append(process)
        
        if still_running:
            self.logger.warning(f"{len(still_running)} processes still running on {host}")
            return {
                "success": False,
                "host": host,
                "processes_still_running": len(still_running),
                "expected": 0,
                "running_processes": still_running
            }
        
        self.logger.info(f"Successfully verified process kill on {host}")
        
        return {
            "success": True,
            "host": host,
            "processes_still_running": 0,
            "expected": 0
        }
    
    def _verify_process_hang(self) -> Dict[str, Any]:
        """
        Verify that processes are hung (stopped).
        
        Returns:
            Dictionary with verification results
            
        Raises:
            ProcessFaultInjectionError: If verification fails
        """
        host = self.scenario.get("host")
        
        if not host:
            raise ProcessFaultInjectionError("Host must be specified for verification")
        
        if not self.killed_processes:
            raise ProcessFaultInjectionError("No stopped processes to verify")
        
        # Check each process that was stopped
        not_stopped = []
        for process in self.killed_processes:
            pid = process["pid"]
            
            # Check process state
            state_command = f"ps -o stat= -p {pid} 2>/dev/null || echo ''"
            stdout, stderr, exit_code = self._execute_command(host, state_command)
            
            # Process should be in state T (stopped)
            if not stdout.strip() or 'T' not in stdout:
                # Process is not stopped
                not_stopped.append(process)
        
        if not_stopped:
            self.logger.warning(f"{len(not_stopped)} processes not stopped on {host}")
            return {
                "success": False,
                "host": host,
                "processes_not_stopped": len(not_stopped),
                "expected": 0,
                "not_stopped_processes": not_stopped
            }
        
        self.logger.info(f"Successfully verified process hang on {host}")
        
        return {
            "success": True,
            "host": host,
            "processes_not_stopped": 0,
            "expected": 0
        }
    
    def _verify_resource_exhaustion(self) -> Dict[str, Any]:
        """
        Verify that resource exhaustion is active.
        
        Returns:
            Dictionary with verification results
            
        Raises:
            ProcessFaultInjectionError: If verification fails
        """
        host = self.scenario.get("host")
        resource_type = self.scenario.get("resource_type", "cpu").lower()
        
        if not host:
            raise ProcessFaultInjectionError("Host must be specified for verification")
        
        # Check for high resource usage
        if resource_type == "cpu":
            # Check CPU usage
            check_command = "top -bn1 | grep 'Cpu(s)' | awk '{print $2}'"
            stdout, stderr, exit_code = self._execute_command(host, check_command)
            
            if exit_code != 0 or not stdout.strip():
                return {
                    "success": False,
                    "host": host,
                    "error": "Failed to check CPU usage"
                }
            
            try:
                cpu_usage = float(stdout.strip().replace(',', '.'))
                high_cpu = cpu_usage > 70.0  # Consider high if >70%
                
                return {
                    "success": high_cpu,
                    "host": host,
                    "cpu_usage": cpu_usage,
                    "high_cpu": high_cpu
                }
            except ValueError:
                return {
                    "success": False,
                    "host": host,
                    "error": f"Invalid CPU usage value: {stdout.strip()}"
                }
                
        elif resource_type == "memory":
            # Check memory usage
            check_command = "free | grep Mem | awk '{print $3/$2 * 100.0}'"
            stdout, stderr, exit_code = self._execute_command(host, check_command)
            
            if exit_code != 0 or not stdout.strip():
                return {
                    "success": False,
                    "host": host,
                    "error": "Failed to check memory usage"
                }
            
            try:
                mem_usage = float(stdout.strip().replace(',', '.'))
                high_mem = mem_usage > 70.0  # Consider high if >70%
                
                return {
                    "success": high_mem,
                    "host": host,
                    "memory_usage_percent": mem_usage,
                    "high_memory": high_mem
                }
            except ValueError:
                return {
                    "success": False,
                    "host": host,
                    "error": f"Invalid memory usage value: {stdout.strip()}"
                }
                
        elif resource_type == "io":
            # Check for IO activity
            check_command = "iostat -x 1 2 | tail -n 4 | head -n 1 | awk '{print $NF}'"
            stdout, stderr, exit_code = self._execute_command(host, check_command)
            
            if exit_code != 0 or not stdout.strip():
                return {
                    "success": False,
                    "host": host,
                    "error": "Failed to check IO usage"
                }
            
            try:
                io_util = float(stdout.strip().replace(',', '.'))
                high_io = io_util > 50.0  # Consider high if >50%
                
                return {
                    "success": high_io,
                    "host": host,
                    "io_utilization_percent": io_util,
                    "high_io": high_io
                }
            except ValueError:
                return {
                    "success": False,
                    "host": host,
                    "error": f"Invalid IO utilization value: {stdout.strip()}"
                }
                
        else:
            return {
                "success": False,
                "host": host,
                "error": f"Unsupported resource type for verification: {resource_type}"
            }
    
    def _cleanup_process_hang(self) -> Dict[str, Any]:
        """
        Clean up hung processes by sending SIGCONT and optionally SIGTERM.
        
        Returns:
            Dictionary with cleanup results
        """
        host = self.scenario.get("host")
        terminate_after_continue = self.scenario.get("terminate_after_continue", False)
        
        if not host or not self.killed_processes:
            return {"success": True, "message": "No stopped processes to clean up"}
        
        # Continue each stopped process
        continued_processes = []
        for process in self.killed_processes:
            pid = process["pid"]
            
            # Send SIGCONT to resume the process
            cont_command = f"sudo kill -CONT {pid} 2>/dev/null || echo 'Process not found'"
            stdout, stderr, exit_code = self._execute_command(host, cont_command)
            
            if "Process not found" not in stdout:
                continued_processes.append(process)
                
                # Optionally terminate the process
                if terminate_after_continue:
                    term_command = f"sudo kill -TERM {pid} 2>/dev/null || echo 'Process not found'"
                    self._execute_command(host, term_command)
        
        self.logger.info(f"Continued {len(continued_processes)} stopped processes on {host}")
        
        return {
            "success": True,
            "host": host,
            "processes_continued": len(continued_processes),
            "terminated_after_continue": terminate_after_continue
        }
    
    def _cleanup_resource_exhaustion(self) -> Dict[str, Any]:
        """
        Clean up resource exhaustion by terminating stress processes.
        
        Returns:
            Dictionary with cleanup results
        """
        host = self.scenario.get("host")
        
        if not host:
            return {"success": True, "message": "No host specified for cleanup"}
        
        # Kill stress processes
        kill_command = "pkill -f 'stress' || pkill -f 'stress-ng' || echo 'No stress processes found'"
        stdout, stderr, exit_code = self._execute_command(host, kill_command)
        
        # Also clean up any dd processes
        dd_command = "pkill -f 'dd if=/dev/zero' || echo 'No dd processes found'"
        self._execute_command(host, dd_command)
        
        # And clean up any Python processes used for memory stress
        python_command = "pkill -f 'data = bytearray' || echo 'No Python memory stress processes found'"
        self._execute_command(host, python_command)
        
        # Try to remove any temporary files
        cleanup_command = "rm -f /tmp/stress_io_test"
        self._execute_command(host, cleanup_command)
        
        self.logger.info(f"Cleaned up resource exhaustion processes on {host}")
        
        return {
            "success": True,
            "host": host,
            "message": "Resource exhaustion processes terminated"
        }