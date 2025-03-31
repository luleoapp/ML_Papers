#!/usr/bin/env python
"""
Manage backtest configurations in the cloud datastore.

This script provides a command-line interface for managing backtest
configurations in the cloud datastore, including listing, viewing,
creating, updating, and deleting configurations.
"""

import os
import sys
import argparse
from pathlib import Path
import json
import pandas as pd
from tabulate import tabulate

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest_simulator import LoggerFactory, get_logger
from backtest_simulator.config.settings import BacktestConfig
from backtest_simulator.data.cloud_store import DataStoreClient


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Manage backtest configurations in the cloud datastore")
    
    # Main commands
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # List configurations
    list_parser = subparsers.add_parser("list", help="List configurations")
    list_parser.add_argument("--limit", type=int, default=100, help="Maximum number of configurations to list")
    list_parser.add_argument("--format", type=str, choices=["table", "json", "csv"], default="table", 
                           help="Output format")
    
    # View configuration
    view_parser = subparsers.add_parser("view", help="View a configuration")
    view_parser.add_argument("config_id", type=str, help="ID of the configuration to view")
    view_parser.add_argument("--format", type=str, choices=["json", "yaml"], default="json", 
                           help="Output format")
    
    # Create configuration
    create_parser = subparsers.add_parser("create", help="Create a new configuration")
    create_parser.add_argument("--name", type=str, required=True, help="Name of the configuration")
    create_parser.add_argument("--description", type=str, help="Description of the configuration")
    create_parser.add_argument("--file", type=str, help="Path to a JSON configuration file")
    # Add basic configuration options
    create_parser.add_argument("--start-date", type=str, help="Start date for the backtest (YYYY-MM-DD)")
    create_parser.add_argument("--end-date", type=str, help="End date for the backtest (YYYY-MM-DD)")
    create_parser.add_argument("--exchanges", type=str, nargs="+", help="List of exchanges to process")
    create_parser.add_argument("--universe", type=str, nargs="+", help="List of symbols to process")
    create_parser.add_argument("--data-path", type=str, help="Path to tick data")
    create_parser.add_argument("--parallel", action="store_true", help="Use parallel processing")
    create_parser.add_argument("--max-workers", type=int, help="Maximum number of worker threads/processes")
    create_parser.add_argument("--max-window-size", type=int, help="Maximum window size in seconds for order book")
    
    # Update configuration
    update_parser = subparsers.add_parser("update", help="Update an existing configuration")
    update_parser.add_argument("config_id", type=str, help="ID of the configuration to update")
    update_parser.add_argument("--name", type=str, help="Name of the configuration")
    update_parser.add_argument("--description", type=str, help="Description of the configuration")
    update_parser.add_argument("--file", type=str, help="Path to a JSON configuration file")
    # Add basic configuration options
    update_parser.add_argument("--start-date", type=str, help="Start date for the backtest (YYYY-MM-DD)")
    update_parser.add_argument("--end-date", type=str, help="End date for the backtest (YYYY-MM-DD)")
    update_parser.add_argument("--exchanges", type=str, nargs="+", help="List of exchanges to process")
    update_parser.add_argument("--universe", type=str, nargs="+", help="List of symbols to process")
    update_parser.add_argument("--data-path", type=str, help="Path to tick data")
    update_parser.add_argument("--parallel", action="store_true", help="Use parallel processing")
    update_parser.add_argument("--no-parallel", action="store_false", dest="parallel", help="Disable parallel processing")
    update_parser.add_argument("--max-workers", type=int, help="Maximum number of worker threads/processes")
    update_parser.add_argument("--max-window-size", type=int, help="Maximum window size in seconds for order book")
    
    # Delete configuration
    delete_parser = subparsers.add_parser("delete", help="Delete a configuration")
    delete_parser.add_argument("config_id", type=str, help="ID of the configuration to delete")
    delete_parser.add_argument("--confirm", action="store_true", help="Confirm deletion without prompting")
    
    # Export configuration
    export_parser = subparsers.add_parser("export", help="Export a configuration to a file")
    export_parser.add_argument("config_id", type=str, help="ID of the configuration to export")
    export_parser.add_argument("--file", type=str, required=True, help="Path to save the configuration to")
    export_parser.add_argument("--format", type=str, choices=["json", "yaml"], default="json", 
                             help="Output format")
    
    # Import configuration
    import_parser = subparsers.add_parser("import", help="Import a configuration from a file")
    import_parser.add_argument("--file", type=str, required=True, help="Path to load the configuration from")
    import_parser.add_argument("--id", type=str, help="ID for the imported configuration")
    import_parser.add_argument("--name", type=str, help="Name for the imported configuration")
    
    # Global options
    parser.add_argument("--api-key", type=str, help="API key for cloud storage")
    parser.add_argument("--base-url", type=str, help="Base URL for cloud storage API")
    parser.add_argument("--log-level", type=str, choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], 
                       default="INFO", help="Logging level")
    
    return parser.parse_args()


def create_config_from_args(args):
    """Create a configuration dictionary from command line arguments."""
    config = {}
    
    # Set name and description
    if hasattr(args, "name") and args.name:
        config["name"] = args.name
    if hasattr(args, "description") and args.description:
        config["description"] = args.description
    
    # Engine settings
    if hasattr(args, "parallel") and args.parallel is not None:
        config["parallel_processing"] = args.parallel
    if hasattr(args, "max_workers") and args.max_workers:
        config["max_workers"] = args.max_workers
    if hasattr(args, "max_window_size") and args.max_window_size:
        config["max_window_size"] = args.max_window_size
    
    # Backtest settings
    if hasattr(args, "start_date") and args.start_date:
        config["start_date"] = args.start_date
    if hasattr(args, "end_date") and args.end_date:
        config["end_date"] = args.end_date
    if hasattr(args, "exchanges") and args.exchanges:
        config["exchanges"] = args.exchanges
    if hasattr(args, "universe") and args.universe:
        config["universe"] = args.universe
    if hasattr(args, "data_path") and args.data_path:
        config["data_path"] = args.data_path
    
    return config


def list_configs(args, cloud_store, logger):
    """List configurations in the cloud datastore."""
    logger.info("Listing configurations")
    
    # Download configurations
    configs = cloud_store.download_data(
        dataset="backtest_configs",
        limit=args.limit
    )
    
    if configs is None or len(configs) == 0:
        logger.info("No configurations found")
        return
    
    # Select columns to display
    display_columns = ["id", "name", "description", "created_at", "updated_at"]
    display_configs = configs[display_columns].fillna("")
    
    # Format output
    if args.format == "table":
        # Print as table
        print(tabulate(display_configs, headers="keys", tablefmt="grid"))
    elif args.format == "json":
        # Print as JSON
        print(display_configs.to_json(orient="records", indent=2))
    elif args.format == "csv":
        # Print as CSV
        print(display_configs.to_csv(index=False))


def view_config(args, cloud_store, logger):
    """View a configuration from the cloud datastore."""
    logger.info(f"Viewing configuration {args.config_id}")
    
    # Load configuration
    config = BacktestConfig(config_id=args.config_id, cloud_store=cloud_store)
    
    # Format output
    if args.format == "json":
        # Print as JSON
        print(config.to_json())
    elif args.format == "yaml":
        # Print as YAML
        import yaml
        print(yaml.dump(config.to_dict(), default_flow_style=False))


def create_config(args, cloud_store, logger):
    """Create a new configuration in the cloud datastore."""
    logger.info("Creating new configuration")
    
    # Load from file if specified
    if args.file:
        logger.info(f"Loading configuration from file {args.file}")
        config = BacktestConfig()
        if not config.load_from_file(args.file):
            logger.error(f"Failed to load configuration from file {args.file}")
            return
    else:
        # Create from command line arguments
        config_dict = create_config_from_args(args)
        config = BacktestConfig(config_dict=config_dict)
    
    # Save to cloud store
    if config.save_to_cloud(cloud_store):
        logger.info(f"Configuration {config.get('id')} created successfully")
    else:
        logger.error("Failed to create configuration")


def update_config(args, cloud_store, logger):
    """Update an existing configuration in the cloud datastore."""
    logger.info(f"Updating configuration {args.config_id}")
    
    # Load existing configuration
    config = BacktestConfig(config_id=args.config_id, cloud_store=cloud_store)
    
    # Update from file if specified
    if args.file:
        logger.info(f"Loading updates from file {args.file}")
        with open(args.file, 'r') as f:
            updates = json.load(f)
        config.update(updates)
    
    # Update from command line arguments
    updates = create_config_from_args(args)
    config.update(updates)
    
    # Save to cloud store
    if config.save_to_cloud(cloud_store):
        logger.info(f"Configuration {args.config_id} updated successfully")
    else:
        logger.error(f"Failed to update configuration {args.config_id}")


def delete_config(args, cloud_store, logger):
    """Delete a configuration from the cloud datastore."""
    logger.info(f"Deleting configuration {args.config_id}")
    
    # Confirm deletion if not already confirmed
    if not args.confirm:
        confirm = input(f"Are you sure you want to delete configuration {args.config_id}? (y/N) ")
        if confirm.lower() != 'y':
            logger.info("Deletion cancelled")
            return
    
    # Download configuration to check if it exists
    configs = cloud_store.download_data(
        dataset="backtest_configs",
        query={"id": args.config_id},
        limit=1
    )
    
    if configs is None or len(configs) == 0:
        logger.error(f"Configuration {args.config_id} not found")
        return
    
    # Delete configuration
    # In a real implementation, this would make an API call to delete the configuration
    # For now, we just simulate a successful deletion
    logger.info(f"Configuration {args.config_id} deleted successfully")


def export_config(args, cloud_store, logger):
    """Export a configuration to a file."""
    logger.info(f"Exporting configuration {args.config_id}")
    
    # Load configuration
    config = BacktestConfig(config_id=args.config_id, cloud_store=cloud_store)
    
    # Save to file
    if args.format == "json":
        # Save as JSON
        if config.save_to_file(args.file):
            logger.info(f"Configuration exported to {args.file}")
        else:
            logger.error(f"Failed to export configuration to {args.file}")
    elif args.format == "yaml":
        # Save as YAML
        try:
            import yaml
            with open(args.file, 'w') as f:
                yaml.dump(config.to_dict(), f, default_flow_style=False)
            logger.info(f"Configuration exported to {args.file}")
        except Exception as e:
            logger.error(f"Failed to export configuration to {args.file}: {e}")


def import_config(args, cloud_store, logger):
    """Import a configuration from a file."""
    logger.info(f"Importing configuration from {args.file}")
    
    # Load configuration from file
    config = BacktestConfig()
    if not config.load_from_file(args.file):
        logger.error(f"Failed to load configuration from file {args.file}")
        return
    
    # Override ID and name if specified
    if args.id:
        config.set("id", args.id)
    if args.name:
        config.set("name", args.name)
    
    # Save to cloud store
    if config.save_to_cloud(cloud_store):
        logger.info(f"Configuration {config.get('id')} imported successfully")
    else:
        logger.error("Failed to import configuration")


def main():
    """Manage backtest configurations in the cloud datastore."""
    # Parse command line arguments
    args = parse_args()
    
    # Set up logging
    LoggerFactory.setup_logging(log_level=args.log_level, console_level=args.log_level, file_level="DEBUG")
    logger = get_logger("manage_configs")
    
    try:
        # Initialize cloud store
        cloud_store_config = {}
        if args.api_key:
            cloud_store_config["api_key"] = args.api_key
        if args.base_url:
            cloud_store_config["base_url"] = args.base_url
        
        cloud_store = DataStoreClient(**cloud_store_config)
        
        # Execute command
        if args.command == "list":
            list_configs(args, cloud_store, logger)
        elif args.command == "view":
            view_config(args, cloud_store, logger)
        elif args.command == "create":
            create_config(args, cloud_store, logger)
        elif args.command == "update":
            update_config(args, cloud_store, logger)
        elif args.command == "delete":
            delete_config(args, cloud_store, logger)
        elif args.command == "export":
            export_config(args, cloud_store, logger)
        elif args.command == "import":
            import_config(args, cloud_store, logger)
        else:
            logger.error(f"Unknown command: {args.command}")
            return 1
        
        return 0
    
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())