# Cross-DC Failover Toolkit Integration Guide

## Overview

This guide provides details on how to properly integrate with the Teracloud Streams Cross-DC Failover Toolkit (com.teracloud.streams.crossdcfailover) when creating cross-datacenter failover tests using the Automated Testing Framework.

## Toolkit Functionality

The Cross-DC Failover Toolkit provides application-level failover capabilities for Teracloud Streams applications. It enables:

1. **Automatic Failure Detection**: The toolkit monitors the health of the primary datacenter and detects failures through missed heartbeats, failed connections, and other indicators.

2. **Automatic Failover Initiation**: Upon detecting a failure condition, the toolkit automatically activates processing in the secondary datacenter without requiring programmatic intervention.

3. **State Management**: The toolkit handles replication of necessary state between datacenters to minimize data loss during failover events.

4. **Monitoring and Observability**: Failover status and related metrics are available through application logs and metrics.

## Integration Approach

The testing framework integrates with the toolkit through:

1. **Configuration via SAB Parameters**: The toolkit is configured through submission parameters when deploying the Streams Application Bundle (SAB).

2. **SPL Composite Operators**: The toolkit provides operators that are included in the SPL application code to enable failover.

3. **Observation-Based Monitoring**: The framework monitors the toolkit through logs and metrics, without directly controlling it.

## Integration Points

### 1. Application Configuration

When configuring a test scenario, include the necessary toolkit parameters in the `submission_params` section:

```yaml
submission_params:
  jobName: "CrossDCFailoverTest"
  crossDCFailoverEnabled: "true"
  primaryDataCenter: "dc1"
  secondaryDataCenter: "dc2"
  heartbeatIntervalSeconds: "5"
  failoverTimeoutSeconds: "30"
```

### 2. SPL Application Requirements

The SPL application being tested must:

- Import the toolkit: `use com.teracloud.streams.crossdcfailover::*;`
- Include appropriate composite operators, typically:
  - `CrossDCFailover` - Main operator for enabling cross-DC capabilities
  - `RemoteDataCenterMonitor` - Monitors the health of remote data centers
  - `StateHandler` - Manages state synchronization between datacenters

### 3. Monitoring Failover

The framework monitors the toolkit's behavior through:

- The `RemoteDataCenterStatus` stream exposed by the toolkit
- Application logs containing keywords like "failover", "data center", "heartbeat"
- Metrics emitted by toolkit operators

### 4. Testing Best Practices

1. **Use Automatic Failover Mode**: Always specify `failover_condition: "automatic"` in test scenarios, as this aligns with how the toolkit operates.

2. **Test Multiple Failure Types**: Configure various fault scenarios (network partition, API-driven stops, process failures) to validate the toolkit's detection capabilities.

3. **Set Realistic Expectations**: Configure appropriate RTO/RPO expectations based on the toolkit's capabilities and network characteristics.

4. **Monitor Toolkit Status**: Use the `CrossDCToolkitClient` to monitor the toolkit's status during tests.

## Code Examples

### Monitoring Toolkit Status

```python
# Initialize the toolkit client
toolkit_client = CrossDCToolkitClient(
    primary_api_client=primary_api,
    secondary_api_client=secondary_api,
    config={
        "instance_id": "streams-instance-1",
        "job_id": "job-123",
        "status_check_interval_seconds": 5,
        "status_stream_name": "RemoteDataCenterStatus",
        "log_search_keywords": ["failover", "heartbeat", "data center"]
    }
)

# Get current status
status = toolkit_client.get_failover_status()

# Monitor for failover
result = toolkit_client.monitor_failover_status(timeout_seconds=120)
```

### Defining a Test Scenario

```yaml
test_id: "network_partition_001"
description: "Test cross-DC failover when network partition occurs"

# Streams application bundle to test
streams_application_sab: "applications/crossdc_sample_app.sab"

# Toolkit configuration parameters
submission_params:
  jobName: "CrossDCFailoverTest"
  crossDCFailoverEnabled: "true"
  primaryDataCenter: "dc1"
  secondaryDataCenter: "dc2"
  heartbeatIntervalSeconds: "5"
  failoverTimeoutSeconds: "30"

# Fault scenario configuration
fault_scenario:
  type: "network_partition"
  host: "primary-host"
  target_network: "10.0.2.0/24"  # Secondary DC network
  duration_seconds: 300

# Expected failover behavior
failover_condition: "automatic"

# Recovery expectations
expected_recovery_time_seconds: 60
expected_data_loss_percentage: 1.0
```

## Important Notes

1. **No Direct Control**: The toolkit does not provide a REST API for directly triggering failover - it operates automatically based on its detection mechanisms.

2. **Focus on Monitoring**: Your integration should focus on monitoring the toolkit's behavior rather than attempting to control it.

3. **Toolkit Configuration**: All toolkit configuration happens at SAB submission time - you cannot change its behavior during runtime.

4. **Event-Based**: The toolkit operates based on events (heartbeat failures, network issues) rather than direct commands.

## Troubleshooting

Common issues and solutions:

1. **No Failover Detected**: Ensure that the fault injection is actually causing a communication disruption between datacenters that the toolkit can detect.

2. **Slow Failover**: Check and adjust the `heartbeatIntervalSeconds` and `failoverTimeoutSeconds` parameters to optimize detection time.

3. **Missing Status Information**: Ensure the SPL application properly includes the required toolkit operators and exposes status streams.

4. **Excessive Data Loss**: Review state synchronization configuration in the toolkit to improve RPO metrics.

## Additional Resources

- Teracloud Streams Documentation: [Cross-DC Failover Toolkit](https://doc.streams.teracloud.com/)
- Toolkit API Reference: [com.teracloud.streams.crossdcfailover](https://doc.streams.teracloud.com/operators/crossdcfailover)
- Sample Applications: See `examples/` directory for sample applications that use the toolkit