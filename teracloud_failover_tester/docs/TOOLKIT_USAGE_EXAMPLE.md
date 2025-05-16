# Cross-DC Failover Toolkit Usage Example

This guide provides a step-by-step example of using the Automated Cross-DC Failover Testing Framework with the Cross-DC Failover Toolkit integration.

## Prerequisites

- Teracloud Streams 7.2.0+ with Cross-DC Failover Toolkit installed
- Access to both primary and secondary data centers
- A Streams Application that uses the `com.teracloud.streams.crossdcfailover` toolkit
- The Automated Cross-DC Failover Testing Framework installed and configured

## Step 1: Configure the Framework

Create a configuration file (`config.yaml`) with your data center details and toolkit settings:

```yaml
datacenters:
  primary:
    api_url: "https://primary-dc-api.example.com"
    auth_token: "YOUR_PRIMARY_DC_TOKEN"
    instance_id: "streams-instance-1"
    verify_ssl: true
  
  secondary:
    api_url: "https://secondary-dc-api.example.com"
    auth_token: "YOUR_SECONDARY_DC_TOKEN"
    instance_id: "streams-instance-2"
    verify_ssl: true

crossdc_toolkit:
  status_check_interval_seconds: 5
  local_dc_name: "dc1"
  remote_dc_name: "dc2"
  operation_mode: 1  # 1 = active, 0 = passive

monitoring:
  metrics_collection_interval_seconds: 5
  prometheus:
    primary_url: "https://prometheus-primary.example.com"
    secondary_url: "https://prometheus-secondary.example.com"
    username: "prometheus_user"
    password: "prometheus_password"
    verify_ssl: true
    
fault_injection:
  ssh:
    username: "admin"
    key_file: "/path/to/private_key"
  network:
    sudo_required: true
  
reporting:
  output_dir: "./test_results"
  formats: ["html", "json", "junit"]
```

## Step 2: Create a Test Scenario

Create a test scenario file (`toolkit_failover_test.yaml`) with the following content:

```yaml
test_id: "network_partition_toolkit_test"
description: "Test failover during network partition using Cross-DC Toolkit"

# Application details
streams_application_sab: "/path/to/my_failover_app.sab"
submission_params:
  instance_id: "streams-instance-1"
  job_name: "failover-test-job"
  # Toolkit-specific parameters
  crossdc.mode: "active"
  crossdc.primary.dc: "dc1"
  crossdc.secondary.dc: "dc2"
  crossdc.replication.enabled: "true"
  crossdc.autostart.secondary: "true"

# Test data configuration
pre_failover_data:
  generator_type: "deterministic"
  event_count: 5000
  injection_rate_events_per_second: 100
  input_port: "IngestPort"
  output_port: "OutputPort"
  schema:
    event_id: "string"
    timestamp: "timestamp"
    value: "number"
    payload: "string"

# Fault scenario
fault_scenario:
  type: "network_partition"
  target: "primary_dc"
  duration_seconds: 60
  options:
    host_name: "primary-host.example.com"

# Test validation criteria
expected_recovery_time_seconds: 60  # RTO target
expected_data_loss_percentage: 0.5  # RPO target
```

## Step 3: Run the Test

Execute the test using the framework's main script:

```bash
python main.py --config config.yaml --scenario toolkit_failover_test.yaml --verbose
```

## Step 4: Review the Test Execution

The framework will:

1. Deploy the application to both data centers
2. Configure the Cross-DC Failover Toolkit settings
3. Generate and inject test data
4. Monitor the application and collect baseline metrics
5. Inject a network partition fault
6. Monitor failover progress using the toolkit client
7. Validate that the secondary DC takes over successfully
8. Calculate RPO (data loss) and RTO (recovery time)
9. Generate detailed reports

## Step 5: Analyze the Results

After the test completes, examine the results in the `test_results` directory:

### HTML Report

The HTML report provides a visual overview of the test, including:
- Test summary and status
- Failover timeline with key events
- Data loss analysis (RPO)
- Recovery time analysis (RTO)
- Toolkit status throughout the test

### JSON Report

The JSON report contains detailed metrics that can be processed programmatically:

```json
{
  "test_id": "network_partition_toolkit_test",
  "status": "passed",
  "start_time": "2023-10-26T15:30:00.123Z",
  "end_time": "2023-10-26T15:32:45.678Z",
  "failover": {
    "detected": true,
    "start_time": "2023-10-26T15:30:30.123Z",
    "completion_time": "2023-10-26T15:31:15.456Z",
    "recovery_time_seconds": 45.333,
    "expected_recovery_time_seconds": 60,
    "rto_satisfied": true
  },
  "data_validation": {
    "injected_count": 5000,
    "retrieved_count": 4975,
    "missing_events": 25,
    "loss_percentage": 0.5,
    "expected_loss_percentage": 0.5,
    "rpo_satisfied": true
  },
  "toolkit_status": {
    "primary_dc_status": "down",
    "secondary_dc_status": "up",
    "failover_detected": true
  }
}
```

## Step 6: Customize and Extend

This example can be extended in several ways:

### Test Different Fault Scenarios

Modify the `fault_scenario` section to test different failures:

```yaml
fault_scenario:
  type: "process_fault"  # API, network, or process fault
  target: "primary_job"  # Target specific components
  action: "terminate"    # Stop, terminate, pause, etc.
```

### Modify Toolkit Configuration

Test different Cross-DC Failover Toolkit settings:

```yaml
submission_params:
  # ... other parameters ...
  crossdc.mode: "passive"  # Test passive mode
  crossdc.replication.type: "synchronous"  # Test synchronous replication
  crossdc.failback.automatic: "false"  # Disable automatic failback
```

### Add Custom Validation Checks

Add custom validation criteria for the toolkit:

```yaml
expected_metrics:
  "toolkit_status.primary_dc.instance_status":
    equals: "down"
  "toolkit_status.secondary_dc.job_health":
    equals: "healthy"
  "toolkit_metrics.replication_lag_seconds":
    max: 5.0
```

## Conclusion

The Cross-DC Failover Toolkit integration provides a comprehensive way to test and validate the failover behavior of Teracloud Streams applications. By simulating realistic failure scenarios and monitoring the toolkit's response, you can ensure your applications will meet their resilience requirements in production environments.