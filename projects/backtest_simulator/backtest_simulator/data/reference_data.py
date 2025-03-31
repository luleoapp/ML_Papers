"""Reference data loading and management for backtest engine."""

import os
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union, Any, Tuple, Set

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from .cloud_store import DataStoreClient


class ReferenceDataManager:
    """Manager for loading and accessing reference data."""
    
    def __init__(self, 
                 datastore_name: str = "prod",
                 workspace: Optional[str] = None,
                 cache_dir: Optional[str] = None):
        """Initialize the reference data manager.
        
        Args:
            datastore_name: Name of the datastore to use
            workspace: Workspace in the datastore
            cache_dir: Directory to cache reference data locally
        """
        self.datastore_name = datastore_name
        self.workspace = workspace
        
        # Set up local cache
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            self.cache_dir = Path.home() / ".backtest_cache" / "reference_data"
        
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize DataStore client
        self.cloud_store = DataStoreClient(
            datastore_name=datastore_name,
            workspace=workspace
        )
        self.cloud_store.connect()
        
        # In-memory cache for loaded data
        self._memory_cache: Dict[str, Any] = {}
    
    def load_reference_data(self, 
                           dataset_name: str,
                           partition: str = "default",
                           filters: Optional[Dict[str, Any]] = None,
                           as_records: bool = True,
                           use_cache: bool = True,
                           cache_name: Optional[str] = None) -> Union[List[Dict[str, Any]], pd.DataFrame]:
        """Load reference data from DataStore.
        
        Args:
            dataset_name: Name of the dataset to load
            partition: Partition in the dataset
            filters: Optional filters to apply to the data
            as_records: Whether to return as list of dictionaries (True) or DataFrame (False)
            use_cache: Whether to use the cache
            cache_name: Optional name for the cache entry
            
        Returns:
            Reference data as a list of dictionaries or DataFrame
        """
        # Generate cache key
        cache_key = cache_name or f"{dataset_name}_{partition}"
        if filters:
            filter_str = "_".join(f"{k}_{v}" for k, v in sorted(filters.items()))
            cache_key += f"_{filter_str}"
        
        # Check memory cache
        if use_cache and cache_key in self._memory_cache:
            data = self._memory_cache[cache_key]
            if as_records and isinstance(data, pd.DataFrame):
                return data.to_dict('records')
            elif not as_records and isinstance(data, list):
                return pd.DataFrame(data)
            return data
        
        # Check disk cache
        cache_path = self.cache_dir / f"{cache_key}.parquet"
        if use_cache and cache_path.exists():
            try:
                df = pd.read_parquet(cache_path)
                
                # Apply filters if provided
                if filters:
                    for key, value in filters.items():
                        if key in df.columns:
                            if isinstance(value, (list, tuple, set)):
                                df = df[df[key].isin(value)]
                            else:
                                df = df[df[key] == value]
                
                # Store in memory cache
                self._memory_cache[cache_key] = df
                
                # Return in requested format
                if as_records:
                    return df.to_dict('records')
                return df
            except Exception as e:
                print(f"Error loading from cache: {e}")
        
        # Load from DataStore
        try:
            df = self.cloud_store.download_dataset(
                dataset_name=dataset_name,
                partition=partition,
                format_type="pandas"
            )
            
            # Apply filters if provided
            if filters:
                for key, value in filters.items():
                    if key in df.columns:
                        if isinstance(value, (list, tuple, set)):
                            df = df[df[key].isin(value)]
                        else:
                            df = df[df[key] == value]
            
            # Cache the data
            df.to_parquet(cache_path)
            self._memory_cache[cache_key] = df
            
            # Return in requested format
            if as_records:
                return df.to_dict('records')
            return df
        except Exception as e:
            raise RuntimeError(f"Error loading reference data: {e}")
    
    def load_universe(self, 
                     dataset_name: str,
                     partition: str = "default",
                     filters: Optional[Dict[str, Any]] = None,
                     required_fields: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Load a universe of symbols from DataStore.
        
        This is a specialized method for loading symbol universes.
        
        Args:
            dataset_name: Name of the dataset containing the universe
            partition: Partition in the dataset
            filters: Optional filters to apply to the universe
            required_fields: Required fields for each symbol entry
            
        Returns:
            Universe as a list of dictionaries
        """
        # Define standard required fields if not provided
        if required_fields is None:
            required_fields = ["ticker", "listing_exchange"]
        
        # Load universe data
        universe_data = self.load_reference_data(
            dataset_name=dataset_name,
            partition=partition,
            filters=filters,
            as_records=True,
            cache_name=f"universe_{dataset_name}_{partition}"
        )
        
        # Validate universe data
        valid_records = []
        for record in universe_data:
            # Check that all required fields are present
            if all(field in record for field in required_fields):
                valid_records.append(record)
            else:
                missing = [field for field in required_fields if field not in record]
                print(f"Skipping record with missing fields: {missing}")
        
        return valid_records
    
    def load_price_data(self,
                       dataset_name: str,
                       symbols: List[str],
                       start_date: Union[str, datetime],
                       end_date: Union[str, datetime],
                       price_field: str = "close",
                       partition: str = "default") -> pd.DataFrame:
        """Load historical price data for a list of symbols.
        
        Args:
            dataset_name: Name of the dataset containing price data
            symbols: List of symbols to load prices for
            start_date: Start date for the price data
            end_date: End date for the price data
            price_field: Field to use for prices (e.g., 'close', 'open')
            partition: Partition in the dataset
            
        Returns:
            DataFrame with price data
        """
        # Convert dates to strings if they're datetime objects
        if isinstance(start_date, datetime):
            start_date = start_date.strftime("%Y-%m-%d")
        if isinstance(end_date, datetime):
            end_date = end_date.strftime("%Y-%m-%d")
        
        # Create a cache key for this request
        symbol_str = "_".join(sorted(symbols)) if len(symbols) <= 5 else f"{len(symbols)}_symbols"
        cache_key = f"prices_{dataset_name}_{partition}_{start_date}_{end_date}_{symbol_str}"
        
        # Try to load from cache
        cache_path = self.cache_dir / f"{cache_key}.parquet"
        if cache_path.exists():
            try:
                return pd.read_parquet(cache_path)
            except Exception:
                pass
        
        # Load from DataStore
        df = self.cloud_store.download_dataset(
            dataset_name=dataset_name,
            partition=partition,
            format_type="pandas"
        )
        
        # Filter by date and symbols
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
            df = df[(df['date'] >= start_date) & (df['date'] <= end_date)]
        
        # Filter by symbols
        symbol_col = 'ticker'
        if symbol_col in df.columns:
            df = df[df[symbol_col].isin(symbols)]
        
        # Cache the filtered data
        df.to_parquet(cache_path)
        
        return df
    
    def load_risk_model(self,
                       dataset_name: str,
                       model_date: Union[str, datetime],
                       symbols: Optional[List[str]] = None,
                       factors: Optional[List[str]] = None,
                       partition: str = "default") -> Dict[str, Any]:
        """Load a risk model for a specific date.
        
        Args:
            dataset_name: Name of the dataset containing the risk model
            model_date: Date of the risk model
            symbols: Optional list of symbols to filter the model
            factors: Optional list of factors to include
            partition: Partition in the dataset
            
        Returns:
            Dictionary with risk model components
        """
        # Convert date to string if it's a datetime object
        if isinstance(model_date, datetime):
            model_date_str = model_date.strftime("%Y-%m-%d")
        else:
            model_date_str = model_date
        
        # Create a cache key for this request
        cache_key = f"risk_model_{dataset_name}_{partition}_{model_date_str}"
        
        # Try to load from cache
        cache_path = self.cache_dir / f"{cache_key}.json"
        if cache_path.exists():
            try:
                with open(cache_path, 'r') as f:
                    model_data = json.load(f)
                return model_data
            except Exception:
                pass
        
        # Load from DataStore
        df = self.cloud_store.download_dataset(
            dataset_name=dataset_name,
            partition=partition,
            format_type="pandas"
        )
        
        # Filter by date
        date_col = 'date'
        if date_col in df.columns:
            df['date'] = pd.to_datetime(df['date'])
            df = df[df['date'] == model_date_str]
        
        # Filter by symbols if provided
        if symbols and 'ticker' in df.columns:
            df = df[df['ticker'].isin(symbols)]
        
        # Convert to a structured dictionary
        model_data = {
            'date': model_date_str,
            'exposures': {},
            'factor_returns': {},
            'factor_covariance': {},
            'specific_risk': {}
        }
        
        # Extract exposures (factor loadings)
        if 'ticker' in df.columns and 'factor' in df.columns and 'exposure' in df.columns:
            exposures_df = df[['ticker', 'factor', 'exposure']].copy()
            
            # Filter factors if provided
            if factors:
                exposures_df = exposures_df[exposures_df['factor'].isin(factors)]
            
            # Pivot to get factor loadings in a matrix form
            exposures_pivot = exposures_df.pivot(index='ticker', columns='factor', values='exposure')
            model_data['exposures'] = exposures_pivot.to_dict(orient='index')
        
        # Extract factor returns if available
        if 'factor' in df.columns and 'return' in df.columns:
            factor_returns_df = df[['factor', 'return']].drop_duplicates()
            
            # Filter factors if provided
            if factors:
                factor_returns_df = factor_returns_df[factor_returns_df['factor'].isin(factors)]
            
            model_data['factor_returns'] = dict(zip(factor_returns_df['factor'], factor_returns_df['return']))
        
        # Extract factor covariance if available
        if 'factor1' in df.columns and 'factor2' in df.columns and 'covariance' in df.columns:
            factor_cov_df = df[['factor1', 'factor2', 'covariance']].copy()
            
            # Filter factors if provided
            if factors:
                factor_cov_df = factor_cov_df[
                    factor_cov_df['factor1'].isin(factors) & 
                    factor_cov_df['factor2'].isin(factors)
                ]
            
            # Convert to a nested dictionary
            factor_cov = {}
            for _, row in factor_cov_df.iterrows():
                if row['factor1'] not in factor_cov:
                    factor_cov[row['factor1']] = {}
                factor_cov[row['factor1']][row['factor2']] = row['covariance']
            
            model_data['factor_covariance'] = factor_cov
        
        # Extract specific risk if available
        if 'ticker' in df.columns and 'specific_risk' in df.columns:
            specific_risk_df = df[['ticker', 'specific_risk']].drop_duplicates()
            
            # Filter symbols if provided
            if symbols:
                specific_risk_df = specific_risk_df[specific_risk_df['ticker'].isin(symbols)]
            
            model_data['specific_risk'] = dict(zip(specific_risk_df['ticker'], specific_risk_df['specific_risk']))
        
        # Cache the model data
        with open(cache_path, 'w') as f:
            json.dump(model_data, f)
        
        return model_data
    
    def load_multiple_reference_sets(self, 
                                    data_requests: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Load multiple reference datasets in one operation.
        
        Args:
            data_requests: List of data request specifications, each containing:
                - name: Name for this reference set
                - dataset_name: Dataset to load from
                - partition: Partition to load from
                - type: Type of data ('universe', 'prices', 'risk_model', or 'generic')
                - Additional parameters specific to the data type
            
        Returns:
            Dictionary mapping reference set names to loaded data
        """
        reference_data = {}
        
        for request in data_requests:
            name = request.get('name')
            if not name:
                raise ValueError("Each data request must have a 'name' field")
            
            dataset_name = request.get('dataset_name')
            if not dataset_name:
                raise ValueError(f"Data request '{name}' must have a 'dataset_name' field")
            
            partition = request.get('partition', 'default')
            data_type = request.get('type', 'generic')
            
            try:
                if data_type == 'universe':
                    # Load universe
                    filters = request.get('filters')
                    required_fields = request.get('required_fields')
                    
                    reference_data[name] = self.load_universe(
                        dataset_name=dataset_name,
                        partition=partition,
                        filters=filters,
                        required_fields=required_fields
                    )
                
                elif data_type == 'prices':
                    # Load price data
                    symbols = request.get('symbols')
                    if not symbols:
                        raise ValueError(f"Price data request '{name}' must specify 'symbols'")
                    
                    start_date = request.get('start_date')
                    if not start_date:
                        raise ValueError(f"Price data request '{name}' must specify 'start_date'")
                    
                    end_date = request.get('end_date')
                    if not end_date:
                        raise ValueError(f"Price data request '{name}' must specify 'end_date'")
                    
                    price_field = request.get('price_field', 'close')
                    
                    reference_data[name] = self.load_price_data(
                        dataset_name=dataset_name,
                        symbols=symbols,
                        start_date=start_date,
                        end_date=end_date,
                        price_field=price_field,
                        partition=partition
                    )
                
                elif data_type == 'risk_model':
                    # Load risk model
                    model_date = request.get('model_date')
                    if not model_date:
                        raise ValueError(f"Risk model request '{name}' must specify 'model_date'")
                    
                    symbols = request.get('symbols')
                    factors = request.get('factors')
                    
                    reference_data[name] = self.load_risk_model(
                        dataset_name=dataset_name,
                        model_date=model_date,
                        symbols=symbols,
                        factors=factors,
                        partition=partition
                    )
                
                else:
                    # Generic reference data
                    filters = request.get('filters')
                    as_records = request.get('as_records', True)
                    use_cache = request.get('use_cache', True)
                    
                    reference_data[name] = self.load_reference_data(
                        dataset_name=dataset_name,
                        partition=partition,
                        filters=filters,
                        as_records=as_records,
                        use_cache=use_cache
                    )
            
            except Exception as e:
                print(f"Error loading reference data '{name}': {e}")
                reference_data[name] = None
        
        return reference_data
    
    def clear_cache(self, pattern: Optional[str] = None) -> int:
        """Clear the reference data cache.
        
        Args:
            pattern: Optional pattern to match cache files to clear
                     If None, all cache files are cleared
        
        Returns:
            Number of cache files cleared
        """
        # Clear memory cache
        if pattern:
            keys_to_remove = [k for k in self._memory_cache if pattern in k]
            for k in keys_to_remove:
                del self._memory_cache[k]
        else:
            self._memory_cache.clear()
        
        # Clear disk cache
        count = 0
        if pattern:
            for cache_file in self.cache_dir.glob(f"*{pattern}*"):
                if cache_file.is_file():
                    cache_file.unlink()
                    count += 1
        else:
            for cache_file in self.cache_dir.glob("*"):
                if cache_file.is_file():
                    cache_file.unlink()
                    count += 1
        
        return count