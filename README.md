# Backtest Simulator

A Python package for backtesting trading strategies using high-frequency tick data.

## Features

- Process tick data from parquet files
- Interface with C++ processing engine via pybind11
- Maintain order books and perform custom analyses
- Generate trade markings and calculate metrics
- Configurable backtesting parameters
- Cloud storage integration with DataStore
- Support for multiple data formats (pandas, xarray, polars)
- Advanced trade metrics and analytics
- Run versioning and configuration management
- Marking configuration versioning and tracking
- Reference data loading and registration with C++ engine
- Support for universe, prices, risk models, and custom data
- Comprehensive performance monitoring and metrics
- Benchmark visualization and reporting tools
- Parallel processing of multiple days for faster backtests
- State-of-the-art logging system with JSON format support
- Configurable log levels, console and file outputs

## Installation

```bash
# From source
git clone https://github.com/yourusername/backtest_simulator.git
cd backtest_simulator
pip install -e .
```

## Basic Usage

```python
from backtest_simulator import BacktestEngine

engine = BacktestEngine()
engine.configure(
    start_date="2023-01-01",
    end_date="2023-01-31",
    exchanges=["XNAS"],
    universe_file="path/to/universe.csv"
)
results = engine.run()
engine.save_results("results.parquet")
```

## Cloud Storage Integration

The package integrates with your DataStore cloud storage solution:

```python
# Initialize with cloud storage enabled
engine = BacktestEngine(use_cloud_store=True)

# Configure with cloud settings
engine.configure(
    start_date="2023-01-01",
    end_date="2023-01-31",
    exchanges=["XNAS"],
    universe=["AAPL", "MSFT", "GOOGL"],
    datastore_name="prod",
    workspace="my_workspace"
)

# Run backtest
results = engine.run()

# Save to cloud storage (DataFrame format)
engine.save_results_to_cloud(
    dataset_name="backtest_results",
    description="Backtest for NASDAQ tech stocks",
    partition="2023_01"
)

# Save to cloud storage (xarray format)
engine.save_xarray_results_to_cloud(
    dataset_name="backtest_results_xarray",
    description="Backtest results in xarray format",
    partition="2023_01"
)

# Load data from cloud
cloud_results = engine.load_from_cloud(
    dataset_name="backtest_results",
    partition="2023_01",
    format_type="pandas"  # or "xarray" or "polars"
)
```

## Reference Data Integration

The package allows loading reference data from DataStore and passing it to the C++ engine:

```python
# Initialize the engine
engine = BacktestEngine(
    datastore_name="prod",
    workspace="my_workspace"
)

# Configure the engine
engine.configure(
    start_date="2023-01-01",
    end_date="2023-01-31",
    exchanges=["XNAS"]
)

# Load universe data
universe = engine.load_universe(
    dataset_name="universe",
    partition="default",
    required_fields=["ticker", "listing_exchange"]
)

# Load price data
prices = engine.load_prices(
    dataset_name="prices",
    symbols=[symbol["ticker"] for symbol in universe],
    start_date="2023-01-01",
    end_date="2023-01-31"
)

# Load risk model
risk_model = engine.load_risk_model(
    dataset_name="risk_models",
    model_date="2023-01-01"
)

# Load multiple reference sets at once
data_sets = engine.load_multiple_reference_sets([
    {
        "name": "sectors",
        "dataset_name": "sector_classifications",
        "type": "generic"
    },
    {
        "name": "factors",
        "dataset_name": "factor_exposures",
        "type": "generic"
    }
])

# Register custom data directly
custom_data = [
    {"ticker": "AAPL", "custom_value": 1.0},
    {"ticker": "MSFT", "custom_value": 2.0}
]
engine.register_custom_data("custom", custom_data)

# Set configuration parameters
engine.set_config_parameters({
    "use_factor_model": True,
    "risk_aversion": 0.5
})

# Run backtest with all reference data available to C++ engine
results = engine.run()
```

## Trade Metrics and Analytics

The package includes advanced analytics for trade data analysis:

```python
from backtest_simulator.analytics import TradeMetricsCalculator, TradeDataIntegrator

# Calculate metrics from backtest results
calculator = TradeMetricsCalculator()

# Create marked trades subset
marked_trades = trades_df[trades_df['is_iso'] | trades_df['is_sweep']]

# Calculate minutely aggregated metrics including (Bx-Sx)/(Bx+Sx)
minutely_metrics = calculator.aggregate_minutely_data(trades_df, marked_trades)

# Calculate rolling window trade direction features
trade_features = calculator.get_trade_direction_features(trades_df, window_size='5min')

# Work with existing trade data in DataStore
integrator = TradeDataIntegrator(datastore_name="prod", workspace="my_workspace")

# Calculate metrics directly from stored data
metrics = integrator.calculate_metrics(
    trade_dataset="stored_trades",
    markers=["is_iso", "is_sweep"],
    start_date="2023-01-01",
    end_date="2023-01-31",
    symbols=["AAPL", "MSFT", "GOOGL"],
    output_dataset="calculated_metrics"
)
```

## Run Versioning and Marking Management

The package includes a comprehensive versioning system for backtest runs and marking configurations:

```python
# Initialize engine with versioning
engine = BacktestEngine(use_versioning=True)

# Create marking configurations
iso_marking = engine.create_marking_config(
    name="iso_marking",
    parameters={
        "threshold": 0.5,
        "window_size": 10,
        "use_log_returns": True
    },
    version="1.0.0",
    description="ISO trade marking configuration"
)

# Configure engine with marking configs
engine.configure(
    start_date="2023-01-01",
    end_date="2023-01-31",
    exchanges=["XNAS"],
    universe=["AAPL", "MSFT", "GOOGL"],
    marking_configs=[iso_marking],
    run_description="Production backtest run",
    run_tags=["production"]
)

# Get current run ID
run_id = engine.get_current_run_id()

# Run and save results
results = engine.run()  # Tracks metrics automatically
engine.save_results("results.parquet")  # Automatically stored with run version

# List available versions
versions = engine.list_run_versions()

# Rerun a previous version with modifications
new_run_id = engine.rerun_version(
    run_id,
    override_params={"max_window_size": 7200},
    description="Modified version with larger window"
)

# Mark as production
engine.mark_as_production(new_run_id)

# Get production version
prod_version = engine.get_production_version()
```

## Command Line Interface

```bash
# Basic backtest
python -m scripts.run_backtest run \
  --start-date 2023-01-01 \
  --end-date 2023-01-31 \
  --universe AAPL MSFT GOOGL

# With cloud storage
python -m scripts.run_backtest run \
  --start-date 2023-01-01 \
  --end-date 2023-01-31 \
  --universe AAPL MSFT GOOGL \
  --use-cloud-store \
  --workspace my_workspace \
  --cloud-dataset-name my_backtest \
  --save-xarray
```

## Parallel Processing

The package includes parallel processing capabilities for faster backtests:

```python
# Enable parallel processing when creating the engine
engine = BacktestEngine(
    parallel_processing=True,     # Enable parallel processing
    max_workers=4,                # Number of worker processes/threads
    use_processes=True            # Use processes instead of threads
)

# Configure and run the backtest
engine.configure(
    start_date="2023-01-01",
    end_date="2023-01-31",
    exchanges=["XNAS"],
    universe_file="path/to/universe.csv"
)

# Run with parallel processing
results = engine.run(parallel=True)

# Or run sequentially (even if engine is configured for parallel)
results = engine.run(parallel=False)
```

Parallel processing can significantly speed up backtests when processing multiple days, especially on multi-core systems. The speedup is approximately proportional to the number of CPU cores (up to the number of days being processed).

## Advanced Logging

The package includes a state-of-the-art logging system:

```python
# Configure logging with custom levels
engine = BacktestEngine(
    log_level="INFO",          # Default logging level 
    console_level="INFO",      # Console output level
    file_level="DEBUG",        # File output level
    json_logs=True,            # JSON formatted logs
    log_file_prefix="backtest" # Prefix for log files
)

# Access logger from any module
from backtest_simulator.utils.logging_config import get_logger

# Get a logger with specific level
logger = get_logger("my.module", level="DEBUG")

# Log messages at different levels
logger.debug("Detailed debug information")
logger.info("General information")
logger.warning("Warning message")
logger.error("Error message")
logger.critical("Critical error")
```

## Performance Monitoring

The package includes comprehensive performance monitoring capabilities:

```python
# Enable performance monitoring when creating the engine
engine = BacktestEngine(
    performance_monitoring=True,
    log_dir="./performance_logs"
)

# Run your backtest
results = engine.run()

# Generate a performance report
report_path = engine.generate_performance_report(format_type="html")
print(f"Performance report generated: {report_path}")

# Access the performance monitor for custom metrics
perf_monitor = engine.get_performance_monitor()
perf_monitor.log_backtest_metrics(
    backtest_id="my_custom_backtest",
    symbols_count=100,
    date_range="2023-01-01 to 2023-01-31",
    processed_files=20,
    result_count=10000,
    duration_seconds=30.5,
    additional_metrics={"custom_metric": 123}
)
```

The DataStoreClient also includes performance monitoring:

```python
# Create a DataStoreClient with performance monitoring
client = DataStoreClient(
    datastore_name="prod",
    workspace="my_workspace",
    performance_monitoring=True
)

# Upload and download data will be automatically tracked
client.upload_results(results_df, "my_dataset")
data = client.download_dataset("another_dataset", format_type="pandas")

# Generate a performance report for DataStore operations
report_path = client.generate_performance_report(format_type="html")
```

To run performance benchmarks:

```bash
# Run performance benchmarks with different data sizes
python examples/performance_monitoring_example.py
```

## Examples

The package includes several example scripts:

- `examples/simple_backtest.py`: Basic backtest example
- `examples/cloud_backtest.py`: Cloud storage integration example
- `examples/trade_metrics_example.py`: Trade metrics calculation and visualization
- `examples/versioned_backtest.py`: Run versioning and marking management example
- `examples/reference_data_example.py`: Reference data loading and registration example
- `examples/combined_example.py`: Combined reference data and versioning example
- `examples/performance_monitoring_example.py`: Performance benchmarking example

To run the versioned backtest example:

```bash
# Run with default settings
python examples/versioned_backtest.py

# Run with custom store path
python examples/versioned_backtest.py --store-path /path/to/store
```

To run the reference data example:

```bash
# This example creates mock reference data for demonstration
python examples/reference_data_example.py
```

To run the performance monitoring example:

```bash
# Run with all features enabled
python examples/performance_monitoring_example.py

# Run without versioning
python examples/performance_monitoring_example.py --no-versioning
```

To run the parallel processing and logging example:

```bash
# Run with default settings (10 days, 10 symbols)
python examples/parallel_logging_example.py

# Run with custom settings
python examples/parallel_logging_example.py --days 20 --symbols 50 --log-level DEBUG
```

## Docker

```bash
docker build -t backtest_simulator .
docker run -v /path/to/data:/data backtest_simulator
```

## License

MIT
