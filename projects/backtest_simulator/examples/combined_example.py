#!/usr/bin/env python
"""Example combining reference data and versioning in the backtest simulator."""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest_simulator import BacktestEngine
from backtest_simulator.analytics import TradeMetricsCalculator


def create_mock_data():
    """Create mock reference data for the example."""
    # Create a temporary directory for mock data
    temp_dir = Path("./mock_data")
    temp_dir.mkdir(exist_ok=True)
    
    # Create universe
    symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NFLX", "TSLA"]
    universe = []
    
    for symbol in symbols:
        universe.append({
            "ticker": symbol,
            "listing_exchange": "XNAS",
            "sector": np.random.choice(["Technology", "Consumer", "Communication"]),
            "market_cap": np.random.randint(100000, 3000000),
            "is_index_member": np.random.choice([True, False], p=[0.7, 0.3])
        })
    
    universe_df = pd.DataFrame(universe)
    universe_df.to_parquet(temp_dir / "universe.parquet")
    
    # Create price data
    today = datetime.now()
    start_date = today - timedelta(days=30)
    end_date = today - timedelta(days=1)
    
    prices = []
    date_range = pd.date_range(start=start_date, end=end_date, freq='B')
    
    for symbol in symbols:
        base_price = np.random.uniform(50, 500)
        price_series = np.cumsum(np.random.normal(0, 1, size=len(date_range))) * 0.01 * base_price + base_price
        
        for i, date in enumerate(date_range):
            prices.append({
                "ticker": symbol,
                "date": date.strftime("%Y-%m-%d"),
                "open": price_series[i] * (1 - 0.005 + 0.01 * np.random.random()),
                "high": price_series[i] * (1 + 0.01 * np.random.random()),
                "low": price_series[i] * (1 - 0.01 * np.random.random()),
                "close": price_series[i],
                "volume": np.random.randint(100000, 10000000)
            })
    
    prices_df = pd.DataFrame(prices)
    prices_df.to_parquet(temp_dir / "prices.parquet")
    
    return {
        "universe_path": temp_dir / "universe.parquet",
        "prices_path": temp_dir / "prices.parquet",
        "symbols": symbols,
        "temp_dir": temp_dir
    }


def run_combined_example():
    """Run an example combining reference data and versioning."""
    print("Creating mock data...")
    mock_data = create_mock_data()
    
    # Initialize the backtest engine with versioning
    engine = BacktestEngine(use_versioning=True)
    
    # Create marking configuration
    print("Creating marking configuration...")
    iso_marking = engine.create_marking_config(
        name="iso_marking",
        parameters={
            "threshold": 0.75,
            "min_size": 100,
            "max_levels": 3,
            "use_nbbo": True
        },
        version="1.0.0",
        description="ISO trade marking configuration"
    )
    
    # Configure the engine
    start_date = datetime.now() - timedelta(days=30)
    end_date = datetime.now() - timedelta(days=1)
    
    print("Configuring backtest engine...")
    engine.configure(
        start_date=start_date,
        end_date=end_date,
        exchanges=["XNAS"],
        universe=mock_data["symbols"],
        marking_configs=[iso_marking],
        run_description="Combined reference data and versioning example",
        run_tags=["example", "reference_data"]
    )
    
    # Load and register reference data
    print("Loading reference data...")
    universe_df = pd.read_parquet(mock_data["universe_path"])
    prices_df = pd.read_parquet(mock_data["prices_path"])
    
    print("Registering reference data with C++ engine...")
    engine.register_custom_data("universe", universe_df)
    engine.register_custom_data("prices", prices_df)
    
    # Configure additional parameters
    engine.set_config_parameters({
        "use_prices": True,
        "price_field": "close",
        "tick_size": 0.01,
        "max_order_book_levels": 10
    })
    
    # Store the current run ID
    run_id = engine.get_current_run_id()
    print(f"Current run ID: {run_id}")
    
    # Run the backtest
    print("Running backtest...")
    results = engine.run()
    
    # Save the results
    os.makedirs("results", exist_ok=True)
    output_path = "results/combined_example.parquet"
    engine.save_results(output_path, store_with_run=True)
    print(f"Results saved to {output_path}")
    
    # Calculate trade metrics
    if results:
        print("\nCalculating trade metrics...")
        trades_df = pd.DataFrame(results)
        
        calculator = TradeMetricsCalculator()
        
        # Extract subset of trades that are marked (e.g., ISO trades)
        has_marking = "is_iso" in trades_df.columns
        if has_marking:
            marked_trades = trades_df[trades_df["is_iso"] == True]
            if not marked_trades.empty:
                # Calculate minutely metrics with (Bx-Sx)/(Bx+Sx) formula
                minutely_metrics = calculator.aggregate_minutely_data(
                    trades_df, marked_trades
                )
                print("Minutely metrics calculated with trade imbalance formula")
                if not minutely_metrics.empty:
                    print("\nSample minutely metrics:")
                    print(minutely_metrics.head())
    
    # Demonstrate versioning capabilities
    print("\nDemonstrating versioning capabilities...")
    
    # Get versions
    versions = engine.list_run_versions()
    print(f"Found {len(versions)} run versions")
    
    # Create a modified run
    print("\nCreating modified run...")
    new_run_id = engine.rerun_version(
        run_id,
        override_params={"max_order_book_levels": 5},
        description="Modified run with reduced order book levels"
    )
    print(f"Created new run with ID: {new_run_id}")
    
    # Mark as production
    engine.mark_as_production(new_run_id)
    print(f"Marked run {new_run_id} as production")
    
    # Get production version
    prod_version = engine.get_production_version()
    if prod_version:
        print(f"Production version: {prod_version['version_id']}")
    
    # Get markings for a run
    markings = engine.get_markings_for_run(run_id)
    if markings:
        print("\nMarkings for run:")
        for marking in markings:
            print(f"  {marking['name']} v{marking['version']}")
    
    # Clean up
    print("\nCleaning up...")
    for file in mock_data["temp_dir"].glob("*.parquet"):
        file.unlink()
    mock_data["temp_dir"].rmdir()
    
    print("Example completed successfully.")


if __name__ == "__main__":
    run_combined_example()