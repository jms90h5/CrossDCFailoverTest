# Teracloud Streams Automated Cross-DC Failover Testing Framework

This repository contains a comprehensive automated testing framework for validating cross-datacenter failover capabilities in Teracloud Streams applications.

## Repository Structure

- `/teracloud_failover_tester` - The main framework implementation
  - `/config` - Configuration management
  - `/data_handler` - Test data generation and validation
  - `/docs` - Documentation and guides
  - `/fault_injection` - Fault simulation components
  - `/monitoring` - Metrics collection
  - `/orchestrator` - Test execution engine
  - `/reporting` - Results reporting
  - `/scenarios` - Sample test scenarios
  - `/streams_client` - API clients for Teracloud Streams
  - `/tests` - Unit and integration tests
  - `/utils` - Common utilities

- `Design_Plan_Condensed.txt` - Summary of the framework design
- `Implementation_Plan_Condensed.txt` - Summary of the implementation plan

## Key Components

- Comprehensive test orchestration
- Fault injection capabilities (network, process, API)
- Cross-DC Failover Toolkit integration
- Metrics collection and validation
- RPO and RTO measurement
- Reporting and analysis

## Getting Started

For detailed usage instructions, please refer to the [Documentation](teracloud_failover_tester/docs/USAGE.md) and the [Toolkit Integration Guide](teracloud_failover_tester/docs/TOOLKIT_INTEGRATION.md).

## Implementation Status

All planned components have been successfully implemented. For a complete overview of the implementation, see the [Final Implementation Report](teracloud_failover_tester/FINAL_IMPLEMENTATION_REPORT.md).

## License

[License information will be added here]