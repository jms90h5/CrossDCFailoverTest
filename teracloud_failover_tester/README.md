# Teracloud Streams Automated Cross-DC Failover Tester

A comprehensive automated testing framework for validating the cross-datacenter failover capabilities of Teracloud Streams applications.

## Overview

This framework automates the entire test lifecycle for Teracloud Streams cross-DC failover scenarios:
- Application deployment and configuration
- Test data generation and injection
- Fault simulation (network, process, API-based)
- Failover monitoring and metrics collection
- Cross-DC Failover Toolkit integration and monitoring
- Data validation and result analysis
- Reporting and visualization

## Features

- **Comprehensive Testing**: Test end-to-end cross-DC failover mechanisms
- **Automation**: Minimize manual intervention throughout the test lifecycle
- **Repeatability**: Enable consistent execution for regression testing
- **Realistic Simulation**: Simulate various failure scenarios (network issues, service outages, DC failures)
- **Metrics Collection**: Quantify key metrics (RTO, RPO, throughput recovery)
- **Extensibility**: Easily accommodate new test scenarios and features

## Prerequisites

- Python 3.9 or higher
- Teracloud Streams 7.2.0+ with:
  - Enhanced REST Management API
  - Data Exchange Service
  - Cross-DC Failover Toolkit
- Network access to both primary and secondary data centers
- Appropriate credentials and permissions

## Installation

```bash
# Clone the repository
git clone https://github.com/organization/teracloud-failover-tester.git
cd teracloud-failover-tester

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure your environment
cp config/config.yaml.example config/config.yaml
# Edit config.yaml with your environment details
```

## Quick Start

```bash
# Run a simple failover test
python main.py --scenario scenarios/network_partition_test.yaml

# Generate a detailed report
python main.py --scenario scenarios/comprehensive_test.yaml --report html
```

## Documentation

For complete documentation, see:
- [User Guide](docs/USAGE.md)
- [API Reference](docs/api_reference.md)
- [Toolkit Integration Guide](docs/TOOLKIT_INTEGRATION.md)
- [Configuration Guide](docs/configuration_guide.md)

## License

[License details will go here]

## Contributing

[Contribution guidelines will go here]