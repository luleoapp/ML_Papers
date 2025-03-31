#!/usr/bin/env python
"""
Run a backtest using the backtest simulator.

This script provides a command-line interface for running backtests
with the option to load configurations from the cloud.
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta
import json

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest_simulator import BacktestEngine, LoggerFactory, get_logger
from backtest_simulator.config.settings import BacktestConfig
from backtest_simulator.data.cloud_store import DataStoreClient


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Run a backtest using the backtest simulator")
    
    # Configuration source
    config_group = parser.add_mutually_exclusive_group()
    config_group.add_argument("--config-id", type=str, help="ID of the configuration to load from cloud store")
    config_group.add_argument("--config-file", type=str, help="Path to a JSON configuration file")
    
    # Engine settings
    parser.add_argument("--no-cloud-store", action="store_true", help="Disable cloud storage")
    parser.add_argument("--parallel", action="store_true", help="Use parallel processing")
    parser.add_argument("--no-parallel", action="store_false", dest="parallel", help="Disable parallel processing")
    parser.add_argument("--max-workers", type=int, help="Maximum number of worker threads/processes")
    parser.add_argument("--max-window-size", type=int, help="Maximum window size in seconds for order book")
    parser.add_argument("--upload-batch-size", type=int, help="Batch size for marking uploads")
    parser.add_argument("--upload-interval", type=float, help="Interval between uploads in seconds")
    parser.add_argument("--use-processes", action="store_true", help="Use processes instead of threads")
    parser.add_argument("--log-level", type=str, choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], 
                        help="Logging level")
    parser.add_argument("--no-performance-monitor", action="store_false", dest="performance_monitor", 
                        help="Disable performance monitoring")
    
    # Backtest settings
    parser.add_argument("--start-date", type=str, help="Start date for the backtest (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, help="End date for the backtest (YYYY-MM-DD)")
    parser.add_argument("--exchanges", type=str, nargs="+", help="List of exchanges to process")
    parser.add_argument("--universe", type=str, nargs="+", help="List of symbols to process")
    parser.add_argument("--data-path", type=str, help="Path to tick data")
    
    # Cloud store settings
    parser.add_argument("--api-key", type=str, help="API key for cloud storage")
    parser.add_argument("--base-url", type=str, help="Base URL for cloud storage API")
    
    # Output settings
    parser.add_argument("--output-dataset", type=str, help="Dataset name for output data")
    parser.add_argument("--output-partition", type=str, help="Partition for output data")
    
    # Save configuration
    parser.add_argument("--save-config", action="store_true", help="Save configuration to cloud store")
    parser.add_argument("--save-config-file", type=str, help="Path to save configuration to")
    
    parser.set_defaults(parallel=None, performance_monitor=True)
    
    return parser.parse_args()


def create_config_from_args(args):
    """Create a configuration dictionary from command line arguments."""
    config = {}
    
    # Engine settings
    if args.no_cloud_store:
        config["use_cloud_store"] = False
    if args.parallel is not None:
        config["parallel_processing"] = args.parallel
    if args.max_workers:
        config["max_workers"] = args.max_workers
    if args.max_window_size:
        config["max_window_size"] = args.max_window_size
    if args.upload_batch_size:
        config["upload_batch_size"] = args.upload_batch_size
    if args.upload_interval:
        config["upload_interval"] = args.upload_interval
    if args.use_processes:
        config["use_processes"] = args.use_processes
    if args.log_level:
        config["log_level"] = args.log_level
    
    config["performance_monitor_enabled"] = args.performance_monitor
    
    # Backtest settings
    if args.start_date:
        config["start_date"] = args.start_date
    if args.end_date:
        config["end_date"] = args.end_date
    if args.exchanges:
        config["exchanges"] = args.exchanges
    if args.universe:
        config["universe"] = args.universe
    if args.data_path:
        config["data_path"] = args.data_path
    
    # Cloud store settings
    if args.api_key or args.base_url:
        config["cloud_store_config"] = {}
        if args.api_key:
            config["cloud_store_config"]["api_key"] = args.api_key
        if args.base_url:
            config["cloud_store_config"]["base_url"] = args.base_url
    
    # Output settings
    if args.output_dataset:
        config["output_dataset"] = args.output_dataset
    if args.output_partition:
        config["output_partition"] = args.output_partition
    
    return config


def main():
    """Run a backtest using the backtest simulator."""
    # Parse command line arguments
    args = parse_args()
    
    # Set up logging
    LoggerFactory.setup_logging(log_level="INFO", console_level="INFO", file_level="DEBUG")
    logger = get_logger("run_backtest")
    
    logger.info("Starting backtest")
    
    try:
        # Initialize cloud store if needed
        cloud_store = None
        if args.config_id or not args.no_cloud_store:
            cloud_store = DataStoreClient()
        
        # Load configuration
        config = None
        if args.config_id:
            # Load from cloud
            logger.info(f"Loading configuration {args.config_id} from cloud store")
            config = BacktestConfig(config_id=args.config_id, cloud_store=cloud_store)
        elif args.config_file:
            # Load from file
            logger.info(f"Loading configuration from file {args.config_file}")
            config = BacktestConfig()
            config.load_from_file(args.config_file)
        else:
            # Create from command line arguments
            logger.info("Creating configuration from command line arguments")
            config_dict = create_config_from_args(args)
            config = BacktestConfig(config_dict=config_dict)
        
        # Check required configuration
        if not config.get("data_path"):
            logger.error("No data path specified")
            sys.exit(1)
        
        if not config.get("universe"):
            logger.error("No universe specified")
            sys.exit(1)
        
        # Save configuration if requested
        if args.save_config and cloud_store:
            logger.info("Saving configuration to cloud store")
            config.save_to_cloud(cloud_store)
        
        if args.save_config_file:
            logger.info(f"Saving configuration to file {args.save_config_file}")
            config.save_to_file(args.save_config_file)
        
        # Initialize the backtest engine
        logger.info("Initializing backtest engine")
        
        engine_config = {
            "use_cloud_store": config.get("use_cloud_store", True),
            "cloud_store_config": config.get("cloud_store_config"),
            "parallel_processing": config.get("parallel_processing", True),
            "max_workers": config.get("max_workers", 4),
            "max_window_size": config.get("max_window_size", 3600),
            "upload_batch_size": config.get("upload_batch_size", 10000),
            "upload_interval": config.get("upload_interval", 5.0),
            "use_processes": config.get("use_processes", False),
            "log_level": config.get("log_level", "INFO"),
            "performance_monitor_enabled": config.get("performance_monitor_enabled", True)
        }
        
        engine = BacktestEngine(**engine_config)
        
        # Configure the engine
        logger.info("Configuring backtest engine")
        
        backtest_config = {
            "start_date": config.get("start_date"),
            "end_date": config.get("end_date"),
            "exchanges": config.get("exchanges", ["XNAS", "XNYS"]),
            "universe": config.get("universe"),
            "data_path": config.get("data_path"),
            "output_dataset": config.get("output_dataset", "backtest_results"),
            "output_partition": config.get("output_partition")
        }
        
        engine.configure(**backtest_config)
        
        # Run the backtest
        logger.info("Running backtest")
        results = engine.run(parallel=config.get("parallel_processing"))
        
        # Print summary
        result_count = len(results) if results else 0
        logger.info(f"Backtest completed with {result_count} results")
        
        # Wait for any remaining callbacks to be processed
        logger.info("Waiting for callbacks to complete")
        engine.shutdown(wait_for_callbacks=True)
        
        return 0
    
    except Exception as e:
        logger.error(f"Error running backtest: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())