"""
JSON schemas for validating configuration and test scenario files.
"""

# Schema for the global configuration file
CONFIG_SCHEMA = {
    "type": "object",
    "required": ["datacenters"],
    "properties": {
        "datacenters": {
            "type": "object",
            "required": ["primary", "secondary"],
            "properties": {
                "primary": {
                    "type": "object",
                    "required": ["api_url", "auth_token"],
                    "properties": {
                        "api_url": {"type": "string", "format": "uri"},
                        "auth_token": {"type": "string"},
                        "verify_ssl": {"type": "boolean"},
                        "domain_id": {"type": "string"},
                        "instance_id": {"type": "string"}
                    }
                },
                "secondary": {
                    "type": "object",
                    "required": ["api_url", "auth_token"],
                    "properties": {
                        "api_url": {"type": "string", "format": "uri"},
                        "auth_token": {"type": "string"},
                        "verify_ssl": {"type": "boolean"},
                        "domain_id": {"type": "string"},
                        "instance_id": {"type": "string"}
                    }
                }
            }
        },
        "credentials": {
            "type": "object",
            "additionalProperties": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "number"},
                    {"type": "boolean"}
                ]
            }
        },
        "fault_injection": {
            "type": "object",
            "properties": {
                "ssh": {
                    "type": "object",
                    "properties": {
                        "username": {"type": "string"},
                        "private_key_path": {"type": "string"},
                        "password": {"type": "string"},
                        "connection_timeout": {"type": "number"},
                        "hosts": {
                            "type": "object",
                            "additionalProperties": {
                                "type": "object",
                                "required": ["hostname"],
                                "properties": {
                                    "hostname": {"type": "string"},
                                    "port": {"type": "integer"},
                                    "username": {"type": "string"},
                                    "password": {"type": "string"},
                                    "private_key_path": {"type": "string"}
                                }
                            }
                        }
                    }
                },
                "network": {
                    "type": "object",
                    "properties": {
                        "tc_available": {"type": "boolean"},
                        "iptables_available": {"type": "boolean"},
                        "interfaces": {
                            "type": "object",
                            "additionalProperties": {"type": "string"}
                        },
                        "primary_network": {"type": "string"},
                        "secondary_network": {"type": "string"}
                    }
                }
            }
        },
        "monitoring": {
            "type": "object",
            "properties": {
                "metrics_collection_interval_seconds": {"type": "number"},
                "prometheus": {
                    "type": "object",
                    "properties": {
                        "primary_url": {"type": "string", "format": "uri"},
                        "secondary_url": {"type": "string", "format": "uri"},
                        "username": {"type": "string"},
                        "password": {"type": "string"},
                        "verify_ssl": {"type": "boolean"}
                    }
                },
                "jmx": {
                    "type": "object",
                    "properties": {
                        "enabled": {"type": "boolean"},
                        "primary_host": {"type": "string"},
                        "primary_port": {"type": "integer"},
                        "secondary_host": {"type": "string"},
                        "secondary_port": {"type": "integer"}
                    }
                }
            }
        },
        "data_exchange": {
            "type": "object",
            "properties": {
                "endpoint_timeout_seconds": {"type": "number"},
                "max_batch_size": {"type": "integer"},
                "default_format": {"type": "string", "enum": ["json", "csv"]}
            }
        },
        "data_handler": {
            "type": "object",
            "properties": {
                "validation_timeout_seconds": {"type": "number"},
                "storage_dir": {"type": "string"}
            }
        },
        "logging": {
            "type": "object",
            "properties": {
                "console_level": {"type": "string", "enum": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]},
                "file_level": {"type": "string", "enum": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]},
                "log_format": {"type": "string"},
                "json_logs": {"type": "boolean"}
            }
        }
    }
}

# Schema for test scenario files
SCENARIO_SCHEMA = {
    "type": "object",
    "required": ["test_id", "description", "streams_application_sab", "fault_scenario"],
    "properties": {
        "test_id": {"type": "string"},
        "description": {"type": "string"},
        "streams_application_sab": {"type": "string"},
        "submission_params": {
            "type": "object",
            "additionalProperties": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "number"},
                    {"type": "boolean"}
                ]
            }
        },
        "pre_failover_data": {
            "type": "object",
            "properties": {
                "generator_type": {"type": "string", "enum": ["deterministic", "file", "random"]},
                "event_count": {"type": "integer"},
                "data_size_bytes": {"type": "integer"},
                "input_file": {"type": "string"},
                "data_format": {"type": "string", "enum": ["json", "csv"]},
                "schema": {
                    "type": "object",
                    "additionalProperties": {"type": "string"}
                },
                "injection_rate_events_per_second": {"type": "number"},
                "batch_size": {"type": "integer"}
            }
        },
        "fault_scenario": {
            "type": "object",
            "required": ["type"],
            "properties": {
                "type": {"type": "string", "enum": ["network_partition", "network_latency", "network_packet_loss", "process_kill", "api_initiated"]},
                "target": {"type": "string"},
                "duration_seconds": {"type": "number"},
                "latency_ms": {"type": "number"},
                "packet_loss_percentage": {"type": "number"},
                "bandwidth_limit_kbps": {"type": "number"},
                "process_name": {"type": "string"},
                "process_pattern": {"type": "string"},
                "api_operation": {"type": "string"}
            }
        },
        "failover_trigger_method": {
            "type": "string", 
            "enum": ["automatic", "api_initiated", "manual"]
        },
        "post_failover_validation_checks": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["type"],
                "properties": {
                    "type": {"type": "string", "enum": ["data_integrity", "performance", "availability"]},
                    "description": {"type": "string"},
                    "threshold": {"type": "number"},
                    "metric": {"type": "string"}
                }
            }
        },
        "expected_recovery_time_seconds": {"type": "number"},
        "expected_data_loss_percentage": {"type": "number"},
        "expected_metrics": {
            "type": "object",
            "additionalProperties": {
                "type": "object",
                "properties": {
                    "min": {"type": "number"},
                    "max": {"type": "number"},
                    "equals": {"type": "number"},
                    "description": {"type": "string"}
                }
            }
        }
    }
}