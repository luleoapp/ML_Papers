"""
Reference data loading and processing.

This module provides a ReferenceDataLoader class for loading reference data
from cloud storage and preparing it for the C++ engine.
"""

import logging
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta

from backtest_simulator.utils.logging_config import get_logger
from backtest_simulator.utils.performance import PerformanceMonitor


class ReferenceDataLoader:
    """Loads reference data from cloud storage for the C++ engine."""
    
    def __init__(self, 
                cloud_store: Any = None,
                performance_monitor: Optional[PerformanceMonitor] = None):
        """Initialize the reference data loader.
        
        Args:
            cloud_store: Cloud storage client
            performance_monitor: Optional performance monitor for tracking metrics
        """
        # Set up logger
        self.logger = get_logger(f"{__name__}.ReferenceDataLoader")
        self.logger.info("Initializing reference data loader")
        
        # Save configuration
        self.cloud_store = cloud_store
        self.performance_monitor = performance_monitor
        
        self.logger.info("Reference data loader initialized")
    
    def load_reference_data(self, 
                           start_date: Union[str, datetime],
                           end_date: Union[str, datetime],
                           universe: List[str],
                           datasets: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Load reference data for the given time period and universe.
        
        Args:
            start_date: Start date for reference data
            end_date: End date for reference data
            universe: List of symbols to load data for
            datasets: Optional mapping of dataset types to dataset names
            
        Returns:
            Dictionary of reference data for the C++ engine
        """
        # Track performance if enabled
        if self.performance_monitor:
            self.performance_monitor.start_operation("load_reference_data")
        
        try:
            # Convert dates to strings if they are datetime objects
            if isinstance(start_date, datetime):
                start_date = start_date.strftime("%Y%m%d")
            if isinstance(end_date, datetime):
                end_date = end_date.strftime("%Y%m%d")
            
            self.logger.info(f"Loading reference data from {start_date} to {end_date} for {len(universe)} symbols")
            
            # Use default datasets if not provided
            if not datasets:
                datasets = {
                    "universe": "universe",
                    "pricing": "pricing",
                    "risk": "risk_models"
                }
            
            # Initialize result
            reference_data = {
                "universe": [],
                "pricing": {},
                "risk_models": {}
            }
            
            # If no cloud store is available, create minimal placeholder data
            if not self.cloud_store:
                self.logger.warning("No cloud store available, creating placeholder data")
                for symbol in universe:
                    reference_data["universe"].append({
                        "ticker": symbol,
                        "listing_exchange": "XNAS",
                        "sector": "Technology",
                        "is_index_member": True
                    })
                return reference_data
            
            # Load universe data
            if "universe" in datasets:
                universe_data = self.cloud_store.get_reference_data(
                    dataset=datasets["universe"],
                    universe=universe
                )
                
                if universe_data and "universe" in universe_data:
                    reference_data["universe"] = universe_data["universe"]
                else:
                    # Create minimal placeholder data if not available
                    self.logger.warning("Universe data not available, creating placeholder data")
                    for symbol in universe:
                        reference_data["universe"].append({
                            "ticker": symbol,
                            "listing_exchange": "XNAS",
                            "sector": "Technology",
                            "is_index_member": True
                        })
            
            # Load pricing data
            if "pricing" in datasets:
                pricing_data = self.cloud_store.get_reference_data(
                    dataset=datasets["pricing"],
                    date=start_date,
                    universe=universe
                )
                
                if pricing_data and "pricing" in pricing_data:
                    reference_data["pricing"] = pricing_data["pricing"]
            
            # Load risk model data
            if "risk" in datasets:
                risk_data = self.cloud_store.get_reference_data(
                    dataset=datasets["risk"],
                    date=start_date,
                    universe=universe
                )
                
                if risk_data and "risk_models" in risk_data:
                    reference_data["risk_models"] = risk_data["risk_models"]
            
            self.logger.info(f"Loaded reference data with {len(reference_data['universe'])} symbols")
            
            return reference_data
        
        except Exception as e:
            self.logger.error(f"Error loading reference data: {e}", exc_info=True)
            
            # Return minimal placeholder data on error
            reference_data = {"universe": []}
            for symbol in universe:
                reference_data["universe"].append({
                    "ticker": symbol,
                    "listing_exchange": "XNAS",
                    "sector": "Technology",
                    "is_index_member": True
                })
            
            return reference_data
        
        finally:
            # End performance tracking
            if self.performance_monitor:
                self.performance_monitor.end_operation("load_reference_data")