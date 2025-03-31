#!/usr/bin/env python
"""Example script for calculating trade metrics."""

import os
import sys
from pathlib import Path
import pandas as pd
from datetime import datetime, timedelta
import matplotlib.pyplot as plt

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest_simulator import BacktestEngine
from backtest_simulator.analytics import TradeMetricsCalculator, TradeDataIntegrator


def generate_sample_data():
    """Generate sample trade data for demonstration."""
    # Create 1000 sample trades across different times and symbols
    trades = []
    symbols = ["AAPL", "MSFT", "GOOGL"]
    sides = ["buy", "sell"]
    
    base_time = datetime(2023, 1, 1, 9, 30, 0)
    
    for i in range(1000):
        symbol = symbols[i % len(symbols)]
        trade_time = base_time + timedelta(seconds=i*6)  # 10 trades per minute
        
        # Create patterns for demonstration
        if symbol == "AAPL":
            # More buys in first half of the day, more sells in second half
            mid_point = base_time + timedelta(hours=3)
            if trade_time < mid_point:
                side = sides[0] if i % 3 != 0 else sides[1]  # 2/3 buys
            else:
                side = sides[1] if i % 3 != 0 else sides[0]  # 2/3 sells
        elif symbol == "MSFT":
            # Alternating 15-minute periods of buy and sell dominance
            period = (trade_time.hour * 60 + trade_time.minute) // 15
            if period % 2 == 0:
                side = sides[0] if i % 3 != 0 else sides[1]  # 2/3 buys
            else:
                side = sides[1] if i % 3 != 0 else sides[0]  # 2/3 sells
        else:
            # GOOGL: Random with slight buy bias
            side = sides[0] if i % 5 != 0 else sides[1]  # 4/5 buys
        
        # Price movement: uptrend for AAPL, downtrend for MSFT, sideways for GOOGL
        if symbol == "AAPL":
            base_price = 150
            trend = 0.001 * i
            noise = (i % 10) * 0.05
        elif symbol == "MSFT":
            base_price = 250
            trend = -0.001 * i
            noise = (i % 8) * 0.04
        else:
            base_price = 100
            trend = 0
            noise = (i % 12) * 0.1
            
        price = base_price + trend + noise
        
        # Size varies by symbol
        if symbol == "AAPL":
            size = 100 + (i % 5) * 20
        elif symbol == "MSFT":
            size = 50 + (i % 10) * 15
        else:
            size = 200 + (i % 3) * 50
        
        # Add some markers
        is_iso = bool(i % 5 == 0)  # Every 5th trade is ISO
        is_sweep = bool(i % 7 == 0)  # Every 7th trade is sweep
        
        trades.append({
            "symbol": symbol,
            "trade_time": trade_time,
            "trade_price": price,
            "trade_size": size,
            "trade_side": side,
            "is_iso": is_iso,
            "is_sweep": is_sweep
        })
    
    return pd.DataFrame(trades)


def calculate_and_plot_metrics():
    """Calculate trade metrics and plot visualizations."""
    # Generate sample data
    print("Generating sample trade data...")
    trades_df = generate_sample_data()
    
    # Create a calculator
    calculator = TradeMetricsCalculator()
    
    # Create marked trades subset (ISO or sweep)
    marked_trades = trades_df[trades_df['is_iso'] | trades_df['is_sweep']]
    
    # Calculate minutely metrics
    print("Calculating minutely metrics...")
    minutely_metrics = calculator.aggregate_minutely_data(trades_df, marked_trades)
    
    # Save results
    output_dir = Path(__file__).parent.parent / "results"
    output_dir.mkdir(exist_ok=True)
    minutely_metrics.to_csv(output_dir / "minutely_metrics.csv", index=False)
    print(f"Saved minutely metrics to {output_dir}/minutely_metrics.csv")
    
    # Calculate trade direction features with 5-minute window
    print("Calculating trade direction features...")
    trade_features = calculator.get_trade_direction_features(trades_df, window_size='5min')
    trade_features.to_csv(output_dir / "trade_features.csv", index=False)
    print(f"Saved trade features to {output_dir}/trade_features.csv")
    
    # Create visualizations
    print("Creating visualizations...")
    create_visualizations(minutely_metrics, output_dir)


def create_visualizations(metrics, output_dir):
    """Create visualizations of the calculated metrics."""
    # Create a directory for plots
    plots_dir = output_dir / "plots"
    plots_dir.mkdir(exist_ok=True)
    
    # Plot imbalance ratio for each symbol
    plt.figure(figsize=(12, 8))
    for symbol in metrics['symbol'].unique():
        symbol_metrics = metrics[metrics['symbol'] == symbol]
        plt.plot(symbol_metrics['minute'], symbol_metrics['imbalance'], label=f"{symbol} All Trades")
        plt.plot(symbol_metrics['minute'], symbol_metrics['marked_imbalance'], linestyle='--', 
                 label=f"{symbol} Marked Trades")
    
    plt.title("Trade Imbalance Ratio (Bx-Sx)/(Bx+Sx)")
    plt.xlabel("Time")
    plt.ylabel("Imbalance Ratio")
    plt.legend()
    plt.grid(True)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(plots_dir / "imbalance_ratio.png")
    print(f"Saved imbalance plot to {plots_dir}/imbalance_ratio.png")
    
    # Plot volume for each symbol
    plt.figure(figsize=(12, 8))
    for symbol in metrics['symbol'].unique():
        symbol_metrics = metrics[metrics['symbol'] == symbol]
        plt.plot(symbol_metrics['minute'], symbol_metrics['volume'], label=f"{symbol} Volume")
    
    plt.title("Trading Volume by Symbol")
    plt.xlabel("Time")
    plt.ylabel("Volume")
    plt.legend()
    plt.grid(True)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(plots_dir / "volume.png")
    print(f"Saved volume plot to {plots_dir}/volume.png")
    
    # Plot the ratio of marked trades to all trades
    plt.figure(figsize=(12, 8))
    for symbol in metrics['symbol'].unique():
        symbol_metrics = metrics[metrics['symbol'] == symbol]
        # Calculate ratio of marked volume to total volume
        marked_volume = symbol_metrics['Bx'] + symbol_metrics['Sx']
        total_volume = symbol_metrics['volume']
        ratio = marked_volume / total_volume
        plt.plot(symbol_metrics['minute'], ratio, label=f"{symbol}")
    
    plt.title("Marked Trades Ratio to Total Volume")
    plt.xlabel("Time")
    plt.ylabel("Ratio")
    plt.legend()
    plt.grid(True)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(plots_dir / "marked_ratio.png")
    print(f"Saved marked ratio plot to {plots_dir}/marked_ratio.png")


def simulate_datastore_integration():
    """Simulate integration with DataStore."""
    print("\nSimulating DataStore integration...")
    
    # Generate sample data
    trades_df = generate_sample_data()
    
    # Mock the DataStore client to use our sample data
    with patch('backtest_simulator.data.cloud_store.DataStoreClient.download_dataset') as mock_download:
        mock_download.return_value = trades_df
        
        # Create the integrator
        integrator = TradeDataIntegrator(datastore_name="test", workspace="test_workspace")
        
        # Calculate metrics
        print("Calculating metrics from DataStore data...")
        metrics = integrator.calculate_metrics(
            trade_dataset="sample_trades",
            markers=["is_iso", "is_sweep"],
            start_date="2023-01-01",
            end_date="2023-01-02",
            symbols=["AAPL", "MSFT", "GOOGL"],
            output_dataset="sample_metrics"
        )
        
        print(f"Generated metrics for {len(metrics)} time periods")
        print(f"Metrics columns: {metrics.columns.tolist()}")
        print("\nSample of calculated metrics:")
        print(metrics.head())


if __name__ == "__main__":
    # Check if matplotlib is installed
    try:
        import matplotlib.pyplot as plt
        from unittest.mock import patch
        
        # Run the example
        calculate_and_plot_metrics()
        simulate_datastore_integration()
        
    except ImportError:
        print("This example requires matplotlib. Install it with 'pip install matplotlib'.")
        sys.exit(1)