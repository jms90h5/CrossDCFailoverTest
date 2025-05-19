# Teracloud Streams Automated Cross-DC Failover Testing Framework

This repository contains a comprehensive automated testing framework for validating cross-datacenter failover capabilities in Teracloud Streams applications.

## Repository Structure

- `/teracloud_failover_tester` - The main framework implementation
  - `/config` - Configuration management
  - `/data_handler` - Test data generation and validation
  - `/docs` - Documentation and guides
    - Design and implementation documents (.docx)
    - Usage guides and integration instructions
  - `/fault_injection` - Fault simulation components
  - `/monitoring` - Metrics collection
  - `/orchestrator` - Test execution engine
  - `/reporting` - Results reporting
  - `/scenarios` - Sample test scenarios
  - `/scripts` - Helper scripts to simplify common operations
  - `/streams_client` - API clients for Teracloud Streams
  - `/tests` - Unit and integration tests
  - `/utils` - Common utilities

## Key Components

- Comprehensive test orchestration
- Fault injection capabilities (network, process, API)
- Cross-DC Failover Toolkit integration
- Metrics collection and validation
- RPO and RTO measurement
- Reporting and analysis

# Quick Start Guide

This section provides step-by-step instructions to quickly get started with the Teracloud Streams Automated Cross-DC Failover Testing Framework.

## Prerequisites

- **Python Environment**: Python 3.9 or higher
- **Access to Teracloud Streams**: 
  - Teracloud Streams 7.2.0+ with REST Management API enabled
  - Primary and secondary datacenter API endpoints and credentials
  - Cross-DC Failover Toolkit configured in your Streams applications
- **Network Access**: 
  - Access to both datacenter API endpoints
  - SSH access to hosts for fault injection (optional, but required for network/process faults)

## Setup in 5 Minutes

### Step 1: Clone the Repository

```bash
git clone https://github.com/your-organization/CrossDCFailoverTest.git
cd CrossDCFailoverTest
```

### Step 2: Run the Interactive Setup Wizard

The easiest way to get started is using our interactive setup wizard:

```bash
# For most systems
python3 setup_wizard.py

# For RHEL 9/CentOS 9 
# First install required packages:
sudo dnf install python3-pip python3-yaml python3-requests git
python3 setup_wizard.py
```

The wizard will guide you through the entire setup process, including:
- Environment configuration
- Dependency installation
- Authentication setup
- Test configuration

### Step 3: Set Up Environment Variables

```bash
# Source the environment setup script
source scripts/setup_env.sh
```

This interactive script will prompt you for all required credentials and settings.

### Step 4: Run Your First Test

```bash
# Check if everything is properly configured
./scripts/check_status.sh

# Run a network partition test
./scripts/run_test.sh network_partition_test
```

### Step 5: View Results

```bash
# Results are stored in the results directory
ls -l results/

# Open the HTML report in your browser
open results/test_report.html  # Use appropriate command for your OS
```

## Manual Setup Option

For those who prefer a manual approach, follow these steps:

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-organization/CrossDCFailoverTest.git
   cd CrossDCFailoverTest
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure your environment:**
   ```bash
   cp config/config.yaml.example config/config.yaml
   # Edit config.yaml with your environment details
   ```

5. **Set environment variables for credentials:**
   ```bash
   export PRIMARY_API_TOKEN="your-primary-dc-token"
   export SECONDARY_API_TOKEN="your-secondary-dc-token"
   ```

## Basic Usage

### Using Helper Scripts (Recommended)

The framework includes several helper scripts to simplify common operations:

```bash
# Set up environment variables
source scripts/setup_env.sh

# Check if your environment is properly configured
./scripts/check_status.sh

# Run a test with simplified options
./scripts/run_test.sh network_partition_test

# Clean up old test results
./scripts/cleanup.sh --keep-latest 10
```

See the [Scripts Guide](teracloud_failover_tester/scripts/SCRIPTS_GUIDE.md) for more details on these helper scripts.

### Running Tests Directly

To run a test with default settings:

```bash
python main.py --scenario scenarios/network_partition_test.yaml
```

### Common Command-Line Options
```
--scenario SCENARIO_FILE    Path to the test scenario YAML file (required)
--config CONFIG_FILE        Path to the configuration file (default: config/config.yaml)
--report {junit,html,both}  Report format (default: junit)
--log-level LEVEL           Set logging level (default: INFO)
--output-dir DIR            Directory for test results (default: results)
--skip-cleanup              Skip cleanup after test (useful for debugging)
```

### Example Commands
Run with custom configuration:
```bash
python main.py --scenario scenarios/network_partition_test.yaml --config config/prod.yaml
```

Generate both HTML and JUnit reports:
```bash
python main.py --scenario scenarios/api_stop_job_test.yaml --report both
```

Debug a test with verbose logging:
```bash
python main.py --scenario scenarios/process_kill_test.yaml --log-level DEBUG --skip-cleanup
```

## Understanding Results

Test results are saved in the output directory (default: `results`):
- **Log File**: Contains detailed execution logs
- **JUnit Report**: XML report for CI/CD integration
- **HTML Report**: Visual report with charts and metrics
- **JSON Report**: Machine-readable results data

### Key Metrics
- **RTO (Recovery Time Objective)**: How long the failover took
- **RPO (Recovery Point Objective)**: How much data was lost during failover
- **Throughput Recovery**: How quickly processing capacity returned
- **Data Integrity**: Whether all data was correctly processed

## Getting Started

For detailed usage instructions, please refer to:

- [Complete Documentation](teracloud_failover_tester/docs/USAGE.md) - Comprehensive user guide
- [Command Line Quick Start](teracloud_failover_tester/docs/CONSOLE_USAGE.md) - Simple console instructions
- [RHEL 9 Setup Guide](teracloud_failover_tester/docs/RHEL9_SETUP.md) - Specific instructions for RHEL/CentOS systems
- [Toolkit Integration Guide](teracloud_failover_tester/docs/TOOLKIT_INTEGRATION.md) - Details on Cross-DC Failover Toolkit integration
- [Helper Scripts](teracloud_failover_tester/scripts/SCRIPTS_GUIDE.md) - Utilities to simplify common operations
- [Design Review](teracloud_failover_tester/docs/DESIGN_REVIEW.md) - Validation against Teracloud Streams documentation
- [Recommendations](teracloud_failover_tester/docs/RECOMMENDATIONS.md) - Suggested improvements for alignment with platform capabilities

## Implementation Status

All planned components have been successfully implemented. For a complete overview of the implementation, see the [Final Implementation Report](teracloud_failover_tester/FINAL_IMPLEMENTATION_REPORT.md).

## License

[License information will be added here]