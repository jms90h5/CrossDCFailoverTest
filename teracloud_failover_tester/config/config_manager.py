"""
Configuration Manager - Handles loading and validation of configuration files.
"""

import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional

import yaml
import jsonschema
from jsonschema import validate

from config.schemas import CONFIG_SCHEMA, SCENARIO_SCHEMA


class ConfigManager:
    """
    Manages loading and validation of configuration and test scenario files.
    """
    
    def __init__(self, config_path: str):
        """
        Initialize the configuration manager.
        
        Args:
            config_path: Path to the global configuration file
        """
        self.config_path = Path(config_path)
        self.logger = logging.getLogger("config")
        
        # Initialize configuration cache
        self._config = None
        self._credentials = {}
        
    def load_config(self) -> Dict[str, Any]:
        """
        Load and validate the global configuration.
        
        Returns:
            Dictionary containing the configuration
        
        Raises:
            FileNotFoundError: If the configuration file doesn't exist
            yaml.YAMLError: If the YAML is malformed
            jsonschema.exceptions.ValidationError: If the configuration is invalid
        """
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        
        self.logger.debug(f"Loading configuration from {self.config_path}")
        
        with open(self.config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Validate against schema
        self._validate_config(config, CONFIG_SCHEMA)
        
        # Handle credential placeholders
        self._process_credentials(config)
        
        # Cache for future use
        self._config = config
        
        return config
    
    def load_scenario(self, scenario_path: str) -> Dict[str, Any]:
        """
        Load and validate a test scenario file.
        
        Args:
            scenario_path: Path to the test scenario YAML file
        
        Returns:
            Dictionary containing the test scenario
        
        Raises:
            FileNotFoundError: If the scenario file doesn't exist
            yaml.YAMLError: If the YAML is malformed
            jsonschema.exceptions.ValidationError: If the scenario is invalid
        """
        scenario_path = Path(scenario_path)
        
        if not scenario_path.exists():
            raise FileNotFoundError(f"Scenario file not found: {scenario_path}")
        
        self.logger.debug(f"Loading test scenario from {scenario_path}")
        
        with open(scenario_path, 'r') as f:
            scenario = yaml.safe_load(f)
        
        # Validate against schema
        self._validate_config(scenario, SCENARIO_SCHEMA)
        
        # Expand file paths
        self._process_file_paths(scenario, scenario_path.parent)
        
        return scenario
    
    def get_credential(self, credential_name: str) -> Optional[str]:
        """
        Retrieve a credential by name from the credential cache.
        
        Args:
            credential_name: Name of the credential to retrieve
        
        Returns:
            The credential value or None if not found
        """
        return self._credentials.get(credential_name)
    
    def _validate_config(self, config: Dict[str, Any], schema: Dict[str, Any]):
        """
        Validate a configuration against a JSON schema.
        
        Args:
            config: Configuration to validate
            schema: JSON schema to validate against
        
        Raises:
            jsonschema.exceptions.ValidationError: If validation fails
        """
        try:
            validate(instance=config, schema=schema)
        except jsonschema.exceptions.ValidationError as e:
            self.logger.error(f"Configuration validation failed: {str(e)}")
            raise
    
    def _process_credentials(self, config: Dict[str, Any]):
        """
        Process credential references in the configuration.
        
        Args:
            config: Configuration dictionary to process
        """
        # Look for credentials section
        credentials = config.get('credentials', {})
        
        # Process environment variable references
        for cred_name, cred_value in credentials.items():
            if isinstance(cred_value, str) and cred_value.startswith('$ENV:'):
                env_var = cred_value[5:]  # Remove the $ENV: prefix
                env_value = os.environ.get(env_var)
                
                if env_value is None:
                    self.logger.warning(f"Environment variable {env_var} not found for credential {cred_name}")
                else:
                    self._credentials[cred_name] = env_value
            else:
                self._credentials[cred_name] = cred_value
        
        # Process credential references in config
        self._replace_credential_refs(config)
    
    def _replace_credential_refs(self, obj: Any):
        """
        Recursively replace credential references in an object.
        
        Args:
            obj: Object to process (dict, list, or scalar)
        """
        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, str) and value.startswith('$CRED:'):
                    cred_name = value[6:]  # Remove the $CRED: prefix
                    cred_value = self._credentials.get(cred_name)
                    
                    if cred_value is None:
                        self.logger.warning(f"Credential {cred_name} not found")
                    else:
                        obj[key] = cred_value
                else:
                    self._replace_credential_refs(value)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                if isinstance(item, str) and item.startswith('$CRED:'):
                    cred_name = item[6:]  # Remove the $CRED: prefix
                    cred_value = self._credentials.get(cred_name)
                    
                    if cred_value is None:
                        self.logger.warning(f"Credential {cred_name} not found")
                    else:
                        obj[i] = cred_value
                else:
                    self._replace_credential_refs(item)
    
    def _process_file_paths(self, scenario: Dict[str, Any], base_dir: Path):
        """
        Process and expand file paths in a test scenario.
        
        Args:
            scenario: Test scenario to process
            base_dir: Base directory for relative paths
        """
        # Check for SAB file path
        if 'streams_application_sab' in scenario:
            sab_path = scenario['streams_application_sab']
            
            # If it's a relative path, make it absolute
            if not os.path.isabs(sab_path):
                absolute_path = base_dir / sab_path
                scenario['streams_application_sab'] = str(absolute_path)
        
        # Process other file paths as needed
        # TODO: Add processing for other file paths in the scenario