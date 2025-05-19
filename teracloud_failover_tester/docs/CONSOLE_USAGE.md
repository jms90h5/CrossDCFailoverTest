# Command Line Quick Start Guide

This guide provides simple step-by-step instructions for setting up and using the Teracloud Failover Tester from a command line interface.

## Quick Setup for RHEL 9 / CentOS 9

```bash
# 1. Install required system packages
sudo dnf install python3-pip python3-yaml python3-requests git

# 2. Clone the repository
git clone https://github.com/your-organization/teracloud-failover-tester.git
cd teracloud-failover-tester

# 3. Run the setup wizard
python3 setup_wizard.py

# 4. Set required environment variables
export PRIMARY_API_TOKEN="your-primary-dc-token"
export SECONDARY_API_TOKEN="your-secondary-dc-token"

# 5. Run a test using system Python
python3 main.py --scenario scenarios/network_partition_test.yaml
```

## Quick Setup for Other Systems

```bash
# 1. Clone the repository
git clone https://github.com/your-organization/teracloud-failover-tester.git
cd teracloud-failover-tester

# 2. Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Run the setup wizard
python setup_wizard.py

# 4. Set required environment variables
export PRIMARY_API_TOKEN="your-primary-dc-token"
export SECONDARY_API_TOKEN="your-secondary-dc-token"

# 5. Run a test
python main.py --scenario scenarios/network_partition_test.yaml
```

## Common Command-Line Options

```
--scenario SCENARIO_FILE    Path to the test scenario YAML file (required)
--config CONFIG_FILE        Path to the configuration file (default: config/config.yaml)
--report {junit,html,both}  Report format (default: junit)
--log-level LEVEL           Set logging level (default: INFO)
--output-dir DIR            Directory for test results (default: results)
--skip-cleanup              Skip cleanup after test (useful for debugging)
```

## Example Commands

Run with custom configuration:
```bash
python3 main.py --scenario scenarios/network_partition_test.yaml --config config/prod.yaml
```

Generate both HTML and JUnit reports:
```bash
python3 main.py --scenario scenarios/api_stop_job_test.yaml --report both
```

Debug a test with verbose logging:
```bash
python3 main.py --scenario scenarios/process_kill_test.yaml --log-level DEBUG --skip-cleanup
```

## Finding Test Results

Test results are saved in the output directory (default: `results`):

```bash
# List all test results
ls -l results/

# View the JUnit XML report
cat results/latest_test_report.xml

# Open HTML report in browser (if available)
# Replace with appropriate command for your system
open results/test_report.html
```