"""
Main backtest engine that coordinates the various components.

This module provides the BacktestEngine class that ties together the C++ engine,
callback system, thread management, and data processing.
"""

import os
import time
import logging
from typing import Dict, List, Any, Optional, Union, Tuple
from datetime import datetime, timedelta
from pathlib import Path

from backtest_simulator.utils.logging_config import get_logger, LoggerFactory
from backtest_simulator.utils.performance import PerformanceMonitor
from backtest_simulator.core.thread_manager import ThreadManager
from backtest_simulator.core.callback_manager import CallbackManager
from backtest_simulator.core.pybind_interface import CPPBacktestEngine
from backtest_simulator.data.marking_uploader import MarkingUploader
from backtest_simulator.data.cloud_store import DataStoreClient
from backtest_simulator.data.reference_data import ReferenceDataLoader


class BacktestEngine:
    """Main backtest engine that coordinates all components."""
    
    def __init__(self, 
                 use_cloud_store: bool = True,
                 cloud_store_config: Dict[str, Any] = None,
                 parallel_processing: bool = True,
                 max_workers: int = 4,
                 max_window_size: int = 3600,
                 upload_batch_size: int = 10000,
                 upload_interval: float = 5.0,
                 use_processes: bool = False,
                 log_level: str = "INFO",
                 performance_monitor_enabled: bool = True):
        """Initialize the backtest engine.
        
        Args:
            use_cloud_store: Whether to use cloud storage
            cloud_store_config: Configuration for cloud storage
            parallel_processing: Whether to use parallel processing
            max_workers: Maximum number of worker threads/processes
            max_window_size: Maximum window size in seconds for order book
            upload_batch_size: Batch size for marking uploads
            upload_interval: Interval between uploads in seconds
            use_processes: Whether to use processes instead of threads
            log_level: Logging level
            performance_monitor_enabled: Whether to enable performance monitoring
        """
        # Set up logging
        LoggerFactory.setup_logging(
            log_level=log_level,
            console_level=log_level,
            file_level="DEBUG"
        )
        
        # Set up logger
        self.logger = get_logger(f"{__name__}.BacktestEngine")
        self.logger.info("Initializing backtest engine")
        
        # Set up performance monitor if enabled
        self.performance_monitor = PerformanceMonitor() if performance_monitor_enabled else None
        
        # Save configuration
        self.use_cloud_store = use_cloud_store
        self.parallel_processing = parallel_processing
        self.max_workers = max_workers
        self.max_window_size = max_window_size
        self.upload_batch_size = upload_batch_size
        self.upload_interval = upload_interval
        
        # Initialize cloud storage if enabled
        self.cloud_store = None
        if use_cloud_store:
            self.logger.info("Initializing cloud storage client")
            self.cloud_store = DataStoreClient(**(cloud_store_config or {}))
        
        # Initialize the thread manager
        self.thread_manager = ThreadManager(
            max_processing_workers=max_workers,
            max_upload_workers=max(2, max_workers // 2),
            parallel_uploads=True,
            max_queue_size=upload_batch_size * 2,
            use_processes=use_processes,
            performance_monitor=self.performance_monitor
        )
        
        # Initialize the C++ backtest engine
        self.cpp_engine = CPPBacktestEngine(performance_monitor=self.performance_monitor)
        
        # Initialize the marking uploader if using cloud storage
        self.marking_uploader = None
        if use_cloud_store:
            self.marking_uploader = MarkingUploader(
                cloud_store=self.cloud_store,
                batch_size=upload_batch_size,
                upload_interval=upload_interval,
                performance_monitor=self.performance_monitor
            )
        
        # Initialize reference data loader
        self.reference_data_loader = ReferenceDataLoader(
            cloud_store=self.cloud_store if use_cloud_store else None,
            performance_monitor=self.performance_monitor
        )
        
        # Initialize configuration
        self.config = {}
        self.start_date = None
        self.end_date = None
        self.dates = []
        self.exchanges = []
        self.universe = []
        self.data_path = None
        
        self.configured = False
        
        self.logger.info("Backtest engine initialized")
    
    def configure(self, 
                 start_date: Union[str, datetime],
                 end_date: Union[str, datetime],
                 exchanges: List[str],
                 universe: List[str],
                 data_path: str,
                 reference_data: Dict[str, Any] = None,
                 **kwargs) -> bool:
        """Configure the backtest engine.
        
        Args:
            start_date: Start date for the backtest
            end_date: End date for the backtest
            exchanges: List of exchanges to process
            universe: List of symbols to process
            data_path: Path to tick data
            reference_data: Optional reference data to use
            **kwargs: Additional configuration parameters
            
        Returns:
            True if configuration was successful, False otherwise
        """
        self.logger.info("Configuring backtest engine")
        
        # Convert dates to datetime objects if they are strings
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, "%Y-%m-%d")
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, "%Y-%m-%d")
        
        # Save configuration
        self.start_date = start_date
        self.end_date = end_date
        self.exchanges = exchanges
        self.universe = universe
        self.data_path = data_path
        
        # Generate dates list
        self.dates = []
        current_date = start_date
        while current_date <= end_date:
            self.dates.append(current_date.strftime("%Y%m%d"))
            current_date += timedelta(days=1)
        
        # Build configuration dictionary for C++ engine
        self.config = {
            "start_date": start_date.strftime("%Y%m%d"),
            "end_date": end_date.strftime("%Y%m%d"),
            "exchanges": ",".join(exchanges),
            "universe": ",".join(universe),
            "data_path": data_path,
            "max_window_size": str(self.max_window_size),
            **kwargs
        }
        
        # Configure C++ engine
        success = self.cpp_engine.configure(self.config)
        
        if not success:
            self.logger.error("Failed to configure C++ engine")
            return False
        
        # Load reference data if provided or if a loader is available
        if reference_data:
            self.logger.info("Setting provided reference data")
            success = self.cpp_engine.set_reference_data(reference_data)
            
            if not success:
                self.logger.error("Failed to set reference data")
                return False
        elif self.use_cloud_store and hasattr(self.reference_data_loader, 'load_reference_data'):
            self.logger.info("Loading reference data from cloud store")
            reference_data = self.reference_data_loader.load_reference_data(
                start_date=start_date,
                end_date=end_date,
                universe=universe
            )
            
            success = self.cpp_engine.set_reference_data(reference_data)
            
            if not success:
                self.logger.error("Failed to set reference data")
                return False
        
        # Register callback manager with C++ engine
        success = self.cpp_engine.register_callback_manager(self.thread_manager.callback_manager)
        
        if not success:
            self.logger.error("Failed to register callback manager with C++ engine")
            return False
        
        # Start callback processing if using cloud storage
        if self.use_cloud_store and self.marking_uploader:
            self.logger.info("Starting callback processing for cloud uploads")
            self.thread_manager.start_callback_processing(self.marking_uploader.add_markings)
        
        self.configured = True
        self.logger.info("Backtest engine configured successfully")
        return True
    
    def run(self, parallel: bool = None) -> List[Dict[str, Any]]:
        """Run the backtest.
        
        Args:
            parallel: Whether to use parallel processing (overrides init setting if provided)
            
        Returns:
            List of results from processing each day
        """
        if not self.configured:
            self.logger.error("Backtest engine not configured")
            raise RuntimeError("Backtest engine must be configured before running")
        
        # Determine whether to use parallel processing
        use_parallel = self.parallel_processing if parallel is None else parallel
        
        self.logger.info(f"Running backtest from {self.start_date.strftime('%Y-%m-%d')} to "
                        f"{self.end_date.strftime('%Y-%m-%d')} with "
                        f"{'parallel' if use_parallel else 'serial'} processing")
        
        # Track performance if enabled
        if self.performance_monitor:
            self.performance_monitor.start_operation("backtest_run")
        
        try:
            if use_parallel:
                # Run days in parallel
                self.logger.info(f"Processing {len(self.dates)} days in parallel with {self.max_workers} workers")
                
                # Define a function to process a single day
                def process_day_task(date_str):
                    return self.thread_manager.execute_day_processing(
                        date_str=date_str,
                        process_func=lambda d: self.cpp_engine.process_day(d, self.max_window_size),
                        max_window_size=self.max_window_size
                    )
                
                # Process all days in parallel
                results = self.thread_manager.parallel_execute(
                    items=self.dates,
                    task_func=process_day_task,
                    description="Processing days"
                )
            
            else:
                # Run days serially
                self.logger.info(f"Processing {len(self.dates)} days serially")
                results = []
                
                for date_str in self.dates:
                    # Process the day
                    result = self.thread_manager.execute_day_processing(
                        date_str=date_str,
                        process_func=lambda d: self.cpp_engine.process_day(d, self.max_window_size),
                        max_window_size=self.max_window_size
                    )
                    
                    results.append(result)
            
            self.logger.info(f"Backtest completed with {len(results)} results")
            
            # Wait for any remaining callbacks to be processed
            time.sleep(1.0)
            
            return results
        
        finally:
            # End performance tracking
            if self.performance_monitor:
                self.performance_monitor.end_operation("backtest_run")
    
    def shutdown(self, wait_for_callbacks: bool = True, timeout: Optional[float] = 60.0) -> None:
        """Shutdown the backtest engine and cleanup resources.
        
        Args:
            wait_for_callbacks: Whether to wait for callbacks to complete
            timeout: Maximum time to wait for callbacks to complete
        """
        self.logger.info("Shutting down backtest engine")
        
        # Stop callback processing
        if hasattr(self, 'thread_manager'):
            self.thread_manager.stop_callback_processing(
                wait_for_completion=wait_for_callbacks,
                timeout=timeout
            )
        
        # Flush marking uploader if using cloud storage
        if self.use_cloud_store and hasattr(self, 'marking_uploader') and self.marking_uploader:
            self.logger.info("Flushing marking uploader")
            self.marking_uploader.flush()
        
        # Shutdown thread manager
        if hasattr(self, 'thread_manager'):
            self.logger.info("Shutting down thread manager")
            self.thread_manager.shutdown(wait=wait_for_callbacks)
        
        # Print performance summary if enabled
        if hasattr(self, 'performance_monitor') and self.performance_monitor:
            self.logger.info("Performance summary:")
            self.logger.info(self.performance_monitor.get_summary_text())
        
        self.logger.info("Backtest engine shutdown complete")
    
    def __del__(self):
        """Clean up resources when the instance is garbage collected."""
        try:
            self.shutdown(wait_for_callbacks=False)
        except:
            pass  # Ignore errors during garbage collection