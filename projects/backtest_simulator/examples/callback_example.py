#!/usr/bin/env python
"""Example script demonstrating callback system for C++ engine marking data."""

import os
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import threading

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest_simulator import BacktestEngine
from backtest_simulator.utils.logging_config import LoggerFactory, get_logger
from backtest_simulator.core.callback_manager import CallbackManager


def create_mock_data(days: int = 5, symbols: List[str] = None):
    """Create mock data for the example.
    
    Args:
        days: Number of days to create data for
        symbols: List of symbols to include, or None to use defaults
        
    Returns:
        Tuple containing (temp_dir, universe, dates)
    """
    logger = get_logger(__name__ + ".create_mock_data")
    logger.info(f"Creating mock data for {days} days")
    
    # Use default symbols if none provided
    if symbols is None:
        symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]
    
    # Create a temporary directory for mock data
    temp_dir = Path("./mock_data")
    temp_dir.mkdir(exist_ok=True)
    
    # Create universe file
    universe = []
    for symbol in symbols:
        universe.append({
            "ticker": symbol,
            "listing_exchange": "XNAS",
            "sector": "Technology",
            "is_index_member": True
        })
    
    universe_df = pd.DataFrame(universe)
    universe_df.to_parquet(temp_dir / "universe.parquet")
    
    # Create mock tick data directories
    tick_data_dir = temp_dir / "tick_data"
    tick_data_dir.mkdir(exist_ok=True)
    
    # Create date range
    end_date = datetime.now() - timedelta(days=1)
    start_date = end_date - timedelta(days=days - 1)
    dates = [start_date + timedelta(days=i) for i in range(days)]
    
    # Create mock tick data files
    for date in dates:
        date_str = date.strftime("%Y%m%d")
        date_dir = tick_data_dir / date_str
        date_dir.mkdir(exist_ok=True)
        
        # Create files for each exchange
        for exchange in ["XNAS", "XNYS"]:
            with open(date_dir / f"{exchange}_{date_str}.parquet", "w") as f:
                f.write("MOCK TICK DATA")
    
    logger.info(f"Created mock data in {temp_dir} for dates {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    return temp_dir, symbols, dates


def custom_marking_processor(markings: List[Dict[str, Any]]) -> bool:
    """Custom function to process marking data from C++ callbacks.
    
    In a real implementation, this would upload the data to the cloud.
    For this example, we just print some statistics.
    
    Args:
        markings: List of marking dictionaries
        
    Returns:
        True if processing was successful
    """
    logger = get_logger(__name__ + ".marking_processor")
    
    # Get basic statistics
    marking_count = len(markings)
    symbols = set(marking["ticker"] for marking in markings)
    
    # Calculate average price and quantity
    avg_price = sum(marking["price"] for marking in markings) / marking_count if marking_count > 0 else 0
    avg_qty = sum(marking["qty"] for marking in markings) / marking_count if marking_count > 0 else 0
    
    # Count markings by type
    marking1_counts = {}
    for marking in markings:
        val = marking.get("marking1", 0)
        marking1_counts[val] = marking1_counts.get(val, 0) + 1
    
    logger.info(f"Processed {marking_count} markings for {len(symbols)} symbols")
    logger.info(f"Average price: {avg_price:.2f}, Average qty: {avg_qty:.2f}")
    logger.info(f"Marking1 distribution: {marking1_counts}")
    
    # In a real implementation, this would upload the data to cloud storage
    # For example:
    # df = pd.DataFrame(markings)
    # df.to_parquet("markings.parquet")
    # cloud_client.upload_file("markings.parquet", "marking_data_bucket")
    
    # Simulate some processing time
    time.sleep(0.1)
    
    return True


class CallbackMonitor(threading.Thread):
    """Thread to monitor and report callback statistics."""
    
    def __init__(self, callback_manager: CallbackManager, interval: float = 2.0):
        """Initialize the callback monitor.
        
        Args:
            callback_manager: Callback manager to monitor
            interval: Reporting interval in seconds
        """
        super().__init__(name="callback_monitor", daemon=True)
        self.logger = get_logger(__name__ + ".CallbackMonitor")
        self.callback_manager = callback_manager
        self.interval = interval
        self.stop_event = threading.Event()
    
    def run(self):
        """Run the monitor thread."""
        self.logger.info("Callback monitor started")
        
        while not self.stop_event.is_set():
            # Get statistics from the callback manager
            with self.callback_manager.stats_lock:
                received = self.callback_manager.received_batches
                received_markings = self.callback_manager.received_markings
                uploaded = self.callback_manager.uploaded_batches
                uploaded_markings = self.callback_manager.uploaded_markings
                queue_size = self.callback_manager.markings_queue.qsize()
            
            # Calculate processing rate
            backlog = received - uploaded
            backlog_markings = received_markings - uploaded_markings
            
            self.logger.info(
                f"Callback stats: Received {received} batches ({received_markings} markings), "
                f"Processed {uploaded} batches ({uploaded_markings} markings), "
                f"Backlog: {backlog} batches ({backlog_markings} markings), "
                f"Queue size: {queue_size}"
            )
            
            # Sleep for the interval
            self.stop_event.wait(self.interval)
        
        self.logger.info("Callback monitor stopped")
    
    def stop(self):
        """Stop the monitor thread."""
        self.stop_event.set()
        self.join(timeout=1.0)


def run_callback_example(
    days: int = 5,
    symbols: int = 10,
    parallel: bool = True,
    max_workers: int = 4,
    max_window_size: int = 3600,
    log_level: str = "INFO"
):
    """Run the callback example.
    
    Args:
        days: Number of days to process
        symbols: Number of symbols to process
        parallel: Whether to use parallel processing
        max_workers: Maximum number of worker processes/threads
        max_window_size: Maximum window size in seconds
        log_level: Logging level
    """
    # Set up logging
    LoggerFactory.setup_logging(
        log_level=log_level,
        console_level=log_level,
        file_level="DEBUG",
        json_logs=True,
        log_file_prefix="callback_example"
    )
    
    logger = get_logger(__name__)
    logger.info(f"Starting callback example with {days} days, {symbols} symbols")
    
    # Generate symbol list
    symbol_list = [f"SYM{i+1}" for i in range(symbols)]
    
    # Create mock data
    tick_data_dir, _, dates = create_mock_data(days=days, symbols=symbol_list)
    
    # Create a callback manager for custom processing
    callback_manager = CallbackManager(
        max_queue_size=1000,
        parallel_uploads=True,
        max_upload_workers=2
    )
    
    # Start the callback monitor
    monitor = CallbackMonitor(callback_manager, interval=3.0)
    monitor.start()
    
    try:
        # Start callback processing with our custom processor
        callback_manager.start_processing(custom_marking_processor)
        
        # Initialize the backtest engine
        logger.info("Initializing backtest engine")
        engine = BacktestEngine(
            use_cloud_store=False,  # We're using our custom callback processing
            parallel_processing=parallel,
            max_workers=max_workers,
            max_window_size=max_window_size,
            log_level=log_level
        )
        
        # Configure the engine
        logger.info("Configuring backtest engine")
        start_date = dates[0]
        end_date = dates[-1]
        
        engine.configure(
            start_date=start_date,
            end_date=end_date,
            exchanges=["XNAS", "XNYS"],
            universe=symbol_list,
            data_path=str(tick_data_dir.parent)
        )
        
        # Override the thread manager's callback manager with our custom one
        engine.thread_manager.callback_manager = callback_manager
        
        # Override the C++ engine's callback manager
        engine.cpp_engine._callback_manager = callback_manager
        
        # Run the backtest
        logger.info(f"Running backtest from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        results = engine.run(parallel=parallel)
        
        # Wait for all callbacks to be processed
        logger.info("Waiting for callback processing to complete...")
        time.sleep(5.0)  # Allow time for remaining callbacks to be processed
        
        # Print final statistics
        with callback_manager.stats_lock:
            received = callback_manager.received_batches
            received_markings = callback_manager.received_markings
            uploaded = callback_manager.uploaded_batches
            uploaded_markings = callback_manager.uploaded_markings
        
        logger.info(f"Backtest completed with {len(results)} results")
        logger.info(f"Final callback stats: Received {received} batches ({received_markings} markings), "
                   f"Processed {uploaded} batches ({uploaded_markings} markings)")
        
        # Stop the engine and callback processing
        logger.info("Shutting down")
        callback_manager.stop_processing(wait_for_completion=True)
        monitor.stop()
        
        # Clean up
        logger.info("Cleaning up")
        for file in tick_data_dir.parent.glob("**/*"):
            if file.is_file():
                file.unlink()
        
        for dir_path in [p for p in tick_data_dir.parent.glob("**/*") if p.is_dir()]:
            try:
                dir_path.rmdir()
            except OSError:
                pass
        
        try:
            tick_data_dir.parent.rmdir()
        except OSError:
            pass
    
    except Exception as e:
        logger.error(f"Error in callback example: {e}", exc_info=True)
        raise
    
    finally:
        # Make sure we stop the monitor thread
        if monitor.is_alive():
            monitor.stop()


if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Callback System Example")
    parser.add_argument("--days", type=int, default=5, help="Number of days to process")
    parser.add_argument("--symbols", type=int, default=10, help="Number of symbols to process")
    parser.add_argument("--parallel", action="store_true", help="Use parallel processing")
    parser.add_argument("--max-workers", type=int, default=4, help="Maximum number of workers")
    parser.add_argument("--max-window-size", type=int, default=3600, help="Maximum window size in seconds")
    parser.add_argument("--log-level", type=str, default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                        help="Logging level")
    
    args = parser.parse_args()
    
    # Run the example
    run_callback_example(
        days=args.days,
        symbols=args.symbols,
        parallel=args.parallel,
        max_workers=args.max_workers,
        max_window_size=args.max_window_size,
        log_level=args.log_level
    )