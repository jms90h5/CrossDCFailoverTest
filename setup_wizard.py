#!/usr/bin/env python3
"""
Setup Wizard for Teracloud Failover Tester

This script provides an interactive command-line interface to help users
set up their environment for running the Teracloud Failover Tester.

RHEL 9 Setup Instructions:
  sudo dnf install python3-pip python3-yaml python3-requests
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

def print_banner():
    """Print a welcome banner for the setup wizard."""
    print("\n" + "=" * 80)
    print("   TERACLOUD STREAMS FAILOVER TESTER - SETUP WIZARD")
    print("=" * 80)
    print("\nThis wizard will guide you through setting up the Teracloud Failover Tester.\n")

def check_prerequisites():
    """Check if all prerequisites are met."""
    print("Checking prerequisites...")
    
    # Check Python version
    python_version = sys.version_info
    if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 9):
        print(" ❌ Python 3.9 or higher is required.")
        print(f"    Current version: {python_version.major}.{python_version.minor}.{python_version.micro}")
        return False
    print(" ✅ Python version OK")
    
    # Check for required modules
    try:
        import yaml
        print(" ✅ PyYAML module available")
    except ImportError:
        print(" ⚠️ PyYAML module not found.")
        print("    For RHEL 9: sudo dnf install python3-yaml")
        print("    For other systems: pip3 install PyYAML")
        return False
    
    try:
        import requests
        print(" ✅ Requests module available")
    except ImportError:
        print(" ⚠️ Requests module not found.")
        print("    For RHEL 9: sudo dnf install python3-requests")
        print("    For other systems: pip3 install requests")
        return False
    
    # Check Git installation
    try:
        subprocess.run(["git", "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(" ✅ Git is installed")
    except (subprocess.SubprocessError, FileNotFoundError):
        print(" ⚠️ Git is not installed or not available in PATH")
        print("    For RHEL 9: sudo dnf install git")
        return False
    
    return True

def check_system_type():
    """Detect system type and provide appropriate setup guidance."""
    # Check if we're on RHEL/CentOS
    is_rhel = False
    if os.path.exists("/etc/redhat-release"):
        with open("/etc/redhat-release", "r") as f:
            content = f.read().lower()
            if "red hat" in content or "centos" in content:
                is_rhel = True
                print("\nRHEL/CentOS system detected.")
                print("System Python will be used for setup.")
    
    return is_rhel

def setup_environment(use_system_python=False):
    """Set up the environment for the failover tester."""
    
    if use_system_python:
        print("\nUsing system Python installation...")
        print(" ✅ System Python will be used for all operations")
        return True
    else:
        return setup_virtual_environment()

def setup_virtual_environment():
    """Create and activate a virtual environment."""
    print("\nSetting up virtual environment...")
    
    # Check if venv already exists
    if Path("venv").exists():
        overwrite = input("Virtual environment already exists. Recreate? (y/n): ").lower() == 'y'
        if overwrite:
            shutil.rmtree("venv")
        else:
            print(" ✅ Using existing virtual environment")
            return True
    
    try:
        subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)
        print(" ✅ Virtual environment created successfully")
        
        # Instructions for activation
        if sys.platform == "win32":
            print("\nTo activate the virtual environment, run:")
            print("    venv\\Scripts\\activate")
        else:
            print("\nTo activate the virtual environment, run:")
            print("    source venv/bin/activate")
        
        return True
    except subprocess.SubprocessError as e:
        print(f" ❌ Failed to create virtual environment: {str(e)}")
        return False

def install_dependencies(use_system_python=False):
    """Install dependencies from requirements.txt."""
    print("\nInstalling dependencies...")
    
    if not Path("requirements.txt").exists():
        print(" ❌ requirements.txt not found")
        return False
    
    if use_system_python:
        print("\nFor RHEL systems, we recommend installing dependencies with dnf:")
        print("sudo dnf install python3-pip python3-yaml python3-requests")
        
        with open("requirements.txt", "r") as f:
            content = f.read()
            print("\nOther required packages from requirements.txt:")
            for line in content.splitlines():
                if line.strip() and not line.strip().startswith("#"):
                    if "yaml" not in line.lower() and "requests" not in line.lower():
                        print(f"- {line.strip()}")
        
        install_system = input("\nDo you want to attempt installation with pip3? (y/n): ").lower() == 'y'
        if not install_system:
            print(" ℹ️ Skipping system package installation")
            return True
            
        # Install with system pip
        pip_cmd = "pip3"
        
    else:
        # Determine pip command for virtualenv
        pip_cmd = "pip"
        if "VIRTUAL_ENV" not in os.environ:
            if sys.platform == "win32":
                pip_cmd = ".\\venv\\Scripts\\pip"
            else:
                pip_cmd = "./venv/bin/pip"
    
    try:
        subprocess.run([pip_cmd, "install", "-r", "requirements.txt"], check=True)
        print(" ✅ Dependencies installed successfully")
        return True
    except subprocess.SubprocessError as e:
        print(f" ❌ Failed to install dependencies: {str(e)}")
        return False

def configure_environment():
    """Set up the configuration file."""
    print("\nConfiguring environment...")
    
    config_dir = Path("config")
    example_config = config_dir / "config.yaml.example"
    config_file = config_dir / "config.yaml"
    
    if not example_config.exists():
        print(f" ❌ Example configuration file {example_config} not found")
        return False
    
    # Check if config already exists
    if config_file.exists():
        overwrite = input("Configuration file already exists. Reconfigure? (y/n): ").lower() == 'y'
        if not overwrite:
            print(" ✅ Using existing configuration")
            return True
    
    # Load example config
    try:
        import yaml
        with open(example_config, 'r') as f:
            config = yaml.safe_load(f) or {}
    except Exception as e:
        print(f" ❌ Failed to load example configuration: {str(e)}")
        return False
    
    print("\nConfiguring datacenters...")
    
    # Primary datacenter configuration
    print("\n--- Primary Datacenter ---")
    if 'datacenters' not in config:
        config['datacenters'] = {}
    if 'primary' not in config['datacenters']:
        config['datacenters']['primary'] = {}
    
    primary_url = input("Primary DC API URL [https://streams-api.primary-dc.example.com/v2]: ")
    if primary_url:
        config['datacenters']['primary']['api_url'] = primary_url
    
    primary_token_env = input("Environment variable for primary DC token [PRIMARY_API_TOKEN]: ") or "PRIMARY_API_TOKEN"
    config['datacenters']['primary']['auth_token'] = f"$ENV:{primary_token_env}"
    
    # Secondary datacenter configuration
    print("\n--- Secondary Datacenter ---")
    if 'secondary' not in config['datacenters']:
        config['datacenters']['secondary'] = {}
    
    secondary_url = input("Secondary DC API URL [https://streams-api.secondary-dc.example.com/v2]: ")
    if secondary_url:
        config['datacenters']['secondary']['api_url'] = secondary_url
    
    secondary_token_env = input("Environment variable for secondary DC token [SECONDARY_API_TOKEN]: ") or "SECONDARY_API_TOKEN"
    config['datacenters']['secondary']['auth_token'] = f"$ENV:{secondary_token_env}"
    
    # Fault injection configuration
    print("\n--- Fault Injection Configuration ---")
    if 'fault_injection' not in config:
        config['fault_injection'] = {}
    if 'ssh' not in config['fault_injection']:
        config['fault_injection']['ssh'] = {}
    
    # SSH configuration for fault injection
    use_ssh = input("Do you want to configure SSH for fault injection? (y/n): ").lower() == 'y'
    if use_ssh:
        ssh_host = input("SSH host for fault injection: ")
        ssh_user = input("SSH username: ")
        ssh_auth_type = input("SSH authentication type (password/key) [key]: ") or "key"
        
        config['fault_injection']['ssh']['host'] = ssh_host
        config['fault_injection']['ssh']['username'] = ssh_user
        
        if ssh_auth_type.lower() == 'password':
            ssh_password_env = input("Environment variable for SSH password [SSH_PASSWORD]: ") or "SSH_PASSWORD"
            config['fault_injection']['ssh']['auth_type'] = 'password'
            config['fault_injection']['ssh']['password'] = f"$ENV:{ssh_password_env}"
        else:
            ssh_key_path = input("Path to SSH private key [~/.ssh/id_rsa]: ") or "~/.ssh/id_rsa"
            config['fault_injection']['ssh']['auth_type'] = 'key'
            config['fault_injection']['ssh']['key_path'] = ssh_key_path
    
    # Write the configuration file
    try:
        with open(config_file, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        print(f" ✅ Configuration written to {config_file}")
        
        # Set up environment variables
        print("\nTo set up the required environment variables, run:")
        print(f"export {primary_token_env}=\"your-primary-dc-token\"")
        print(f"export {secondary_token_env}=\"your-secondary-dc-token\"")
        if use_ssh and ssh_auth_type.lower() == 'password':
            print(f"export {ssh_password_env}=\"your-ssh-password\"")
        
        return True
    except Exception as e:
        print(f" ❌ Failed to write configuration: {str(e)}")
        return False

def finalize_setup(use_system_python=False):
    """Provide instructions for finalizing the setup."""
    print("\n" + "=" * 80)
    print("   SETUP COMPLETE")
    print("=" * 80)
    
    print("\nTo finalize your setup:")
    
    if not use_system_python:
        if "VIRTUAL_ENV" not in os.environ:
            if sys.platform == "win32":
                print("1. Activate the virtual environment: venv\\Scripts\\activate")
            else:
                print("1. Activate the virtual environment: source venv/bin/activate")
    else:
        print("1. Ensure all system dependencies are installed")
        print("   sudo dnf install python3-pip python3-yaml python3-requests")
    
    print("2. Set the required environment variables (shown above)")
    print("3. Try running a sample test:")
    if use_system_python:
        print("   python3 main.py --scenario scenarios/network_partition_test.yaml")
    else:
        print("   python main.py --scenario scenarios/network_partition_test.yaml")
    
    print("\nFor more information, refer to:")
    print("- Documentation: teracloud_failover_tester/docs/USAGE.md")
    print("- Toolkit Integration Guide: teracloud_failover_tester/docs/TOOLKIT_INTEGRATION.md")
    
    print("\nHappy testing!")

def main():
    """Main function to run the setup wizard."""
    print_banner()
    
    # Detect system type
    is_rhel = check_system_type()
    
    if not check_prerequisites():
        print("\nPlease address the prerequisites before continuing.")
        if is_rhel:
            print("\nFor RHEL 9/CentOS 9 systems, run:")
            print("sudo dnf install python3-pip python3-yaml python3-requests git")
        return 1
    
    print("\nAll prerequisites met. Continuing with setup...\n")
    
    # For RHEL systems, offer to use system Python
    use_system_python = is_rhel
    if is_rhel:
        print("\nOn RHEL/CentOS systems, we recommend using system Python.")
        use_virtualenv = input("Do you want to use a virtual environment instead? (y/n): ").lower() == 'y'
        use_system_python = not use_virtualenv
    
    # Set up environment (system Python or virtualenv)
    if not setup_environment(use_system_python):
        print("\nFailed to set up environment. Exiting.")
        return 1
    
    # Ask if the user wants to install dependencies
    install_deps = input("\nDo you want to install dependencies now? (y/n): ").lower() == 'y'
    if install_deps:
        if not install_dependencies(use_system_python):
            print("\nFailed to install dependencies. You can try again later.")
    else:
        if use_system_python:
            print("\nSkipping dependency installation.")
            print("For RHEL 9 systems, install dependencies with:")
            print("sudo dnf install python3-pip python3-yaml python3-requests")
        else:
            print("\nSkipping dependency installation.")
            print("To install dependencies later, run:")
            print("    pip install -r requirements.txt")
    
    # Ask if the user wants to configure the environment
    configure_env = input("\nDo you want to configure the environment now? (y/n): ").lower() == 'y'
    if configure_env:
        if not configure_environment():
            print("\nFailed to configure environment. You can try again later.")
    else:
        print("\nSkipping environment configuration.")
        print("To configure the environment later, run:")
        print("    cp config/config.yaml.example config/config.yaml")
        print("    # Then edit config.yaml manually")
    
    finalize_setup(use_system_python)
    return 0

if __name__ == "__main__":
    sys.exit(main())