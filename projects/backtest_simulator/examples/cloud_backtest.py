#!/usr/bin/env python
"""Example script for running a backtest with cloud storage."""

import os
import sys
from pathlib import Path
import pandas as pd

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest_simulator import BacktestEngine


def run_cloud_backtest():
    """Run a backtest and store results in the cloud."""
    # Initialize the engine with cloud storage enabled
    engine = BacktestEngine(use_cloud_store=True)
    
    # Configure the engine with cloud settings
    engine.configure(
        start_date="2023-01-01",
        end_date="2023-01-31",
        exchanges=["XNAS"],
        universe=["AAPL", "MSFT", "GOOGL", "AMZN", "META"],
        # Cloud DataStore settings
        datastore_name="prod",
        workspace="my_workspace"
    )
    
    # Run the backtest
    print(f"Running backtest from 2023-01-01 to 2023-01-31...")
    results = engine.run()
    
    # Print some results
    print(f"Processed {len(results)} trades")
    
    if results:
        # Save to local storage
        os.makedirs("results", exist_ok=True)
        output_path = "results/cloud_backtest.parquet"
        engine.save_results(output_path)
        print(f"Results saved locally to {output_path}")
        
        # Save to cloud storage as pandas DataFrame
        engine.save_results_to_cloud(
            dataset_name="backtest_results",
            description="Backtest results for NASDAQ tech stocks",
            partition="2023_01"
        )
        print("Results saved to cloud storage as pandas DataFrame")
        
        # Save to cloud storage as xarray Dataset
        engine.save_xarray_results_to_cloud(
            dataset_name="backtest_results_xarray",
            description="Backtest results for NASDAQ tech stocks as xarray",
            partition="2023_01"
        )
        print("Results saved to cloud storage as xarray Dataset")
        
        # Load existing results from cloud
        print("\nLoading results from cloud storage...")
        cloud_results = engine.load_from_cloud(
            dataset_name="backtest_results",
            partition="2023_01",
            format_type="pandas"
        )
        print(f"Loaded {len(cloud_results)} rows from cloud storage")
        
        # Load xarray results from cloud
        cloud_xarray = engine.load_from_cloud(
            dataset_name="backtest_results_xarray",
            partition="2023_01",
            format_type="xarray"
        )
        print(f"Loaded xarray Dataset with variables: {list(cloud_xarray.data_vars)}")


if __name__ == "__main__":
    run_cloud_backtest()