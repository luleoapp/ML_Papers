"""Thread management for backtest simulator."""

import threading
import time
import queue
import logging
from typing import Dict, List, Any, Optional, Callable, Union, Tuple
import concurrent.futures
from datetime import datetime
import os

from ..utils.logging_config import get_logger
from ..utils.performance import timed_operation, PerformanceMonitor
from .callback_manager import CallbackManager

# Configure logger
logger = get_logger(__name__)


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
            max_processing_workers: Maximum number of workers for processing
            max_upload_workers: Maximum number of workers for uploading
            parallel_uploads: Whether to upload marking data in parallel
            max_queue_size: Maximum size of the marking data queue
            use_processes: Whether to use processes instead of threads for processing
            performance_monitor: Performance monitor instance
        """
        self.logger = get_logger(f"{__name__}.ThreadManager")
        self.logger.info("Initializing thread manager")
        
        # Set up parameters
        self.max_processing_workers = max_processing_workers
        self.max_upload_workers = max_upload_workers
        self.parallel_uploads = parallel_uploads
        self.max_queue_size = max_queue_size
        self.use_processes = use_processes
        
        # Set up performance monitoring
        self.performance_monitor = performance_monitor
        
        # Create callback manager
        self.callback_manager = CallbackManager(
            max_queue_size=max_queue_size,
            parallel_uploads=parallel_uploads,
            max_upload_workers=max_upload_workers,
            performance_monitor=performance_monitor
        )
        
        # Create executor for processing
        if use_processes:
            self.executor = concurrent.futures.ProcessPoolExecutor(
                max_workers=max_processing_workers
            )
            self.logger.info(f"Using process pool with {max_processing_workers} workers")
        else:
            self.executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=max_processing_workers,
                thread_name_prefix="processing_worker"
            )
            self.logger.info(f"Using thread pool with {max_processing_workers} workers")
        
        # Statistics
        self.submitted_tasks = 0
        self.completed_tasks = 0
        self.failed_tasks = 0
        self.stats_lock = threading.Lock()
        
        self.logger.info("Thread manager initialized")
    
    def start_callback_processing(self, upload_func: Callable[[List[Dict[str, Any]]], None]) -> None:
        """Start processing callbacks.
        
        Args:
            upload_func: Function to call for uploading marking data
        """
        self.logger.info("Starting callback processing")
        self.callback_manager.start_processing(upload_func)
    
    def stop_callback_processing(self, wait_for_completion: bool = True, timeout: Optional[float] = 60.0) -> None:
        """Stop processing callbacks.
        
        Args:
            wait_for_completion: Whether to wait for all queued batches to be processed
            timeout: Maximum time to wait for processing to complete
        """
        self.logger.info("Stopping callback processing")
        self.callback_manager.stop_processing(
            wait_for_completion=wait_for_completion,
            timeout=timeout
        )
    
    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the thread manager.
        
        Args:
            wait: Whether to wait for all tasks to complete
        """
        self.logger.info("Shutting down thread manager")
        
        # Stop callback processing
        self.stop_callback_processing(wait_for_completion=wait)
        
        # Shutdown executor
        self.executor.shutdown(wait=wait)
        
        # Log final statistics
        with self.stats_lock:
            self.logger.info(
                f"Thread manager summary: Submitted {self.submitted_tasks} tasks, "
                f"Completed {self.completed_tasks}, Failed {self.failed_tasks}"
            )
    
    @timed_operation("parallel_execute")
    def parallel_execute(self, 
                        items: List[Any], 
                        task_func: Callable[[Any], Any],
                        combine_results_func: Optional[Callable[[List[Any]], Any]] = None,
                        description: str = "Processing items") -> Union[List[Any], Any]:
        """Execute tasks in parallel.
        
        Args:
            items: List of items to process
            task_func: Function to apply to each item
            combine_results_func: Optional function to combine the results
            description: Description of the processing task for logging
            
        Returns:
            List of results in the same order as input items, or combined result
        """
        if not items:
            self.logger.warning(f"{description}: No items to process")
            return [] if combine_results_func is None else combine_results_func([])
        
        self.logger.info(f"{description}: Starting parallel execution of {len(items)} items")
        
        # Initialize results list
        results = [None] * len(items)
        futures_to_index = {}
        
        # Submit tasks to executor
        for i, item in enumerate(items):
            future = self.executor.submit(self._execute_task, task_func, item, i)
            futures_to_index[future] = i
            
            # Update statistics
            with self.stats_lock:
                self.submitted_tasks += 1
        
        # Process results as they complete
        completed = 0
        last_log_time = time.time()
        start_time = time.time()
        
        for future in concurrent.futures.as_completed(futures_to_index):
            index = futures_to_index[future]
            
            try:
                result, task_index, success = future.result()
                
                # Store the result
                results[index] = result
                
                # Update statistics
                with self.stats_lock:
                    if success:
                        self.completed_tasks += 1
                    else:
                        self.failed_tasks += 1
            
            except Exception as e:
                self.logger.error(f"Error processing item {index}: {e}")
                
                # Update statistics
                with self.stats_lock:
                    self.failed_tasks += 1
            
            # Log progress
            completed += 1
            now = time.time()
            if now - last_log_time >= 5.0 or completed == len(items):  # Log every 5 seconds or at end
                progress = (completed / len(items)) * 100
                elapsed = now - start_time
                rate = completed / elapsed if elapsed > 0 else 0
                remaining = (elapsed / completed) * (len(items) - completed) if completed > 0 else 0
                
                self.logger.info(
                    f"{description}: Progress: {progress:.1f}% ({completed}/{len(items)}) "
                    f"- {rate:.2f} items/sec - ETA: {remaining:.1f}s"
                )
                last_log_time = now
        
        # Calculate final statistics
        end_time = time.time()
        total_time = end_time - start_time
        rate = len(items) / total_time if total_time > 0 else 0
        
        self.logger.info(
            f"{description}: Completed execution of {len(items)} items in {total_time:.2f} seconds "
            f"({rate:.2f} items/sec)"
        )
        
        # Combine results if needed
        if combine_results_func is not None:
            self.logger.info("Combining results")
            return combine_results_func(results)
        
        return results
    
    def _execute_task(self, task_func: Callable[[Any], Any], item: Any, index: int) -> Tuple[Any, int, bool]:
        """Execute a task with proper error handling.
        
        Args:
            task_func: Function to apply to the item
            item: Item to process
            index: Index of the item in the original list
            
        Returns:
            Tuple containing (result, index, success flag)
        """
        task_id = f"task_{index}_{os.getpid()}_{threading.get_ident()}"
        
        try:
            # Record performance if enabled
            timer_id = None
            if self.performance_monitor:
                timer_id = self.performance_monitor.start_timer(
                    "execute_task",
                    {"task_id": task_id, "index": index}
                )
            
            # Execute the task
            result = task_func(item)
            
            # Log performance data
            if self.performance_monitor and timer_id:
                self.performance_monitor.stop_timer(
                    timer_id,
                    {"success": True}
                )
            
            return result, index, True
        
        except Exception as e:
            self.logger.error(f"Error executing task {task_id}: {e}")
            
            # Log performance data with error
            if self.performance_monitor and timer_id:
                self.performance_monitor.stop_timer(
                    timer_id,
                    {"error": str(e), "success": False}
                )
            
            # Return None result with index and failure flag
            return None, index, False