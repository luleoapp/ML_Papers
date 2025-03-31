"""Integration with existing trade data in DataStore."""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Union, Any, Tuple
from datetime import datetime, timedelta

from ..data.cloud_store import DataStoreClient


class TradeDataIntegrator:
    """Integrator for working with existing trade data in DataStore."""
    
    def __init__(self, 
                datastore_name: str = "prod",
                workspace: Optional[str] = None):
        """Initialize the trade data integrator.
        
        Args:
            datastore_name: Name of the datastore
            workspace: Name of the workspace
        """
        self.cloud_store = DataStoreClient(
            datastore_name=datastore_name, 
            workspace=workspace
        )
        self.cloud_store.connect()
    
    def get_trade_data(self, 
                      dataset_name: str, 
                      partition: str = "default",
                      start_date: Optional[Union[str, datetime]] = None,
                      end_date: Optional[Union[str, datetime]] = None,
                      symbols: Optional[List[str]] = None) -> pd.DataFrame:
        """Retrieve trade data from DataStore.
        
        Args:
            dataset_name: Name of the dataset
            partition: Partition to retrieve from
            start_date: Optional start date filter
            end_date: Optional end date filter
            symbols: Optional list of symbols to filter
            
        Returns:
            DataFrame with trade data
        """
        # Download the dataset
        df = self.cloud_store.download_dataset(
            dataset_name=dataset_name,
            partition=partition,
            format_type="pandas"
        )
        
        # Apply filters
        if start_date is not None:
            if isinstance(start_date, str):
                start_date = pd.to_datetime(start_date)
            df = df[df['trade_time'] >= start_date]
            
        if end_date is not None:
            if isinstance(end_date, str):
                end_date = pd.to_datetime(end_date)
            df = df[df['trade_time'] <= end_date]
            
        if symbols is not None:
            df = df[df['symbol'].isin(symbols)]
            
        return df
    
    def get_marked_trades(self, 
                         dataset_name: str, 
                         markers: List[str],
                         partition: str = "default",
                         start_date: Optional[Union[str, datetime]] = None,
                         end_date: Optional[Union[str, datetime]] = None,
                         symbols: Optional[List[str]] = None) -> pd.DataFrame:
        """Retrieve marked trades from DataStore.
        
        Args:
            dataset_name: Name of the dataset
            markers: List of marker columns to filter by (e.g., ['is_iso', 'is_sweep'])
            partition: Partition to retrieve from
            start_date: Optional start date filter
            end_date: Optional end date filter
            symbols: Optional list of symbols to filter
            
        Returns:
            DataFrame with marked trades
        """
        # Get all trades
        df = self.get_trade_data(
            dataset_name=dataset_name,
            partition=partition,
            start_date=start_date,
            end_date=end_date,
            symbols=symbols
        )
        
        # Filter for trades that have at least one of the markers
        mask = pd.Series(False, index=df.index)
        for marker in markers:
            if marker in df.columns:
                mask = mask | df[marker]
        
        return df[mask]
    
    def calculate_metrics(self, 
                        trade_dataset: str, 
                        markers: List[str],
                        partition: str = "default",
                        start_date: Optional[Union[str, datetime]] = None,
                        end_date: Optional[Union[str, datetime]] = None,
                        symbols: Optional[List[str]] = None,
                        output_dataset: Optional[str] = None) -> pd.DataFrame:
        """Calculate metrics from trade data and save to DataStore.
        
        Args:
            trade_dataset: Name of the trade dataset
            markers: List of marker columns
            partition: Partition to retrieve from
            start_date: Optional start date filter
            end_date: Optional end date filter
            symbols: Optional list of symbols to filter
            output_dataset: Optional name for output dataset
            
        Returns:
            DataFrame with calculated metrics
        """
        from .trade_metrics import TradeMetricsCalculator
        
        # Get trades and marked trades
        trades = self.get_trade_data(
            dataset_name=trade_dataset,
            partition=partition,
            start_date=start_date,
            end_date=end_date,
            symbols=symbols
        )
        
        marked_trades = self.get_marked_trades(
            dataset_name=trade_dataset,
            markers=markers,
            partition=partition,
            start_date=start_date,
            end_date=end_date,
            symbols=symbols
        )
        
        # Calculate metrics
        calculator = TradeMetricsCalculator()
        metrics = calculator.aggregate_minutely_data(trades, marked_trades)
        
        # Save results if output dataset is specified
        if output_dataset:
            self.cloud_store.upload_results(
                metrics,
                dataset_name=output_dataset,
                description=f"Minutely trade metrics from {start_date} to {end_date}",
                partition=f"metrics_{partition}"
            )
        
        return metrics