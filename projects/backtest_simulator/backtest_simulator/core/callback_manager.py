"""Manager for handling callbacks from C++ engine and processing marking data."""

import queue
import threading
import time
import logging
from typing import Dict, List, Any, Optional, Callable, Union
import concurrent.futures
import numpy as np

from ..utils.logging_config import get_logger
from ..utils.performance import timed_operation, PerformanceMonitor

# Configure logger
logger = get_logger(__name__)


class CallbackManager:
    """Manages callbacks from C++ engine and processes marking data."""
    
    def __init__(self, 
                max_queue_size: int = 1000,
                parallel_uploads: bool = True,
                max_upload_workers: int = 4,
                performance_monitor: Optional[PerformanceMonitor] = None):
        """Initialize the callback manager.
        
        Args:
            max_queue_size: Maximum size of the marking data queue
            parallel_uploads: Whether to upload marking data in parallel
            max_upload_workers: Maximum number of upload workers
            performance_monitor: Performance monitor instance
        """
        self.logger = get_logger(f"{__name__}.CallbackManager")
        self.logger.info("Initializing callback manager")
        
        # Create queue for marking data batches
        self.markings_queue = queue.Queue(maxsize=max_queue_size)
        
        # Set up upload parameters
        self.parallel_uploads = parallel_uploads
        self.max_upload_workers = max_upload_workers
        
        # Thread management
        self.upload_thread = None
        self.stop_event = threading.Event()
        self.is_running = False
        
        # Performance monitoring
        self.performance_monitor = performance_monitor
        
        # Upload executor for parallel processing
        self.upload_executor = None
        if self.parallel_uploads:
            self.upload_executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=max_upload_workers,
                thread_name_prefix="upload_worker"
            )
        
        # Statistics
        self.received_batches = 0
        self.received_markings = 0
        self.uploaded_batches = 0
        self.uploaded_markings = 0
        self.stats_lock = threading.Lock()
    
    def start_processing(self, upload_func: Callable[[List[Dict[str, Any]]], None]) -> None:
        """Start processing marking data.
        
        Args:
            upload_func: Function to call for uploading marking data
        """
        if self.is_running:
            self.logger.warning("Callback manager is already running")
            return
        
        self.logger.info("Starting callback processing")
        self.stop_event.clear()
        self.is_running = True
        
        # Start upload thread
        self.upload_thread = threading.Thread(
            target=self._upload_worker,
            args=(upload_func,),
            name="marking_upload_thread"
        )
        self.upload_thread.daemon = True
        self.upload_thread.start()
        
        self.logger.info("Callback processing started")
    
    def stop_processing(self, wait_for_completion: bool = True, timeout: Optional[float] = 60.0) -> None:
        """Stop processing marking data.
        
        Args:
            wait_for_completion: Whether to wait for all queued batches to be processed
            timeout: Maximum time to wait for processing to complete
        """
        if not self.is_running:
            return
        
        self.logger.info("Stopping callback processing")
        
        # Set stop event to signal threads to stop
        self.stop_event.set()
        
        # Wait for upload thread to finish if requested
        if wait_for_completion and self.upload_thread is not None:
            try:
                queue_size = self.markings_queue.qsize()
                if queue_size > 0:
                    self.logger.info(f"Waiting for {queue_size} queued marking batches to be processed")
                
                self.upload_thread.join(timeout=timeout)
                
                if self.upload_thread.is_alive():
                    self.logger.warning(f"Upload thread did not complete within {timeout} seconds")
            except Exception as e:
                self.logger.error(f"Error while waiting for upload thread: {e}")
        
        # Shutdown executor if it exists
        if self.upload_executor is not None:
            self.upload_executor.shutdown(wait=wait_for_completion)
            self.upload_executor = None
        
        self.is_running = False
        self.logger.info("Callback processing stopped")
        
        # Log final statistics
        with self.stats_lock:
            self.logger.info(
                f"Processing summary: Received {self.received_batches} batches "
                f"({self.received_markings} markings), Uploaded {self.uploaded_batches} batches "
                f"({self.uploaded_markings} markings)"
            )
    
    def process_marking_batch(self, markings_batch: List[Dict[str, Any]]) -> None:
        """Process a batch of markings from the C++ engine.
        
        This method will be called by the C++ engine via pybind11.
        
        Args:
            markings_batch: Batch of markings from the C++ engine
        """
        if not self.is_running:
            self.logger.warning("Received marking batch but processing is not running")
            return
        
        batch_size = len(markings_batch)
        
        # Update statistics
        with self.stats_lock:
            self.received_batches += 1
            self.received_markings += batch_size
        
        # Record performance if enabled
        if self.performance_monitor:
            timer_id = self.performance_monitor.start_timer(
                "process_marking_batch",
                {"batch_size": batch_size}
            )
        
        try:
            # Put batch in queue
            self.markings_queue.put(markings_batch, block=True, timeout=5.0)
            
            self.logger.debug(
                f"Queued marking batch with {batch_size} markings "
                f"(queue size: {self.markings_queue.qsize()})"
            )
            
            # Log performance data
            if self.performance_monitor:
                self.performance_monitor.stop_timer(
                    timer_id,
                    {
                        "queue_size": self.markings_queue.qsize(),
                        "total_received": self.received_markings
                    }
                )
        
        except queue.Full:
            self.logger.error(
                f"Marking queue is full, dropping batch with {batch_size} markings"
            )
            
            # Log performance data with error
            if self.performance_monitor:
                self.performance_monitor.stop_timer(
                    timer_id,
                    {"error": "queue_full"}
                )
    
    def _upload_worker(self, upload_func: Callable[[List[Dict[str, Any]]], None]) -> None:
        """Worker thread for uploading marking data.
        
        Args:
            upload_func: Function to call for uploading marking data
        """
        self.logger.info("Upload worker thread started")
        
        while not self.stop_event.is_set() or not self.markings_queue.empty():
            try:
                # Get batch from queue with timeout to check stop event periodically
                try:
                    markings_batch = self.markings_queue.get(block=True, timeout=0.5)
                except queue.Empty:
                    continue
                
                batch_size = len(markings_batch)
                
                # Record performance if enabled
                if self.performance_monitor:
                    timer_id = self.performance_monitor.start_timer(
                        "upload_marking_batch",
                        {"batch_size": batch_size}
                    )
                
                # Process the batch
                try:
                    if self.parallel_uploads and self.upload_executor:
                        # Split large batches for parallel upload
                        if batch_size > 1000:
                            # Split into sub-batches of approximately equal size
                            sub_batch_count = min(self.max_upload_workers, batch_size // 500)
                            sub_batches = np.array_split(markings_batch, sub_batch_count)
                            
                            # Submit each sub-batch to the executor
                            futures = []
                            for sub_batch in sub_batches:
                                future = self.upload_executor.submit(upload_func, sub_batch.tolist())
                                futures.append(future)
                            
                            # Wait for all uploads to complete
                            concurrent.futures.wait(futures)
                            
                            # Check for exceptions
                            for future in futures:
                                future.result()  # This will raise any exceptions from the threads
                        else:
                            # Upload small batch directly
                            upload_func(markings_batch)
                    else:
                        # Upload batch serially
                        upload_func(markings_batch)
                    
                    # Update statistics
                    with self.stats_lock:
                        self.uploaded_batches += 1
                        self.uploaded_markings += batch_size
                    
                    self.logger.debug(f"Uploaded marking batch with {batch_size} markings")
                    
                    # Log performance data
                    if self.performance_monitor:
                        self.performance_monitor.stop_timer(
                            timer_id,
                            {
                                "total_uploaded": self.uploaded_markings,
                                "queue_remaining": self.markings_queue.qsize()
                            }
                        )
                
                except Exception as e:
                    self.logger.error(f"Error uploading marking batch: {e}")
                    
                    # Log performance data with error
                    if self.performance_monitor:
                        self.performance_monitor.stop_timer(
                            timer_id,
                            {"error": str(e)}
                        )
                
                finally:
                    # Signal that the task is done
                    self.markings_queue.task_done()
            
            except Exception as e:
                self.logger.error(f"Unexpected error in upload worker: {e}")
        
        self.logger.info("Upload worker thread stopped")


# Global callback function for C++ engine to call
_global_callback_manager: Optional[CallbackManager] = None

def set_global_callback_manager(manager: CallbackManager) -> None:
    """Set the global callback manager for C++ callbacks.
    
    Args:
        manager: Callback manager to use
    """
    global _global_callback_manager
    _global_callback_manager = manager

def get_global_callback_manager() -> Optional[CallbackManager]:
    """Get the global callback manager.
    
    Returns:
        Global callback manager or None if not set
    """
    return _global_callback_manager

def global_callback_handler(markings_batch: List[Dict[str, Any]]) -> None:
    """Global callback handler for C++ engine.
    
    This function is exposed to the C++ engine via pybind11.
    
    Args:
        markings_batch: Batch of markings from the C++ engine
    """
    if _global_callback_manager is None:
        logger.error("Received marking batch but no callback manager is set")
        return
    
    _global_callback_manager.process_marking_batch(markings_batch)