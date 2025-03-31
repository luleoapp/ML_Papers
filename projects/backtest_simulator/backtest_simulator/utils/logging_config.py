"""Advanced logging configuration for the backtest simulator."""

import os
import sys
import logging
import logging.config
import time
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union, Any

# Optional colored logging
try:
    import colorlog
    HAS_COLORLOG = True
except ImportError:
    HAS_COLORLOG = False


class CustomJSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def __init__(self, fmt=None, datefmt=None, style='%', app_name="backtest_simulator"):
        super().__init__(fmt, datefmt, style)
        self.app_name = app_name
        self.hostname = os.uname().nodename
        self.process_id = os.getpid()
        self.instance_id = str(uuid.uuid4())[:8]
    
    def format(self, record: logging.LogRecord) -> str:
        """Format the record as a JSON string."""
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "app": self.app_name,
            "host": self.hostname,
            "pid": self.process_id,
            "thread": record.threadName,
            "instance": self.instance_id,
            "filename": record.filename,
            "line": record.lineno,
            "function": record.funcName
        }
        
        # Include exception info if available
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info)
            }
        
        # Include extra fields
        for key, value in record.__dict__.items():
            if key not in ["args", "asctime", "created", "exc_info", "exc_text", 
                         "filename", "funcName", "id", "levelname", "levelno", 
                         "lineno", "module", "msecs", "message", "msg", "name", 
                         "pathname", "process", "processName", "relativeCreated", 
                         "stack_info", "thread", "threadName"]:
                log_data[key] = value
        
        return json.dumps(log_data)


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
                    max_file_size: int = 10 * 1024 * 1024,  # 10 MB
                    backup_count: int = 10) -> None:
        """Configure logging for the entire application.
        
        Args:
            log_dir: Directory to store log files. If None, logs will be stored in ./logs
            log_level: Default logging level for all loggers
            console_level: Logging level for console output
            file_level: Logging level for file output
            json_logs: Whether to use JSON formatting for log files
            log_file_prefix: Prefix for log files
            app_name: Application name for logs
            enable_console: Whether to enable console logging
            max_file_size: Maximum size of each log file in bytes before rotation
            backup_count: Number of backup files to keep
        """
        # Create log directory if it doesn't exist
        if log_dir is None:
            log_dir = os.path.join(os.getcwd(), "logs")
        
        log_dir_path = Path(log_dir)
        log_dir_path.mkdir(parents=True, exist_ok=True)
        
        # Normalize log levels
        log_level = cls._normalize_log_level(log_level)
        console_level = cls._normalize_log_level(console_level)
        file_level = cls._normalize_log_level(file_level)
        
        # Generate log file paths
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir_path / f"{log_file_prefix}_{timestamp}.log"
        error_log_file = log_dir_path / f"{log_file_prefix}_{timestamp}_error.log"
        
        # Create formatters
        if HAS_COLORLOG and enable_console:
            console_formatter = colorlog.ColoredFormatter(
                "%(log_color)s%(asctime)s [%(levelname)-8s] %(name)s: %(message)s%(reset)s",
                datefmt="%Y-%m-%d %H:%M:%S",
                log_colors={
                    'DEBUG': 'cyan',
                    'INFO': 'green',
                    'WARNING': 'yellow',
                    'ERROR': 'red',
                    'CRITICAL': 'red,bg_white',
                }
            )
        else:
            console_formatter = logging.Formatter(
                "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
        
        if json_logs:
            file_formatter = CustomJSONFormatter(app_name=app_name)
        else:
            file_formatter = logging.Formatter(
                "%(asctime)s [%(levelname)-8s] [%(thread)d] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
        
        # Configure handlers
        handlers = {}
        
        if enable_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(console_level)
            console_handler.setFormatter(console_formatter)
            handlers["console"] = {
                "class": "logging.StreamHandler",
                "level": console_level,
                "formatter": "console",
                "stream": "ext://sys.stdout"
            }
        
        # File handler for regular logs
        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_file,
            maxBytes=max_file_size,
            backupCount=backup_count
        )
        file_handler.setLevel(file_level)
        file_handler.setFormatter(file_formatter)
        handlers["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "level": file_level,
            "formatter": "file",
            "filename": str(log_file),
            "maxBytes": max_file_size,
            "backupCount": backup_count
        }
        
        # File handler for error logs
        error_file_handler = logging.handlers.RotatingFileHandler(
            filename=error_log_file,
            maxBytes=max_file_size,
            backupCount=backup_count
        )
        error_file_handler.setLevel(logging.ERROR)
        error_file_handler.setFormatter(file_formatter)
        handlers["error_file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "ERROR",
            "formatter": "file",
            "filename": str(error_log_file),
            "maxBytes": max_file_size,
            "backupCount": backup_count
        }
        
        # Build logging config
        config = {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "console": {
                    "format": "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
                    "datefmt": "%Y-%m-%d %H:%M:%S"
                },
                "file": {
                    "format": "%(asctime)s [%(levelname)-8s] [%(thread)d] %(name)s: %(message)s",
                    "datefmt": "%Y-%m-%d %H:%M:%S"
                }
            },
            "handlers": handlers,
            "loggers": {
                "": {  # Root logger
                    "level": log_level,
                    "handlers": list(handlers.keys())
                },
                "backtest_simulator": {
                    "level": log_level,
                    "handlers": list(handlers.keys()),
                    "propagate": False
                }
            }
        }
        
        # Apply configuration
        logging.config.dictConfig(config)
        
        # Log startup message
        logger = logging.getLogger("backtest_simulator")
        logger.info(f"Logging configured: level={log_level}, directory={log_dir}")
        logger.debug(f"Log file: {log_file}")
        
        # Create symbolic link to latest log files
        cls._create_latest_symlink(log_file, log_dir_path / f"{log_file_prefix}_latest.log")
        cls._create_latest_symlink(error_log_file, log_dir_path / f"{log_file_prefix}_latest_error.log")
    
    @staticmethod
    def _normalize_log_level(level: str) -> str:
        """Normalize log level string to uppercase."""
        level_upper = level.upper()
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        
        if level_upper not in valid_levels:
            print(f"WARNING: Invalid log level '{level}'. Using 'INFO' instead.")
            return "INFO"
        
        return level_upper
    
    @staticmethod
    def _create_latest_symlink(log_file: Path, symlink_path: Path) -> None:
        """Create a symbolic link to the latest log file."""
        try:
            # Remove existing symlink if it exists
            if symlink_path.exists():
                symlink_path.unlink()
            
            # Create new symlink
            symlink_path.symlink_to(log_file)
        except Exception as e:
            # Don't fail if symlink creation fails
            print(f"WARNING: Failed to create symlink to latest log: {e}")
    
    @classmethod
    def get_logger(cls, name: str, level: Optional[str] = None) -> logging.Logger:
        """Get a logger with the specified name and level.
        
        Args:
            name: Name of the logger
            level: Optional level to set for this logger
            
        Returns:
            Configured logger
        """
        logger = logging.getLogger(name)
        
        if level is not None:
            logger.setLevel(cls._normalize_log_level(level))
        
        return logger


# Global function to get logger
def get_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """Get a logger with the specified name and level.
    
    Args:
        name: Name of the logger
        level: Optional level to set for this logger
        
    Returns:
        Configured logger
    """
    return LoggerFactory.get_logger(name, level)