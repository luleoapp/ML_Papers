"""
Callback manager for handling data from C++ engine callbacks.

This module provides a CallbackManager class that handles callbacks from the C++ engine,
managing queues of marking data, and supporting parallel or serial processing.
"""

import queue
import threading
import time
import logging
from typing import Dict, List, Any, Callable, Optional, Tuple
import concurrent.futures
from pathlib import Path

from backtest_simulator.utils.logging_config import get_logger
from backtest_simulator.utils.performance import PerformanceMonitor


# Global callback handler function that will be registered with the C++ engine
def global_callback_handler(marking_batch: List[Dict[str, Any]]) -> bool:
    """Global callback handler for C++ engine.
    
    This function will be registered with the C++ engine and will forward
    marking data to the appropriate CallbackManager instance.
    
    Args:
        marking_batch: Batch of marking data from the C++ engine
        
    Returns:
        True if the batch was successfully processed, False otherwise
    """
    # Get the current thread ID
    thread_id = threading.get_ident()
    
    # Look up the callback manager for this thread
    callback_manager = CallbackManager.get_instance(thread_id)
    
    if callback_manager:
        # Forward the batch to the callback manager
        return callback_manager.process_marking_batch(marking_batch)
    else:
        # Log an error if no callback manager is registered for this thread
        logger = get_logger("global_callback_handler")
        logger.error(f"No callback manager registered for thread {thread_id}")
        return False


class CallbackManager:
    """Manages callbacks from C++ engine and processes marking data."""
    
    # Class-level dictionary to store instances by thread ID
    _instances = {}
    _instances_lock = threading.RLock()
    
    @classmethod
    def get_instance(cls, thread_id: int) -> Optional['CallbackManager']:
        """Get the CallbackManager instance for a given thread ID.
        
        Args:
            thread_id: Thread ID to get the instance for
            
        Returns:
            CallbackManager instance or None if not found
        """
        with cls._instances_lock:
            return cls._instances.get(thread_id)
    
    @classmethod
    def register_instance(cls, thread_id: int, instance: 'CallbackManager') -> None:
        """Register a CallbackManager instance for a given thread ID.
        
        Args:
            thread_id: Thread ID to register the instance for
            instance: CallbackManager instance to register
        """
        with cls._instances_lock:
            cls._instances[thread_id] = instance
    
    @classmethod
    def unregister_instance(cls, thread_id: int) -> None:
        """Unregister a CallbackManager instance for a given thread ID.
        
        Args:
            thread_id: Thread ID to unregister the instance for
        """
        with cls._instances_lock:
            if thread_id in cls._instances:
                del cls._instances[thread_id]
    
    def __init__(self, 
                max_queue_size: int = 1000,
                parallel_uploads: bool = True,
                max_upload_workers: int = 4,
                performance_monitor: Optional['PerformanceMonitor'] = None):
        """Initialize the callback manager.
        
        Args:
            max_queue_size: Maximum size of the markings queue
            parallel_uploads: Whether to use parallel uploads
            max_upload_workers: Maximum number of worker threads for parallel uploads
            performance_monitor: Optional performance monitor for tracking metrics
        """
        # Initialize thread storage
        self._thread_id = threading.get_ident()
        
        # Register this instance with the class
        self.__class__.register_instance(self._thread_id, self)
        
        # Set up logger
        self.logger = get_logger(f"{__name__}.CallbackManager.{self._thread_id}")
        self.logger.info("Initializing callback manager")
        
        # Initialize the queue for marking data
        self.markings_queue = queue.Queue(maxsize=max_queue_size)
        
        # Set up configuration
        self.parallel_uploads = parallel_uploads
        self.max_upload_workers = max_upload_workers
        self.performance_monitor = performance_monitor
        
        # Set up processing flag and thread
        self._processing = False
        self._processing_thread = None
        self._executor = None
        
        # Set up upload function
        self._upload_func = None
        
        # Set up statistics
        self.stats_lock = threading.RLock()
        self.received_batches = 0
        self.received_markings = 0
        self.uploaded_batches = 0
        self.uploaded_markings = 0
        self.upload_errors = 0
        
        # Register callback
        self.logger.info("Callback manager initialized")
    
    def process_marking_batch(self, marking_batch: List[Dict[str, Any]]) -> bool:
        """Process a batch of marking data from the C++ engine.
        
        This method is called by the global callback handler when a batch
        of marking data is received from the C++ engine.
        
        Args:
            marking_batch: Batch of marking data from the C++ engine
            
        Returns:
            True if the batch was successfully processed, False otherwise
        """
        # Check if the batch is empty
        if not marking_batch:
            return True
        
        # Update statistics
        with self.stats_lock:
            self.received_batches += 1
            self.received_markings += len(marking_batch)
        
        # Track performance if enabled
        if self.performance_monitor:
            self.performance_monitor.start_operation("callback_processing")
        
        try:
            # Put the batch in the queue
            self.markings_queue.put(marking_batch, block=True, timeout=5.0)
            return True
        except queue.Full:
            # Log error if the queue is full
            self.logger.error(f"Marking queue is full, dropping batch of {len(marking_batch)} markings")
            return False
        except Exception as e:
            # Log any other error
            self.logger.error(f"Error processing marking batch: {e}", exc_info=True)
            return False
        finally:
            # End performance tracking
            if self.performance_monitor:
                self.performance_monitor.end_operation("callback_processing")
    
    def start_processing(self, upload_func: Callable[[List[Dict[str, Any]]], bool]) -> bool:
        """Start processing marking data.
        
        Args:
            upload_func: Function to call with each batch of marking data
            
        Returns:
            True if processing was started successfully, False otherwise
        """
        # Check if already processing
        if self._processing:
            self.logger.warning("Callback processing is already started")
            return False
        
        # Set up upload function
        self._upload_func = upload_func
        
        # Set processing flag
        self._processing = True
        
        # Set up thread pool executor if using parallel uploads
        if self.parallel_uploads:
            self.logger.info(f"Starting parallel processing with {self.max_upload_workers} workers")
            self._executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=self.max_upload_workers,
                thread_name_prefix="callback_upload"
            )
        
        # Start processing thread
        self._processing_thread = threading.Thread(
            target=self._processing_loop,
            name="callback_processing",
            daemon=True
        )
        self._processing_thread.start()
        
        self.logger.info("Callback processing started")
        return True
    
    def stop_processing(self, wait_for_completion: bool = True, timeout: Optional[float] = 60.0) -> bool:
        """Stop processing marking data.
        
        Args:
            wait_for_completion: Whether to wait for processing to complete
            timeout: Maximum time to wait for processing to complete
            
        Returns:
            True if processing was stopped successfully, False otherwise
        """
        # Check if not processing
        if not self._processing:
            self.logger.warning("Callback processing is not started")
            return False
        
        # Set processing flag
        self._processing = False
        
        # Wait for processing to complete if requested
        if wait_for_completion and self._processing_thread is not None:
            self.logger.info("Waiting for callback processing to complete")
            self._processing_thread.join(timeout=timeout)
            
            if self._processing_thread.is_alive():
                self.logger.warning("Callback processing did not complete within timeout")
                return False
        
        # Shut down executor if using parallel uploads
        if self.parallel_uploads and self._executor is not None:
            self.logger.info("Shutting down executor")
            self._executor.shutdown(wait=wait_for_completion)
        
        # Clear processing thread and executor
        self._processing_thread = None
        self._executor = None
        
        # Clear upload function
        self._upload_func = None
        
        self.logger.info("Callback processing stopped")
        return True
    
    def _processing_loop(self) -> None:
        """Main processing loop for marking data.
        
        This method runs in a separate thread and processes marking data
        from the queue.
        """
        self.logger.info("Processing loop started")
        
        # Set up futures list if using parallel uploads
        futures = []
        
        try:
            while self._processing or not self.markings_queue.empty():
                try:
                    # Get a batch from the queue
                    batch = self.markings_queue.get(block=True, timeout=1.0)
                    
                    # Process the batch
                    if self.parallel_uploads and self._executor is not None:
                        # Submit to executor
                        future = self._executor.submit(self._process_batch, batch)
                        futures.append(future)
                        
                        # Clean up completed futures
                        futures = [f for f in futures if not f.done()]
                    else:
                        # Process directly in this thread
                        self._process_batch(batch)
                    
                    # Mark task as done
                    self.markings_queue.task_done()
                
                except queue.Empty:
                    # Queue is empty, continue
                    continue
                
                except Exception as e:
                    # Log any other error
                    self.logger.error(f"Error in processing loop: {e}", exc_info=True)
            
            # Wait for all futures to complete if using parallel uploads
            if self.parallel_uploads and self._executor is not None:
                self.logger.info(f"Waiting for {len(futures)} pending uploads to complete")
                concurrent.futures.wait(futures)
        
        except Exception as e:
            # Log any other error
            self.logger.error(f"Error in processing loop: {e}", exc_info=True)
        
        self.logger.info("Processing loop stopped")
    
    def _process_batch(self, batch: List[Dict[str, Any]]) -> bool:
        """Process a batch of marking data.
        
        Args:
            batch: Batch of marking data to process
            
        Returns:
            True if the batch was successfully processed, False otherwise
        """
        # Check if upload function is set
        if self._upload_func is None:
            self.logger.error("No upload function set")
            return False
        
        # Track performance if enabled
        if self.performance_monitor:
            self.performance_monitor.start_operation("marking_upload")
        
        try:
            # Call upload function
            result = self._upload_func(batch)
            
            # Update statistics
            if result:
                with self.stats_lock:
                    self.uploaded_batches += 1
                    self.uploaded_markings += len(batch)
            else:
                with self.stats_lock:
                    self.upload_errors += 1
            
            return result
        
        except Exception as e:
            # Log error
            self.logger.error(f"Error uploading marking batch: {e}", exc_info=True)
            
            # Update statistics
            with self.stats_lock:
                self.upload_errors += 1
            
            return False
        
        finally:
            # End performance tracking
            if self.performance_monitor:
                self.performance_monitor.end_operation("marking_upload")
    
    def __del__(self):
        """Clean up resources when the instance is garbage collected."""
        # Unregister this instance
        self.__class__.unregister_instance(self._thread_id)
        
        # Stop processing if still running
        if self._processing:
            self.stop_processing(wait_for_completion=False)