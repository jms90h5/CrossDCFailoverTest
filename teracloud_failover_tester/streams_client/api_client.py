"""
Teracloud Streams REST Management API client.
"""

import logging
import time
from typing import Dict, List, Optional, Any, Union
import os
import json

import requests
from requests.adapters import HTTPAdapter
from requests.exceptions import RequestException
from urllib3.util.retry import Retry


class APIError(Exception):
    """Base exception for API errors."""
    def __init__(self, message: str, status_code: Optional[int] = None, response: Optional[Any] = None):
        self.status_code = status_code
        self.response = response
        super().__init__(message)


class AuthenticationError(APIError):
    """Exception for authentication errors."""
    pass


class ResourceNotFoundError(APIError):
    """Exception for resource not found errors."""
    pass


class StreamsApiClient:
    """
    Client for interacting with the Teracloud Streams REST Management API.
    
    Based on documentation at:
    https://doc.streams.teracloud.com/com.ibm.streams.admin.doc/doc/managemonitorstreamsapi.html
    https://doc.streams.teracloud.com/external-reference/redoc-static.html
    """
    
    def __init__(
        self, 
        base_url: str, 
        auth_token: str, 
        verify_ssl: bool = True,
        timeout: int = 60,
        max_retries: int = 3
    ):
        """
        Initialize the Streams API client.
        
        Args:
            base_url: Base URL of the Streams REST Management API
            auth_token: Authentication token for the API
            verify_ssl: Whether to verify SSL certificates
            timeout: Default timeout for API requests in seconds
            max_retries: Maximum number of retries for failed requests
        """
        self.base_url = base_url.rstrip('/')
        self.auth_token = auth_token
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self.logger = logging.getLogger("streams_api")
        
        # Set up session with retry logic
        self.session = requests.Session()
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST", "PUT", "DELETE"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Set default headers
        self.session.headers.update({
            'Authorization': f'Bearer {auth_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
    
    def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
        expected_status_codes: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """
        Make an HTTP request to the Streams API.
        
        Args:
            method: HTTP method to use
            endpoint: API endpoint (relative to base URL)
            params: Query parameters
            data: Request body data (will be serialized to JSON)
            files: Files to upload
            timeout: Request timeout (overrides default)
            expected_status_codes: List of expected status codes
            
        Returns:
            Response data as a dictionary
            
        Raises:
            AuthenticationError: If authentication fails
            ResourceNotFoundError: If the resource is not found
            APIError: For other API errors
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        timeout = timeout or self.timeout
        expected_status_codes = expected_status_codes or [200, 201, 202, 204]
        
        # Prepare request kwargs
        kwargs = {
            'params': params,
            'timeout': timeout,
            'verify': self.verify_ssl
        }
        
        # Handle data and files
        if files:
            # If we have files, we can't use JSON content type
            if data:
                # Convert data to form fields
                kwargs['data'] = data
            kwargs['files'] = files
            # Remove Content-Type header when uploading files
            headers = self.session.headers.copy()
            if 'Content-Type' in headers:
                del headers['Content-Type']
            kwargs['headers'] = headers
        elif data:
            # JSON-encode the data
            kwargs['data'] = json.dumps(data)
        
        # Log the request
        self.logger.debug(f"{method} {url}")
        if params:
            self.logger.debug(f"Params: {params}")
        if data and not files:
            self.logger.debug(f"Data: {data}")
        
        try:
            response = self.session.request(method, url, **kwargs)
            
            # Check for error status codes
            if response.status_code not in expected_status_codes:
                if response.status_code == 401:
                    raise AuthenticationError(
                        "Authentication failed",
                        status_code=response.status_code,
                        response=response.text
                    )
                elif response.status_code == 404:
                    raise ResourceNotFoundError(
                        f"Resource not found: {endpoint}",
                        status_code=response.status_code,
                        response=response.text
                    )
                else:
                    # Try to get error details from response
                    error_msg = f"API error: {response.status_code}"
                    try:
                        error_data = response.json()
                        if isinstance(error_data, dict):
                            if 'message' in error_data:
                                error_msg = f"API error: {error_data['message']}"
                            elif 'error' in error_data:
                                error_msg = f"API error: {error_data['error']}"
                    except:
                        # If we can't parse the JSON, use the raw text
                        if response.text:
                            error_msg = f"API error: {response.text[:200]}"
                    
                    raise APIError(
                        error_msg,
                        status_code=response.status_code,
                        response=response.text
                    )
            
            # Handle empty responses
            if not response.content or response.status_code == 204:
                return {}
            
            # Parse JSON response
            try:
                return response.json()
            except json.JSONDecodeError:
                self.logger.warning(f"Failed to parse JSON response: {response.text[:200]}")
                return {"raw_response": response.text}
                
        except RequestException as e:
            self.logger.error(f"Request error: {str(e)}")
            raise APIError(f"Request failed: {str(e)}")
    
    # Instance Management
    
    def get_instances(self) -> List[Dict[str, Any]]:
        """
        Get a list of all Streams instances.
        
        Returns:
            List of instance objects
        """
        response = self._make_request("GET", "instances")
        return response.get("instances", [])
    
    def get_instance(self, instance_id: str) -> Dict[str, Any]:
        """
        Get details for a specific Streams instance.
        
        Args:
            instance_id: ID of the instance
            
        Returns:
            Instance details
            
        Raises:
            ResourceNotFoundError: If the instance is not found
        """
        return self._make_request("GET", f"instances/{instance_id}")
    
    # Job Management
    
    def get_jobs(self, instance_id: str) -> List[Dict[str, Any]]:
        """
        Get a list of all jobs in a Streams instance.
        
        Args:
            instance_id: ID of the instance
            
        Returns:
            List of job objects
        """
        response = self._make_request("GET", f"instances/{instance_id}/jobs")
        return response.get("jobs", [])
    
    def get_job(self, instance_id: str, job_id: str) -> Dict[str, Any]:
        """
        Get details for a specific job.
        
        Args:
            instance_id: ID of the instance
            job_id: ID of the job
            
        Returns:
            Job details
            
        Raises:
            ResourceNotFoundError: If the job is not found
        """
        return self._make_request("GET", f"instances/{instance_id}/jobs/{job_id}")
    
    def submit_job(
        self, 
        instance_id: str, 
        sab_path: str, 
        job_name: Optional[str] = None,
        job_group: Optional[str] = None,
        submission_parameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Submit a Streams Application Bundle (SAB) to create a new job.
        
        Args:
            instance_id: ID of the instance
            sab_path: Path to the SAB file
            job_name: Name for the job (optional)
            job_group: Job group (optional)
            submission_parameters: Dictionary of submission parameters
            
        Returns:
            Job submission result
            
        Raises:
            APIError: If the job submission fails
            FileNotFoundError: If the SAB file is not found
        """
        if not os.path.exists(sab_path):
            raise FileNotFoundError(f"SAB file not found: {sab_path}")
        
        # Prepare multipart form data
        files = {
            'sab': (os.path.basename(sab_path), open(sab_path, 'rb'), 'application/octet-stream')
        }
        
        data = {}
        if job_name:
            data['jobName'] = job_name
        if job_group:
            data['jobGroup'] = job_group
        if submission_parameters:
            # Convert parameters to the expected format
            params = []
            for name, value in submission_parameters.items():
                params.append({"name": name, "value": str(value)})
            data['submissionParameters'] = params
        
        try:
            return self._make_request(
                "POST", 
                f"instances/{instance_id}/jobs", 
                data=data,
                files=files,
                expected_status_codes=[200, 201]
            )
        finally:
            # Close the file
            files['sab'][1].close()
    
    def cancel_job(self, instance_id: str, job_id: str) -> Dict[str, Any]:
        """
        Cancel a running job.
        
        Args:
            instance_id: ID of the instance
            job_id: ID of the job
            
        Returns:
            Cancellation result
            
        Raises:
            ResourceNotFoundError: If the job is not found
        """
        return self._make_request("DELETE", f"instances/{instance_id}/jobs/{job_id}")
    
    # Processing Element (PE) Operations
    
    def get_pes(self, instance_id: str, job_id: str) -> List[Dict[str, Any]]:
        """
        Get all Processing Elements (PEs) for a job.
        
        Args:
            instance_id: ID of the instance
            job_id: ID of the job
            
        Returns:
            List of PE objects
            
        Raises:
            ResourceNotFoundError: If the job is not found
        """
        response = self._make_request("GET", f"instances/{instance_id}/jobs/{job_id}/pes")
        return response.get("pes", [])
    
    def get_pe(self, instance_id: str, job_id: str, pe_id: str) -> Dict[str, Any]:
        """
        Get details for a specific Processing Element (PE).
        
        Args:
            instance_id: ID of the instance
            job_id: ID of the job
            pe_id: ID of the PE
            
        Returns:
            PE details
            
        Raises:
            ResourceNotFoundError: If the PE is not found
        """
        return self._make_request("GET", f"instances/{instance_id}/jobs/{job_id}/pes/{pe_id}")
    
    # Metrics Operations
    
    def get_metrics(
        self, 
        instance_id: str, 
        resource_type: str, 
        resource_id: str
    ) -> Dict[str, Any]:
        """
        Get metrics for a specific resource.
        
        Args:
            instance_id: ID of the instance
            resource_type: Type of resource (job, pe, operator, etc.)
            resource_id: ID of the resource
            
        Returns:
            Metrics data
            
        Raises:
            ResourceNotFoundError: If the resource is not found
        """
        return self._make_request(
            "GET", 
            f"instances/{instance_id}/metrics/{resource_type}/{resource_id}"
        )
    
    # Utility Methods
    
    def wait_for_job_state(
        self, 
        instance_id: str, 
        job_id: str, 
        target_state: str, 
        timeout_seconds: int = 300,
        check_interval_seconds: int = 5
    ) -> bool:
        """
        Wait for a job to reach a specific state.
        
        Args:
            instance_id: ID of the instance
            job_id: ID of the job
            target_state: Target state to wait for
            timeout_seconds: Maximum time to wait
            check_interval_seconds: Interval between checks
            
        Returns:
            True if the job reached the target state, False if timed out
            
        Raises:
            ResourceNotFoundError: If the job is not found
        """
        end_time = time.time() + timeout_seconds
        
        while time.time() < end_time:
            try:
                job = self.get_job(instance_id, job_id)
                current_state = job.get("state", "").lower()
                
                if current_state == target_state.lower():
                    self.logger.info(f"Job {job_id} reached state {target_state}")
                    return True
                
                self.logger.debug(f"Job {job_id} is in state {current_state}, waiting for {target_state}")
                time.sleep(check_interval_seconds)
                
            except ResourceNotFoundError:
                self.logger.error(f"Job {job_id} not found while waiting for state {target_state}")
                return False
            except APIError as e:
                self.logger.warning(f"API error while waiting for job state: {str(e)}")
                # Continue retrying
                time.sleep(check_interval_seconds)
        
        self.logger.warning(
            f"Timeout waiting for job {job_id} to reach state {target_state}"
        )
        return False
    
    def wait_for_job_health(
        self, 
        instance_id: str, 
        job_id: str, 
        target_health: str, 
        timeout_seconds: int = 300,
        check_interval_seconds: int = 5
    ) -> bool:
        """
        Wait for a job to reach a specific health status.
        
        Args:
            instance_id: ID of the instance
            job_id: ID of the job
            target_health: Target health to wait for (e.g., "healthy")
            timeout_seconds: Maximum time to wait
            check_interval_seconds: Interval between checks
            
        Returns:
            True if the job reached the target health, False if timed out
            
        Raises:
            ResourceNotFoundError: If the job is not found
        """
        end_time = time.time() + timeout_seconds
        
        while time.time() < end_time:
            try:
                job = self.get_job(instance_id, job_id)
                current_health = job.get("health", "").lower()
                
                if current_health == target_health.lower():
                    self.logger.info(f"Job {job_id} reached health {target_health}")
                    return True
                
                self.logger.debug(f"Job {job_id} has health {current_health}, waiting for {target_health}")
                time.sleep(check_interval_seconds)
                
            except ResourceNotFoundError:
                self.logger.error(f"Job {job_id} not found while waiting for health {target_health}")
                return False
            except APIError as e:
                self.logger.warning(f"API error while waiting for job health: {str(e)}")
                # Continue retrying
                time.sleep(check_interval_seconds)
        
        self.logger.warning(
            f"Timeout waiting for job {job_id} to reach health {target_health}"
        )
        return False