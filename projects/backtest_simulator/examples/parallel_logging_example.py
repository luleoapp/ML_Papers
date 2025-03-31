#!/usr/bin/env python
"""Example demonstrating parallel processing and advanced logging capabilities."""

import os
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest_simulator import BacktestEngine
from backtest_simulator.utils.logging_config import LoggerFactory, get_logger
from backtest_simulator.utils.performance import timed_operation


@timed_operation("create_mock_data")
def create_mock_data(symbol_count: int = 10, days: int = 30):
    """Create mock data for testing."""
    logger = get_logger(__name__ + ".create_mock_data")
    logger.info(f"Creating mock data with {symbol_count} symbols over {days} days")
    
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
    
    logger.debug(f"Created universe with {len(universe)} entries")
    universe_df = pd.DataFrame(universe)
    universe_df.to_parquet(temp_dir / "universe.parquet")
    
    # Create tick data files structure
    today = datetime.now()
    start_date = today - timedelta(days=days)
    end_date = today - timedelta(days=1)
    date_range = pd.date_range(start=start_date, end=end_date, freq='B')
    
    logger.info(f"Creating tick data files for {len(date_range)} dates")
    
    tick_data_dir = temp_dir / "tick_data"
    tick_data_dir.mkdir(exist_ok=True)
    
    # For each trading day, create a directory with mock files
    for date in date_range:
        date_str = date.strftime("%Y%m%d")
        date_dir = tick_data_dir / date_str
        date_dir.mkdir(exist_ok=True)
        
        logger.debug(f"Creating files for date {date_str}")
        
        # Create a mock tick file for XNAS and XNYS
        for exchange in ["XNAS", "XNYS"]:
            # Just create an empty file - we'll use mock processing in C++ engine
            with open(date_dir / f"{exchange}_{date_str}.parquet", "w") as f:
                f.write("MOCK TICK DATA FILE")
    
    logger.info(f"Created mock data in {temp_dir}")
    return {
        "universe_path": temp_dir / "universe.parquet",
        "tick_data_dir": tick_data_dir,
        "symbols": symbols,
        "date_range": date_range,
        "temp_dir": temp_dir
    }


def run_parallel_comparison(days: int = 10, symbol_count: int = 10, log_level: str = "INFO"):
    """Run a comparison between sequential and parallel processing."""
    # Set up logging
    LoggerFactory.setup_logging(
        log_dir="./logs",
        log_level=log_level,
        console_level=log_level,
        file_level="DEBUG",
        json_logs=True,
        log_file_prefix="parallel_comparison"
    )
    
    logger = get_logger(__name__)
    logger.info(f"Starting parallel processing comparison with {days} days and {symbol_count} symbols")
    
    # Create mock data
    mock_data = create_mock_data(symbol_count=symbol_count, days=days)
    
    # Set data_path for engine to find tick data
    os.environ["BACKTEST_DATA_PATH"] = str(mock_data["tick_data_dir"].parent)
    
    # Results storage
    sequential_times = []
    parallel_times = []
    worker_counts = [1, 2, 4, 8]  # Different worker counts to test
    
    # Run sequential benchmark
    logger.info("Running sequential benchmark")
    engine_sequential = BacktestEngine(
        use_versioning=False,
        performance_monitoring=True,
        parallel_processing=False,
        log_level=log_level,
        log_file_prefix="sequential"
    )
    
    # Configure the engine
    start_date = mock_data["date_range"][0]
    end_date = mock_data["date_range"][-1]
    
    logger.info(f"Configuring backtest engine for {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    engine_sequential.configure(
        start_date=start_date,
        end_date=end_date,
        exchanges=["XNAS", "XNYS"],
        universe=mock_data["symbols"],
        data_path=str(mock_data["tick_data_dir"].parent)
    )
    
    # Register reference data
    universe_df = pd.read_parquet(mock_data["universe_path"])
    engine_sequential.register_custom_data("universe", universe_df)
    
    # Run the sequential benchmark
    start_time = time.time()
    results_sequential = engine_sequential.run(parallel=False)
    sequential_time = time.time() - start_time
    sequential_times.append(sequential_time)
    
    logger.info(f"Sequential run completed in {sequential_time:.2f} seconds with {len(results_sequential)} results")
    
    # Generate sequential report
    sequential_report = engine_sequential.generate_performance_report(
        output_file="./logs/sequential_report.html",
        format_type="html"
    )
    
    # Run parallel benchmarks with different worker counts
    for worker_count in worker_counts:
        logger.info(f"Running parallel benchmark with {worker_count} workers")
        
        engine_parallel = BacktestEngine(
            use_versioning=False,
            performance_monitoring=True,
            parallel_processing=True,
            max_workers=worker_count,
            use_processes=True,  # Use processes for better parallelism
            log_level=log_level,
            log_file_prefix=f"parallel_{worker_count}"
        )
        
        # Configure the engine
        engine_parallel.configure(
            start_date=start_date,
            end_date=end_date,
            exchanges=["XNAS", "XNYS"],
            universe=mock_data["symbols"],
            data_path=str(mock_data["tick_data_dir"].parent)
        )
        
        # Register reference data
        engine_parallel.register_custom_data("universe", universe_df)
        
        # Run the parallel benchmark
        start_time = time.time()
        results_parallel = engine_parallel.run(parallel=True)
        parallel_time = time.time() - start_time
        parallel_times.append(parallel_time)
        
        logger.info(f"Parallel run with {worker_count} workers completed in {parallel_time:.2f} seconds with {len(results_parallel)} results")
        
        # Generate parallel report
        parallel_report = engine_parallel.generate_performance_report(
            output_file=f"./logs/parallel_{worker_count}_report.html",
            format_type="html"
        )
    
    # Create summary visualization
    plt.figure(figsize=(12, 8))
    
    # Plot 1: Performance comparison
    plt.subplot(2, 1, 1)
    
    # Plot sequential time as horizontal line
    plt.axhline(y=sequential_time, linestyle='--', color='red', label=f'Sequential: {sequential_time:.2f}s')
    
    # Plot parallel times
    worker_labels = [f"{w} workers" for w in worker_counts]
    plt.plot(worker_labels, parallel_times, 'o-', linewidth=2, color='blue', label='Parallel')
    
    # Add data labels
    for i, time_value in enumerate(parallel_times):
        plt.text(i, time_value + 0.5, f"{time_value:.2f}s", ha='center')
    
    plt.xlabel('Worker Count')
    plt.ylabel('Run Time (seconds)')
    plt.title(f'Performance Comparison: {days} days, {symbol_count} symbols')
    plt.grid(True)
    plt.legend()
    
    # Plot 2: Speedup comparison
    plt.subplot(2, 1, 2)
    
    # Calculate speedup
    speedups = [sequential_time / p_time for p_time in parallel_times]
    
    # Plot speedup
    plt.plot(worker_labels, speedups, 'o-', linewidth=2, color='green')
    
    # Add ideal speedup line
    ideal_speedups = [min(w, days) for w in worker_counts]  # Speedup limited by number of days
    plt.plot(worker_labels, ideal_speedups, '--', color='gray', alpha=0.7, label='Ideal Speedup')
    
    # Add data labels
    for i, speedup in enumerate(speedups):
        plt.text(i, speedup + 0.1, f"{speedup:.2f}x", ha='center')
    
    plt.xlabel('Worker Count')
    plt.ylabel('Speedup Factor')
    plt.title('Speedup Comparison')
    plt.grid(True)
    plt.legend()
    
    plt.tight_layout()
    plt.savefig("./logs/parallel_comparison_results.png")
    
    # Create an HTML summary report
    html_content = f"""
    <html>
    <head>
        <title>Parallel Processing Comparison</title>
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
        <h1>Parallel Processing Comparison</h1>
        <p>Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p>Test Configuration: {days} days, {symbol_count} symbols</p>
        
        <h2>Test Results</h2>
        <table>
            <tr>
                <th>Processing Type</th>
                <th>Workers</th>
                <th>Run Time (s)</th>
                <th>Speedup Factor</th>
            </tr>
            <tr>
                <td>Sequential</td>
                <td>1</td>
                <td>{sequential_time:.2f}</td>
                <td>1.00x</td>
            </tr>
    """
    
    for i, worker_count in enumerate(worker_counts):
        html_content += f"""
            <tr>
                <td>Parallel</td>
                <td>{worker_count}</td>
                <td>{parallel_times[i]:.2f}</td>
                <td>{speedups[i]:.2f}x</td>
            </tr>
        """
    
    html_content += """
        </table>
        
        <h2>Performance Visualization</h2>
        <img src="parallel_comparison_results.png" alt="Performance Comparison" class="summary-image">
        
        <h2>Detailed Performance Reports</h2>
        <div class="report-links">
            <p><a href="sequential_report.html" target="_blank">Sequential Run Report</a></p>
    """
    
    for worker_count in worker_counts:
        html_content += f"""
            <p><a href="parallel_{worker_count}_report.html" target="_blank">
                Parallel Run Report ({worker_count} workers)
            </a></p>
        """
    
    html_content += """
        </div>
    </body>
    </html>
    """
    
    summary_path = Path("./logs/parallel_comparison_summary.html")
    with open(summary_path, 'w') as f:
        f.write(html_content)
    
    logger.info(f"Benchmark completed. Summary report: {summary_path}")
    logger.info(f"Results summary:")
    logger.info(f"  Sequential: {sequential_time:.2f} seconds")
    
    for i, worker_count in enumerate(worker_counts):
        logger.info(f"  Parallel ({worker_count} workers): {parallel_times[i]:.2f} seconds, {speedups[i]:.2f}x speedup")
    
    # Clean up
    logger.info("Cleaning up")
    
    for file in mock_data["temp_dir"].glob("**/*.parquet"):
        file.unlink()
    
    for date_dir in mock_data["tick_data_dir"].iterdir():
        if date_dir.is_dir():
            date_dir.rmdir()
    
    mock_data["tick_data_dir"].rmdir()
    mock_data["temp_dir"].rmdir()
    
    return summary_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parallel Processing and Logging Example")
    parser.add_argument("--days", type=int, default=10, help="Number of days to simulate")
    parser.add_argument("--symbols", type=int, default=10, help="Number of symbols to simulate")
    parser.add_argument("--log-level", type=str, default="INFO", 
                        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                        help="Logging level")
    args = parser.parse_args()
    
    summary_path = run_parallel_comparison(
        days=args.days,
        symbol_count=args.symbols,
        log_level=args.log_level
    )
    
    print(f"\nBenchmark completed! Summary available at: {summary_path}")