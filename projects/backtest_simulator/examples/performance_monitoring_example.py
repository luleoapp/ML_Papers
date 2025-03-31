#!/usr/bin/env python
"""Example script demonstrating performance monitoring capabilities."""

import os
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest_simulator import BacktestEngine
from backtest_simulator.utils.performance import timed_operation


@timed_operation("create_mock_data")
def create_mock_data(symbol_count: int = 10, days: int = 30):
    """Create mock reference data with specified dimensions.
    
    Args:
        symbol_count: Number of symbols to generate
        days: Number of days of price data
        
    Returns:
        Dictionary with mock data
    """
    print(f"Creating mock data with {symbol_count} symbols over {days} days...")
    
    # Create a temporary directory for mock data
    temp_dir = Path("./mock_data")
    temp_dir.mkdir(exist_ok=True)
    
    # Create universe with specified symbol count
    symbols = [f"SYM{i}" for i in range(1, symbol_count + 1)]
    universe = []
    
    for symbol in symbols:
        universe.append({
            "ticker": symbol,
            "listing_exchange": "XNAS" if np.random.random() > 0.3 else "XNYS",
            "sector": np.random.choice(["Technology", "Consumer", "Communication", "Healthcare", "Energy"]),
            "market_cap": np.random.randint(100000, 3000000),
            "is_index_member": np.random.choice([True, False], p=[0.7, 0.3])
        })
    
    universe_df = pd.DataFrame(universe)
    universe_df.to_parquet(temp_dir / "universe.parquet")
    
    # Create price data with specified days
    today = datetime.now()
    start_date = today - timedelta(days=days)
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
    
    # Create tick data files structure
    tick_data_dir = temp_dir / "tick_data"
    tick_data_dir.mkdir(exist_ok=True)
    
    # For each trading day, create a directory with mock files
    for date in date_range:
        date_str = date.strftime("%Y%m%d")
        date_dir = tick_data_dir / date_str
        date_dir.mkdir(exist_ok=True)
        
        # Create a mock tick file for XNAS and XNYS
        for exchange in ["XNAS", "XNYS"]:
            # Just create an empty file - we'll use mock processing in C++ engine
            with open(date_dir / f"{exchange}_{date_str}.parquet", "w") as f:
                f.write("MOCK TICK DATA FILE")
    
    return {
        "universe_path": temp_dir / "universe.parquet",
        "prices_path": temp_dir / "prices.parquet",
        "tick_data_dir": tick_data_dir,
        "symbols": symbols,
        "date_range": date_range,
        "temp_dir": temp_dir
    }


def run_benchmark_tests(use_versioning: bool = True):
    """Run benchmark tests with different parameters and monitor performance."""
    print("Running performance benchmark tests...")
    
    # Create performance log directory
    log_dir = Path("./performance_logs")
    log_dir.mkdir(exist_ok=True)
    
    # Run tests with different data sizes
    test_configs = [
        {"symbol_count": 5, "days": 5},
        {"symbol_count": 10, "days": 10},
        {"symbol_count": 20, "days": 20},
        {"symbol_count": 50, "days": 30}
    ]
    
    results = []
    
    for config in test_configs:
        symbol_count = config["symbol_count"]
        days = config["days"]
        print(f"\nRunning benchmark with {symbol_count} symbols and {days} days...")
        
        # Create mock data with specified dimensions
        mock_data = create_mock_data(symbol_count=symbol_count, days=days)
        
        # Set data_path for engine to find tick data
        os.environ["BACKTEST_DATA_PATH"] = str(mock_data["tick_data_dir"].parent)
        
        # Initialize the backtest engine with performance monitoring
        engine = BacktestEngine(
            use_versioning=use_versioning,
            performance_monitoring=True,
            log_dir=str(log_dir)
        )
        
        # Configure the engine
        start_date = mock_data["date_range"][0]
        end_date = mock_data["date_range"][-1]
        
        print(f"Configuring backtest engine for {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}...")
        engine.configure(
            start_date=start_date,
            end_date=end_date,
            exchanges=["XNAS", "XNYS"],
            universe=mock_data["symbols"],
            run_description=f"Performance test: {symbol_count} symbols, {days} days",
            run_tags=["benchmark", f"symbols_{symbol_count}", f"days_{days}"]
        )
        
        # Load and register reference data
        print("Registering reference data...")
        universe_df = pd.read_parquet(mock_data["universe_path"])
        prices_df = pd.read_parquet(mock_data["prices_path"])
        
        engine.register_custom_data("universe", universe_df)
        engine.register_custom_data("prices", prices_df)
        
        # Run the backtest
        print("Running backtest...")
        start_time = time.time()
        results_list = engine.run()
        run_time = time.time() - start_time
        
        # Save results
        os.makedirs("results", exist_ok=True)
        output_path = f"results/benchmark_{symbol_count}symbols_{days}days.parquet"
        engine.save_results(output_path)
        
        # Generate a performance report
        report_path = engine.generate_performance_report(
            format_type="html"
        )
        
        # Store the test results
        results.append({
            "symbol_count": symbol_count,
            "days": days,
            "run_time": run_time,
            "result_count": len(results_list),
            "report_path": report_path
        })
        
        print(f"Test completed in {run_time:.2f} seconds with {len(results_list)} results")
        print(f"Performance report: {report_path}")
        
        # Clean up mock data for this test
        for file in mock_data["temp_dir"].glob("**/*.parquet"):
            file.unlink()
        for date_dir in mock_data["tick_data_dir"].iterdir():
            if date_dir.is_dir():
                date_dir.rmdir()
        mock_data["tick_data_dir"].rmdir()
        mock_data["temp_dir"].rmdir()
    
    # Generate a summary plot
    print("\nGenerating performance summary...")
    plt.figure(figsize=(12, 8))
    
    # Plot 1: Run time vs symbol count
    plt.subplot(2, 2, 1)
    symbol_counts = [r["symbol_count"] for r in results]
    run_times = [r["run_time"] for r in results]
    plt.plot(symbol_counts, run_times, 'o-', linewidth=2)
    plt.xlabel('Number of Symbols')
    plt.ylabel('Run Time (seconds)')
    plt.title('Run Time vs Symbol Count')
    plt.grid(True)
    
    # Plot 2: Run time vs day count
    plt.subplot(2, 2, 2)
    days = [r["days"] for r in results]
    plt.plot(days, run_times, 'o-', linewidth=2, color='green')
    plt.xlabel('Number of Days')
    plt.ylabel('Run Time (seconds)')
    plt.title('Run Time vs Day Count')
    plt.grid(True)
    
    # Plot 3: Processing rate (results per second) vs symbol count
    plt.subplot(2, 2, 3)
    processing_rates = [r["result_count"] / r["run_time"] if r["run_time"] > 0 else 0 for r in results]
    plt.plot(symbol_counts, processing_rates, 'o-', linewidth=2, color='red')
    plt.xlabel('Number of Symbols')
    plt.ylabel('Results Per Second')
    plt.title('Processing Rate vs Symbol Count')
    plt.grid(True)
    
    # Plot 4: Result count vs (symbol count * day count)
    plt.subplot(2, 2, 4)
    data_size = [r["symbol_count"] * r["days"] for r in results]
    result_counts = [r["result_count"] for r in results]
    plt.scatter(data_size, result_counts, s=100, alpha=0.7, color='purple')
    
    # Add labels for each point
    for i, (x, y) in enumerate(zip(data_size, result_counts)):
        plt.annotate(f"{symbol_counts[i]}s,{days[i]}d", 
                    (x, y), 
                    textcoords="offset points",
                    xytext=(0, 10), 
                    ha='center')
    
    plt.xlabel('Data Size (Symbols × Days)')
    plt.ylabel('Result Count')
    plt.title('Result Count vs Data Size')
    plt.grid(True)
    
    plt.tight_layout()
    plt.savefig(log_dir / "performance_summary.png")
    
    # Create HTML summary report
    html_content = f"""
    <html>
    <head>
        <title>Backtest Performance Benchmark Summary</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            h1, h2 {{ color: #333366; }}
            table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
            th, td {{ text-align: left; padding: 8px; border: 1px solid #ddd; }}
            th {{ background-color: #f2f2f2; }}
            tr:nth-child(even) {{ background-color: #f9f9f9; }}
            .summary-image {{ max-width: 100%; margin: 20px 0; }}
            .report-links {{ margin: 20px 0; }}
        </style>
    </head>
    <body>
        <h1>Backtest Performance Benchmark Summary</h1>
        <p>Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        
        <h2>Test Results</h2>
        <table>
            <tr>
                <th>Symbols</th>
                <th>Days</th>
                <th>Run Time (s)</th>
                <th>Result Count</th>
                <th>Results/Second</th>
                <th>Data Size</th>
            </tr>
    """
    
    for r in results:
        processing_rate = r["result_count"] / r["run_time"] if r["run_time"] > 0 else 0
        data_size = r["symbol_count"] * r["days"]
        
        html_content += f"""
            <tr>
                <td>{r["symbol_count"]}</td>
                <td>{r["days"]}</td>
                <td>{r["run_time"]:.2f}</td>
                <td>{r["result_count"]}</td>
                <td>{processing_rate:.2f}</td>
                <td>{data_size}</td>
            </tr>
        """
    
    html_content += """
        </table>
        
        <h2>Performance Visualization</h2>
        <img src="performance_summary.png" alt="Performance Summary" class="summary-image">
        
        <h2>Detailed Performance Reports</h2>
        <div class="report-links">
    """
    
    for r in results:
        if r["report_path"]:
            report_name = os.path.basename(r["report_path"])
            html_content += f"""
            <p><a href="{report_name}" target="_blank">
                Performance Report: {r["symbol_count"]} symbols, {r["days"]} days
            </a></p>
            """
    
    html_content += """
        </div>
    </body>
    </html>
    """
    
    summary_path = log_dir / "benchmark_summary.html"
    with open(summary_path, 'w') as f:
        f.write(html_content)
    
    print(f"\nBenchmark tests completed. Summary report: {summary_path}")
    print(f"Performance visualization: {log_dir / 'performance_summary.png'}")
    return summary_path


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run performance benchmark tests")
    parser.add_argument("--no-versioning", action="store_true", help="Disable versioning")
    args = parser.parse_args()
    
    run_benchmark_tests(use_versioning=not args.no_versioning)