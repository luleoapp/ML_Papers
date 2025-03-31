"""Python interface to the C++ backtest engine using pybind11."""

from datetime import datetime
from typing import Dict, List, Any, Optional, Union, Callable
import os
import sys
import threading
import numpy as np
import pandas as pd

from ..utils.logging_config import get_logger
from .callback_manager import (
    CallbackManager, global_callback_handler, 
    set_global_callback_manager, get_global_callback_manager
)

# Configure logger
logger = get_logger(__name__)

# Try to import the C++ extension
try:
    from ..cpp.backtest_engine import (
        BacktestEngine as _CPPBacktestEngine,
        ReferenceDataSet,
        ReferenceRecord,
        ValueType,
        register_marking_callback
    )
    _HAS_CPP_ENGINE = True
    logger.info("C++ extension loaded successfully")
except ImportError as e:
    _HAS_CPP_ENGINE = False
    logger.warning(f"C++ extension not found. Using mock implementation for development: {e}")
    
    # Define dummy types for development
    class ValueType:
        pass
    
    class ReferenceRecord(dict):
        pass
    
    class ReferenceDataSet(list):
        pass
    
    def register_marking_callback(callback_func):
        logger.warning("Mock implementation: register_marking_callback called")
        pass


class CPPBacktestEngine:
    """Interface to the C++ backtest engine.
    
    This class provides a Python interface to the C++ backtest engine, abstracting
    away the details of the C++ implementation. If the C++ extension is not available,
    it falls back to a mock implementation for development purposes.
    """
    
    def __init__(self, callback_manager: Optional[CallbackManager] = None):
        """Initialize the C++ backtest engine interface.
        
        Args:
            callback_manager: Optional callback manager for handling marking data callbacks
        """
        self.logger = get_logger(f"{__name__}.CPPBacktestEngine")
        self.logger.info("Initializing C++ backtest engine interface")
        
        self._config: Dict[str, Any] = {}
        self._callback_manager = callback_manager
        
        # Thread-local storage to ensure each thread has its own engine instance
        # when using parallel processing
        self._thread_local = threading.local()
        
        # Register the callback handler if we have a real engine
        if _HAS_CPP_ENGINE:
            # Set the global callback manager if provided
            if callback_manager:
                set_global_callback_manager(callback_manager)
                # Register the global callback handler with the C++ engine
                register_marking_callback(global_callback_handler)
                self.logger.info("Registered marking callback with C++ engine")
        else:
            self._mock_reference_data = {}
            self._mock_config_params = {}
            
            # Log that we're using a mock implementation
            self.logger.warning("Using mock implementation for C++ engine")
    
    def _get_engine_instance(self) -> Any:
        """Get a thread-local engine instance.
        
        This ensures that each thread has its own C++ engine instance,
        which is important for parallel processing.
        
        Returns:
            C++ engine instance
        """
        if not _HAS_CPP_ENGINE:
            return None
        
        if not hasattr(self._thread_local, "engine"):
            # Create a new engine instance for this thread
            self._thread_local.engine = _CPPBacktestEngine()
            
            # Configure the engine with the current configuration
            if self._config:
                string_config = {k: str(v) for k, v in self._config.items()}
                self._thread_local.engine.configure(string_config)
            
            self.logger.debug(f"Created new C++ engine instance for thread {threading.get_ident()}")
        
        return self._thread_local.engine
    
    def configure(self, config: Dict[str, Any]) -> None:
        """Configure the C++ engine.
        
        Args:
            config: Configuration dictionary
        """
        self.logger.info("Configuring C++ engine")
        self._config = config
        
        # Add max_window_size if it's not already in the config
        if "max_window_size" not in self._config:
            self._config["max_window_size"] = "3600"  # Default 1 hour in seconds
        
        if _HAS_CPP_ENGINE:
            # Convert all values to strings for the C++ engine
            string_config = {k: str(v) for k, v in config.items()}
            
            # Configure all existing engine instances
            if hasattr(self._thread_local, "engine"):
                self._thread_local.engine.configure(string_config)
        else:
            # Store the configuration for the mock implementation
            self._mock_config_params.update(config)
            
        self.logger.debug(f"Engine configured with parameters: {config}")
    
    def process_file(self, 
                     file_path: str, 
                     date_str: str, 
                     exchange: str, 
                     universe: List[str]) -> List[Dict[str, Any]]:
        """Process a tick data file and return results.
        
        Args:
            file_path: Path to the tick data file
            date_str: Date string in format YYYY-MM-DD
            exchange: Exchange name
            universe: List of symbols to process
            
        Returns:
            List of dictionaries containing the results
        """
        self.logger.debug(f"Processing file {file_path} for date {date_str} exchange {exchange}")
        
        if _HAS_CPP_ENGINE:
            # Get the thread-local engine instance
            engine = self._get_engine_instance()
            
            # Call the C++ engine to process the file
            return engine.process_file(file_path, date_str, exchange, universe)
        else:
            # Mock implementation for development
            return self._mock_process_file(file_path, date_str, exchange, universe)
    
    def register_reference_data(self, 
                              name: str, 
                              data: List[Dict[str, Any]]) -> bool:
        """Register reference data with the C++ engine.
        
        Args:
            name: Name to identify this reference data
            data: The reference data
            
        Returns:
            True if registration was successful
        """
        if _HAS_CPP_ENGINE:
            # Convert the data to C++ types
            return self._engine.register_reference_data(name, data)
        else:
            # Mock implementation
            self._mock_reference_data[name] = data
            print(f"MOCK: Registered reference data '{name}' with {len(data)} records")
            return True
    
    def get_reference_data_manager(self):
        """Get the reference data manager from the C++ engine.
        
        Returns:
            Reference data manager
        """
        if _HAS_CPP_ENGINE:
            return self._engine.get_reference_data_manager()
        else:
            # Return a mock manager
            return _MockReferenceDataManager(self._mock_reference_data)
    
    def get_engine_config(self):
        """Get the engine configuration from the C++ engine.
        
        Returns:
            Engine configuration
        """
        if _HAS_CPP_ENGINE:
            return self._engine.get_engine_config()
        else:
            # Return a mock config
            return _MockEngineConfig(self._mock_config_params)
    
    def set_config_parameter(self, key: str, value: Any) -> None:
        """Set a runtime configuration parameter.
        
        Args:
            key: Parameter name
            value: Parameter value
        """
        if _HAS_CPP_ENGINE:
            self._engine.set_config_parameter(key, value)
        else:
            # Mock implementation
            self._mock_config_params[key] = value
            print(f"MOCK: Set config parameter '{key}' to {value}")
    
    def get_config_parameter(self, key: str) -> Any:
        """Get a runtime configuration parameter.
        
        Args:
            key: Parameter name
            
        Returns:
            Parameter value
        """
        if _HAS_CPP_ENGINE:
            return self._engine.get_config_parameter(key)
        else:
            # Mock implementation
            return self._mock_config_params.get(key)
    
    def _mock_process_file(self, 
                          file_path: str, 
                          date_str: str, 
                          exchange: str, 
                          universe: List[str]) -> List[Dict[str, Any]]:
        """Mock implementation for development without the C++ engine.
        
        Args:
            file_path: Path to the tick data file
            date_str: Date string in format YYYY-MM-DD
            exchange: Exchange name
            universe: List of symbols to process
            
        Returns:
            Mock results
        """
        self.logger.info(f"MOCK: Processing file {file_path} for date {date_str} on exchange {exchange}")
        self.logger.debug(f"MOCK: Universe size: {len(universe)}")
        
        # Generate some mock results for development
        mock_results = []
        
        # Check if we have reference data
        has_universe = "universe" in self._mock_reference_data
        has_prices = "prices" in self._mock_reference_data
        has_risk_model = "risk_model" in self._mock_reference_data
        
        # Get max_window_size from config
        max_window_size = int(self._mock_config_params.get("max_window_size", 3600))
        self.logger.debug(f"MOCK: Using max_window_size of {max_window_size} seconds")
        
        # Generate mock marking data and send callbacks
        if self._callback_manager:
            # Generate batches of mock markings
            num_batches = 3  # Simulate multiple batches
            for batch_idx in range(num_batches):
                # Create a batch of markings
                markings_batch = []
                
                # Add markings for each symbol
                for symbol in universe:
                    # Create multiple markings per symbol
                    for i in range(5):  # 5 markings per symbol
                        # Create a marking with random values
                        marking = {
                            "ticker": symbol,
                            "trade_time": int(datetime.now().timestamp() * 1_000_000_000),  # nanoseconds
                            "price": 100.0 + np.random.randn(),
                            "qty": int(100 * np.random.random() + 10),
                            "marking1": int(np.random.choice([-1, 0, 1])),
                            "marking2": int(np.random.choice([-2, -1, 0, 1, 2])),
                            "marking3": np.random.randn() * 2.0
                        }
                        markings_batch.append(marking)
                
                # Send the batch to the callback manager
                if markings_batch:
                    self.logger.debug(f"MOCK: Sending batch of {len(markings_batch)} markings to callback manager")
                    self._callback_manager.process_marking_batch(markings_batch)
        
        # Generate mock trade results
        for symbol in universe[:min(5, len(universe))]:  # Limit to first 5 symbols to avoid too much output
            # Generate multiple results per symbol
            for i in range(5):
                time_str = f"{date_str}T{9 + i // 2:02d}:{30 + (i % 2) * 15:02d}:00.000000"
                
                result = {
                    "date": date_str,
                    "exchange": exchange,
                    "symbol": symbol,
                    "trade_id": i + 1,
                    "trade_time": time_str,
                    "trade_price": 100.0 + i * 0.1,
                    "trade_size": 100 + i * 10,
                    "trade_side": "buy" if i % 2 == 0 else "sell",
                    "return_10s": 0.001 * (i + 1),
                    "is_iso": bool(i % 2),
                    "bid_price_level2": 99.95 - i * 0.05,
                    "bid_size_level2": 200 + i * 20,
                    "ask_price_level3": 100.05 + i * 0.05,
                    "ask_size_level3": 300 + i * 30,
                    "max_window_size": max_window_size
                }
                
                # Add reference data info
                if has_universe:
                    result["has_universe_data"] = "true"
                if has_prices:
                    result["has_price_data"] = "true"
                if has_risk_model:
                    result["has_risk_model"] = "true"
                    
                mock_results.append(result)
        
        self.logger.info(f"MOCK: Generated {len(mock_results)} results")
        return mock_results


class _MockReferenceDataManager:
    """Mock implementation of the ReferenceDataManager for development."""
    
    def __init__(self, reference_data: Dict[str, List[Dict[str, Any]]]):
        """Initialize the mock reference data manager.
        
        Args:
            reference_data: Dictionary of reference data sets
        """
        self._reference_data = reference_data
    
    def register_reference_data(self, name: str, data: List[Dict[str, Any]]) -> bool:
        """Register a reference data set.
        
        Args:
            name: Name to identify this reference data set
            data: The reference data records
            
        Returns:
            True if registration was successful
        """
        self._reference_data[name] = data
        return True
    
    def get_reference_data(self, name: str) -> List[Dict[str, Any]]:
        """Get a reference data set by name.
        
        Args:
            name: Name of the reference data set
            
        Returns:
            The reference data set
        """
        return self._reference_data.get(name, [])
    
    def has_reference_data(self, name: str) -> bool:
        """Check if a reference data set exists.
        
        Args:
            name: Name of the reference data set
            
        Returns:
            True if the reference data set exists
        """
        return name in self._reference_data
    
    def get_reference_data_names(self) -> List[str]:
        """Get a list of all registered reference data set names.
        
        Returns:
            List of reference data set names
        """
        return list(self._reference_data.keys())
    
    def remove_reference_data(self, name: str) -> bool:
        """Remove a reference data set.
        
        Args:
            name: Name of the reference data set to remove
            
        Returns:
            True if the reference data set was removed
        """
        if name in self._reference_data:
            del self._reference_data[name]
            return True
        return False
    
    def clear_reference_data(self) -> None:
        """Clear all reference data sets."""
        self._reference_data.clear()
    
    def find_records(self, name: str, field: str, value: Any) -> List[Dict[str, Any]]:
        """Find records in a reference data set that match a filter.
        
        Args:
            name: Name of the reference data set
            field: Field to filter on
            value: Value to match
            
        Returns:
            List of matching records
        """
        data = self.get_reference_data(name)
        return [record for record in data if record.get(field) == value]
    
    def get_projection(self, name: str, fields: List[str]) -> List[Dict[str, Any]]:
        """Get a subset of a reference data set with only specific fields.
        
        Args:
            name: Name of the reference data set
            fields: Fields to include
            
        Returns:
            List of records with only the specified fields
        """
        data = self.get_reference_data(name)
        result = []
        
        for record in data:
            projected = {field: record.get(field) for field in fields if field in record}
            if projected:
                result.append(projected)
        
        return result


class _MockEngineConfig:
    """Mock implementation of the EngineConfig for development."""
    
    def __init__(self, parameters: Dict[str, Any]):
        """Initialize the mock engine configuration.
        
        Args:
            parameters: Dictionary of configuration parameters
        """
        self._parameters = parameters
    
    def set_parameter(self, key: str, value: Any) -> None:
        """Set a configuration parameter.
        
        Args:
            key: Parameter name
            value: Parameter value
        """
        self._parameters[key] = value
    
    def get_parameter(self, key: str) -> Any:
        """Get a configuration parameter.
        
        Args:
            key: Parameter name
            
        Returns:
            Parameter value
        """
        return self._parameters.get(key)
    
    def has_parameter(self, key: str) -> bool:
        """Check if a parameter exists.
        
        Args:
            key: Parameter name
            
        Returns:
            True if the parameter exists
        """
        return key in self._parameters
    
    def get_parameter_names(self) -> List[str]:
        """Get all parameter names.
        
        Returns:
            List of parameter names
        """
        return list(self._parameters.keys())
    
    def clear_parameters(self) -> None:
        """Clear all parameters."""
        self._parameters.clear()
