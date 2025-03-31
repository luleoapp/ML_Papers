"""
Python interface to the C++ backtest engine via pybind11.

This module provides a wrapper around the C++ backtest engine, handling
thread-local engine instances, callback registration, and configuration.
"""

import threading
import logging
from typing import Dict, List, Any, Optional, Callable, Union
from datetime import datetime, timedelta
import os
from pathlib import Path

from backtest_simulator.utils.logging_config import get_logger
from backtest_simulator.utils.performance import PerformanceMonitor
from backtest_simulator.core.callback_manager import CallbackManager, global_callback_handler


# Import the C++ module
try:
    from backtest_simulator.cpp import _cpp_backtest_engine as cpp_engine
    _CPPBacktestEngine = cpp_engine.BacktestEngine
except ImportError:
    # For testing/documentation purposes when C++ module is not available
    class _CPPBacktestEngine:
        def __init__(self):
            pass
        
        def configure(self, config: Dict[str, str]) -> bool:
            return True
        
        def register_callback(self, callback: Callable[[List[Dict[str, Any]]], bool]) -> bool:
            return True
        
        def process_day(self, date_str: str, max_window_size: int = 3600) -> Dict[str, Any]:
            return {"status": "success", "date": date_str, "markings": 0}
        
        def set_reference_data(self, reference_data: Dict[str, Any]) -> bool:
            return True


class CPPBacktestEngine:
    """Python wrapper around the C++ backtest engine."""
    
    def __init__(self, performance_monitor: Optional[PerformanceMonitor] = None):
        """Initialize the C++ backtest engine wrapper.
        
        Args:
            performance_monitor: Optional performance monitor for tracking metrics
        """
        # Set up logger
        self.logger = get_logger(f"{__name__}.CPPBacktestEngine")
        self.logger.info("Initializing C++ backtest engine wrapper")
        
        # Set up thread-local storage for engine instances
        self._thread_local = threading.local()
        
        # Save performance monitor
        self.performance_monitor = performance_monitor
        
        # Save configuration for new thread-local instances
        self._config = None
        
        # Store callback manager for this instance
        self._callback_manager = None
        
        self.logger.info("C++ backtest engine wrapper initialized")
    
    def configure(self, config: Dict[str, Any]) -> bool:
        """Configure the C++ backtest engine.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            True if configuration was successful, False otherwise
        """
        self.logger.info("Configuring C++ backtest engine")
        
        # Save configuration for future thread-local instances
        self._config = config.copy()
        
        # Convert all values to strings for C++ configuration
        string_config = {k: str(v) for k, v in config.items()}
        
        # Get the engine instance for this thread
        engine = self._get_engine_instance()
        
        # Configure the engine
        try:
            result = engine.configure(string_config)
            
            if result:
                self.logger.info("C++ backtest engine configured successfully")
            else:
                self.logger.error("Failed to configure C++ backtest engine")
            
            return result
        
        except Exception as e:
            self.logger.error(f"Error configuring C++ backtest engine: {e}", exc_info=True)
            return False
    
    def register_callback_manager(self, callback_manager: CallbackManager) -> bool:
        """Register a callback manager with the C++ backtest engine.
        
        Args:
            callback_manager: Callback manager to register
            
        Returns:
            True if registration was successful, False otherwise
        """
        self.logger.info("Registering callback manager with C++ backtest engine")
        
        # Save callback manager
        self._callback_manager = callback_manager
        
        # Register the global callback handler with the C++ engine
        engine = self._get_engine_instance()
        
        try:
            result = engine.register_callback(global_callback_handler)
            
            if result:
                self.logger.info("Callback manager registered successfully")
            else:
                self.logger.error("Failed to register callback manager")
            
            return result
        
        except Exception as e:
            self.logger.error(f"Error registering callback manager: {e}", exc_info=True)
            return False
    
    def process_day(self, date_str: str, max_window_size: int = 3600) -> Dict[str, Any]:
        """Process a single day of data.
        
        Args:
            date_str: Date string to process (YYYYMMDD format)
            max_window_size: Maximum window size in seconds for order book
            
        Returns:
            Results from processing the day
        """
        self.logger.info(f"Processing day {date_str} with max window size {max_window_size}")
        
        # Track performance if enabled
        if self.performance_monitor:
            self.performance_monitor.start_operation(f"cpp_process_day_{date_str}")
        
        try:
            # Get the engine instance for this thread
            engine = self._get_engine_instance()
            
            # Register the callback manager if not already done
            if self._callback_manager is not None and hasattr(engine, 'register_callback'):
                engine.register_callback(global_callback_handler)
            
            # Process the day
            result = engine.process_day(date_str, max_window_size)
            
            self.logger.info(f"Day {date_str} processed successfully")
            return result
        
        except Exception as e:
            self.logger.error(f"Error processing day {date_str}: {e}", exc_info=True)
            return {"status": "error", "date": date_str, "error": str(e)}
        
        finally:
            # End performance tracking
            if self.performance_monitor:
                self.performance_monitor.end_operation(f"cpp_process_day_{date_str}")
    
    def set_reference_data(self, reference_data: Dict[str, Any]) -> bool:
        """Set reference data for the C++ backtest engine.
        
        Args:
            reference_data: Reference data dictionary
            
        Returns:
            True if setting reference data was successful, False otherwise
        """
        self.logger.info("Setting reference data for C++ backtest engine")
        
        # Track performance if enabled
        if self.performance_monitor:
            self.performance_monitor.start_operation("set_reference_data")
        
        try:
            # Get the engine instance for this thread
            engine = self._get_engine_instance()
            
            # Set the reference data
            result = engine.set_reference_data(reference_data)
            
            if result:
                self.logger.info("Reference data set successfully")
            else:
                self.logger.error("Failed to set reference data")
            
            return result
        
        except Exception as e:
            self.logger.error(f"Error setting reference data: {e}", exc_info=True)
            return False
        
        finally:
            # End performance tracking
            if self.performance_monitor:
                self.performance_monitor.end_operation("set_reference_data")
    
    def _get_engine_instance(self) -> Any:
        """Get a thread-local engine instance.
        
        Returns:
            Thread-local engine instance
        """
        # Check if an instance already exists for this thread
        if not hasattr(self._thread_local, "engine"):
            # Create a new engine instance for this thread
            self._thread_local.engine = _CPPBacktestEngine()
            
            # Configure the engine with the current configuration
            if self._config:
                string_config = {k: str(v) for k, v in self._config.items()}
                self._thread_local.engine.configure(string_config)
            
            # Register the callback handler if a callback manager is set
            if self._callback_manager is not None:
                self._thread_local.engine.register_callback(global_callback_handler)
            
            # Track the thread ID for troubleshooting
            self._thread_local.thread_id = threading.get_ident()
            
            self.logger.debug(f"Created new engine instance for thread {self._thread_local.thread_id}")
        
        return self._thread_local.engine