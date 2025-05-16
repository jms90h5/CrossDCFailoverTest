# Cross-DC Failover Toolkit Integration

This document provides a detailed overview of the integration between the Automated Cross-DC Failover Testing Framework and the Teracloud Streams Cross-DC Failover Toolkit.

## Overview

The Cross-DC Failover Toolkit (`com.teracloud.streams.crossdcfailover`) is a component in Teracloud Streams 7.2.0+ that enables application-level failover between data centers. It provides mechanisms for applications to maintain state across data centers and coordinate failover processes. Our framework integrates with this toolkit to accurately detect and validate failover events.

## Integration Design

Since the Cross-DC Failover Toolkit does not expose a direct REST API for management, our integration approach uses several indirect methods:

1. **Status Monitoring**: We monitor the application's status via the standard Streams REST Management API to infer toolkit state
2. **Metrics Collection**: We collect toolkit-specific metrics through Streams metrics endpoints
3. **Log Analysis**: We analyze application logs for indicators of toolkit status
4. **Application Behavior**: We observe the behavior of the application components across data centers

## Key Components

### 1. CrossDCToolkitClient

The primary integration component is the `CrossDCToolkitClient` class, which provides these key capabilities:

- **Failover Status Monitoring**: Tracks the status of primary and secondary data centers and detects failover events
- **Service Availability Checking**: Verifies if the service is accessible in each data center
- **Toolkit Metrics Collection**: Gathers performance and health metrics from the toolkit
- **Resilience Features**: Implements fallback mechanisms when direct toolkit interaction isn't possible

Location: `streams_client/crossdc_toolkit_client.py`

### 2. Test Orchestrator Integration

The Test Orchestrator has been enhanced to leverage the CrossDCToolkitClient:

- **Failover Monitoring Phase**: Uses the toolkit client for more accurate failover detection
- **Post-Failover Phase**: Verifies service availability using toolkit status
- **Validation Phase**: Adds toolkit-specific validation to ensure proper functionality
- **Metrics Integration**: Incorporates toolkit metrics into the overall test results

Location: `orchestrator/test_orchestrator.py`

## Implementation Details

### Failover Detection Strategy

The framework detects failover events through these mechanisms:

1. **Primary DC Status**: Monitors the status of the instance and job in the primary data center
2. **Secondary DC Status**: Monitors the status of the instance and job in the secondary data center
3. **State Transition**: Detects when the primary is down and the secondary becomes active
4. **Timing Measurement**: Records timestamps for RTO (Recovery Time Objective) calculation

### Fallback Mechanisms

In environments where the toolkit integration is limited or unavailable, the framework falls back to:

1. **Metrics-Based Detection**: Uses application metrics to infer failover state
2. **API-Based Verification**: Directly checks application status through the REST Management API
3. **Data Flow Monitoring**: Verifies the flow of test data to confirm failover completion

## Configuration

The toolkit integration is configured through the `crossdc_toolkit` section in the configuration file:

```yaml
crossdc_toolkit:
  instance_id: "streams-instance-1"
  job_id: "job-123"
  status_check_interval_seconds: 10
  local_dc_name: "dc1"
  remote_dc_name: "dc2"
  operation_mode: 1  # 1 = active, 0 = passive
```

## Usage Example

Here's an example of how to use the toolkit integration in a test scenario:

```yaml
test_id: "network_partition_failover"
description: "Test failover during network partition between DCs"
streams_application_sab: "/path/to/application.sab"
submission_params:
  instance_id: "streams-instance-1"
  job_name: "failover-test"
  toolkit_mode: "active"
  
pre_failover_data:
  generator_type: "deterministic"
  event_count: 1000
  
fault_scenario:
  type: "network_partition"
  target: "primary_dc"
  
failover_trigger_method: "toolkit_auto"

expected_recovery_time_seconds: 60
expected_data_loss_percentage: 0.1
```

## Validation Criteria

The toolkit integration adds these validation checks to test completion:

1. **Failover Detection**: Verifies that the toolkit properly detected the failover event
2. **Secondary DC Activation**: Confirms the secondary data center is running and healthy
3. **Primary DC Status**: Checks if the primary has recovered or remains down
4. **Recovery Time**: Validates the failover completed within expected time thresholds

## Limitations and Future Enhancements

### Current Limitations

- Limited direct access to toolkit internal state
- Requires inference of toolkit status through indirect means
- No programmatic way to trigger failover through the toolkit directly

### Planned Enhancements

- Additional toolkit metrics collection when available
- Enhanced log analysis for toolkit status determination
- More sophisticated failover validation
- Support for toolkit configuration updates via REST API (when available)

## Conclusion

The integration with the Cross-DC Failover Toolkit enhances the framework's ability to accurately detect, monitor, and validate failover events in Teracloud Streams applications. It provides a robust foundation for comprehensive failover testing while accounting for the architectural constraints of the toolkit's design.