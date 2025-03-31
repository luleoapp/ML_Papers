"""Parallel processing utilities for the backtest simulator."""

import os
import time
import logging
import concurrent.futures
from datetime import datetime
from typing import Dict, List, Optional, Union, Any, Callable, Tuple, TypeVar, Generic

from .logging_config import get_logger

T = TypeVar('T')
R = TypeVar('R')

# Configure logger
logger = get_logger(__name__)


class ParallelProcessor:
    """Process items in parallel using thread or process pools."""
    
    def __init__(self, 
                max_workers: Optional[int] = None, 
                use_processes: bool = False, 
                timeout: Optional[float] = None,
                name: str = "ParallelProcessor"):
        """Initialize the parallel processor.
        
        Args:
            max_workers: Maximum number of workers. If None, uses CPU count.
            use_processes: Whether to use process pool (True) or thread pool (False).
            timeout: Timeout in seconds for each task.
            name: Name for this processor (used in logging).
        """
        self.max_workers = max_workers or os.cpu_count()
        self.use_processes = use_processes
        self.timeout = timeout
        self.name = name
        self.logger = get_logger(f"{__name__}.{name}")
        
        self.logger.info(f"Initialized {self.__class__.__name__} with {self.max_workers} "
                        f"workers, using {'processes' if use_processes else 'threads'}")
    
    def process(self, 
               items: List[T], 
               task_func: Callable[[T], R],
               callback: Optional[Callable[[T, R], None]] = None,
               error_callback: Optional[Callable[[T, Exception], None]] = None,
               description: str = "Processing items") -> List[R]:
        """Process items in parallel.
        
        Args:
            items: List of items to process.
            task_func: Function to apply to each item.
            callback: Optional callback function to call with each result.
            error_callback: Optional callback function to call when an error occurs.
            description: Description of the processing task for logging.
            
        Returns:
            List of results in the same order as input items.
        """
        if not items:
            self.logger.warning(f"{description}: No items to process")
            return []
        
        results = [None] * len(items)
        executor_cls = concurrent.futures.ProcessPoolExecutor if self.use_processes else concurrent.futures.ThreadPoolExecutor
        
        self.logger.info(f"{description}: Starting parallel processing of {len(items)} items "
                        f"with {self.max_workers} workers")
        start_time = time.time()
        
        with executor_cls(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_index = {}
            for i, item in enumerate(items):
                future = executor.submit(self._execute_task, task_func, item)
                future_to_index[future] = (i, item)
            
            # Process results as they complete
            completed = 0
            last_log_time = time.time()
            for future in concurrent.futures.as_completed(future_to_index):
                index, item = future_to_index[future]
                
                try:
                    if self.timeout is not None:
                        result = future.result(timeout=self.timeout)
                    else:
                        result = future.result()
                    
                    # Store the result and call callback if provided
                    results[index] = result
                    if callback is not None:
                        try:
                            callback(item, result)
                        except Exception as cb_err:
                            self.logger.error(f"Error in callback for item {index}: {cb_err}")
                    
                except Exception as exc:
                    self.logger.error(f"Error processing item {index}: {exc}")
                    if error_callback is not None:
                        try:
                            error_callback(item, exc)
                        except Exception as cb_err:
                            self.logger.error(f"Error in error_callback for item {index}: {cb_err}")
                
                # Log progress
                completed += 1
                now = time.time()
                if now - last_log_time >= 5.0 or completed == len(items):  # Log every 5 seconds or at end
                    progress = (completed / len(items)) * 100
                    elapsed = now - start_time
                    rate = completed / elapsed if elapsed > 0 else 0
                    estimated_total = elapsed / (completed / len(items)) if completed > 0 else 0
                    remaining = estimated_total - elapsed
                    
                    self.logger.info(f"{description}: Progress: {progress:.1f}% ({completed}/{len(items)}) "
                                    f"- {rate:.2f} items/sec - ETA: {remaining:.1f}s")
                    last_log_time = now
        
        # Calculate final statistics
        end_time = time.time()
        total_time = end_time - start_time
        rate = len(items) / total_time if total_time > 0 else 0
        
        self.logger.info(f"{description}: Completed processing {len(items)} items in {total_time:.2f} seconds "
                        f"({rate:.2f} items/sec)")
        
        return results
    
    def _execute_task(self, task_func: Callable[[T], R], item: T) -> R:
        """Execute a task with proper logging and timing.
        
        Args:
            task_func: Function to apply to the item.
            item: Item to process.
            
        Returns:
            Result of applying task_func to item.
        """
        start_time = time.time()
        
        try:
            result = task_func(item)
            
            # Log task execution time
            execution_time = time.time() - start_time
            self.logger.debug(f"Task executed in {execution_time:.3f} seconds")
            
            return result
        
        except Exception as e:
            execution_time = time.time() - start_time
            self.logger.error(f"Task failed after {execution_time:.3f} seconds: {e}")
            raise


class DayProcessor:
    """Process multiple days of data in parallel."""
    
    def __init__(self, 
                max_workers: Optional[int] = None,
                use_processes: bool = False,
                timeout: Optional[float] = None):
        """Initialize the day processor.
        
        Args:
            max_workers: Maximum number of worker processes/threads.
            use_processes: Whether to use process pool instead of thread pool.
            timeout: Optional timeout for each day's processing.
        """
        self.parallel_processor = ParallelProcessor(
            max_workers=max_workers,
            use_processes=use_processes,
            timeout=timeout,
            name="DayProcessor"
        )
        self.logger = get_logger(__name__ + ".DayProcessor")
    
    def process_days(self, 
                    dates: List[datetime],
                    process_day_func: Callable[[datetime], Any],
                    exchanges: List[str],
                    combine_results_func: Optional[Callable[[List[Any]], Any]] = None,
                    show_progress: bool = True) -> Union[List[Any], Any]:
        """Process multiple days in parallel.
        
        Args:
            dates: List of dates to process.
            process_day_func: Function to process a single date.
            exchanges: List of exchanges to process for each date.
            combine_results_func: Optional function to combine the results from all days.
            show_progress: Whether to show progress information.
            
        Returns:
            Combined results if combine_results_func is provided, otherwise list of results.
        """
        if not dates:
            self.logger.warning("No dates to process")
            return [] if combine_results_func is None else combine_results_func([])
        
        self.logger.info(f"Processing {len(dates)} days across {len(exchanges)} exchanges "
                        f"using {self.parallel_processor.max_workers} workers")
        
        # Prepare task function
        def task_func(date):
            try:
                return process_day_func(date)
            except Exception as e:
                self.logger.error(f"Error processing date {date.strftime('%Y-%m-%d')}: {e}")
                raise
        
        # Process all dates in parallel
        day_results = self.parallel_processor.process(
            items=dates,
            task_func=task_func,
            description="Processing days",
        )
        
        # Combine results if needed
        if combine_results_func is not None:
            self.logger.info("Combining results from all days")
            return combine_results_func(day_results)
        
        return day_results


# Factory function to create a day processor
def create_day_processor(max_workers: Optional[int] = None,
                        use_processes: bool = False,
                        timeout: Optional[float] = None) -> DayProcessor:
    """Create a day processor with the specified parameters.
    
    Args:
        max_workers: Maximum number of worker processes/threads.
        use_processes: Whether to use process pool instead of thread pool.
        timeout: Optional timeout for each day's processing.
        
    Returns:
        DayProcessor instance
    """
    return DayProcessor(
        max_workers=max_workers,
        use_processes=use_processes,
        timeout=timeout
    )