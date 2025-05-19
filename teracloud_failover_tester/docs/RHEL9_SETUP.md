# RHEL 9 / CentOS 9 Setup Guide

This document provides detailed step-by-step instructions for setting up and running the Teracloud Failover Tester on RHEL 9 or CentOS 9 systems.

## Prerequisites

Ensure you have:

- RHEL 9 or CentOS 9 system with admin (sudo) privileges
- Access to Teracloud Streams environment (primary and secondary datacenters)
- Network connectivity to both datacenters
- Authentication tokens or credentials for both datacenters

## Step 1: Install Required System Packages

```bash
# Install Git and required Python packages
sudo dnf install git python3-pip python3-yaml python3-requests

# Verify Python version (should be 3.9+)
python3 --version
```

## Step 2: Clone the Repository

```bash
# Clone the repository
git clone https://github.com/your-organization/teracloud-failover-tester.git

# Move into the project directory
cd teracloud-failover-tester
```

## Step 3: Run the Setup Wizard

```bash
# Run the setup wizard
python3 setup_wizard.py
```

The wizard will:
- Automatically detect your RHEL system
- Recommend using system Python (recommended for RHEL)
- Guide you through configuration setup
- Create a config file based on your inputs

## Step 4: Set Environment Variables

Based on the environment variables you specified during setup:

```bash
# Set API tokens for both datacenters
export PRIMARY_API_TOKEN="your-primary-dc-token"
export SECONDARY_API_TOKEN="your-secondary-dc-token"

# If you configured SSH with password authentication
export SSH_PASSWORD="your-ssh-password"
```

## Step 5: Run a Test

```bash
# Run a simple network partition test
python3 main.py --scenario scenarios/network_partition_test.yaml
```

## Step 6: View Test Results

```bash
# List all files in the results directory
ls -l results/

# View the test log
cat results/test_log.txt

# View the JUnit XML report
cat results/latest_test_report.xml

# View HTML report (if generated)
firefox results/test_report.html  # Or your preferred browser
```

## Common Issues on RHEL 9

### Package Installation Issues

If you encounter package installation issues:

```bash
# Make sure your system is up to date
sudo dnf update

# Try installing packages individually
sudo dnf install python3-pip
sudo dnf install python3-yaml
sudo dnf install python3-requests
```

### Permission Issues

If you encounter permission issues:

```bash
# Ensure the script is executable
chmod +x setup_wizard.py

# Check SELinux status if getting unexpected permission errors
getenforce
```

### Firewall Issues

If tests fail due to connectivity issues:

```bash
# Check firewall status
sudo firewall-cmd --state

# Allow necessary ports (example - adjust as needed)
sudo firewall-cmd --permanent --add-port=8443/tcp
sudo firewall-cmd --reload
```

## Running Without Virtual Environment

When using system Python on RHEL 9, you don't need a virtual environment. The main benefit is that you can use system-managed packages that are optimized for your environment.

If you prefer to use a virtual environment anyway:

```bash
# Install the venv module if needed
sudo dnf install python3-virtualenv

# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies in the virtual environment
pip install -r requirements.txt
```

## Additional Resources

- [Documentation](USAGE.md) - Comprehensive usage guide
- [Toolkit Integration Guide](TOOLKIT_INTEGRATION.md) - Details on Cross-DC Failover Toolkit integration
- [Command Line Quick Start](CONSOLE_USAGE.md) - Simplified command-line instructions