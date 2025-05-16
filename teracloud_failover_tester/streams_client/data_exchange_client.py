"""
Client for interacting with the Teracloud Streams Data Exchange Service.

Based on documentation at:
https://doc.streams.teracloud.com/com.ibm.streams.dev.doc/doc/enabling-streams-data-exchange.html
"""

import logging
import json
import time
from typing import Dict, List, Any, Optional, Union, Iterable
import csv
from io import StringIO

from streams_client.api_client import StreamsApiClient, APIError


class DataExchangeError(Exception):
    """Base exception for Data Exchange errors."""
    pass


class DataExchangeClient:
    """
    Client for interacting with the Teracloud Streams Data Exchange Service.
    
    This client provides methods for injecting data into and retrieving data
    from Teracloud Streams applications using the Data Exchange REST APIs.
    """
    
    def __init__(
        self,
        primary_api_client: StreamsApiClient,
        secondary_api_client: StreamsApiClient,
        config: Dict[str, Any]
    ):
        """
        Initialize the Data Exchange client.
        
        Args:
            primary_api_client: API client for the primary data center
            secondary_api_client: API client for the secondary data center
            config: Configuration dictionary for the Data Exchange client
        """
        self.primary_api_client = primary_api_client
        self.secondary_api_client = secondary_api_client
        self.config = config
        
        # Set default configuration values
        self.endpoint_timeout = config.get("endpoint_timeout_seconds", 60)
        self.max_batch_size = config.get("max_batch_size", 1000)
        self.default_format = config.get("default_format", "json")
        
        self.logger = logging.getLogger("data_exchange")
    
    def inject_data(
        self,
        instance_id: str,
        job_id: str,
        port_name: str,
        data: Union[List[Dict[str, Any]], List[List[Any]], Dict[str, Any]],
        dc_type: str = "primary",
        data_format: Optional[str] = None,
        wait_for_completion: bool = True
    ) -> Dict[str, Any]:
        """
        Inject data into a Streams application using the Data Exchange service.
        
        Args:
            instance_id: ID of the Streams instance
            job_id: ID of the job
            port_name: Name of the input port to inject data into
            data: Data to inject (list of dictionaries for JSON, list of lists for CSV, or single dict)
            dc_type: Data center type ("primary" or "secondary")
            data_format: Format of the data ("json" or "csv"), defaults to self.default_format
            wait_for_completion: Whether to wait for the operation to complete
            
        Returns:
            Dictionary containing the response from the Data Exchange service
            
        Raises:
            DataExchangeError: If data injection fails
        """
        data_format = data_format or self.default_format
        api_client = self._get_api_client(dc_type)
        
        # Select the appropriate endpoint
        endpoint = f"instances/{instance_id}/jobs/{job_id}/ports/input/{port_name}"
        
        # Convert single dictionary to list if needed
        if isinstance(data, dict):
            data = [data]
        
        # Handle empty data
        if not data:
            self.logger.warning("No data to inject")
            return {"success": True, "count": 0}
        
        # Format data appropriately
        payload = self._format_data_for_injection(data, data_format)
        
        try:
            headers = {"Content-Type": f"application/{"json" if data_format == "json" else "csv"}"}
            
            # Use batch processing for large datasets
            if len(data) > self.max_batch_size:
                return self._batch_inject_data(
                    api_client=api_client,
                    endpoint=endpoint,
                    data=data,
                    data_format=data_format,
                    headers=headers,
                    wait_for_completion=wait_for_completion
                )
            
            # Make the request
            response = api_client._make_request(
                method="POST",
                endpoint=endpoint,
                data=payload,
                timeout=self.endpoint_timeout,
                expected_status_codes=[200, 201, 202]
            )
            
            # Wait for completion if needed
            if wait_for_completion and "id" in response:
                operation_id = response["id"]
                self._wait_for_operation(api_client, instance_id, job_id, operation_id)
            
            return response
            
        except APIError as e:
            self.logger.error(f"Failed to inject data: {str(e)}")
            raise DataExchangeError(f"Data injection failed: {str(e)}")
    
    def retrieve_data(
        self,
        instance_id: str,
        job_id: str,
        port_name: str,
        dc_type: str = "secondary",
        data_format: Optional[str] = None,
        max_tuples: int = 1000,
        timeout_seconds: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve data from a Streams application using the Data Exchange service.
        
        Args:
            instance_id: ID of the Streams instance
            job_id: ID of the job
            port_name: Name of the output port to retrieve data from
            dc_type: Data center type ("primary" or "secondary")
            data_format: Format of the data ("json" or "csv"), defaults to self.default_format
            max_tuples: Maximum number of tuples to retrieve
            timeout_seconds: Timeout for the operation, defaults to self.endpoint_timeout
            
        Returns:
            List of retrieved data items
            
        Raises:
            DataExchangeError: If data retrieval fails
        """
        data_format = data_format or self.default_format
        api_client = self._get_api_client(dc_type)
        timeout = timeout_seconds or self.endpoint_timeout
        
        # Select the appropriate endpoint
        endpoint = f"instances/{instance_id}/jobs/{job_id}/ports/output/{port_name}"
        
        # Prepare query parameters
        params = {
            "maxTuples": max_tuples,
            "format": data_format
        }
        
        try:
            # Make the request
            response = api_client._make_request(
                method="GET",
                endpoint=endpoint,
                params=params,
                timeout=timeout,
                expected_status_codes=[200]
            )
            
            # Parse the response based on format
            if data_format == "json":
                if "tuples" in response:
                    return response["tuples"]
                return []
            elif data_format == "csv":
                if "raw_response" in response:
                    return self._parse_csv_response(response["raw_response"])
                return []
            else:
                self.logger.warning(f"Unsupported data format: {data_format}")
                return []
            
        except APIError as e:
            self.logger.error(f"Failed to retrieve data: {str(e)}")
            raise DataExchangeError(f"Data retrieval failed: {str(e)}")
    
    def _get_api_client(self, dc_type: str) -> StreamsApiClient:
        """
        Get the appropriate API client based on data center type.
        
        Args:
            dc_type: Data center type ("primary" or "secondary")
            
        Returns:
            The appropriate API client
            
        Raises:
            ValueError: If dc_type is invalid
        """
        if dc_type.lower() == "primary":
            return self.primary_api_client
        elif dc_type.lower() == "secondary":
            return self.secondary_api_client
        else:
            raise ValueError(f"Invalid DC type: {dc_type}. Must be 'primary' or 'secondary'.")
    
    def _format_data_for_injection(
        self, 
        data: Union[List[Dict[str, Any]], List[List[Any]]],
        data_format: str
    ) -> Dict[str, Any]:
        """
        Format data for injection into the Data Exchange service.
        
        Args:
            data: Data to format
            data_format: Format of the data ("json" or "csv")
            
        Returns:
            Formatted data ready for injection
            
        Raises:
            ValueError: If data_format is invalid
        """
        if data_format == "json":
            return {"tuples": data}
        elif data_format == "csv":
            # Convert data to CSV string
            if not data:
                return ""
            
            output = StringIO()
            
            # If the data is a list of dictionaries, extract the keys for the header
            if isinstance(data[0], dict):
                fieldnames = list(data[0].keys())
                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(data)
            else:
                # Assume it's a list of lists
                writer = csv.writer(output)
                writer.writerows(data)
            
            return output.getvalue()
        else:
            raise ValueError(f"Unsupported data format: {data_format}")
    
    def _parse_csv_response(self, csv_data: str) -> List[Dict[str, Any]]:
        """
        Parse CSV response data into a list of dictionaries.
        
        Args:
            csv_data: CSV data string
            
        Returns:
            List of dictionaries representing the CSV data
        """
        result = []
        reader = csv.reader(StringIO(csv_data))
        
        # Get the header row
        try:
            header = next(reader)
        except StopIteration:
            # Empty CSV
            return result
        
        # Process data rows
        for row in reader:
            # Create a dictionary with header keys and row values
            item = {}
            for i, value in enumerate(row):
                if i < len(header):
                    # Try to convert numeric values
                    try:
                        # Try as int first
                        item[header[i]] = int(value)
                    except ValueError:
                        try:
                            # Then try as float
                            item[header[i]] = float(value)
                        except ValueError:
                            # Keep as string
                            item[header[i]] = value
                else:
                    # More values than headers
                    self.logger.warning(f"CSV row has more columns than header: {row}")
            
            result.append(item)
        
        return result
    
    def _batch_inject_data(
        self,
        api_client: StreamsApiClient,
        endpoint: str,
        data: Union[List[Dict[str, Any]], List[List[Any]]],
        data_format: str,
        headers: Dict[str, str],
        wait_for_completion: bool
    ) -> Dict[str, Any]:
        """
        Inject large datasets in batches.
        
        Args:
            api_client: API client to use
            endpoint: Endpoint to send data to
            data: Data to inject
            data_format: Format of the data
            headers: Request headers
            wait_for_completion: Whether to wait for operations to complete
            
        Returns:
            Dictionary containing the combined results
            
        Raises:
            DataExchangeError: If batch injection fails
        """
        self.logger.info(f"Batch injecting {len(data)} items in batches of {self.max_batch_size}")
        
        total_injected = 0
        operation_ids = []
        
        # Split data into batches
        for i in range(0, len(data), self.max_batch_size):
            batch = data[i:i + self.max_batch_size]
            
            self.logger.debug(f"Injecting batch {i//self.max_batch_size + 1} with {len(batch)} items")
            
            # Format the batch
            payload = self._format_data_for_injection(batch, data_format)
            
            try:
                # Send the batch
                response = api_client._make_request(
                    method="POST",
                    endpoint=endpoint,
                    data=payload,
                    timeout=self.endpoint_timeout,
                    expected_status_codes=[200, 201, 202]
                )
                
                # Track operation IDs if needed
                if wait_for_completion and "id" in response:
                    operation_ids.append(response["id"])
                
                # Update count
                if "count" in response:
                    total_injected += response["count"]
                else:
                    total_injected += len(batch)
                    
            except APIError as e:
                self.logger.error(f"Failed to inject batch: {str(e)}")
                raise DataExchangeError(f"Batch injection failed: {str(e)}")
        
        # Wait for all operations to complete if needed
        if wait_for_completion and operation_ids:
            instance_id, job_id = self._parse_instance_job_from_endpoint(endpoint)
            for op_id in operation_ids:
                self._wait_for_operation(api_client, instance_id, job_id, op_id)
        
        return {
            "success": True,
            "count": total_injected,
            "batches": len(data) // self.max_batch_size + (1 if len(data) % self.max_batch_size > 0 else 0)
        }
    
    def _parse_instance_job_from_endpoint(self, endpoint: str) -> tuple:
        """
        Parse instance ID and job ID from an endpoint string.
        
        Args:
            endpoint: Endpoint string
            
        Returns:
            Tuple of (instance_id, job_id)
            
        Raises:
            ValueError: If endpoint format is invalid
        """
        # Expected format: "instances/{instance_id}/jobs/{job_id}/ports/..."
        parts = endpoint.split('/')
        if len(parts) < 5 or parts[0] != "instances" or parts[2] != "jobs":
            raise ValueError(f"Invalid endpoint format: {endpoint}")
        
        return parts[1], parts[3]
    
    def _wait_for_operation(
        self,
        api_client: StreamsApiClient,
        instance_id: str,
        job_id: str,
        operation_id: str,
        timeout_seconds: Optional[int] = None,
        check_interval_seconds: int = 1
    ) -> bool:
        """
        Wait for a Data Exchange operation to complete.
        
        Args:
            api_client: API client to use
            instance_id: ID of the instance
            job_id: ID of the job
            operation_id: ID of the operation to wait for
            timeout_seconds: Maximum time to wait
            check_interval_seconds: Interval between checks
            
        Returns:
            True if operation completed successfully, False otherwise
        """
        timeout = timeout_seconds or self.endpoint_timeout
        end_time = time.time() + timeout
        
        endpoint = f"instances/{instance_id}/jobs/{job_id}/operations/{operation_id}"
        
        while time.time() < end_time:
            try:
                response = api_client._make_request(
                    method="GET",
                    endpoint=endpoint,
                    timeout=check_interval_seconds * 2
                )
                
                status = response.get("status", "").lower()
                
                if status == "completed":
                    self.logger.debug(f"Operation {operation_id} completed successfully")
                    return True
                elif status == "failed":
                    error = response.get("error", "Unknown error")
                    self.logger.error(f"Operation {operation_id} failed: {error}")
                    return False
                elif status == "running" or status == "pending":
                    self.logger.debug(f"Operation {operation_id} still {status}")
                    time.sleep(check_interval_seconds)
                else:
                    self.logger.warning(f"Unknown operation status: {status}")
                    time.sleep(check_interval_seconds)
                    
            except APIError as e:
                self.logger.warning(f"Error checking operation status: {str(e)}")
                time.sleep(check_interval_seconds)
        
        self.logger.warning(f"Timeout waiting for operation {operation_id}")
        return False