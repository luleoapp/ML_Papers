"""
Thread manager for coordinating parallel processing and callbacks.

This module provides a ThreadManager class that manages threads for parallel
execution of backtest tasks and coordinates callback handling.
"""

import os
import time
import logging
import threading
import multiprocessing
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from typing import Dict, List, Any, Callable, Optional, Tuple, TypeVar, Generic, Iterator

from backtest_simulator.utils.logging_config import get_logger
from backtest_simulator.utils.performance import PerformanceMonitor
from backtest_simulator.core.callback_manager import CallbackManager


# Type variables for generic function typing
T = TypeVar('T')
R = TypeVar('R')


class ThreadManager:
    """Manages threads for parallel execution and callback handling."""
    
    def __init__(self, 
                max_processing_workers: int = 4,
                max_upload_workers: int = 4,
                parallel_uploads: bool = True,
                max_queue_size: int = 1000,
                use_processes: bool = False,
                performance_monitor: Optional[PerformanceMonitor] = None):
        """Initialize the thread manager.
        
        Args:
            max_processing_workers: Maximum number of worker threads for processing
            max_upload_workers: Maximum number of worker threads for uploads
            parallel_uploads: Whether to use parallel uploads
            max_queue_size: Maximum size of the markings queue
            use_processes: Whether to use processes instead of threads for processing
            performance_monitor: Optional performance monitor for tracking metrics
        """
        # Set up logger
        self.logger = get_logger(f"{__name__}.ThreadManager")
        self.logger.info("Initializing thread manager")
        
        # Save configuration
        self.max_processing_workers = max_processing_workers
        self.max_upload_workers = max_upload_workers
        self.parallel_uploads = parallel_uploads
        self.max_queue_size = max_queue_size
        self.use_processes = use_processes
        self.performance_monitor = performance_monitor
        
        # Initialize callback manager
        self.callback_manager = CallbackManager(
            max_queue_size=max_queue_size,
            parallel_uploads=parallel_uploads,
            max_upload_workers=max_upload_workers,
            performance_monitor=performance_monitor
        )
        
        # Initialize executor for processing
        if use_processes:
            self.logger.info(f"Using process pool with {max_processing_workers} workers")
            self.executor = ProcessPoolExecutor(max_workers=max_processing_workers)
        else:
            self.logger.info(f"Using thread pool with {max_processing_workers} workers")
            self.executor = ThreadPoolExecutor(
                max_workers=max_processing_workers,
                thread_name_prefix="backtest_worker"
            )
        
        # Set up statistics
        self.stats_lock = threading.RLock()
        self.submitted_tasks = 0
        self.completed_tasks = 0
        self.failed_tasks = 0
        
        self.logger.info("Thread manager initialized")
    
    def parallel_execute(self, 
                         items: List[T], 
                         task_func: Callable[[T], R], 
                         description: str = "Processing items",
                         show_progress: bool = True) -> List[R]:
        """Execute a task function on multiple items in parallel.
        
        Args:
            items: List of items to process
            task_func: Function to call for each item
            description: Description of the task for logging
            show_progress: Whether to show progress logs
            
        Returns:
            List of results from the task function
        """
        if not items:
            self.logger.warning(f"No items to process for '{description}'")
            return []
        
        # Log start of processing
        self.logger.info(f"Starting {description} with {len(items)} items using {self.max_processing_workers} workers")
        
        # Track performance if enabled
        if self.performance_monitor:
            self.performance_monitor.start_operation(f"parallel_execute_{description.replace(' ', '_')}")
        
        results = []
        futures = {}
        
        try:
            # Submit all tasks
            for item in items:
                future = self.executor.submit(task_func, item)
                futures[future] = item
                
                with self.stats_lock:
                    self.submitted_tasks += 1
            
            # Process results as they complete
            items_total = len(items)
            items_processed = 0
            progress_pct = 0
            progress_step = 10  # Log every 10%
            
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                    
                    with self.stats_lock:
                        self.completed_tasks += 1
                    
                    # Update and log progress if enabled
                    if show_progress:
                        items_processed += 1
                        new_progress_pct = int(items_processed * 100 / items_total)
                        
                        if new_progress_pct >= progress_pct + progress_step:
                            progress_pct = new_progress_pct
                            self.logger.info(f"{description} progress: {progress_pct}% ({items_processed}/{items_total})")
                
                except Exception as e:
                    # Log error
                    item = futures[future]
                    self.logger.error(f"Error processing item {item}: {e}", exc_info=True)
                    
                    with self.stats_lock:
                        self.failed_tasks += 1
            
            # Log completion
            self.logger.info(f"Completed {description} with {len(results)} successful results out of {len(items)} items")
            
            return results
        
        finally:
            # End performance tracking
            if self.performance_monitor:
                self.performance_monitor.end_operation(f"parallel_execute_{description.replace(' ', '_')}")
    
    def start_callback_processing(self, upload_func: Callable[[List[Dict[str, Any]]], bool]) -> bool:
        """Start processing callbacks.
        
        Args:
            upload_func: Function to call with each batch of marking data
            
        Returns:
            True if processing was started successfully, False otherwise
        """
        return self.callback_manager.start_processing(upload_func)
    
    def stop_callback_processing(self, wait_for_completion: bool = True, timeout: Optional[float] = 60.0) -> bool:
        """Stop processing callbacks.
        
        Args:
            wait_for_completion: Whether to wait for processing to complete
            timeout: Maximum time to wait for processing to complete
            
        Returns:
            True if processing was stopped successfully, False otherwise
        """
        return self.callback_manager.stop_processing(wait_for_completion, timeout)
    
    def execute_day_processing(self, 
                              date_str: str, 
                              process_func: Callable[[str], Dict[str, Any]],
                              max_window_size: int = 3600) -> Dict[str, Any]:
        """Execute processing for a single day.
        
        Args:
            date_str: Date string to process (YYYYMMDD format)
            process_func: Function to call for processing the day
            max_window_size: Maximum window size in seconds for order book
            
        Returns:
            Results from the processing function
        """
        # Log start of processing
        self.logger.info(f"Processing day {date_str} with max window size {max_window_size}")
        
        # Track performance if enabled
        if self.performance_monitor:
            self.performance_monitor.start_operation(f"process_day_{date_str}")
        
        try:
            # Execute the processing function
            result = process_func(date_str)
            
            # Log completion
            self.logger.info(f"Completed processing day {date_str}")
            
            return result
        
        except Exception as e:
            # Log error
            self.logger.error(f"Error processing day {date_str}: {e}", exc_info=True)
            raise
        
        finally:
            # End performance tracking
            if self.performance_monitor:
                self.performance_monitor.end_operation(f"process_day_{date_str}")
    
    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the thread manager.
        
        Args:
            wait: Whether to wait for tasks to complete
        """
        # Log shutdown
        self.logger.info("Shutting down thread manager")
        
        # Shutdown the executor
        if self.executor is not None:
            self.executor.shutdown(wait=wait)
            self.executor = None
        
        # Log shutdown complete
        self.logger.info("Thread manager shutdown complete")