"""
Centralized logging configuration for CDR Validation Pipeline
Integrates with Azure Monitor and supports structured logging
"""

import logging
import sys
import json
from datetime import datetime
from typing import Optional, Dict, Any
from pythonjsonlogger import jsonlogger
import os


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with additional fields"""

    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]) -> None:
        super().add_fields(log_record, record, message_dict)

        # Add timestamp
        if not log_record.get('timestamp'):
            log_record['timestamp'] = datetime.utcnow().isoformat() + 'Z'

        # Add level
        if log_record.get('level'):
            log_record['level'] = log_record['level'].upper()
        else:
            log_record['level'] = record.levelname

        # Add service metadata
        log_record['service'] = 'cdr-validation'
        log_record['environment'] = os.getenv('ENVIRONMENT', 'development')

        # Add custom fields if present
        if hasattr(record, 'test_run_id'):
            log_record['test_run_id'] = record.test_run_id
        if hasattr(record, 'phase'):
            log_record['phase'] = record.phase
        if hasattr(record, 'file_name'):
            log_record['file_name'] = record.file_name


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    json_format: bool = True,
    azure_monitor: bool = False
) -> logging.Logger:
    """
    Setup centralized logging configuration

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path for file logging
        json_format: Use JSON formatting for structured logs
        azure_monitor: Enable Azure Monitor integration

    Returns:
        Configured root logger
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper()))

    if json_format:
        formatter = CustomJsonFormatter(
            '%(timestamp)s %(level)s %(name)s %(message)s'
        )
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(getattr(logging, level.upper()))
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # Azure Monitor handler
    if azure_monitor:
        try:
            from opencensus.ext.azure.log_exporter import AzureLogHandler
            connection_string = os.getenv('APPLICATIONINSIGHTS_CONNECTION_STRING')

            if connection_string:
                azure_handler = AzureLogHandler(connection_string=connection_string)
                azure_handler.setLevel(logging.WARNING)  # Only send warnings and above to Azure
                root_logger.addHandler(azure_handler)
                root_logger.info("Azure Monitor logging enabled")
            else:
                root_logger.warning("Azure Monitor enabled but APPLICATIONINSIGHTS_CONNECTION_STRING not set")
        except ImportError:
            root_logger.warning("opencensus-ext-azure not installed, skipping Azure Monitor integration")

    return root_logger


def get_logger(name: str, test_run_id: Optional[str] = None, phase: Optional[str] = None) -> logging.Logger:
    """
    Get a logger with optional context

    Args:
        name: Logger name (typically __name__)
        test_run_id: Optional test run ID for correlation
        phase: Optional phase (pre_cdr, post_cdr)

    Returns:
        Configured logger with context
    """
    logger = logging.getLogger(name)

    # Add context as extra fields
    if test_run_id or phase:
        logger = logging.LoggerAdapter(logger, {
            'test_run_id': test_run_id,
            'phase': phase
        })

    return logger


class LogContext:
    """Context manager for adding context to logs"""

    def __init__(self, logger: logging.Logger, **context):
        self.logger = logger
        self.context = context
        self.original_extra = {}

    def __enter__(self):
        # Store original context
        if isinstance(self.logger, logging.LoggerAdapter):
            self.original_extra = self.logger.extra.copy()
            self.logger.extra.update(self.context)
        return self.logger

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore original context
        if isinstance(self.logger, logging.LoggerAdapter):
            self.logger.extra = self.original_extra


def log_function_call(func):
    """Decorator to log function calls with parameters and results"""

    def wrapper(*args, **kwargs):
        logger = logging.getLogger(func.__module__)
        func_name = func.__name__

        # Log entry
        logger.debug(f"Entering {func_name}", extra={
            'function': func_name,
            'args': str(args),
            'kwargs': str(kwargs)
        })

        try:
            result = func(*args, **kwargs)
            logger.debug(f"Exiting {func_name}", extra={
                'function': func_name,
                'result': str(result)
            })
            return result
        except Exception as e:
            logger.error(f"Error in {func_name}: {str(e)}", extra={
                'function': func_name,
                'error': str(e)
            }, exc_info=True)
            raise

    return wrapper


def log_execution_time(func):
    """Decorator to log function execution time"""
    import time

    def wrapper(*args, **kwargs):
        logger = logging.getLogger(func.__module__)
        func_name = func.__name__

        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.info(f"{func_name} completed in {execution_time:.2f}s", extra={
                'function': func_name,
                'execution_time_seconds': execution_time
            })
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"{func_name} failed after {execution_time:.2f}s: {str(e)}", extra={
                'function': func_name,
                'execution_time_seconds': execution_time,
                'error': str(e)
            })
            raise

    return wrapper


# Initialize default logging on module import
if os.getenv('DISABLE_DEFAULT_LOGGING') != 'true':
    setup_logging(
        level=os.getenv('LOG_LEVEL', 'INFO'),
        json_format=os.getenv('LOG_FORMAT', 'json') == 'json',
        azure_monitor=os.getenv('AZURE_MONITOR_LOGGING', 'false').lower() == 'true'
    )
