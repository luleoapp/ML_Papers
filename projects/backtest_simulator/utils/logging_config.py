"""
Logging configuration utilities for the backtest simulator.

This module provides a LoggerFactory class for creating and configuring loggers
with various output formats and destinations.
"""

import os
import sys
import json
import logging
import logging.handlers
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime
import atexit
import threading
from queue import Queue


# Global logger cache to avoid duplicate loggers
_logger_cache = {}
_logger_cache_lock = threading.RLock()


class JsonFormatter(logging.Formatter):
    """Format log records as JSON."""
    
    def __init__(self, app_name: str = "backtest_simulator", **kwargs):
        """Initialize the JSON formatter.
        
        Args:
            app_name: Name of the application
            **kwargs: Additional fields to include in the JSON
        """
        super().__init__()
        self.app_name = app_name
        self.additional_fields = kwargs
    
    def format(self, record: logging.LogRecord) -> str:
        """Format the log record as JSON.
        
        Args:
            record: Log record to format
            
        Returns:
            JSON string representation of the log record
        """
        # Create base log object
        log_obj = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "app": self.app_name,
            "name": record.name,
            "level": record.levelname,
            "message": record.getMessage(),
            "thread": record.threadName,
            "thread_id": record.thread,
            "process_id": record.process
        }
        
        # Add exception info if present
        if record.exc_info:
            log_obj["exception"] = {
                "type": record.exc_info[0].__name__,
                "value": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info)
            }
        
        # Add any additional fields from record.args if it's a dict
        if isinstance(record.args, dict):
            for key, value in record.args.items():
                if key not in log_obj:
                    log_obj[key] = value
        
        # Add any additional fields provided during initialization
        for key, value in self.additional_fields.items():
            if key not in log_obj:
                log_obj[key] = value
        
        return json.dumps(log_obj)


class AsyncHandler(logging.Handler):
    """Asynchronous logging handler that processes logs in a separate thread."""
    
    def __init__(self, handler: logging.Handler, queue_size: int = 1000):
        """Initialize the async handler.
        
        Args:
            handler: The actual handler to use for processing logs
            queue_size: Maximum size of the log queue
        """
        super().__init__(level=handler.level)
        self.handler = handler
        self.queue = Queue(maxsize=queue_size)
        self.thread = threading.Thread(target=self._process_logs, name="async_log_handler", daemon=True)
        self.thread.start()
        
        # Register cleanup function
        atexit.register(self.close)
    
    def emit(self, record: logging.LogRecord) -> None:
        """Add the log record to the queue.
        
        Args:
            record: Log record to process
        """
        try:
            self.queue.put_nowait(record)
        except:
            # If the queue is full, log to stderr
            sys.stderr.write(f"Log queue full, dropping log: {record.getMessage()}\n")
    
    def _process_logs(self) -> None:
        """Process logs from the queue."""
        while True:
            try:
                record = self.queue.get()
                
                # None is a signal to stop
                if record is None:
                    break
                
                self.handler.emit(record)
                
                self.queue.task_done()
            except Exception as e:
                sys.stderr.write(f"Error processing log: {e}\n")
    
    def close(self) -> None:
        """Close the handler and stop the thread."""
        try:
            # Signal the thread to stop
            self.queue.put(None)
            
            # Wait for the thread to finish
            if self.thread.is_alive():
                self.thread.join(timeout=2.0)
            
            # Close the actual handler
            self.handler.close()
            
            super().close()
        except:
            pass


class LoggerFactory:
    """Factory for creating and configuring loggers."""
    
    @classmethod
    def setup_logging(cls, 
                     log_dir: Optional[str] = None, 
                     log_level: str = "INFO",
                     console_level: str = "INFO",
                     file_level: str = "DEBUG",
                     json_logs: bool = False,
                     log_file_prefix: str = "backtest",
                     app_name: str = "backtest_simulator",
                     enable_console: bool = True,
                     max_file_size: int = 10 * 1024 * 1024,
                     backup_count: int = 10,
                     async_logging: bool = True) -> None:
        """Set up logging for the entire application.
        
        Args:
            log_dir: Directory to write log files to, or None for no file logging
            log_level: Overall logging level
            console_level: Logging level for console output
            file_level: Logging level for file output
            json_logs: Whether to format logs as JSON
            log_file_prefix: Prefix for log files
            app_name: Name of the application for JSON logs
            enable_console: Whether to enable console logging
            max_file_size: Maximum size of log files before rotation
            backup_count: Number of backup log files to keep
            async_logging: Whether to use asynchronous logging
        """
        # Convert log levels from strings to constants
        log_level = cls._get_log_level(log_level)
        console_level = cls._get_log_level(console_level)
        file_level = cls._get_log_level(file_level)
        
        # Configure the root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
        
        # Remove any existing handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Configure formatters
        if json_logs:
            formatter = JsonFormatter(app_name=app_name)
        else:
            formatter = logging.Formatter(
                fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
        
        # Add console handler if enabled
        if enable_console:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(console_level)
            console_handler.setFormatter(formatter)
            
            if async_logging:
                root_logger.addHandler(AsyncHandler(console_handler))
            else:
                root_logger.addHandler(console_handler)
        
        # Add file handler if log_dir is provided
        if log_dir:
            # Create log directory if it doesn't exist
            log_dir = Path(log_dir)
            log_dir.mkdir(parents=True, exist_ok=True)
            
            # Create log file path
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = log_dir / f"{log_file_prefix}_{timestamp}.log"
            
            # Create file handler with rotation
            file_handler = logging.handlers.RotatingFileHandler(
                filename=log_file,
                maxBytes=max_file_size,
                backupCount=backup_count
            )
            file_handler.setLevel(file_level)
            file_handler.setFormatter(formatter)
            
            if async_logging:
                root_logger.addHandler(AsyncHandler(file_handler))
            else:
                root_logger.addHandler(file_handler)
    
    @staticmethod
    def _get_log_level(level: str) -> int:
        """Convert log level string to logging constant.
        
        Args:
            level: Log level string
            
        Returns:
            Log level constant
        """
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL
        }
        return level_map.get(level.upper(), logging.INFO)


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the specified name.
    
    Args:
        name: Logger name
        
    Returns:
        Logger instance
    """
    with _logger_cache_lock:
        if name in _logger_cache:
            return _logger_cache[name]
        
        logger = logging.getLogger(name)
        _logger_cache[name] = logger
        return logger