# Teracloud Streams Automated Cross-DC Failover Tester: User Guide

This document provides detailed instructions for configuring and running the Teracloud Streams Automated Cross-DC Failover Testing Framework.

## Prerequisites

Before using the framework, ensure you have:

1. **Python Environment**: Python 3.9 or higher
2. **Teracloud Streams Environment**: 
   - Access to Teracloud Streams 7.2.0+ with REST Management API
   - Primary and secondary datacenters configured
   - Cross-DC Failover Toolkit configured in your Streams applications
   - Data Exchange Service endpoints in your Streams applications
3. **Network Access**: 
   - Access to both datacenter API endpoints
   - SSH access to hosts where network/process faults will be injected
4. **Required Packages**:
   - Python modules: pyyaml, requests
   - For RHEL 9/CentOS: python3-pip, python3-yaml, python3-requests

## Installation

### Automated Setup Using Wizard (Recommended)

The easiest way to set up the framework is using our interactive setup wizard:

```bash
# Clone the repository
git clone https://github.com/your-organization/teracloud-failover-tester.git
cd teracloud-failover-tester

# Run the setup wizard
python3 setup_wizard.py
```

The wizard will:
- Check prerequisites
- Set up a virtual environment (or use system Python on RHEL/CentOS)
- Help install dependencies
- Guide you through configuration setup
- Provide next steps for running tests

### RHEL 9 / CentOS 9 Setup

For RHEL 9 or CentOS 9 systems, you can use the system Python installation:

```bash
# Install required system packages
sudo dnf install python3-pip python3-yaml python3-requests git

# Run the setup wizard
python3 setup_wizard.py
```

The wizard will automatically detect RHEL/CentOS systems and recommend using system Python.

### Manual Installation Steps

Alternatively, you can set up manually:

1. Clone the repository:
   ```bash
   git clone https://github.com/your-organization/teracloud-failover-tester.git
   cd teracloud-failover-tester
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure your environment:
   ```bash
   cp config/config.yaml.example config/config.yaml
   # Edit config.yaml with your environment details
   ```

## Configuration

### Global Configuration File

The global configuration file (`config/config.yaml`) contains framework-wide settings:

```yaml
# Datacenters configuration
datacenters:
  primary:
    api_url: "https://streams-api.primary-dc.example.com/v2"
    auth_token: "$CRED:primary_api_token"
    # ...
  secondary:
    api_url: "https://streams-api.secondary-dc.example.com/v2"
    # ...

# Credentials (can reference environment variables)
credentials:
  primary_api_token: "$ENV:PRIMARY_API_TOKEN"
  # ...

# Fault injection configuration
fault_injection:
  ssh:
    # SSH connection details
  network:
    # Network fault configuration
```

### Credential Management

You can manage credentials in two ways:

1. **Direct Values**: Store values directly in the `credentials` section (not recommended for sensitive data)
2. **Environment Variables**: Reference environment variables with `$ENV:VARIABLE_NAME`

Example of setting environment variables:
```bash
export PRIMARY_API_TOKEN="your-api-token"
export SSH_PASSWORD="your-ssh-password"
```

### Test Scenario Files

Test scenarios are defined in YAML files in the `scenarios` directory. Each file defines:

- Test identification
- Application bundle and parameters
- Pre-failover data generation
- Fault scenario details
- Validation checks
- Expected metrics and thresholds

Example scenario:
```yaml
test_id: "network_partition_001"
description: "Test cross-DC failover when network partition occurs"

streams_application_sab: "applications/crossdc_sample_app.sab"
submission_params:
  jobName: "CrossDCFailoverTest"
  # ...

pre_failover_data:
  generator_type: "deterministic"
  event_count: 10000
  # ...

fault_scenario:
  type: "network_partition"
  host: "primary-host"
  target_network: "10.0.2.0/24"
  # ...

# ...
```

## Running Tests

### Basic Test Execution

To run a test with default settings:

```bash
python main.py --scenario scenarios/network_partition_test.yaml
```

### Command-Line Options

```
--scenario SCENARIO_FILE    Path to the test scenario YAML file (required)
--config CONFIG_FILE        Path to the configuration file (default: config/config.yaml)
--report {junit,html,both,none}  Report format (default: junit)
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

## Creating Custom Test Scenarios

To create a custom test scenario:

1. Copy an existing scenario file:
   ```bash
   cp scenarios/network_partition_test.yaml scenarios/my_custom_test.yaml
   ```

2. Edit the file to define your test parameters:
   - Update test identification
   - Configure your application bundle and parameters
   - Define the fault scenario (network_partition, process_kill, api_initiated, etc.)
   - Set validation checks and expected metrics

3. Run your custom test:
   ```bash
   python main.py --scenario scenarios/my_custom_test.yaml
   ```

## Troubleshooting

### Common Issues

- **API Connection Errors**: Check API URLs and tokens in configuration
- **SSH Access Failures**: Verify SSH credentials and host connectivity
- **Application Deployment Issues**: Check SAB file path and submission parameters
- **Permission Errors**: Ensure sufficient privileges for fault injection

### Logs and Debugging

For detailed troubleshooting, increase the log level:
```bash
python main.py --scenario your_scenario.yaml --log-level DEBUG
```

Review the logs in the output directory for errors and warnings.

## Support and Feedback

For issues or questions, please contact:
- Teracloud Support Team: support@teracloud.example.com
- Project Maintainers: failover-tester-team@example.com