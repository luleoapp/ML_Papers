"""Interface for working with reference data in the C++ engine."""

import os
import json
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Union, Any, Set, Tuple, Type, TypeVar, cast

import pandas as pd
import numpy as np

from ..data.reference_data import ReferenceDataManager


class DataType(Enum):
    """Types of values that can be passed to C++."""
    BOOL = "bool"
    INT = "int"
    DOUBLE = "double" 
    STRING = "string"
    BOOL_VECTOR = "bool_vector"
    INT_VECTOR = "int_vector" 
    DOUBLE_VECTOR = "double_vector"
    STRING_VECTOR = "string_vector"


class ReferenceDataInterface:
    """Interface for loading and registering reference data with the C++ engine."""
    
    def __init__(self, 
                cpp_engine,
                datastore_name: str = "prod",
                workspace: Optional[str] = None):
        """Initialize the reference data interface.
        
        Args:
            cpp_engine: C++ backtest engine instance
            datastore_name: Name of the datastore to use
            workspace: Workspace in the datastore
        """
        self.cpp_engine = cpp_engine
        
        # Initialize the Python-side reference data manager
        self.reference_manager = ReferenceDataManager(
            datastore_name=datastore_name,
            workspace=workspace
        )
        
        # Get the C++ reference data manager
        self.cpp_reference_manager = self.cpp_engine.get_reference_data_manager()
        
        # Get the C++ engine configuration
        self.cpp_engine_config = self.cpp_engine.get_engine_config()
    
    def load_and_register_universe(self, 
                                 dataset_name: str,
                                 partition: str = "default",
                                 reference_name: Optional[str] = None,
                                 filters: Optional[Dict[str, Any]] = None,
                                 required_fields: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Load a universe from DataStore and register it with the C++ engine.
        
        Args:
            dataset_name: Name of the dataset to load
            partition: Partition to load from
            reference_name: Name to register the data with (defaults to 'universe')
            filters: Optional filters to apply
            required_fields: Required fields for each entry
            
        Returns:
            The loaded universe data
        """
        # Set default reference name
        if reference_name is None:
            reference_name = "universe"
        
        # Load universe data
        universe_data = self.reference_manager.load_universe(
            dataset_name=dataset_name,
            partition=partition,
            filters=filters,
            required_fields=required_fields
        )
        
        # Register with the C++ engine
        self._register_dict_list_with_cpp(reference_name, universe_data)
        
        return universe_data
    
    def load_and_register_prices(self,
                               dataset_name: str,
                               symbols: List[str],
                               start_date: Union[str, pd.Timestamp],
                               end_date: Union[str, pd.Timestamp],
                               reference_name: Optional[str] = None,
                               price_field: str = "close",
                               partition: str = "default") -> pd.DataFrame:
        """Load price data and register it with the C++ engine.
        
        Args:
            dataset_name: Name of the dataset to load
            symbols: List of symbols to load prices for
            start_date: Start date for the price data
            end_date: End date for the price data
            reference_name: Name to register the data with (defaults to 'prices')
            price_field: Field to use for prices (e.g., 'close', 'open')
            partition: Partition to load from
            
        Returns:
            The loaded price data
        """
        # Set default reference name
        if reference_name is None:
            reference_name = "prices"
        
        # Load price data
        price_data = self.reference_manager.load_price_data(
            dataset_name=dataset_name,
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            price_field=price_field,
            partition=partition
        )
        
        # Register with the C++ engine
        self._register_dataframe_with_cpp(reference_name, price_data)
        
        return price_data
    
    def load_and_register_risk_model(self,
                                   dataset_name: str,
                                   model_date: Union[str, pd.Timestamp],
                                   reference_name: Optional[str] = None,
                                   symbols: Optional[List[str]] = None,
                                   factors: Optional[List[str]] = None,
                                   partition: str = "default") -> Dict[str, Any]:
        """Load a risk model and register it with the C++ engine.
        
        Args:
            dataset_name: Name of the dataset to load
            model_date: Date of the risk model
            reference_name: Name to register the data with (defaults to 'risk_model')
            symbols: Optional list of symbols to filter
            factors: Optional list of factors to include
            partition: Partition to load from
            
        Returns:
            The loaded risk model data
        """
        # Set default reference name
        if reference_name is None:
            reference_name = "risk_model"
        
        # Load risk model
        risk_model = self.reference_manager.load_risk_model(
            dataset_name=dataset_name,
            model_date=model_date,
            symbols=symbols,
            factors=factors,
            partition=partition
        )
        
        # Risk model is a complex nested structure, so we need to flatten it
        # to register with C++. We'll register each component separately.
        
        # Register date info
        self._set_config_parameter(f"{reference_name}_date", risk_model["date"])
        
        # Register factor returns
        factor_returns = []
        for factor, ret in risk_model["factor_returns"].items():
            factor_returns.append({
                "factor": factor,
                "return": ret
            })
        self._register_dict_list_with_cpp(f"{reference_name}_factor_returns", factor_returns)
        
        # Register exposures (factor loadings)
        exposures = []
        for ticker, factors in risk_model["exposures"].items():
            for factor, exposure in factors.items():
                exposures.append({
                    "ticker": ticker,
                    "factor": factor,
                    "exposure": exposure
                })
        self._register_dict_list_with_cpp(f"{reference_name}_exposures", exposures)
        
        # Register specific risk
        specific_risks = []
        for ticker, risk in risk_model["specific_risk"].items():
            specific_risks.append({
                "ticker": ticker,
                "specific_risk": risk
            })
        self._register_dict_list_with_cpp(f"{reference_name}_specific_risks", specific_risks)
        
        # Register factor covariance matrix
        factor_cov = []
        for factor1, factors in risk_model["factor_covariance"].items():
            for factor2, cov in factors.items():
                factor_cov.append({
                    "factor1": factor1,
                    "factor2": factor2,
                    "covariance": cov
                })
        self._register_dict_list_with_cpp(f"{reference_name}_factor_covariance", factor_cov)
        
        return risk_model
    
    def load_and_register_generic(self,
                                dataset_name: str,
                                reference_name: str,
                                partition: str = "default",
                                filters: Optional[Dict[str, Any]] = None,
                                as_records: bool = True) -> Union[List[Dict[str, Any]], pd.DataFrame]:
        """Load generic reference data and register it with the C++ engine.
        
        Args:
            dataset_name: Name of the dataset to load
            reference_name: Name to register the data with
            partition: Partition to load from
            filters: Optional filters to apply
            as_records: Whether to return data as records or DataFrame
            
        Returns:
            The loaded reference data
        """
        # Load reference data
        data = self.reference_manager.load_reference_data(
            dataset_name=dataset_name,
            partition=partition,
            filters=filters,
            as_records=as_records
        )
        
        # Register with the C++ engine
        if as_records:
            self._register_dict_list_with_cpp(reference_name, data)
        else:
            self._register_dataframe_with_cpp(reference_name, data)
        
        return data
    
    def load_multiple_reference_sets(self, data_requests: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Load and register multiple reference datasets in one operation.
        
        Args:
            data_requests: List of data request specifications
            
        Returns:
            Dictionary mapping reference set names to loaded data
        """
        # Load the reference data
        result = self.reference_manager.load_multiple_reference_sets(data_requests)
        
        # Register each dataset with the C++ engine
        for request in data_requests:
            name = request.get('name')
            data = result.get(name)
            
            if data is not None:
                data_type = request.get('type', 'generic')
                
                if data_type == 'universe' or isinstance(data, list):
                    self._register_dict_list_with_cpp(name, data)
                elif isinstance(data, pd.DataFrame):
                    self._register_dataframe_with_cpp(name, data)
                elif isinstance(data, dict):
                    # For complex structures like risk models, we don't auto-register
                    # They should be handled separately
                    pass
        
        return result
    
    def register_custom_data(self, 
                           reference_name: str, 
                           data: Union[List[Dict[str, Any]], pd.DataFrame]) -> None:
        """Register custom data with the C++ engine.
        
        Args:
            reference_name: Name to register the data with
            data: Data to register (list of dicts or DataFrame)
        """
        if isinstance(data, pd.DataFrame):
            self._register_dataframe_with_cpp(reference_name, data)
        else:
            self._register_dict_list_with_cpp(reference_name, data)
    
    def set_config_parameters(self, config: Dict[str, Any]) -> None:
        """Set multiple configuration parameters at once.
        
        Args:
            config: Dictionary of configuration parameters
        """
        for key, value in config.items():
            self._set_config_parameter(key, value)
    
    def _register_dict_list_with_cpp(self, 
                                   reference_name: str, 
                                   data: List[Dict[str, Any]]) -> None:
        """Register a list of dictionaries with the C++ engine.
        
        Args:
            reference_name: Name to register the data with
            data: List of dictionaries to register
        """
        if not data:
            print(f"Warning: Empty data for {reference_name}")
            return
        
        # Create C++ reference data set
        cpp_data = []
        
        # Process each record
        for record_dict in data:
            cpp_record = {}
            
            # Convert each field based on its type
            for key, value in record_dict.items():
                if value is None:
                    continue
                
                # Convert to appropriate C++ type
                if isinstance(value, bool):
                    cpp_record[key] = value
                elif isinstance(value, int):
                    cpp_record[key] = value
                elif isinstance(value, float):
                    cpp_record[key] = value
                elif isinstance(value, str):
                    cpp_record[key] = value
                elif isinstance(value, list) or isinstance(value, np.ndarray):
                    # Convert list to the appropriate vector type
                    if len(value) > 0:
                        if isinstance(value[0], bool):
                            cpp_record[key] = list(value)
                        elif isinstance(value[0], int):
                            cpp_record[key] = list(value)
                        elif isinstance(value[0], float):
                            cpp_record[key] = list(value)
                        elif isinstance(value[0], str):
                            cpp_record[key] = list(value)
                elif isinstance(value, dict):
                    # Skip dictionaries for now (not directly supported in ValueType)
                    # Complex nested structures should be flattened or serialized
                    pass
                else:
                    # Try to convert to string as fallback
                    try:
                        cpp_record[key] = str(value)
                    except:
                        pass
            
            if cpp_record:
                cpp_data.append(cpp_record)
        
        # Register with C++ engine
        self.cpp_reference_manager.register_reference_data(reference_name, cpp_data)
    
    def _register_dataframe_with_cpp(self, 
                                   reference_name: str, 
                                   df: pd.DataFrame) -> None:
        """Register a pandas DataFrame with the C++ engine.
        
        Args:
            reference_name: Name to register the data with
            df: DataFrame to register
        """
        if df.empty:
            print(f"Warning: Empty DataFrame for {reference_name}")
            return
        
        # Convert DataFrame to list of dictionaries
        records = df.to_dict('records')
        
        # Register with C++ engine
        self._register_dict_list_with_cpp(reference_name, records)
    
    def _set_config_parameter(self, key: str, value: Any) -> None:
        """Set a configuration parameter in the C++ engine.
        
        Args:
            key: Parameter name
            value: Parameter value
        """
        # Convert value to the appropriate C++ type
        if isinstance(value, bool):
            self.cpp_engine.set_config_parameter(key, value)
        elif isinstance(value, int):
            self.cpp_engine.set_config_parameter(key, value)
        elif isinstance(value, float):
            self.cpp_engine.set_config_parameter(key, value)
        elif isinstance(value, str):
            self.cpp_engine.set_config_parameter(key, value)
        elif isinstance(value, list) or isinstance(value, np.ndarray):
            # Convert list to the appropriate vector type
            if len(value) > 0:
                if isinstance(value[0], bool):
                    self.cpp_engine.set_config_parameter(key, list(value))
                elif isinstance(value[0], int):
                    self.cpp_engine.set_config_parameter(key, list(value))
                elif isinstance(value[0], float):
                    self.cpp_engine.set_config_parameter(key, list(value))
                elif isinstance(value[0], str):
                    self.cpp_engine.set_config_parameter(key, list(value))
        else:
            # Try to convert to string as fallback
            try:
                self.cpp_engine.set_config_parameter(key, str(value))
            except:
                print(f"Warning: Could not set config parameter {key}")
    
    def get_config_parameter(self, key: str) -> Any:
        """Get a configuration parameter from the C++ engine.
        
        Args:
            key: Parameter name
            
        Returns:
            Parameter value
        """
        return self.cpp_engine.get_config_parameter(key)