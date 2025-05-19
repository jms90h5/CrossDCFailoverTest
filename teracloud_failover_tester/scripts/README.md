# Helper Scripts

This directory contains helper scripts to simplify working with the Teracloud Failover Tester.

## Available Scripts

### setup_env.sh

Interactive script to set up environment variables for testing.

```bash
# Usage (must be sourced, not executed)
source setup_env.sh
```

This script will:
- Prompt for datacenter API tokens
- Prompt for datacenter URLs
- Optionally set up SSH credentials for fault injection
- Export all variables to your current shell environment

### run_test.sh

Simplified interface for running tests.

```bash
# Usage
./run_test.sh <scenario_name> [options]

# Examples
./run_test.sh network_partition_test
./run_test.sh api_stop_job_test --report both --log-level DEBUG
```

Options:
- `-c, --config FILE` - Config file
- `-r, --report FORMAT` - Report format: junit, html, both
- `-l, --log-level LEVEL` - Log level: DEBUG, INFO, WARNING
- `-o, --output-dir DIR` - Output directory
- `-s, --skip-cleanup` - Skip cleanup after test
- `-h, --help` - Show help message

### cleanup.sh

Tool to clean up old test results.

```bash
# Usage
./cleanup.sh [options]

# Examples
./cleanup.sh --keep-latest 10
./cleanup.sh --keep-days 14 --dry-run
```

Options:
- `-d, --dir DIR` - Results directory
- `-n, --keep-latest N` - Keep latest N test results
- `-t, --keep-days N` - Keep results newer than N days
- `--dry-run` - Show what would be deleted without deleting
- `-h, --help` - Show help message

### check_status.sh

Checks if your environment is properly set up for testing.

```bash
# Usage
./check_status.sh
```

This script will:
- Verify Python installation
- Check for required dependencies
- Check configuration files
- Verify environment variables
- List available test scenarios
- Test datacenter connectivity
- Check results directory

## Usage in RHEL 9 / CentOS 9

All scripts automatically detect RHEL/CentOS systems and adjust commands accordingly (using python3 instead of python when appropriate).

For RHEL 9 systems:

```bash
# Set up environment
source scripts/setup_env.sh

# Check status
./scripts/check_status.sh

# Run a test
./scripts/run_test.sh network_partition_test
```