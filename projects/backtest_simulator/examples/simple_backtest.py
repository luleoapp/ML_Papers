#!/usr/bin/env python
"""Example script for running a simple backtest."""

import os
import sys
from pathlib import Path
import pandas as pd

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest_simulator import BacktestEngine


def run_simple_backtest():
    """Run a simple backtest with mock data."""
    # Initialize the engine
    engine = BacktestEngine()
    
    # Configure the engine
    engine.configure(
        start_date="2023-01-01",
        end_date="2023-01-31",
        exchanges=["XNAS"],
        universe=["AAPL", "MSFT", "GOOGL", "AMZN", "META"],
        # Since we don't have real data, we'll use the mock implementation
    )
    
    # Run the backtest
    print(f"Running backtest from 2023-01-01 to 2023-01-31...")
    results = engine.run()
    
    # Print some results
    print(f"Processed {len(results)} trades")
    
    if results:
        # Convert to DataFrame for analysis
        df = pd.DataFrame(results)
        print("\nSample results:")
        print(df.head())
        
        # Save the results
        os.makedirs("results", exist_ok=True)
        output_path = "results/simple_backtest.parquet"
        engine.save_results(output_path)
        print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    run_simple_backtest()