#!/usr/bin/env python
"""Example script for running versioned backtests."""

import os
import sys
from pathlib import Path
import pandas as pd
from datetime import datetime, timedelta
import json
import argparse

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest_simulator import BacktestEngine


def print_section(title):
    """Print a section title."""
    print(f"\n{'-' * 80}")
    print(f"  {title}")
    print(f"{'-' * 80}")


def create_and_run_version(store_path: str, run_name: str, marking_configs: list):
    """Create and run a new backtest version."""
    print_section(f"Creating and running version: {run_name}")
    
    # Initialize engine with versioning
    engine = BacktestEngine(use_versioning=True, local_store_path=store_path)
    
    # Get dates for the backtest
    today = datetime.now()
    start_date = today - timedelta(days=30)
    end_date = today - timedelta(days=1)
    
    # Configure the engine
    engine.configure(
        start_date=start_date,
        end_date=end_date,
        exchanges=["XNAS"],
        universe=["AAPL", "MSFT", "GOOGL", "AMZN", "META"],
        max_window_size=3600,
        use_multiple_exchanges=False,
        marking_configs=marking_configs,
        run_description=f"Backtest run: {run_name}",
        run_tags=["example", run_name]
    )
    
    # Get the current run ID
    run_id = engine.get_current_run_id()
    print(f"Created run version with ID: {run_id}")
    
    # Run the backtest
    print("Running backtest...")
    results = engine.run()
    print(f"Backtest complete with {len(results)} results")
    
    # Save results
    results_path = Path(store_path) / f"results_{run_id}.parquet"
    engine.save_results(str(results_path))
    print(f"Results saved to: {results_path}")
    
    return run_id, engine


def modify_and_rerun(engine, original_run_id, modifications):
    """Modify parameters and rerun a backtest version."""
    print_section(f"Rerunning version {original_run_id} with modifications")
    
    # Print the modifications
    print("Modifications:")
    for key, value in modifications.items():
        print(f"  {key}: {value}")
    
    # Rerun with modifications
    new_run_id = engine.rerun_version(
        original_run_id,
        override_params=modifications,
        description=f"Modified version of {original_run_id}"
    )
    
    print(f"Created new run version with ID: {new_run_id}")
    
    # Run the backtest
    print("Running backtest...")
    results = engine.run()
    print(f"Backtest complete with {len(results)} results")
    
    # Save results
    results_path = Path(engine.run_manager.local_store_path) / f"results_{new_run_id}.parquet"
    engine.save_results(str(results_path))
    print(f"Results saved to: {results_path}")
    
    return new_run_id


def list_and_compare_versions(engine, version_ids):
    """List and compare backtest versions."""
    print_section("Listing and comparing versions")
    
    # Get all versions
    print("All available versions:")
    all_versions = engine.list_run_versions()
    for v in all_versions:
        print(f"  {v['version_id']}: {v['description']}")
    
    # Compare specified versions
    if len(version_ids) >= 2:
        print(f"\nComparing versions: {version_ids[0]} vs {version_ids[1]}")
        v1 = engine.get_run_version(version_ids[0])
        v2 = engine.get_run_version(version_ids[1])
        
        # Compare configs
        print("\nConfiguration differences:")
        for key in set(v1["config"].keys()) | set(v2["config"].keys()):
            if key not in v1["config"]:
                print(f"  {key}: [not in v1] -> {v2['config'][key]}")
            elif key not in v2["config"]:
                print(f"  {key}: {v1['config'][key]} -> [not in v2]")
            elif v1["config"][key] != v2["config"][key]:
                print(f"  {key}: {v1['config'][key]} -> {v2['config'][key]}")
        
        # Compare metrics
        if "metrics" in v1 and "metrics" in v2:
            print("\nMetrics comparison:")
            for key in set(v1["metrics"].keys()) | set(v2["metrics"].keys()):
                if key not in v1["metrics"]:
                    print(f"  {key}: [not in v1] -> {v2['metrics'][key]}")
                elif key not in v2["metrics"]:
                    print(f"  {key}: {v1['metrics'][key]} -> [not in v2]")
                elif v1["metrics"][key] != v2["metrics"][key]:
                    print(f"  {key}: {v1['metrics'][key]} -> {v2['metrics'][key]}")


def mark_production_version(engine, version_id):
    """Mark a version as production."""
    print_section(f"Marking version {version_id} as production")
    
    # Mark as production
    success = engine.mark_as_production(version_id)
    
    if success:
        print(f"Successfully marked version {version_id} as production")
    else:
        print(f"Failed to mark version {version_id} as production")
    
    # Get and print the production version
    prod_version = engine.get_production_version()
    if prod_version:
        print(f"Current production version: {prod_version['version_id']}")
        print(f"Description: {prod_version['description']}")
        print(f"Created at: {prod_version['created_at']}")
    else:
        print("No production version set")


def manage_marking_configs(engine, store_path):
    """Create and manage marking configurations."""
    print_section("Managing marking configurations")
    
    # Create marking configuration for ISO trades
    iso_marking = engine.create_marking_config(
        name="iso_marking",
        parameters={
            "threshold": 0.5,
            "window_size": 10,
            "use_log_returns": True
        },
        version="1.0.0",
        description="ISO trade marking configuration"
    )
    print(f"Created ISO marking configuration: {iso_marking.name} v{iso_marking.version}")
    
    # Create marking configuration for sweep trades
    sweep_marking = engine.create_marking_config(
        name="sweep_marking",
        parameters={
            "min_size": 1000,
            "max_levels": 3,
            "aggressive_side_only": True
        },
        version="1.0.0",
        description="Sweep trade marking configuration"
    )
    print(f"Created sweep marking configuration: {sweep_marking.name} v{sweep_marking.version}")
    
    # Create an updated version of ISO marking
    iso_marking_v2 = engine.create_marking_config(
        name="iso_marking",
        parameters={
            "threshold": 0.4,  # Lower threshold
            "window_size": 15,  # Larger window
            "use_log_returns": True
        },
        version="1.1.0",
        description="ISO trade marking with adjusted parameters"
    )
    print(f"Created updated ISO marking configuration: {iso_marking_v2.name} v{iso_marking_v2.version}")
    
    # List all marking types
    marking_types = engine.marking_manager.list_marking_types()
    print(f"\nAvailable marking types: {marking_types}")
    
    # List versions for a marking type
    for marking_type in marking_types:
        versions = engine.marking_manager.list_marking_versions(marking_type)
        print(f"\nVersions for {marking_type}: {versions}")
        
        # Get latest version
        latest = engine.marking_manager.get_marking_config(marking_type)
        print(f"Latest version of {marking_type}: v{latest.version}")
        print(f"Parameters: {latest.parameters}")
    
    # Create a bundle of markings
    bundle = engine.marking_manager.create_marking_bundle(
        name="standard_markings",
        marking_configs=[iso_marking_v2, sweep_marking],
        description="Bundle of standard markings for production use"
    )
    print(f"\nCreated marking bundle: {bundle['name']}")
    print(f"Contains {len(bundle['markings'])} markings")
    
    # Return the bundle for use in backtests
    return bundle


def run_versioned_backtest_demo():
    """Run a complete demonstration of versioned backtesting."""
    # Create a store path for this example
    store_path = Path.home() / ".backtest_store" / "example"
    store_path.mkdir(parents=True, exist_ok=True)
    print(f"Using store path: {store_path}")
    
    # Initialize engine to manage marking configurations
    engine = BacktestEngine(use_versioning=True, local_store_path=str(store_path))
    
    # Create and manage marking configurations
    bundle = manage_marking_configs(engine, store_path)
    
    # Get markings from the bundle
    markings = engine.marking_manager.get_markings_from_bundle("standard_markings")
    
    # Create and run initial version
    v1_id, engine = create_and_run_version(
        str(store_path),
        "initial_version",
        markings
    )
    
    # Modify parameters and rerun
    modifications = {
        "max_window_size": 7200,  # Increase from 3600 to 7200
        "buffer_size": 20000      # Add a new parameter
    }
    v2_id = modify_and_rerun(engine, v1_id, modifications)
    
    # List and compare versions
    list_and_compare_versions(engine, [v1_id, v2_id])
    
    # Mark the better version as production
    # In a real scenario, you would choose based on performance metrics
    mark_production_version(engine, v2_id)
    
    print_section("All steps completed successfully")
    print("Backtest versions and results are stored in:")
    print(f"  {store_path}")


if __name__ == "__main__":
    # Add command-line options
    parser = argparse.ArgumentParser(description="Run a versioned backtest demo")
    parser.add_argument("--store-path", help="Path to store backtest data")
    args = parser.parse_args()
    
    # Use provided store path or default
    store_path = args.store_path or None
    
    # Run the demo
    run_versioned_backtest_demo()