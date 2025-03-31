"""Module for uploading marking data to cloud storage."""

import os
import time
import datetime
import queue
import json
import logging
from typing import Dict, List, Any, Optional, Union
import tempfile
import uuid
import pandas as pd
import numpy as np

from ..utils.logging_config import get_logger
from ..utils.performance import timed_operation, PerformanceMonitor
from .cloud_store import DataStoreClient

# Configure logger
logger = get_logger(__name__)


class MarkingUploader:
    """Uploads marking data to cloud storage."""
    
    def __init__(self, 
                cloud_store: DataStoreClient,
                dataset_name: str = None,
                partition: str = None,
                batch_size: int = 10000,
                upload_interval: float = 5.0,
                max_retries: int = 3,
                retry_delay: float = 2.0,
                performance_monitor: Optional[PerformanceMonitor] = None):
        """Initialize the marking uploader.
        
        Args:
            cloud_store: DataStoreClient instance
            dataset_name: Name of the dataset to upload to
            partition: Partition to upload to
            batch_size: Maximum batch size for uploads
            upload_interval: Minimum time between uploads in seconds
            max_retries: Maximum number of retries for failed uploads
            retry_delay: Delay between retries in seconds
            performance_monitor: Performance monitor instance
        """
        self.logger = get_logger(f"{__name__}.MarkingUploader")
        self.logger.info("Initializing marking uploader")
        
        self.cloud_store = cloud_store
        self.dataset_name = dataset_name or f"markings_{datetime.datetime.now().strftime('%Y%m%d')}"
        self.partition = partition or "default"
        self.batch_size = batch_size
        self.upload_interval = upload_interval
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.performance_monitor = performance_monitor
        
        # Tracking metrics
        self.upload_count = 0
        self.total_markings = 0
        self.failed_uploads = 0
        self.last_upload_time = 0
        
        self.logger.info(
            f"Marking uploader configured for dataset {self.dataset_name}, partition {self.partition}, "
            f"batch size {self.batch_size}"
        )
    
    @timed_operation("upload_markings")
    def upload_markings(self, markings: List[Dict[str, Any]]) -> bool:
        """Upload markings to the cloud store.
        
        Args:
            markings: List of marking dictionaries
            
        Returns:
            True if the upload was successful, False otherwise
        """
        if not markings:
            self.logger.warning("No markings to upload")
            return True
        
        marking_count = len(markings)
        
        # Record performance if enabled
        timer_id = None
        if self.performance_monitor:
            timer_id = self.performance_monitor.start_timer(
                "upload_markings_batch",
                {"count": marking_count}
            )
        
        # Limit upload rate if needed
        current_time = time.time()
        time_since_last_upload = current_time - self.last_upload_time
        
        if time_since_last_upload < self.upload_interval:
            sleep_time = self.upload_interval - time_since_last_upload
            self.logger.debug(f"Rate limiting: Sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)
        
        # Update upload time
        self.last_upload_time = time.time()
        
        # Convert to DataFrame for upload
        try:
            df = pd.DataFrame(markings)
            
            # Add upload metadata
            df['upload_time'] = datetime.datetime.now().isoformat()
            df['upload_batch'] = str(uuid.uuid4())
            
            # Try to upload with retries
            for attempt in range(self.max_retries):
                try:
                    # Upload to cloud store
                    self.cloud_store.upload_results(
                        df,
                        dataset_name=self.dataset_name,
                        description=f"Marking data batch {self.upload_count + 1}",
                        partition=self.partition
                    )
                    
                    # Update metrics
                    self.upload_count += 1
                    self.total_markings += marking_count
                    
                    self.logger.info(
                        f"Successfully uploaded batch of {marking_count} markings "
                        f"(total: {self.total_markings})"
                    )
                    
                    # Log performance data
                    if self.performance_monitor and timer_id:
                        self.performance_monitor.stop_timer(
                            timer_id,
                            {
                                "success": True,
                                "total_uploaded": self.total_markings,
                                "upload_count": self.upload_count
                            }
                        )
                    
                    return True
                
                except Exception as e:
                    if attempt < self.max_retries - 1:
                        self.logger.warning(
                            f"Upload attempt {attempt + 1} failed: {e}. Retrying in {self.retry_delay} seconds..."
                        )
                        time.sleep(self.retry_delay)
                    else:
                        self.failed_uploads += 1
                        self.logger.error(f"Upload failed after {self.max_retries} attempts: {e}")
                        
                        # Try to save locally as fallback
                        self._save_failed_upload(df)
                        
                        # Log performance data with error
                        if self.performance_monitor and timer_id:
                            self.performance_monitor.stop_timer(
                                timer_id,
                                {
                                    "success": False,
                                    "error": str(e),
                                    "failed_uploads": self.failed_uploads
                                }
                            )
                        
                        return False
        
        except Exception as e:
            self.logger.error(f"Error preparing marking data for upload: {e}")
            self.failed_uploads += 1
            
            # Log performance data with error
            if self.performance_monitor and timer_id:
                self.performance_monitor.stop_timer(
                    timer_id,
                    {
                        "success": False,
                        "error": str(e),
                        "failed_uploads": self.failed_uploads
                    }
                )
            
            return False
    
    def _save_failed_upload(self, df: pd.DataFrame) -> None:
        """Save a failed upload to a local file as fallback.
        
        Args:
            df: DataFrame of markings
        """
        try:
            # Create fallback directory if it doesn't exist
            fallback_dir = Path("./failed_uploads")
            fallback_dir.mkdir(parents=True, exist_ok=True)
            
            # Create a unique filename
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"failed_upload_{timestamp}_{uuid.uuid4()}.parquet"
            filepath = fallback_dir / filename
            
            # Save to parquet file
            df.to_parquet(filepath)
            
            self.logger.info(f"Saved failed upload to {filepath}")
        
        except Exception as e:
            self.logger.error(f"Error saving failed upload: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get uploader statistics.
        
        Returns:
            Dictionary of statistics
        """
        return {
            "upload_count": self.upload_count,
            "total_markings": self.total_markings,
            "failed_uploads": self.failed_uploads,
            "dataset_name": self.dataset_name,
            "partition": self.partition,
            "batch_size": self.batch_size
        }