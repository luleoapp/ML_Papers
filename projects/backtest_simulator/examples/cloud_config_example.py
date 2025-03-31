#!/usr/bin/env python
"""
Example demonstrating how to use cloud configurations with the backtest simulator.

This example shows how to create, save, and load configurations from the cloud datastore.
"""

import os
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest_simulator import BacktestEngine, LoggerFactory, get_logger
from backtest_simulator.config.settings import BacktestConfig
from backtest_simulator.data.cloud_store import DataStoreClient


def create_example_config():
    """Create an example configuration."""
    # Create a basic configuration
    config_dict = {
        "name": "Example Cloud Configuration",
        "description": "A simple example configuration for demonstration purposes",
        
        # Engine settings
        "parallel_processing": True,
        "max_workers": 4,
        "max_window_size": 3600,
        "upload_batch_size": 10000,
        "upload_interval": 5.0,
        
        # Backtest settings
        "start_date": (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),
        "end_date": (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
        "exchanges": ["XNAS", "XNYS"],
        "universe": ["AAPL", "MSFT", "GOOGL", "AMZN", "META"],
        "data_path": "/path/to/tick/data",
        
        # Output settings
        "output_dataset": "backtest_results",
        "output_partition": f"example_{datetime.now().strftime('%Y%m%d')}"
    }
    
    return config_dict


def run_cloud_config_example():
    """Run the cloud configuration example."""
    # Set up logging
    LoggerFactory.setup_logging(log_level="INFO", console_level="INFO", file_level="DEBUG")
    logger = get_logger("cloud_config_example")
    
    logger.info("Starting cloud configuration example")
    
    try:
        # Initialize cloud store
        logger.info("Initializing cloud store client")
        cloud_store = DataStoreClient()
        
        # Create a new configuration
        logger.info("Creating a new configuration")
        config_dict = create_example_config()
        config = BacktestConfig(config_dict=config_dict)
        
        # Save configuration to cloud store
        logger.info("Saving configuration to cloud store")
        if not config.save_to_cloud(cloud_store):
            logger.error("Failed to save configuration to cloud store")
            return
        
        config_id = config.get("id")
        logger.info(f"Configuration saved with ID: {config_id}")
        
        # Load configuration from cloud store
        logger.info(f"Loading configuration {config_id} from cloud store")
        loaded_config = BacktestConfig(config_id=config_id, cloud_store=cloud_store)
        
        # Print loaded configuration
        logger.info("Loaded configuration:")
        logger.info(f"  Name: {loaded_config.get('name')}")
        logger.info(f"  Description: {loaded_config.get('description')}")
        logger.info(f"  Start date: {loaded_config.get('start_date')}")
        logger.info(f"  End date: {loaded_config.get('end_date')}")
        logger.info(f"  Universe: {loaded_config.get('universe')}")
        
        # Initialize backtest engine with loaded configuration
        logger.info("Initializing backtest engine with loaded configuration")
        
        engine_config = {
            "use_cloud_store": loaded_config.get("use_cloud_store", True),
            "cloud_store_config": loaded_config.get("cloud_store_config"),
            "parallel_processing": loaded_config.get("parallel_processing", True),
            "max_workers": loaded_config.get("max_workers", 4),
            "max_window_size": loaded_config.get("max_window_size", 3600),
            "upload_batch_size": loaded_config.get("upload_batch_size", 10000),
            "upload_interval": loaded_config.get("upload_interval", 5.0),
            "use_processes": loaded_config.get("use_processes", False),
            "log_level": loaded_config.get("log_level", "INFO"),
            "performance_monitor_enabled": loaded_config.get("performance_monitor_enabled", True)
        }
        
        engine = BacktestEngine(**engine_config)
        
        # Configure the engine
        logger.info("Configuring backtest engine")
        
        backtest_config = {
            "start_date": loaded_config.get("start_date"),
            "end_date": loaded_config.get("end_date"),
            "exchanges": loaded_config.get("exchanges", ["XNAS", "XNYS"]),
            "universe": loaded_config.get("universe"),
            "data_path": loaded_config.get("data_path"),
            "output_dataset": loaded_config.get("output_dataset", "backtest_results"),
            "output_partition": loaded_config.get("output_partition")
        }
        
        # Note: In a real example, the engine would be fully configured and run
        # For demonstration purposes, we just print the configuration
        logger.info("Engine configuration:")
        for key, value in engine_config.items():
            if isinstance(value, dict):
                continue
            logger.info(f"  {key}: {value}")
        
        logger.info("Backtest configuration:")
        for key, value in backtest_config.items():
            if isinstance(value, list) and len(value) > 5:
                logger.info(f"  {key}: {value[:5]} (... and more)")
            else:
                logger.info(f"  {key}: {value}")
        
        # Update the configuration
        logger.info("Updating configuration")
        loaded_config.set("description", "Updated example configuration")
        loaded_config.set("max_workers", 8)
        
        # Save the updated configuration
        logger.info("Saving updated configuration")
        if loaded_config.save_to_cloud(cloud_store):
            logger.info("Configuration updated successfully")
        else:
            logger.error("Failed to update configuration")
        
        logger.info("Cloud configuration example completed successfully")
    
    except Exception as e:
        logger.error(f"Error in cloud configuration example: {e}", exc_info=True)


if __name__ == "__main__":
    run_cloud_config_example()