"""Cloud storage integration using DataStore."""

from typing import Any, Dict, List, Optional, Union
import os
import time
import logging

import pandas as pd
import xarray as xr

from ..utils.performance import timed_operation, PerformanceMonitor

# Set up logging
logger = logging.getLogger(__name__)

try:
    import polars as pl
    HAS_POLARS = True
except ImportError:
    HAS_POLARS = False


class DataStoreClient:
    """Client for interacting with the DataStore cloud service.
    
    This class provides methods for uploading and downloading data from the 
    cloud-based DataStore service.
    """
    
    def __init__(self, 
                 datastore_name: str = "prod",
                 workspace: Optional[str] = None,
                 performance_monitoring: bool = True,
                 log_dir: Optional[str] = None):
        """Initialize the DataStore client.
        
        Args:
            datastore_name: Name of the datastore (e.g., "prod")
            workspace: Name of the workspace to use (defaults to username)
            performance_monitoring: Whether to enable performance monitoring
            log_dir: Directory to store performance logs
        """
        self.datastore_name = datastore_name
        self.workspace = workspace or os.environ.get("USER", "default_workspace")
        self._client = None
        self._workspace_obj = None
        
        # Initialize performance monitoring
        self._performance_monitoring_enabled = performance_monitoring
        if log_dir is None:
            log_dir = os.environ.get('BACKTEST_LOG_DIR', './performance_logs')
        self._performance_monitor = PerformanceMonitor(
            log_dir=log_dir,
            enabled=performance_monitoring
        )
        
    def connect(self) -> 'DataStoreClient':
        """Connect to the DataStore service.
        
        Returns:
            self: The connected client instance
        """
        try:
            # In a real implementation, this would connect to the actual service
            # datastore = datastore.connect(self.datastore_name)
            print(f"Connected to DataStore '{self.datastore_name}'")
            self._client = True  # Mock client
            return self
        except Exception as e:
            raise ConnectionError(f"Failed to connect to DataStore: {e}")
    
    def get_workspace(self) -> Any:
        """Get the current workspace.
        
        Returns:
            Workspace object
        """
        if not self._client:
            self.connect()
            
        if not self._workspace_obj:
            # In a real implementation, this would get the actual workspace
            # self._workspace_obj = self._client.get(self.workspace)
            print(f"Accessing workspace '{self.workspace}'")
            self._workspace_obj = True  # Mock workspace
            
        return self._workspace_obj
    
    @timed_operation("upload_results")
    def upload_results(self,
                       results: Union[pd.DataFrame, List[Dict[str, Any]]],
                       dataset_name: str,
                       description: str = "",
                       partition: str = "default") -> None:
        """Upload backtest results to DataStore.
        
        Args:
            results: Backtest results as DataFrame or list of dicts
            dataset_name: Name of the dataset to create/update
            description: Description of the dataset
            partition: Partition to store the data in
        """
        workspace = self.get_workspace()
        
        # Convert to DataFrame if list
        if isinstance(results, list):
            results_df = pd.DataFrame(results)
        else:
            results_df = results
        
        # Track upload metrics
        start_time = time.time()
        size_bytes = results_df.memory_usage(deep=True).sum()
        
        # In a real implementation, this would create/update the dataset
        # dataset = workspace.create(dataset_name)
        # dataset.put(results_df, description=description, partition=partition)
        
        # For demonstration, simulate network latency
        # Adjust this for mock delay (would be removed in real implementation)
        simulated_upload_time = min(0.01 * len(results_df) * 0.001, 2.0)
        time.sleep(simulated_upload_time)
        
        # Calculate metrics
        duration = time.time() - start_time
        
        # Log performance metrics
        if self._performance_monitoring_enabled:
            self._performance_monitor.log_database_metrics(
                dataset_name=dataset_name,
                record_count=len(results_df),
                size_bytes=size_bytes,
                operation_type="upload",
                duration_seconds=duration,
                additional_info={
                    "partition": partition,
                    "columns": len(results_df.columns),
                    "description": description,
                    "format": "pandas"
                }
            )
        
        logger.info(f"Uploaded results to dataset '{dataset_name}' in workspace '{self.workspace}'")
        logger.info(f"Partition: {partition}, Records: {len(results_df)}, Duration: {duration:.2f}s")
        print(f"Uploaded results to dataset '{dataset_name}' in workspace '{self.workspace}'")
        print(f"Partition: {partition}, Records: {len(results_df)}, Duration: {duration:.2f}s")
    
    def upload_xarray_results(self,
                             results: xr.Dataset,
                             dataset_name: str,
                             description: str = "",
                             partition: str = "default") -> None:
        """Upload xarray results to DataStore.
        
        Args:
            results: Backtest results as xarray Dataset
            dataset_name: Name of the dataset to create/update
            description: Description of the dataset
            partition: Partition to store the data in
        """
        workspace = self.get_workspace()
        
        # In a real implementation, this would create/update the dataset
        # dataset = workspace.create(dataset_name)
        # dataset.put(results, description=description, partition=partition)
        print(f"Uploaded xarray results to dataset '{dataset_name}' in workspace '{self.workspace}'")
        print(f"Partition: {partition}, Variables: {list(results.data_vars)}")
    
    def upload_polars_results(self,
                             results: Any,  # pl.DataFrame
                             dataset_name: str,
                             description: str = "",
                             partition: str = "default") -> None:
        """Upload polars results to DataStore.
        
        Args:
            results: Backtest results as polars DataFrame
            dataset_name: Name of the dataset to create/update
            description: Description of the dataset
            partition: Partition to store the data in
        """
        if not HAS_POLARS:
            raise ImportError("Polars is not installed. Please install it with 'pip install polars'")
            
        workspace = self.get_workspace()
        
        # In a real implementation, this would create/update the dataset
        # dataset = workspace.create(dataset_name)
        # dataset.put(results, description=description, partition=partition)
        print(f"Uploaded polars results to dataset '{dataset_name}' in workspace '{self.workspace}'")
        print(f"Partition: {partition}, Records: {len(results)}")
    
    @timed_operation("download_dataset")
    def download_dataset(self,
                        dataset_name: str,
                        partition: str = "default",
                        format_type: str = "pandas") -> Any:
        """Download a dataset from DataStore.
        
        Args:
            dataset_name: Name of the dataset to download
            partition: Partition to download from
            format_type: Format to download as ('pandas', 'xarray', 'polars')
            
        Returns:
            Downloaded dataset in the specified format
        """
        workspace = self.get_workspace()
        
        # Track download metrics
        start_time = time.time()
        
        # In a real implementation, this would download the actual dataset
        # dataset = workspace.get(dataset_name)
        # data = dataset.get(partition=partition)
        
        # For demonstration, create a random sized mock dataset
        mock_size = 1000  # Simulate 1000 records
        n_columns = 10    # Simulate 10 columns
        
        # Simulate network latency
        # Adjust this for mock delay (would be removed in real implementation)
        simulated_download_time = min(0.01 * mock_size * 0.001, 2.0)
        time.sleep(simulated_download_time)
        
        # Create appropriate mock data based on format
        result = None
        
        if format_type == "pandas":
            # Create a pandas DataFrame with random data
            mock_data = {f"col_{i}": np.random.randn(mock_size) for i in range(n_columns)}
            result = pd.DataFrame(mock_data)
            logger.info(f"Downloaded pandas dataset '{dataset_name}' from partition '{partition}'")
            print(f"Downloaded pandas dataset '{dataset_name}' from partition '{partition}'")
            
        elif format_type == "xarray":
            # Create an xarray Dataset with random data
            data_vars = {f"var_{i}": (["x"], np.random.randn(mock_size)) for i in range(n_columns)}
            result = xr.Dataset(data_vars)
            logger.info(f"Downloaded xarray dataset '{dataset_name}' from partition '{partition}'")
            print(f"Downloaded xarray dataset '{dataset_name}' from partition '{partition}'")
            
        elif format_type == "polars":
            if not HAS_POLARS:
                raise ImportError("Polars is not installed. Please install it with 'pip install polars'")
            # Create a polars DataFrame with random data
            mock_data = {f"col_{i}": np.random.randn(mock_size) for i in range(n_columns)}
            result = pl.DataFrame(mock_data)
            logger.info(f"Downloaded polars dataset '{dataset_name}' from partition '{partition}'")
            print(f"Downloaded polars dataset '{dataset_name}' from partition '{partition}'")
            
        else:
            raise ValueError(f"Unknown format type: {format_type}")
        
        # Calculate metrics
        duration = time.time() - start_time
        
        # Estimate size
        size_bytes = None
        record_count = mock_size
        
        if format_type == "pandas":
            size_bytes = result.memory_usage(deep=True).sum()
        elif format_type == "polars" and HAS_POLARS:
            # Polars has different memory estimation methods
            size_bytes = mock_size * n_columns * 8  # Rough estimate: each value is 8 bytes
        
        # Log performance metrics
        if self._performance_monitoring_enabled:
            self._performance_monitor.log_database_metrics(
                dataset_name=dataset_name,
                record_count=record_count,
                size_bytes=size_bytes,
                operation_type="download",
                duration_seconds=duration,
                additional_info={
                    "partition": partition,
                    "format": format_type,
                    "columns": n_columns
                }
            )
            
            logger.info(f"Download completed in {duration:.2f}s, {record_count} records")
        
        return result
        
    def generate_performance_report(self, output_file: Optional[str] = None, format_type: str = "html") -> Optional[str]:
        """Generate a performance report for the DataStore operations.
        
        Args:
            output_file: Path to write the report to. If None, generates a default path.
            format_type: Format of the report ("json", "csv", or "html").
            
        Returns:
            Path to the generated report.
        """
        if not self._performance_monitoring_enabled:
            print("Performance monitoring is not enabled. No report generated.")
            return None
        
        # Add datastore-specific metadata
        self._performance_monitor.session_metrics["datastore_name"] = self.datastore_name
        self._performance_monitor.session_metrics["workspace"] = self.workspace
        
        return self._performance_monitor.generate_report(output_file, format_type)
        
    def get_performance_monitor(self) -> PerformanceMonitor:
        """Get the performance monitor instance.
        
        Returns:
            Performance monitor instance
        """
        return self._performance_monitor
    
    def enable_performance_monitoring(self, enabled: bool = True) -> None:
        """Enable or disable performance monitoring.
        
        Args:
            enabled: Whether to enable performance monitoring
        """
        self._performance_monitoring_enabled = enabled
        self._performance_monitor.enabled = enabled