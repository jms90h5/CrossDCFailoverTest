"""
Logging utilities for the failover testing framework.
"""

import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional

try:
    from pythonjsonlogger import jsonlogger
    json_logger_available = True
except ImportError:
    json_logger_available = False


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None
) -> None:
    """
    Set up logging for the application.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (if None, logs to console only)
        config: Optional logging configuration from config.yaml
    """
    # Get numeric log level
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Get configuration
    if config is None:
        config = {}
    
    console_level = getattr(logging, config.get("console_level", log_level).upper(), numeric_level)
    file_level = getattr(logging, config.get("file_level", log_level).upper(), numeric_level)
    use_json = config.get("json_logs", False)
    log_format = config.get(
        "log_format", 
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Capture all logs, handlers will filter
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    
    # Create formatter
    if use_json and json_logger_available:
        formatter = jsonlogger.JsonFormatter(
            fmt="%(asctime)s %(name)s %(levelname)s %(message)s"
        )
    else:
        formatter = logging.Formatter(log_format)
    
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Create file handler if log_file is specified
    if log_file:
        # Ensure directory exists
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        
        # Create rotating file handler (10 MB per file, max 5 files)
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8"
        )
        file_handler.setLevel(file_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    # Create framework logger
    logger = logging.getLogger("teracloud_failover_tester")
    logger.info(f"Logging initialized (console: {console_level}, file: {file_level})")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name, prefixed with framework name.
    
    Args:
        name: Logger name
        
    Returns:
        Logger instance
    """
    return logging.getLogger(f"teracloud_failover_tester.{name}")