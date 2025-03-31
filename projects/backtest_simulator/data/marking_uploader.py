"""
Marking uploader for uploading marking data to cloud storage.

This module provides a MarkingUploader class that handles the upload of
marking data to cloud storage with retry logic and error handling.
"""

import time
import logging
import threading
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta

import pandas as pd

from backtest_simulator.utils.logging_config import get_logger
from backtest_simulator.utils.performance import PerformanceMonitor


class MarkingUploader:
    """Uploads marking data to cloud storage."""
    
    def __init__(self, 
                cloud_store: Any,
                dataset_name: str = None,
                partition: str = None,
                batch_size: int = 10000,
                upload_interval: float = 5.0,
                max_retries: int = 3,
                retry_delay: float = 2.0,
                performance_monitor: Optional[PerformanceMonitor] = None):
        """Initialize the marking uploader.
        
        Args:
            cloud_store: Cloud storage client (must have upload_data method)
            dataset_name: Name of the dataset to upload to
            partition: Partition to upload to (e.g. 'YYYYMMDD')
            batch_size: Maximum batch size for uploads
            upload_interval: Interval between uploads in seconds
            max_retries: Maximum number of retries for failed uploads
            retry_delay: Delay between retries in seconds
            performance_monitor: Optional performance monitor for tracking metrics
        """
        # Set up logger
        self.logger = get_logger(f"{__name__}.MarkingUploader")
        self.logger.info("Initializing marking uploader")
        
        # Save configuration
        self.cloud_store = cloud_store
        self.dataset_name = dataset_name
        self.partition = partition
        self.batch_size = batch_size
        self.upload_interval = upload_interval
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.performance_monitor = performance_monitor
        
        # Initialize the upload buffer
        self.buffer = []
        self.buffer_lock = threading.RLock()
        
        # Set up statistics
        self.stats_lock = threading.RLock()
        self.upload_count = 0
        self.upload_success = 0
        self.upload_failure = 0
        self.marking_count = 0
        self.last_upload_time = time.time()
        
        # Set up automatic upload timer if interval is set
        if upload_interval > 0:
            self._setup_upload_timer()
        
        self.logger.info(f"Marking uploader initialized with batch size {batch_size}, interval {upload_interval}s")
    
    def _setup_upload_timer(self) -> None:
        """Set up a timer for automatic uploads."""
        if not hasattr(self, '_upload_timer') or not self._upload_timer.is_alive():
            self._upload_timer = threading.Timer(self.upload_interval, self._timed_upload)
            self._upload_timer.daemon = True
            self._upload_timer.start()
    
    def _timed_upload(self) -> None:
        """Handle timed uploads and reschedule the next upload."""
        try:
            # Perform the upload
            self.upload_markings(force=True)
        except Exception as e:
            self.logger.error(f"Error in timed upload: {e}", exc_info=True)
        finally:
            # Reschedule the timer if still needed
            if hasattr(self, 'upload_interval') and self.upload_interval > 0:
                self._setup_upload_timer()
    
    def add_markings(self, markings: List[Dict[str, Any]]) -> bool:
        """Add markings to the upload buffer.
        
        Args:
            markings: List of marking dictionaries to add
            
        Returns:
            True if markings were added and possibly uploaded, False otherwise
        """
        if not markings:
            return True
        
        # Track performance if enabled
        if self.performance_monitor:
            self.performance_monitor.start_operation("add_markings")
        
        try:
            # Add markings to the buffer
            with self.buffer_lock:
                self.buffer.extend(markings)
                current_size = len(self.buffer)
            
            # Update statistics
            with self.stats_lock:
                self.marking_count += len(markings)
            
            # Auto-upload if batch size is reached
            if current_size >= self.batch_size:
                self.upload_markings()
            
            return True
        
        except Exception as e:
            self.logger.error(f"Error adding markings to buffer: {e}", exc_info=True)
            return False
        
        finally:
            # End performance tracking
            if self.performance_monitor:
                self.performance_monitor.end_operation("add_markings")
    
    def upload_markings(self, force: bool = False) -> bool:
        """Upload markings to cloud storage.
        
        Args:
            force: Whether to force upload even if batch size is not reached
            
        Returns:
            True if upload was successful or not needed, False otherwise
        """
        # Check if there are markings to upload
        with self.buffer_lock:
            if not self.buffer:
                return True
            
            # Check if we should upload based on batch size or force flag
            if len(self.buffer) < self.batch_size and not force:
                # Check if upload interval has passed
                if time.time() - self.last_upload_time < self.upload_interval:
                    return True
            
            # Get markings to upload
            markings_to_upload = self.buffer
            self.buffer = []
        
        # Track performance if enabled
        if self.performance_monitor:
            self.performance_monitor.start_operation("upload_markings")
        
        # Update statistics
        with self.stats_lock:
            self.upload_count += 1
            self.last_upload_time = time.time()
        
        try:
            # Convert markings to dataframe
            df = pd.DataFrame(markings_to_upload)
            
            # Add upload timestamp
            df['upload_time'] = datetime.now().isoformat()
            
            # Set up dataset name and partition if provided
            dataset = self.dataset_name or "markings"
            partition_path = f"{dataset}/{self.partition}" if self.partition else dataset
            
            # Upload the data with retries
            success = self._upload_with_retries(df, partition_path)
            
            # Update statistics
            with self.stats_lock:
                if success:
                    self.upload_success += 1
                else:
                    self.upload_failure += 1
            
            return success
        
        except Exception as e:
            self.logger.error(f"Error uploading markings: {e}", exc_info=True)
            
            # Update statistics
            with self.stats_lock:
                self.upload_failure += 1
            
            return False
        
        finally:
            # End performance tracking
            if self.performance_monitor:
                self.performance_monitor.end_operation("upload_markings")
    
    def _upload_with_retries(self, df: pd.DataFrame, partition_path: str) -> bool:
        """Upload data with retries.
        
        Args:
            df: DataFrame to upload
            partition_path: Partition path to upload to
            
        Returns:
            True if upload was successful, False otherwise
        """
        for retry in range(self.max_retries + 1):
            try:
                # Try to upload the data
                if retry > 0:
                    self.logger.info(f"Retrying upload (attempt {retry}/{self.max_retries})")
                
                # Call the cloud store's upload method
                self.cloud_store.upload_data(
                    df=df,
                    dataset=partition_path,
                    format="parquet",
                    mode="append"
                )
                
                return True
            
            except Exception as e:
                # Log the error
                self.logger.error(f"Upload failed (attempt {retry+1}/{self.max_retries+1}): {e}", exc_info=True)
                
                # Check if we should retry
                if retry < self.max_retries:
                    # Wait before retrying
                    time.sleep(self.retry_delay * (1 + retry))  # Exponential backoff
                else:
                    # Max retries reached, return failure
                    return False
    
    def flush(self) -> bool:
        """Flush all pending markings to cloud storage.
        
        Returns:
            True if flush was successful, False otherwise
        """
        return self.upload_markings(force=True)
    
    def __del__(self):
        """Clean up resources when the instance is garbage collected."""
        # Cancel the upload timer if it exists
        if hasattr(self, '_upload_timer') and self._upload_timer is not None:
            self._upload_timer.cancel()
        
        # Flush any remaining markings
        try:
            self.flush()
        except:
            pass  # Ignore errors during garbage collection