#!/usr/bin/env python
"""Example script for using reference data with the backtest engine."""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest_simulator import BacktestEngine


def create_mock_universe():
    """Create a mock universe for testing."""
    universe = []
    symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NFLX", "TSLA", "NVDA", "AMD", "INTC"]
    exchanges = ["XNAS", "XNYS"]
    
    for symbol in symbols:
        exchange = exchanges[0] if np.random.random() > 0.3 else exchanges[1]
        universe.append({
            "ticker": symbol,
            "listing_exchange": exchange,
            "sector": np.random.choice(["Technology", "Consumer", "Communication"]),
            "market_cap": np.random.randint(100000, 3000000),
            "is_index_member": np.random.choice([True, False], p=[0.7, 0.3]),
            "price": np.random.uniform(50, 500)
        })
    
    return universe


def create_mock_prices(symbols, start_date, end_date):
    """Create mock price data for a list of symbols."""
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
    
    return pd.DataFrame(prices)


def create_mock_risk_model(symbols, date):
    """Create a mock risk model for a specific date."""
    # Define factors
    factors = ["Market", "Size", "Value", "Momentum", "Volatility"]
    
    # Create exposures (factor loadings)
    exposures = {}
    for symbol in symbols:
        exposures[symbol] = {}
        for factor in factors:
            exposures[symbol][factor] = np.random.normal(0, 1)
    
    # Create factor returns
    factor_returns = {}
    for factor in factors:
        factor_returns[factor] = np.random.normal(0, 0.01)
    
    # Create factor covariance matrix
    factor_covariance = {}
    for factor1 in factors:
        factor_covariance[factor1] = {}
        for factor2 in factors:
            if factor1 == factor2:
                factor_covariance[factor1][factor2] = np.random.uniform(0.01, 0.05)
            else:
                # Ensure symmetry
                if factor2 in factor_covariance and factor1 in factor_covariance[factor2]:
                    factor_covariance[factor1][factor2] = factor_covariance[factor2][factor1]
                else:
                    factor_covariance[factor1][factor2] = np.random.uniform(-0.01, 0.01)
    
    # Create specific risk
    specific_risk = {}
    for symbol in symbols:
        specific_risk[symbol] = np.random.uniform(0.1, 0.3)
    
    # Put everything together
    risk_model = {
        "date": date.strftime("%Y-%m-%d"),
        "exposures": exposures,
        "factor_returns": factor_returns,
        "factor_covariance": factor_covariance,
        "specific_risk": specific_risk
    }
    
    return risk_model


def create_mock_reference_data():
    """Create mock reference datasets for testing."""
    # Create a temporary directory to store the mock data
    temp_dir = Path("./mock_data")
    temp_dir.mkdir(exist_ok=True)
    
    # Create universe data
    universe = create_mock_universe()
    universe_df = pd.DataFrame(universe)
    universe_df.to_parquet(temp_dir / "universe.parquet")
    
    # Create price data
    symbols = [rec["ticker"] for rec in universe]
    today = datetime.now()
    start_date = today - timedelta(days=30)
    end_date = today - timedelta(days=1)
    prices = create_mock_prices(symbols, start_date, end_date)
    prices.to_parquet(temp_dir / "prices.parquet")
    
    # Create risk model data
    risk_model = create_mock_risk_model(symbols, start_date)
    
    return {
        "universe_path": temp_dir / "universe.parquet",
        "prices_path": temp_dir / "prices.parquet",
        "risk_model": risk_model,
        "temp_dir": temp_dir
    }


def run_example():
    """Run the reference data example."""
    print("Creating mock reference data...")
    mock_data = create_mock_reference_data()
    
    # Initialize the backtest engine
    engine = BacktestEngine()
    
    # Configure the engine
    start_date = datetime.now() - timedelta(days=30)
    end_date = datetime.now() - timedelta(days=1)
    
    print("Configuring engine...")
    engine.configure(
        start_date=start_date,
        end_date=end_date,
        exchanges=["XNAS", "XNYS"],
        universe=None  # We'll load the universe separately
    )
    
    # Register the mock universe data
    print("\nLoading and registering universe data...")
    universe_df = pd.read_parquet(mock_data["universe_path"])
    engine.register_custom_data("universe", universe_df)
    
    # List the symbols in the universe
    tickers = universe_df["ticker"].tolist()
    print(f"Universe contains {len(tickers)} symbols: {', '.join(tickers)}")
    
    # Register the mock price data
    print("\nLoading and registering price data...")
    prices_df = pd.read_parquet(mock_data["prices_path"])
    engine.register_custom_data("prices", prices_df)
    
    # Calculate some price statistics
    price_stats = prices_df.groupby("ticker")["close"].agg(["mean", "min", "max"]).reset_index()
    print("Price statistics:")
    print(price_stats)
    
    # Register the mock risk model
    print("\nRegistering risk model data...")
    
    # First, we need to register the risk model components separately
    # since the risk model is a complex nested structure
    
    # 1. Register factor returns
    factor_returns = []
    for factor, ret in mock_data["risk_model"]["factor_returns"].items():
        factor_returns.append({
            "factor": factor,
            "return": ret
        })
    engine.register_custom_data("risk_model_factor_returns", factor_returns)
    
    # 2. Register exposures
    exposures = []
    for ticker, factors in mock_data["risk_model"]["exposures"].items():
        for factor, exposure in factors.items():
            exposures.append({
                "ticker": ticker,
                "factor": factor,
                "exposure": exposure
            })
    engine.register_custom_data("risk_model_exposures", exposures)
    
    # 3. Register specific risk
    specific_risks = []
    for ticker, risk in mock_data["risk_model"]["specific_risk"].items():
        specific_risks.append({
            "ticker": ticker,
            "specific_risk": risk
        })
    engine.register_custom_data("risk_model_specific_risks", specific_risks)
    
    # Print the first few exposures for demonstration
    exposures_df = pd.DataFrame(exposures)
    pivot_exposures = exposures_df.pivot(index="ticker", columns="factor", values="exposure")
    print("\nSample factor exposures:")
    print(pivot_exposures.head(5))
    
    # Set a configuration parameter for the risk model date
    engine.set_config_parameters({
        "risk_model_date": mock_data["risk_model"]["date"],
        "use_risk_model": True,
        "risk_scaling_factor": 0.5
    })
    
    # Now run the backtest with the registered reference data
    print("\nRunning backtest with reference data...")
    results = engine.run()
    
    # Print some results
    print(f"\nBacktest completed with {len(results)} results.")
    print("Sample results:")
    for i, result in enumerate(results[:5]):
        print(f"Result {i+1}:")
        for key, value in result.items():
            print(f"  {key}: {value}")
        print()
    
    # Clean up
    print("Cleaning up...")
    for file in mock_data["temp_dir"].glob("*.parquet"):
        file.unlink()
    mock_data["temp_dir"].rmdir()
    
    print("Example completed successfully.")


if __name__ == "__main__":
    run_example()