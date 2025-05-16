"""
Data Handler - Manages test data generation, injection, retrieval, and validation.
"""

import json
import logging
import os
import random
import string
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple, Union

from streams_client.data_exchange_client import DataExchangeClient, DataExchangeError


class DataHandlerError(Exception):
    """Base exception for data handler errors."""
    pass


class DataHandler:
    """
    Manages test data for failover tests.
    
    This class handles:
    - Generating test data
    - Injecting data into the primary DC
    - Retrieving processed data from the secondary DC
    - Validating data integrity across failover
    """
    
    def __init__(
        self,
        data_exchange_client: DataExchangeClient,
        config: Dict[str, Any],
        test_data: Dict[str, Any]
    ):
        """
        Initialize the data handler.
        
        Args:
            data_exchange_client: Client for data injection and retrieval
            config: Configuration for the data handler
            test_data: Test data configuration from the test scenario
        """
        self.data_exchange_client = data_exchange_client
        self.config = config
        self.test_data = test_data
        
        # Set up logger
        self.logger = logging.getLogger("data_handler")
        
        # Set up data storage
        self.validation_timeout = config.get("validation_timeout_seconds", 300)
        self.storage_dir = config.get("storage_dir", "data")
        
        # Create storage directory if needed
        if not os.path.exists(self.storage_dir):
            os.makedirs(self.storage_dir, exist_ok=True)
        
        # Initialize data tracking
        self.injected_data = []
        self.retrieved_data = []
        self.test_id = str(uuid.uuid4())[:8]  # Generate a unique ID for this test run
    
    def generate_and_inject_data(self) -> Dict[str, Any]:
        """
        Generate test data and inject it into the primary DC.
        
        Returns:
            Dictionary with data injection results
            
        Raises:
            DataHandlerError: If generation or injection fails
        """
        self.logger.info("Generating and injecting test data")
        
        # Generate the data
        try:
            data = self._generate_data()
            self.injected_data = data
            
            # Save injected data to disk for validation
            self._save_data(data, "injected_data.json")
            
            self.logger.info(f"Generated {len(data)} test data items")
        except Exception as e:
            self.logger.error(f"Data generation failed: {str(e)}", exc_info=True)
            raise DataHandlerError(f"Failed to generate test data: {str(e)}")
        
        # Inject the data
        try:
            # Get injection parameters
            instance_id = self.config.get("instance_id", "")
            job_id = self.config.get("job_id", "")
            port_name = self.test_data.get("input_port", "input")
            data_format = self.test_data.get("data_format", "json")
            
            # Get injection rate if specified
            injection_rate = self.test_data.get("injection_rate_events_per_second")
            batch_size = self.test_data.get("batch_size", 100)
            
            if not instance_id or not job_id:
                raise DataHandlerError("Instance ID and Job ID must be specified for data injection")
            
            # Handle rate-limited injection
            if injection_rate and injection_rate > 0:
                self.logger.info(f"Injecting data at rate of {injection_rate} events/second")
                injection_result = self._rate_limited_injection(
                    instance_id, job_id, port_name, data, data_format,
                    injection_rate, batch_size
                )
            else:
                # Inject all data at once
                self.logger.info(f"Injecting all {len(data)} items in one batch")
                injection_result = self.data_exchange_client.inject_data(
                    instance_id=instance_id,
                    job_id=job_id,
                    port_name=port_name,
                    data=data,
                    dc_type="primary",
                    data_format=data_format
                )
            
            self.logger.info(f"Successfully injected {injection_result.get('count', 0)} data items")
            return injection_result
            
        except Exception as e:
            self.logger.error(f"Data injection failed: {str(e)}", exc_info=True)
            raise DataHandlerError(f"Failed to inject test data: {str(e)}")
    
    def retrieve_processed_data(self) -> List[Dict[str, Any]]:
        """
        Retrieve processed data from the secondary DC after failover.
        
        Returns:
            List of processed data items
            
        Raises:
            DataHandlerError: If data retrieval fails
        """
        self.logger.info("Retrieving processed data from secondary DC")
        
        try:
            # Get retrieval parameters
            instance_id = self.config.get("instance_id", "")
            job_id = self.config.get("job_id", "")
            port_name = self.test_data.get("output_port", "output")
            data_format = self.test_data.get("data_format", "json")
            
            if not instance_id or not job_id:
                raise DataHandlerError("Instance ID and Job ID must be specified for data retrieval")
            
            # Retrieve the data
            data = self.data_exchange_client.retrieve_data(
                instance_id=instance_id,
                job_id=job_id,
                port_name=port_name,
                dc_type="secondary",
                data_format=data_format,
                max_tuples=self.test_data.get("event_count", 10000) * 2,  # Retrieve more than we expect
                timeout_seconds=self.validation_timeout
            )
            
            # Store retrieved data
            self.retrieved_data = data
            
            # Save retrieved data to disk for validation
            self._save_data(data, "retrieved_data.json")
            
            self.logger.info(f"Retrieved {len(data)} processed data items")
            return data
            
        except Exception as e:
            self.logger.error(f"Data retrieval failed: {str(e)}", exc_info=True)
            raise DataHandlerError(f"Failed to retrieve processed data: {str(e)}")
    
    def validate_data(self) -> Dict[str, Any]:
        """
        Validate data integrity across failover.
        
        Returns:
            Dictionary with validation results
            
        Raises:
            DataHandlerError: If validation fails
        """
        self.logger.info("Validating data integrity")
        
        if not self.injected_data:
            self.logger.warning("No injected data to validate against")
            return {
                "success": False,
                "error": "No injected data to validate against",
                "issues": ["No injected data to validate against"]
            }
        
        if not self.retrieved_data:
            self.logger.warning("No retrieved data to validate")
            return {
                "success": False,
                "error": "No retrieved data to validate",
                "issues": ["No retrieved data to validate"]
            }
        
        self.logger.info(f"Validating {len(self.retrieved_data)} against {len(self.injected_data)} injected items")
        
        validation_result = {
            "success": True,
            "injected_count": len(self.injected_data),
            "retrieved_count": len(self.retrieved_data),
            "issues": []
        }
        
        try:
            # Track missing events
            missing_events = []
            duplicate_events = []
            out_of_order_events = []
            
            # Build a set of injected event IDs for quick lookup
            injected_ids = set()
            id_field = self.test_data.get("id_field", "event_id")
            timestamp_field = self.test_data.get("timestamp_field", "timestamp")
            
            # Create mapping of ID to injected data item
            injected_map = {}
            for item in self.injected_data:
                if id_field in item:
                    event_id = item[id_field]
                    injected_ids.add(event_id)
                    injected_map[event_id] = item
            
            # Track retrieved event IDs
            retrieved_ids = set()
            retrieved_ordered_ids = []
            
            # Validate retrieved data
            for item in self.retrieved_data:
                if id_field in item:
                    event_id = item[id_field]
                    retrieved_ordered_ids.append(event_id)
                    
                    if event_id in retrieved_ids:
                        # Duplicate event
                        duplicate_events.append(event_id)
                    else:
                        retrieved_ids.add(event_id)
                    
                    # Check for data transformation errors
                    if event_id in injected_map:
                        injected_item = injected_map[event_id]
                        
                        # Perform additional validation based on expected transformations
                        # This would depend on the specific test scenario and application behavior
                        # Example: Check if a calculated field matches expected value
            
            # Identify missing events
            for event_id in injected_ids:
                if event_id not in retrieved_ids:
                    missing_events.append(event_id)
            
            # Check for order preservation (if timestamps are present)
            if timestamp_field:
                last_timestamp = None
                for event_id in retrieved_ordered_ids:
                    if event_id in injected_map:
                        injected_item = injected_map[event_id]
                        if timestamp_field in injected_item:
                            timestamp = injected_item[timestamp_field]
                            if last_timestamp is not None and timestamp < last_timestamp:
                                out_of_order_events.append(event_id)
                            last_timestamp = timestamp
            
            # Calculate metrics
            missing_count = len(missing_events)
            duplicate_count = len(duplicate_events)
            out_of_order_count = len(out_of_order_events)
            
            # Calculate data loss percentage
            if injected_ids:
                loss_percentage = (missing_count / len(injected_ids)) * 100.0
            else:
                loss_percentage = 0.0
            
            # Compare with expected data loss
            expected_loss_percentage = self.test_data.get("expected_data_loss_percentage", 0.0)
            loss_within_expected = loss_percentage <= expected_loss_percentage
            
            # Update validation result
            validation_result.update({
                "success": loss_within_expected and not out_of_order_events,
                "missing_events": missing_count,
                "duplicate_events": duplicate_count,
                "out_of_order_events": out_of_order_count,
                "loss_percentage": loss_percentage,
                "expected_loss_percentage": expected_loss_percentage,
                "loss_within_expected": loss_within_expected
            })
            
            # Add issues if any
            if missing_count > 0:
                issue = f"{missing_count} events missing ({loss_percentage:.2f}%)"
                validation_result["issues"].append(issue)
                if missing_count <= 10:
                    validation_result["missing_event_ids"] = missing_events
            
            if duplicate_count > 0:
                issue = f"{duplicate_count} duplicate events"
                validation_result["issues"].append(issue)
                if duplicate_count <= 10:
                    validation_result["duplicate_event_ids"] = duplicate_events
            
            if out_of_order_count > 0:
                issue = f"{out_of_order_count} events out of order"
                validation_result["issues"].append(issue)
                if out_of_order_count <= 10:
                    validation_result["out_of_order_event_ids"] = out_of_order_events
            
            # Log result
            if validation_result["success"]:
                self.logger.info("Data validation passed successfully")
            else:
                self.logger.warning(
                    f"Data validation failed: {', '.join(validation_result['issues'])}"
                )
            
            return validation_result
            
        except Exception as e:
            self.logger.error(f"Data validation failed: {str(e)}", exc_info=True)
            validation_result.update({
                "success": False,
                "error": str(e),
                "issues": [f"Validation error: {str(e)}"]
            })
            return validation_result
    
    def _generate_data(self) -> List[Dict[str, Any]]:
        """
        Generate test data based on configuration.
        
        Returns:
            List of generated data items
        """
        generator_type = self.test_data.get("generator_type", "deterministic")
        event_count = self.test_data.get("event_count", 100)
        schema = self.test_data.get("schema", {})
        
        if generator_type == "deterministic":
            return self._generate_deterministic_data(event_count, schema)
        elif generator_type == "file":
            return self._load_data_from_file()
        elif generator_type == "random":
            return self._generate_random_data(event_count, schema)
        else:
            raise DataHandlerError(f"Unsupported generator type: {generator_type}")
    
    def _generate_deterministic_data(self, count: int, schema: Dict[str, str]) -> List[Dict[str, Any]]:
        """
        Generate deterministic test data with predictable values.
        
        Args:
            count: Number of data items to generate
            schema: Schema defining field types
            
        Returns:
            List of generated data items
        """
        data = []
        
        # Ensure we have the required fields
        if not schema:
            # Use default schema
            schema = {
                "event_id": "string",
                "timestamp": "timestamp",
                "value": "number",
                "payload": "string"
            }
        
        # Generate data items
        for i in range(count):
            item = {}
            
            for field_name, field_type in schema.items():
                if field_type == "string":
                    # For event_id, use a format that makes it easy to track
                    if field_name.lower() in ("event_id", "id"):
                        item[field_name] = f"evt-{self.test_id}-{i:08d}"
                    else:
                        # Generate a deterministic string based on index
                        item[field_name] = f"val-{field_name}-{i}"
                
                elif field_type == "number":
                    # Generate a deterministic number based on index
                    item[field_name] = i * 1.5
                
                elif field_type == "integer":
                    # Generate a deterministic integer based on index
                    item[field_name] = i
                
                elif field_type == "boolean":
                    # Alternate boolean values
                    item[field_name] = (i % 2) == 0
                
                elif field_type == "timestamp":
                    # Generate timestamps with consistent interval
                    base_time = datetime.now() - timedelta(minutes=count)
                    timestamp = base_time + timedelta(seconds=i)
                    
                    # Format as ISO 8601
                    item[field_name] = timestamp.isoformat()
                
                elif field_type == "object":
                    # Generate a nested object
                    item[field_name] = {
                        "id": i,
                        "name": f"obj-{i}",
                        "value": i * 2.5
                    }
                
                elif field_type == "array":
                    # Generate an array of values
                    item[field_name] = [f"item-{j}" for j in range(min(5, i+1))]
            
            data.append(item)
        
        return data
    
    def _generate_random_data(self, count: int, schema: Dict[str, str]) -> List[Dict[str, Any]]:
        """
        Generate random test data.
        
        Args:
            count: Number of data items to generate
            schema: Schema defining field types
            
        Returns:
            List of generated data items
        """
        data = []
        
        # Ensure we have the required fields
        if not schema:
            # Use default schema
            schema = {
                "event_id": "string",
                "timestamp": "timestamp",
                "value": "number",
                "payload": "string"
            }
        
        # Generate data items
        for i in range(count):
            item = {}
            
            for field_name, field_type in schema.items():
                if field_type == "string":
                    # For event_id, use a format that makes it easy to track
                    if field_name.lower() in ("event_id", "id"):
                        item[field_name] = f"evt-{self.test_id}-{i:08d}"
                    else:
                        # Generate a random string
                        length = random.randint(5, 20)
                        item[field_name] = ''.join(random.choices(
                            string.ascii_letters + string.digits, k=length
                        ))
                
                elif field_type == "number":
                    # Generate a random number
                    item[field_name] = random.uniform(0, 1000)
                
                elif field_type == "integer":
                    # Generate a random integer
                    item[field_name] = random.randint(0, 1000)
                
                elif field_type == "boolean":
                    # Generate a random boolean
                    item[field_name] = random.choice([True, False])
                
                elif field_type == "timestamp":
                    # Generate a random timestamp within reasonable range
                    start_time = datetime.now() - timedelta(days=7)
                    end_time = datetime.now()
                    random_seconds = random.randint(0, int((end_time - start_time).total_seconds()))
                    timestamp = start_time + timedelta(seconds=random_seconds)
                    
                    # Format as ISO 8601
                    item[field_name] = timestamp.isoformat()
                
                elif field_type == "object":
                    # Generate a nested object
                    item[field_name] = {
                        "id": random.randint(0, 1000),
                        "name": ''.join(random.choices(string.ascii_letters, k=8)),
                        "value": random.uniform(0, 100)
                    }
                
                elif field_type == "array":
                    # Generate an array of values
                    length = random.randint(0, 5)
                    item[field_name] = [
                        ''.join(random.choices(string.ascii_letters, k=5))
                        for _ in range(length)
                    ]
            
            data.append(item)
        
        return data
    
    def _load_data_from_file(self) -> List[Dict[str, Any]]:
        """
        Load test data from a file.
        
        Returns:
            List of data items from the file
            
        Raises:
            DataHandlerError: If file loading fails
        """
        input_file = self.test_data.get("input_file")
        
        if not input_file:
            raise DataHandlerError("Input file not specified for file generator")
        
        try:
            # Resolve file path (relative to storage directory)
            if not os.path.isabs(input_file):
                input_file = os.path.join(self.storage_dir, input_file)
            
            # Check if file exists
            if not os.path.exists(input_file):
                raise DataHandlerError(f"Input file not found: {input_file}")
            
            # Load data based on file extension
            extension = os.path.splitext(input_file)[1].lower()
            
            if extension == ".json":
                with open(input_file, 'r') as f:
                    data = json.load(f)
                
                # Handle both array and object formats
                if isinstance(data, dict):
                    if "tuples" in data:
                        return data["tuples"]
                    else:
                        return [data]
                elif isinstance(data, list):
                    return data
                else:
                    raise DataHandlerError(f"Unsupported JSON format in {input_file}")
                
            elif extension == ".csv":
                # Use Python's csv module for CSV handling
                import csv
                
                data = []
                with open(input_file, 'r', newline='') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        data.append(dict(row))
                
                return data
                
            else:
                raise DataHandlerError(f"Unsupported file format: {extension}")
                
        except Exception as e:
            if isinstance(e, DataHandlerError):
                raise
            else:
                raise DataHandlerError(f"Failed to load data from file: {str(e)}")
    
    def _rate_limited_injection(
        self, 
        instance_id: str, 
        job_id: str, 
        port_name: str, 
        data: List[Dict[str, Any]],
        data_format: str,
        rate: float,
        batch_size: int
    ) -> Dict[str, Any]:
        """
        Inject data at a controlled rate.
        
        Args:
            instance_id: Streams instance ID
            job_id: Streams job ID
            port_name: Input port name
            data: Data to inject
            data_format: Data format (json or csv)
            rate: Injection rate in events per second
            batch_size: Number of events per batch
            
        Returns:
            Dictionary with injection results
        """
        if not data:
            return {"success": True, "count": 0}
        
        self.logger.info(f"Rate-limited injection: {rate} events/sec, batch size: {batch_size}")
        
        # Calculate batch interval to achieve target rate
        interval = batch_size / rate
        
        total_injected = 0
        start_time = time.time()
        
        # Process data in batches
        for i in range(0, len(data), batch_size):
            batch_start = time.time()
            
            # Get batch of data
            batch = data[i:i+batch_size]
            
            # Inject the batch
            result = self.data_exchange_client.inject_data(
                instance_id=instance_id,
                job_id=job_id,
                port_name=port_name,
                data=batch,
                dc_type="primary",
                data_format=data_format
            )
            
            # Update count
            if "count" in result:
                total_injected += result["count"]
            else:
                total_injected += len(batch)
            
            # Calculate elapsed time and sleep if needed
            elapsed = time.time() - batch_start
            sleep_time = max(0, interval - elapsed)
            
            if sleep_time > 0:
                time.sleep(sleep_time)
            
            # Log progress
            if (i // batch_size) % 10 == 0:
                self.logger.debug(f"Injected {total_injected} events so far")
        
        total_time = time.time() - start_time
        actual_rate = total_injected / total_time if total_time > 0 else 0
        
        self.logger.info(
            f"Injection complete: {total_injected} events in {total_time:.2f} seconds "
            f"(rate: {actual_rate:.2f} events/sec)"
        )
        
        return {
            "success": True,
            "count": total_injected,
            "duration_seconds": total_time,
            "actual_rate": actual_rate
        }
    
    def _save_data(self, data: List[Dict[str, Any]], filename: str) -> None:
        """
        Save data to a file for later analysis.
        
        Args:
            data: Data to save
            filename: Name of the file
        """
        try:
            # Create a timestamped filename
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            file_path = os.path.join(self.storage_dir, f"{timestamp}_{filename}")
            
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            self.logger.debug(f"Saved data to {file_path}")
            
        except Exception as e:
            self.logger.warning(f"Failed to save data to file: {str(e)}")
            # This is non-critical, so just log and continue