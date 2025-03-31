"""Main engine for running backtests."""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Tuple, Callable
import os
import time
import concurrent.futures
import logging

import numpy as np
import pandas as pd
import xarray as xr

from .config.settings import BacktestConfig
from .core.pybind_interface import CPPBacktestEngine
from .core.reference_data_interface import ReferenceDataInterface
from .data.data_loader import DataLoader
from .data.cloud_store import DataStoreClient
from .data.reference_data import ReferenceDataManager
from .utils.date_utils import get_trading_days, is_valid_date
from .utils.performance import PerformanceMonitor, timed_operation
from .utils.parallel_processor import DayProcessor, create_day_processor
from .utils.logging_config import LoggerFactory, get_logger

# Import versioning components if available
try:
    from .versioning.run_manager import RunManager, RunVersion
    from .versioning.marking_config import MarkingManager, MarkingConfig
    _HAS_VERSIONING = True
except ImportError:
    _HAS_VERSIONING = False


class BacktestEngine:
    """Main engine for running backtests."""

    def __init__(self, 
                use_cloud_store: bool = False, 
                use_versioning: bool = False,
                local_store_path: Optional[str] = None,
                datastore_name: str = "prod",
                workspace: Optional[str] = None,
                log_dir: Optional[str] = None,
                log_level: str = "INFO",
                console_level: str = "INFO",
                file_level: str = "DEBUG",
                json_logs: bool = False,
                log_file_prefix: str = "backtest",
                performance_monitoring: bool = True,
                parallel_processing: bool = True,
                max_workers: Optional[int] = None,
                use_processes: bool = False,
                max_window_size: int = 3600,
                parallel_uploads: bool = True,
                max_upload_workers: int = 4,
                marking_batch_size: int = 10000):
        """Initialize the backtest engine.
        
        Args:
            use_cloud_store: Whether to use the cloud DataStore for results
            use_versioning: Whether to use the run versioning system
            local_store_path: Optional path for storing run data
            datastore_name: Name of the DataStore to use
            workspace: Workspace name in DataStore
            log_dir: Directory to store log files
            log_level: Default logging level ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
            console_level: Logging level for console output
            file_level: Logging level for file output
            json_logs: Whether to use JSON formatting for log files
            log_file_prefix: Prefix for log files
            performance_monitoring: Whether to enable performance monitoring
            parallel_processing: Whether to enable parallel processing of multiple days
            max_workers: Maximum number of worker processes/threads for parallel processing
            use_processes: Whether to use processes instead of threads for parallel processing
            max_window_size: Maximum window size in seconds for order book processing
            parallel_uploads: Whether to upload marking data in parallel
            max_upload_workers: Maximum number of workers for uploading marking data
            marking_batch_size: Maximum batch size for marking uploads
        """
        # Set up logging
        self._setup_logging(
            log_dir=log_dir,
            log_level=log_level,
            console_level=console_level,
            file_level=file_level,
            json_logs=json_logs,
            log_file_prefix=log_file_prefix
        )
        
        # Get logger for this class
        self.logger = get_logger(f"{__name__}.BacktestEngine")
        
        self.logger.info("Initializing BacktestEngine")
        
        self.config: Optional[BacktestConfig] = None
        self.cpp_engine: Optional[CPPBacktestEngine] = None
        self.data_loader: Optional[DataLoader] = None
        self.reference_interface: Optional[ReferenceDataInterface] = None
        self.universe: Optional[List[str]] = None
        self.results: List[Dict] = []
        self.use_cloud_store = use_cloud_store
        self.cloud_store: Optional[DataStoreClient] = None
        self.datastore_name = datastore_name
        self.workspace = workspace
        
        # Store configuration parameters
        self.max_window_size = max_window_size
        self.parallel_uploads = parallel_uploads
        self.max_upload_workers = max_upload_workers
        self.marking_batch_size = marking_batch_size
        
        # Initialize performance monitoring
        self._performance_monitoring_enabled = performance_monitoring
        if log_dir is None:
            log_dir = os.environ.get('BACKTEST_LOG_DIR', './performance_logs')
        self._performance_monitor = PerformanceMonitor(
            log_dir=log_dir,
            enabled=performance_monitoring
        )
        
        # Initialize cloud store if requested
        if use_cloud_store:
            self.cloud_store = DataStoreClient(
                datastore_name=datastore_name,
                workspace=workspace,
                performance_monitoring=performance_monitoring,
                log_dir=log_dir
            )
            
            self.logger.info(f"Cloud store initialized for datastore {datastore_name}, workspace {workspace}")
        else:
            self.cloud_store = None
        
        # Import required components for thread management
        from .core.thread_manager import ThreadManager
        from .core.callback_manager import CallbackManager, set_global_callback_manager
        from .data.marking_uploader import MarkingUploader
        
        # Initialize thread manager and callback system
        self.thread_manager = ThreadManager(
            max_processing_workers=max_workers or os.cpu_count(),
            max_upload_workers=max_upload_workers,
            parallel_uploads=parallel_uploads,
            max_queue_size=marking_batch_size * 2,  # Double the marking batch size for queue capacity
            use_processes=use_processes,
            performance_monitor=self._performance_monitor
        )
        
        self.logger.info(f"Thread manager initialized with {self.thread_manager.max_processing_workers} processing workers, "
                       f"{self.thread_manager.max_upload_workers} upload workers")
        
        # Initialize marking uploader if cloud store is available
        if self.cloud_store:
            self.marking_uploader = MarkingUploader(
                cloud_store=self.cloud_store,
                dataset_name=f"markings_{datetime.now().strftime('%Y%m%d')}",
                partition=f"run_{int(time.time())}",
                batch_size=marking_batch_size,
                performance_monitor=self._performance_monitor
            )
            
            self.logger.info("Marking uploader initialized")
        else:
            self.marking_uploader = None
            self.logger.warning("Cloud store not available, marking uploader disabled")
        
        # Initialize parallel processing
        self.parallel_processing = parallel_processing
        
        if self.parallel_processing:
            self.day_processor = create_day_processor(
                max_workers=max_workers,
                use_processes=use_processes
            )
            self.logger.info(f"Parallel processing enabled with {self.day_processor.parallel_processor.max_workers} workers "
                            f"using {'processes' if use_processes else 'threads'}")
        else:
            self.day_processor = None
            self.logger.info("Parallel processing disabled")
            
        # Initialize versioning if requested
        self.use_versioning = use_versioning and _HAS_VERSIONING
        self.run_manager: Optional['RunManager'] = None
        self.marking_manager: Optional['MarkingManager'] = None
        self.current_run_version: Optional['RunVersion'] = None
        
        if self.use_versioning:
            if not _HAS_VERSIONING:
                print("WARNING: Versioning requested but not available. Continuing without versioning.")
            else:
                self.run_manager = RunManager(
                    local_store_path=local_store_path,
                    use_cloud_store=use_cloud_store
                )
                self.marking_manager = MarkingManager(self.run_manager)
    
    def _setup_logging(self,
                     log_dir: Optional[str] = None,
                     log_level: str = "INFO",
                     console_level: str = "INFO",
                     file_level: str = "DEBUG",
                     json_logs: bool = False,
                     log_file_prefix: str = "backtest") -> None:
        """Set up logging for the backtest engine.
        
        Args:
            log_dir: Directory to store log files. If None, logs will be stored in ./logs
            log_level: Default logging level
            console_level: Logging level for console output
            file_level: Logging level for file output
            json_logs: Whether to use JSON formatting for log files
            log_file_prefix: Prefix for log files
        """
        # Configure logging only if it hasn't been configured already
        if not hasattr(self, '_logging_configured'):
            LoggerFactory.setup_logging(
                log_dir=log_dir,
                log_level=log_level,
                console_level=console_level,
                file_level=file_level,
                json_logs=json_logs,
                log_file_prefix=log_file_prefix,
                app_name="backtest_simulator"
            )
            self._logging_configured = True

    def configure(self, 
                  start_date: Union[str, datetime],
                  end_date: Union[str, datetime],
                  exchanges: List[str] = ["XNAS"],
                  universe_file: Optional[str] = None,
                  universe: Optional[List[str]] = None,
                  data_path: Optional[str] = None,
                  datastore_name: str = "prod",
                  workspace: Optional[str] = None,
                  marking_configs: Optional[List[Union[Dict[str, Any], 'MarkingConfig']]] = None,
                  run_description: Optional[str] = None,
                  run_tags: Optional[List[str]] = None,
                  **kwargs) -> None:
        """Configure the backtest engine.
        
        Args:
            start_date: Start date for the backtest
            end_date: End date for the backtest
            exchanges: List of exchanges to include
            universe_file: Path to file containing the universe of symbols
            universe: List of symbols to include (alternative to universe_file)
            data_path: Path to the data files
            datastore_name: Name of the DataStore to use (if using cloud store)
            workspace: Workspace name in DataStore (if using cloud store)
            marking_configs: Optional list of marking configurations
            run_description: Optional description for this run
            run_tags: Optional tags for this run
            **kwargs: Additional configuration parameters
        """
        self.config = BacktestConfig(
            start_date=start_date,
            end_date=end_date,
            exchanges=exchanges,
            universe_file=universe_file,
            universe=universe,
            data_path=data_path,
            **kwargs
        )
        
        # Configure cloud store if enabled
        if self.use_cloud_store and workspace:
            self.cloud_store = DataStoreClient(
                datastore_name=datastore_name,
                workspace=workspace
            )
            self.cloud_store.connect()
            
            # Update run manager cloud store if needed
            if self.use_versioning and self.run_manager:
                self.run_manager.cloud_store = self.cloud_store
        
        self.data_loader = DataLoader(self.config)
        self.universe = self._load_universe()
        # Initialize the callback manager for the C++ engine
        callback_manager = self.thread_manager.callback_manager if self.cloud_store else None
        
        # Create the C++ engine with callback support
        self.cpp_engine = CPPBacktestEngine(callback_manager=callback_manager)
        
        # Apply engine-specific configurations with max_window_size
        engine_config = self.config.to_dict()
        engine_config["max_window_size"] = self.max_window_size
        self.cpp_engine.configure(engine_config)
        
        self.logger.info(f"C++ engine configured with max_window_size={self.max_window_size}")
        
        # Initialize reference data interface
        self.reference_interface = ReferenceDataInterface(
            cpp_engine=self.cpp_engine,
            datastore_name=datastore_name or self.datastore_name,
            workspace=workspace or self.workspace
        )
        
        # Start callback processing if marking uploader is available
        if self.marking_uploader and callback_manager:
            self.logger.info("Starting callback processing for markings")
            self.thread_manager.start_callback_processing(
                upload_func=self.marking_uploader.upload_markings
            )
        
        # Create a run version if versioning is enabled
        if self.use_versioning and self.run_manager and self.marking_manager:
            # Convert marking configs if provided
            marking_objs = []
            if marking_configs:
                for config in marking_configs:
                    if isinstance(config, dict):
                        if "name" in config and "parameters" in config:
                            marking = MarkingConfig(
                                name=config["name"],
                                parameters=config["parameters"],
                                version=config.get("version", "1.0.0"),
                                description=config.get("description")
                            )
                            marking_objs.append(marking)
                    else:
                        marking_objs.append(config)
            
            # Create a run version
            self.current_run_version = self.run_manager.create_run_version(
                config=self.config,
                description=run_description,
                tags=run_tags
            )
            
            # Associate markings if provided
            if marking_objs:
                self.marking_manager.associate_markings_with_run(
                    self.current_run_version.version_id,
                    marking_objs
                )
        
    def _load_universe(self) -> List[str]:
        """Load the universe of symbols."""
        if self.config is None or self.data_loader is None:
            raise ValueError("Engine must be configured before loading universe")
            
        if self.config.universe is not None:
            return self.config.universe
            
        if self.config.universe_file is not None:
            return self.data_loader.load_universe(self.config.universe_file)
            
        raise ValueError("Either universe or universe_file must be provided")
    
    def _get_eligible_dates(self) -> List[datetime]:
        """Get the eligible dates for backtesting.
        
        Filters out dates that are in the out-of-sample period
        (dates where month + year is odd).
        """
        if self.config is None:
            raise ValueError("Engine must be configured before getting eligible dates")
            
        all_trading_days = get_trading_days(
            self.config.start_date,
            self.config.end_date
        )
        
        # Filter out dates where month + year is odd (out-of-sample)
        return [d for d in all_trading_days if is_valid_date(d)]
    
    @timed_operation("backtest_run")
    def run(self, track_metrics: bool = True, parallel: Optional[bool] = None) -> List[Dict]:
        """Run the backtest and return results.
        
        Args:
            track_metrics: Whether to track performance metrics for versioning
            parallel: Whether to use parallel processing. If None, uses the 
                      engine's default parallel_processing setting.
            
        Returns:
            List of dictionaries containing the results, where each dictionary
            represents a row in the results.
        """
        if self.config is None or self.cpp_engine is None or self.data_loader is None:
            raise ValueError("Engine must be configured before running")
        
        # Track start time for metrics
        start_time = datetime.now()
        
        # Determine eligible dates
        eligible_dates = self._get_eligible_dates()
        self.logger.info(f"Running backtest for {len(eligible_dates)} eligible dates "
                        f"from {eligible_dates[0].strftime('%Y-%m-%d')} to {eligible_dates[-1].strftime('%Y-%m-%d')}")
        
        # Reset results
        self.results = []
        processed_files = 0
        processed_dates = 0
        
        # Start a timer for the backtest data processing
        data_proc_timer = None
        if self._performance_monitoring_enabled:
            data_proc_timer = self._performance_monitor.start_timer(
                "backtest_data_processing",
                {
                    "date_count": len(eligible_dates),
                    "exchanges": self.config.exchanges,
                    "universe_size": len(self.universe) if self.universe else 0
                }
            )
        
        # Determine whether to use parallel processing
        use_parallel = self.parallel_processing if parallel is None else parallel
        
        if use_parallel and self.day_processor:
            self.logger.info(f"Using parallel processing for {len(eligible_dates)} dates with "
                           f"{self.day_processor.parallel_processor.max_workers} workers")
            
            # Define the function to process a single date
            def process_date(date: datetime) -> List[Dict]:
                date_results = []
                tick_data_files = self.data_loader.get_tick_data_files(date)
                
                date_str = date.strftime('%Y-%m-%d')
                self.logger.debug(f"Processing date {date_str} with {len(tick_data_files)} files")
                
                for exchange in self.config.exchanges:
                    if exchange in tick_data_files:
                        file_path = tick_data_files[exchange]
                        
                        try:
                            # Process file with C++ engine
                            result_chunk = self.cpp_engine.process_file(
                                str(file_path),
                                date_str,
                                exchange,
                                self.universe
                            )
                            
                            date_results.extend(result_chunk)
                            
                            self.logger.debug(f"Processed {len(result_chunk)} results for {exchange} on {date_str}")
                        except Exception as e:
                            self.logger.error(f"Error processing {exchange} file for {date_str}: {e}")
                            raise
                
                return date_results
            
            # Define a function to combine results from all days
            def combine_results(day_results: List[List[Dict]]) -> List[Dict]:
                combined = []
                total_files = 0
                
                for i, results in enumerate(day_results):
                    combined.extend(results)
                    total_files += len(results)
                    
                return combined
            
            # Process all dates in parallel
            self.results = self.day_processor.process_days(
                dates=eligible_dates,
                process_day_func=process_date,
                exchanges=self.config.exchanges,
                combine_results_func=combine_results,
                show_progress=True
            )
            
            # Count processed files and dates
            processed_dates = len(eligible_dates)
            processed_files = sum(len(self.data_loader.get_tick_data_files(date)) for date in eligible_dates)
            
        else:
            # Sequential processing (original approach)
            self.logger.info("Using sequential processing for dates")
            
            for date in eligible_dates:
                # Load data for the current date
                tick_data_files = self.data_loader.get_tick_data_files(date)
                processed_dates += 1
                
                date_str = date.strftime('%Y-%m-%d')
                self.logger.debug(f"Processing date {date_str} with {len(tick_data_files)} files")
                
                file_proc_timer = None
                if self._performance_monitoring_enabled:
                    file_proc_timer = self._performance_monitor.start_timer(
                        "process_date_files",
                        {"date": date_str, "file_count": len(tick_data_files)}
                    )
                
                for exchange in self.config.exchanges:
                    if exchange in tick_data_files:
                        file_path = tick_data_files[exchange]
                        processed_files += 1
                        
                        cpp_timer = None
                        if self._performance_monitoring_enabled:
                            cpp_timer = self._performance_monitor.start_timer(
                                "cpp_file_processing",
                                {"file": str(file_path), "exchange": exchange}
                            )
                        
                        try:
                            # Process file with C++ engine
                            result_chunk = self.cpp_engine.process_file(
                                str(file_path),
                                date_str,
                                exchange,
                                self.universe
                            )
                            
                            if self._performance_monitoring_enabled and cpp_timer:
                                self._performance_monitor.stop_timer(
                                    cpp_timer,
                                    {"result_count": len(result_chunk)}
                                )
                            
                            self.results.extend(result_chunk)
                            
                            self.logger.debug(f"Processed {len(result_chunk)} results for {exchange} on {date_str}")
                        except Exception as e:
                            self.logger.error(f"Error processing {exchange} file for {date_str}: {e}")
                            if self._performance_monitoring_enabled and cpp_timer:
                                self._performance_monitor.stop_timer(
                                    cpp_timer,
                                    {"error": str(e)}
                                )
                            raise
                
                if self._performance_monitoring_enabled and file_proc_timer:
                    self._performance_monitor.stop_timer(
                        file_proc_timer,
                        {"processed_files": len(tick_data_files)}
                    )
        
        if self._performance_monitoring_enabled and data_proc_timer:
            self._performance_monitor.stop_timer(
                data_proc_timer,
                {
                    "processed_dates": processed_dates,
                    "processed_files": processed_files,
                    "result_count": len(self.results)
                }
            )
        
        # Calculate performance metrics if tracking is enabled
        end_time = datetime.now()
        duration_seconds = (end_time - start_time).total_seconds()
        
        self.logger.info(f"Backtest completed in {duration_seconds:.2f} seconds. "
                       f"Processed {processed_dates} dates, {processed_files} files, "
                       f"generated {len(self.results)} results.")
        
        # Log backtest metrics
        if self._performance_monitoring_enabled:
            run_id = self.current_run_version.version_id if self.use_versioning and self.current_run_version else f"run_{int(time.time())}"
            date_range = f"{self.config.start_date} to {self.config.end_date}"
            
            self._performance_monitor.log_backtest_metrics(
                backtest_id=run_id,
                symbols_count=len(self.universe) if self.universe else 0,
                date_range=date_range,
                processed_files=processed_files,
                result_count=len(self.results),
                duration_seconds=duration_seconds,
                additional_metrics={
                    'eligible_dates': len(eligible_dates),
                    'processed_dates': processed_dates,
                    'exchanges': len(self.config.exchanges),
                    'parallel_processing': use_parallel,
                    'version_id': run_id if self.use_versioning else None
                }
            )
            
        if track_metrics and self.use_versioning and self.run_manager and self.current_run_version:
            # Basic metrics
            metrics = {
                'run_duration_seconds': duration_seconds,
                'eligible_dates': len(eligible_dates),
                'processed_dates': processed_dates,
                'processed_files': processed_files,
                'result_count': len(self.results),
                'symbols_count': len(self.universe) if self.universe else 0,
                'completion_time': end_time.isoformat(),
                'parallel_processing': use_parallel
            }
            
            # Update run version metrics
            self.run_manager.update_run_metrics(
                self.current_run_version.version_id,
                metrics
            )
        
        return self.results
    
    def save_results(self, output_path: str, store_with_run: bool = True) -> None:
        """Save the results to a parquet file.
        
        Args:
            output_path: Path to save the results
            store_with_run: Whether to also store results with the run version
        """
        if not self.results:
            raise ValueError("No results to save. Run backtest first.")
        
        # Convert to DataFrame and save
        df = pd.DataFrame(self.results)
        df.to_parquet(output_path)
        
        # Store with run version if requested
        if store_with_run and self.use_versioning and self.run_manager and self.current_run_version:
            self.run_manager.store_run_artifacts(
                self.current_run_version.version_id,
                output_path,
                artifact_type="results"
            )
    
    @timed_operation("cloud_save_results")
    def save_results_to_cloud(self, 
                             dataset_name: str, 
                             description: str = "",
                             partition: str = "default") -> None:
        """Save the results to the cloud DataStore.
        
        Args:
            dataset_name: Name of the dataset to create/update
            description: Description of the dataset
            partition: Partition to store the data in
        """
        if not self.use_cloud_store or self.cloud_store is None:
            raise ValueError("Cloud store is not enabled or configured")
            
        if not self.results:
            raise ValueError("No results to save. Run backtest first.")
        
        # Convert results to DataFrame and upload
        df = pd.DataFrame(self.results)
        
        # Track database metrics for the upload
        start_time = time.time()
        
        # Upload the data
        self.cloud_store.upload_results(
            df, 
            dataset_name=dataset_name,
            description=description,
            partition=partition
        )
        
        # Log database metrics
        if self._performance_monitoring_enabled:
            duration = time.time() - start_time
            size_bytes = df.memory_usage(deep=True).sum()
            
            self._performance_monitor.log_database_metrics(
                dataset_name=dataset_name,
                record_count=len(df),
                size_bytes=size_bytes,
                operation_type="upload",
                duration_seconds=duration,
                additional_info={
                    "partition": partition,
                    "columns": len(df.columns),
                    "description": description
                }
            )
    
    def results_to_xarray(self) -> xr.Dataset:
        """Convert results to an xarray Dataset.
        
        Returns:
            xarray Dataset containing the results
        """
        if not self.results:
            raise ValueError("No results to convert. Run backtest first.")
        
        # Convert list of dicts to DataFrame
        df = pd.DataFrame(self.results)
        
        # Determine dimensions based on dataframe columns
        # Typical dimensions: date, symbol, trade_id
        # This is a simplistic conversion - adjust as needed
        if 'date' in df.columns and 'symbol' in df.columns:
            # Convert to xarray Dataset
            return df.set_index(['date', 'symbol']).to_xarray()
        elif 'date' in df.columns:
            return df.set_index('date').to_xarray()
        else:
            # Fallback with default index
            return df.to_xarray()
    
    def save_xarray_results_to_cloud(self, 
                                   dataset_name: str, 
                                   description: str = "", 
                                   partition: str = "default") -> None:
        """Save results as xarray Dataset to the cloud DataStore.
        
        Args:
            dataset_name: Name of the dataset to create/update
            description: Description of the dataset
            partition: Partition to store the data in
        """
        if not self.use_cloud_store or self.cloud_store is None:
            raise ValueError("Cloud store is not enabled or configured")
            
        # Convert to xarray and upload
        xarray_data = self.results_to_xarray()
        self.cloud_store.upload_xarray_results(
            xarray_data,
            dataset_name=dataset_name,
            description=description,
            partition=partition
        )
        
    def load_from_cloud(self, 
                       dataset_name: str, 
                       partition: str = "default",
                       format_type: str = "pandas") -> Any:
        """Load a dataset from the cloud DataStore.
        
        Args:
            dataset_name: Name of the dataset to load
            partition: Partition to load from
            format_type: Format to load as ('pandas', 'xarray', 'polars')
            
        Returns:
            Loaded dataset in the specified format
        """
        if not self.use_cloud_store or self.cloud_store is None:
            raise ValueError("Cloud store is not enabled or configured")
            
        return self.cloud_store.download_dataset(
            dataset_name=dataset_name,
            partition=partition,
            format_type=format_type
        )
    
    # Versioning methods
    
    def get_current_run_id(self) -> Optional[str]:
        """Get the ID of the current run version.
        
        Returns:
            Version ID if versioning is enabled and configured, None otherwise
        """
        if not self.use_versioning or not self.current_run_version:
            return None
        
        return self.current_run_version.version_id
    
    def create_marking_config(self, 
                            name: str,
                            parameters: Dict[str, Any],
                            version: str = "1.0.0",
                            description: Optional[str] = None) -> Optional['MarkingConfig']:
        """Create a new marking configuration.
        
        Args:
            name: Name of the marking
            parameters: Parameters for this marking
            version: Version of this marking configuration
            description: Optional description
            
        Returns:
            Created MarkingConfig if versioning is enabled, None otherwise
        """
        if not self.use_versioning or not self.marking_manager:
            print("WARNING: Versioning not enabled or marking manager not available")
            return None
        
        return self.marking_manager.create_marking_config(
            name=name,
            parameters=parameters,
            version=version,
            description=description
        )
    
    def list_run_versions(self, 
                         tags: Optional[List[str]] = None, 
                         start_date: Optional[Union[str, datetime]] = None,
                         end_date: Optional[Union[str, datetime]] = None) -> List[Dict[str, Any]]:
        """List run versions with optional filtering.
        
        Args:
            tags: Optional filter by tags
            start_date: Optional filter by start date
            end_date: Optional filter by end date
            
        Returns:
            List of run versions as dictionaries
        """
        if not self.use_versioning or not self.run_manager:
            return []
        
        versions = self.run_manager.list_run_versions(tags, start_date, end_date)
        return [v.to_dict() for v in versions]
    
    def get_run_version(self, version_id: str) -> Optional[Dict[str, Any]]:
        """Get a run version by ID.
        
        Args:
            version_id: ID of the run version to get
            
        Returns:
            Run version as dictionary if found, None otherwise
        """
        if not self.use_versioning or not self.run_manager:
            return None
        
        version = self.run_manager.get_run_version(version_id)
        return version.to_dict() if version else None
    
    def get_markings_for_run(self, version_id: str) -> List[Dict[str, Any]]:
        """Get marking configurations associated with a run version.
        
        Args:
            version_id: ID of the run version
            
        Returns:
            List of marking configurations as dictionaries
        """
        if not self.use_versioning or not self.marking_manager:
            return []
        
        markings = self.marking_manager.get_markings_for_run(version_id)
        return [m.to_dict() for m in markings]
    
    def load_run_results(self, version_id: str) -> pd.DataFrame:
        """Load results for a specific run version.
        
        Args:
            version_id: ID of the run version
            
        Returns:
            DataFrame with run results
        """
        if not self.use_versioning or not self.run_manager:
            raise ValueError("Versioning not enabled or run manager not available")
        
        artifacts_path = self.run_manager.get_run_artifacts(version_id, "results")
        
        if artifacts_path.is_dir():
            # Find first parquet file in directory
            parquet_files = list(artifacts_path.glob("*.parquet"))
            if not parquet_files:
                raise ValueError(f"No parquet files found in {artifacts_path}")
            return pd.read_parquet(parquet_files[0])
        else:
            # Single file
            return pd.read_parquet(artifacts_path)
    
    def rerun_version(self, 
                     version_id: str,
                     override_params: Optional[Dict[str, Any]] = None,
                     description: Optional[str] = None) -> Optional[str]:
        """Rerun a previous version with optional parameter overrides.
        
        Args:
            version_id: ID of the previous run version
            override_params: Parameters to override from the previous run
            description: Optional description for the new run
            
        Returns:
            ID of the new run version if successful, None otherwise
        """
        if not self.use_versioning or not self.run_manager or not self.marking_manager:
            raise ValueError("Versioning not enabled or managers not available")
        
        # Get the previous run version
        prev_run = self.run_manager.get_run_version(version_id)
        if not prev_run:
            raise ValueError(f"Run version {version_id} not found")
        
        # Get marking configurations
        markings = self.marking_manager.get_markings_for_run(version_id)
        
        # Create description if not provided
        if not description:
            description = f"Rerun of {version_id}"
        
        # Create new run version
        new_run = self.run_manager.create_run_from_previous(
            version_id=version_id,
            override_params=override_params,
            description=description,
            tags=["rerun", f"parent:{version_id}"]
        )
        
        # Store the current run version
        self.current_run_version = new_run
        
        # Associate markings with the new run
        if markings:
            self.marking_manager.associate_markings_with_run(
                new_run.version_id,
                markings
            )
        
        # Configure the engine from the run config
        config_dict = dict(new_run.config)
        
        # Remove markings from config as they're handled separately
        if "markings" in config_dict:
            del config_dict["markings"]
        
        # Update the engine configuration
        self.config = BacktestConfig(**config_dict)
        self.data_loader = DataLoader(self.config)
        self.universe = self._load_universe()
        self.cpp_engine = CPPBacktestEngine()
        self.cpp_engine.configure(self.config.to_dict())
        
        return new_run.version_id
    
    def mark_as_production(self, version_id: str) -> bool:
        """Mark a run version as production.
        
        Args:
            version_id: ID of the run version to mark as production
            
        Returns:
            True if successful, False otherwise
        """
        if not self.use_versioning or not self.run_manager:
            return False
        
        result = self.run_manager.mark_as_production(version_id)
        return result is not None
    
    def get_production_version(self) -> Optional[Dict[str, Any]]:
        """Get the current production run version.
        
        Returns:
            The production run version as dictionary if found, None otherwise
        """
        if not self.use_versioning or not self.run_manager:
            return None
        
        version = self.run_manager.get_production_version()
        return version.to_dict() if version else None
    
    # Performance monitoring methods
    
    def generate_performance_report(self, output_file: Optional[str] = None, format_type: str = "html") -> Optional[str]:
        """Generate a performance report for the current session.
        
        Args:
            output_file: Path to write the report to. If None, generates a default path.
            format_type: Format of the report ("json", "csv", or "html").
            
        Returns:
            Path to the generated report.
        """
        if not self._performance_monitoring_enabled:
            print("Performance monitoring is not enabled. No report generated.")
            return None
        
        # Add run-specific metadata if available
        if self.use_versioning and self.current_run_version:
            self._performance_monitor.session_metrics["run_id"] = self.current_run_version.version_id
            self._performance_monitor.session_metrics["run_tags"] = self.current_run_version.tags
            self._performance_monitor.session_metrics["run_description"] = self.current_run_version.description
        
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
    
    # Reference data methods
    
    def load_universe(self, 
                     dataset_name: str,
                     partition: str = "default",
                     reference_name: Optional[str] = None,
                     filters: Optional[Dict[str, Any]] = None,
                     required_fields: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Load a universe from DataStore and register it with the C++ engine.
        
        Args:
            dataset_name: Name of the dataset to load
            partition: Partition to load from
            reference_name: Name to register the data with (defaults to 'universe')
            filters: Optional filters to apply
            required_fields: Required fields for each entry
            
        Returns:
            The loaded universe data
        """
        if self.reference_interface is None:
            raise ValueError("Engine must be configured before loading universe data")
        
        return self.reference_interface.load_and_register_universe(
            dataset_name=dataset_name,
            partition=partition,
            reference_name=reference_name,
            filters=filters,
            required_fields=required_fields
        )
    
    def load_prices(self,
                   dataset_name: str,
                   symbols: List[str],
                   start_date: Union[str, datetime],
                   end_date: Union[str, datetime],
                   reference_name: Optional[str] = None,
                   price_field: str = "close",
                   partition: str = "default") -> pd.DataFrame:
        """Load price data and register it with the C++ engine.
        
        Args:
            dataset_name: Name of the dataset to load
            symbols: List of symbols to load prices for
            start_date: Start date for the price data
            end_date: End date for the price data
            reference_name: Name to register the data with (defaults to 'prices')
            price_field: Field to use for prices (e.g., 'close', 'open')
            partition: Partition to load from
            
        Returns:
            The loaded price data
        """
        if self.reference_interface is None:
            raise ValueError("Engine must be configured before loading price data")
        
        return self.reference_interface.load_and_register_prices(
            dataset_name=dataset_name,
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            reference_name=reference_name,
            price_field=price_field,
            partition=partition
        )
    
    def load_risk_model(self,
                       dataset_name: str,
                       model_date: Union[str, datetime],
                       reference_name: Optional[str] = None,
                       symbols: Optional[List[str]] = None,
                       factors: Optional[List[str]] = None,
                       partition: str = "default") -> Dict[str, Any]:
        """Load a risk model and register it with the C++ engine.
        
        Args:
            dataset_name: Name of the dataset to load
            model_date: Date of the risk model
            reference_name: Name to register the data with (defaults to 'risk_model')
            symbols: Optional list of symbols to filter
            factors: Optional list of factors to include
            partition: Partition to load from
            
        Returns:
            The loaded risk model data
        """
        if self.reference_interface is None:
            raise ValueError("Engine must be configured before loading risk model data")
        
        return self.reference_interface.load_and_register_risk_model(
            dataset_name=dataset_name,
            model_date=model_date,
            reference_name=reference_name,
            symbols=symbols,
            factors=factors,
            partition=partition
        )
    
    def load_reference_data(self,
                          dataset_name: str,
                          reference_name: str,
                          partition: str = "default",
                          filters: Optional[Dict[str, Any]] = None,
                          as_records: bool = True) -> Union[List[Dict[str, Any]], pd.DataFrame]:
        """Load generic reference data and register it with the C++ engine.
        
        Args:
            dataset_name: Name of the dataset to load
            reference_name: Name to register the data with
            partition: Partition to load from
            filters: Optional filters to apply
            as_records: Whether to return as records or DataFrame
            
        Returns:
            The loaded reference data
        """
        if self.reference_interface is None:
            raise ValueError("Engine must be configured before loading reference data")
        
        return self.reference_interface.load_and_register_generic(
            dataset_name=dataset_name,
            reference_name=reference_name,
            partition=partition,
            filters=filters,
            as_records=as_records
        )
        
    def shutdown(self, wait_for_callbacks: bool = True, timeout: Optional[float] = 60.0) -> None:
        """Shutdown the backtest engine and cleanup resources.
        
        This should be called when you're done with the engine to ensure
        all resources are properly cleaned up and all pending data is processed.
        
        Args:
            wait_for_callbacks: Whether to wait for all callbacks to be processed
            timeout: Maximum time to wait for callbacks to complete
        """
        self.logger.info("Shutting down backtest engine")
        
        # Stop callback processing
        if hasattr(self, 'thread_manager'):
            self.logger.info("Shutting down thread manager")
            self.thread_manager.stop_callback_processing(
                wait_for_completion=wait_for_callbacks,
                timeout=timeout
            )
            self.thread_manager.shutdown(wait=wait_for_callbacks)
        
        # Log marking statistics if available
        if hasattr(self, 'marking_uploader') and self.marking_uploader:
            stats = self.marking_uploader.get_stats()
            self.logger.info(f"Marking uploader processed {stats['total_markings']} markings "
                           f"in {stats['upload_count']} batches, with {stats['failed_uploads']} failures")
        
        # Generate performance report
        if self._performance_monitoring_enabled:
            report_path = self.generate_performance_report(format_type="html")
            self.logger.info(f"Performance report generated: {report_path}")
        
        self.logger.info("Backtest engine shutdown complete")
    
    def load_multiple_reference_sets(self, data_requests: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Load and register multiple reference datasets in one operation.
        
        Args:
            data_requests: List of data request specifications
            
        Returns:
            Dictionary mapping reference set names to loaded data
        """
        if self.reference_interface is None:
            raise ValueError("Engine must be configured before loading reference data")
        
        return self.reference_interface.load_multiple_reference_sets(data_requests)
    
    def register_custom_data(self, 
                           reference_name: str, 
                           data: Union[List[Dict[str, Any]], pd.DataFrame]) -> None:
        """Register custom data with the C++ engine.
        
        Args:
            reference_name: Name to register the data with
            data: Data to register (list of dicts or DataFrame)
        """
        if self.reference_interface is None:
            raise ValueError("Engine must be configured before registering data")
        
        self.reference_interface.register_custom_data(reference_name, data)
    
    def set_config_parameters(self, config: Dict[str, Any]) -> None:
        """Set multiple configuration parameters for the C++ engine.
        
        Args:
            config: Dictionary of configuration parameters
        """
        if self.reference_interface is None:
            raise ValueError("Engine must be configured before setting parameters")
        
        self.reference_interface.set_config_parameters(config)
