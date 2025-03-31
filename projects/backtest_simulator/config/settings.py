"""
Configuration settings for the backtest simulator.

This module provides configuration management for the backtest simulator,
including loading configurations from the cloud datastore.
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
from pathlib import Path

from backtest_simulator.utils.logging_config import get_logger


class BacktestConfig:
    """Configuration for the backtest simulator."""
    
    def __init__(self, 
                config_id: Optional[str] = None,
                cloud_store = None,
                config_dict: Optional[Dict[str, Any]] = None):
        """Initialize the backtest configuration.
        
        Args:
            config_id: ID of the configuration to load from cloud store
            cloud_store: Cloud storage client
            config_dict: Configuration dictionary (overrides cloud store)
        """
        # Set up logger
        self.logger = get_logger(f"{__name__}.BacktestConfig")
        self.logger.info("Initializing backtest configuration")
        
        # Initialize with empty configuration
        self.config = {
            "id": None,
            "name": None,
            "description": None,
            "created_at": None,
            "updated_at": None,
            
            # Engine settings
            "use_cloud_store": True,
            "parallel_processing": True,
            "max_workers": 4,
            "max_window_size": 3600,
            "upload_batch_size": 10000,
            "upload_interval": 5.0,
            "use_processes": False,
            "log_level": "INFO",
            "performance_monitor_enabled": True,
            
            # Backtest settings
            "start_date": None,
            "end_date": None,
            "exchanges": [],
            "universe": [],
            "data_path": None,
            
            # Cloud store settings
            "cloud_store_config": {
                "api_key": None,
                "base_url": None,
                "timeout": 30.0,
                "max_retries": 3
            },
            
            # Reference data settings
            "reference_data_datasets": {
                "universe": "universe",
                "pricing": "pricing",
                "risk": "risk_models"
            },
            
            # Output settings
            "output_dataset": "backtest_results",
            "output_partition": None
        }
        
        # Load from cloud store if config_id is provided
        if config_id and cloud_store:
            self.load_from_cloud(config_id, cloud_store)
        
        # Override with provided dictionary if any
        if config_dict:
            self.update(config_dict)
        
        # Generate a default ID if none provided
        if not self.config["id"]:
            self.config["id"] = f"config_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Set default dates if not provided
        today = datetime.now()
        if not self.config["end_date"]:
            self.config["end_date"] = (today - timedelta(days=1)).strftime("%Y-%m-%d")
        if not self.config["start_date"]:
            self.config["start_date"] = (today - timedelta(days=30)).strftime("%Y-%m-%d")
        
        # Set default output partition if not provided
        if not self.config["output_partition"]:
            self.config["output_partition"] = f"{self.config['id']}/{datetime.now().strftime('%Y%m%d')}"
            
        self.logger.info(f"Backtest configuration initialized with ID {self.config['id']}")
    
    def load_from_cloud(self, config_id: str, cloud_store) -> bool:
        """Load configuration from cloud store.
        
        Args:
            config_id: ID of the configuration to load
            cloud_store: Cloud storage client
            
        Returns:
            True if configuration was loaded successfully, False otherwise
        """
        self.logger.info(f"Loading configuration {config_id} from cloud store")
        
        try:
            # Download configuration from cloud store
            config_data = cloud_store.download_data(
                dataset="backtest_configs",
                query={"id": config_id},
                limit=1
            )
            
            if config_data is None or len(config_data) == 0:
                self.logger.error(f"Configuration {config_id} not found in cloud store")
                return False
            
            # Convert DataFrame to dictionary
            config_dict = config_data.iloc[0].to_dict()
            
            # Parse any JSON string values
            for key, value in config_dict.items():
                if isinstance(value, str) and (value.startswith('{') or value.startswith('[')):
                    try:
                        config_dict[key] = json.loads(value)
                    except:
                        pass
            
            # Update configuration
            self.update(config_dict)
            
            self.logger.info(f"Configuration {config_id} loaded successfully")
            return True
        
        except Exception as e:
            self.logger.error(f"Error loading configuration from cloud store: {e}", exc_info=True)
            return False
    
    def save_to_cloud(self, cloud_store) -> bool:
        """Save configuration to cloud store.
        
        Args:
            cloud_store: Cloud storage client
            
        Returns:
            True if configuration was saved successfully, False otherwise
        """
        self.logger.info(f"Saving configuration {self.config['id']} to cloud store")
        
        try:
            # Update timestamps
            now = datetime.now().isoformat()
            if not self.config["created_at"]:
                self.config["created_at"] = now
            self.config["updated_at"] = now
            
            # Convert configuration to DataFrame
            import pandas as pd
            
            # Convert nested dictionaries to JSON strings
            config_dict = {}
            for key, value in self.config.items():
                if isinstance(value, (dict, list)):
                    config_dict[key] = json.dumps(value)
                else:
                    config_dict[key] = value
            
            config_df = pd.DataFrame([config_dict])
            
            # Upload to cloud store
            result = cloud_store.upload_data(
                df=config_df,
                dataset="backtest_configs",
                mode="overwrite"
            )
            
            if result:
                self.logger.info(f"Configuration {self.config['id']} saved successfully")
                return True
            else:
                self.logger.error(f"Failed to save configuration {self.config['id']}")
                return False
        
        except Exception as e:
            self.logger.error(f"Error saving configuration to cloud store: {e}", exc_info=True)
            return False
    
    def update(self, config_dict: Dict[str, Any]) -> None:
        """Update configuration with values from a dictionary.
        
        Args:
            config_dict: Dictionary of configuration values to update
        """
        # Update top-level keys
        for key, value in config_dict.items():
            if key in self.config:
                # Special handling for nested dictionaries
                if isinstance(self.config[key], dict) and isinstance(value, dict):
                    self.config[key].update(value)
                else:
                    self.config[key] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value.
        
        Args:
            key: Configuration key
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set a configuration value.
        
        Args:
            key: Configuration key
            value: Configuration value
        """
        self.config[key] = value
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary.
        
        Returns:
            Dictionary of configuration values
        """
        return self.config.copy()
    
    def from_dict(self, config_dict: Dict[str, Any]) -> None:
        """Load configuration from dictionary.
        
        Args:
            config_dict: Dictionary of configuration values
        """
        self.config = config_dict.copy()
    
    def to_json(self) -> str:
        """Convert configuration to JSON string.
        
        Returns:
            JSON string of configuration values
        """
        return json.dumps(self.config, indent=2)
    
    def from_json(self, json_str: str) -> None:
        """Load configuration from JSON string.
        
        Args:
            json_str: JSON string of configuration values
        """
        self.config = json.loads(json_str)
    
    def save_to_file(self, file_path: str) -> bool:
        """Save configuration to a JSON file.
        
        Args:
            file_path: Path to save the file to
            
        Returns:
            True if configuration was saved successfully, False otherwise
        """
        try:
            with open(file_path, 'w') as f:
                json.dump(self.config, f, indent=2)
            return True
        except Exception as e:
            self.logger.error(f"Error saving configuration to file: {e}", exc_info=True)
            return False
    
    def load_from_file(self, file_path: str) -> bool:
        """Load configuration from a JSON file.
        
        Args:
            file_path: Path to load the file from
            
        Returns:
            True if configuration was loaded successfully, False otherwise
        """
        try:
            with open(file_path, 'r') as f:
                self.config = json.load(f)
            return True
        except Exception as e:
            self.logger.error(f"Error loading configuration from file: {e}", exc_info=True)
            return False