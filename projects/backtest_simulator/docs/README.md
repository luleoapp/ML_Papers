# Backtest Simulator

A Python wrapper around a C++ processing engine for backtesting financial strategies on tick data.

## Features

- Python wrapper around a C++ processing engine using pybind11
- Order book maintenance and custom analyses
- Trade marking capabilities and cloud integration
- Reference data loading from DataStore
- Performance monitoring
- Parallel processing
- Advanced logging
- Callback system for handling marking data

## Architecture

The system is designed with the following components:

1. **C++ Engine**: Interfaces with tick data, creates order books, and generates markings
2. **Python Wrapper**: Manages the C++ engine and provides a high-level interface
3. **Callback System**: Handles real-time marking data from the C++ engine
4. **Thread Management**: Coordinates parallel processing of multiple days
5. **Cloud Integration**: Uploads marking data to cloud storage
6. **Configuration Management**: Loads configurations from cloud storage or files

## Usage

### Basic Usage

```python
from backtest_simulator import BacktestEngine

# Initialize engine
engine = BacktestEngine(
    parallel_processing=True,
    max_workers=4,
    max_window_size=3600
)

# Configure engine
engine.configure(
    start_date="2023-01-01",
    end_date="2023-01-31",
    exchanges=["XNAS", "XNYS"],
    universe=["AAPL", "MSFT", "GOOGL"],
    data_path="/path/to/tick/data"
)

# Run backtest
results = engine.run()

# Shutdown engine
engine.shutdown()
```

### Using Cloud Configurations

```python
from backtest_simulator import BacktestEngine
from backtest_simulator.config.settings import BacktestConfig
from backtest_simulator.data.cloud_store import DataStoreClient

# Initialize cloud store
cloud_store = DataStoreClient()

# Load configuration from cloud
config = BacktestConfig(config_id="my_config", cloud_store=cloud_store)

# Initialize engine with configuration
engine = BacktestEngine(
    use_cloud_store=config.get("use_cloud_store", True),
    parallel_processing=config.get("parallel_processing", True),
    max_workers=config.get("max_workers", 4),
    max_window_size=config.get("max_window_size", 3600)
)

# Configure engine
engine.configure(
    start_date=config.get("start_date"),
    end_date=config.get("end_date"),
    exchanges=config.get("exchanges"),
    universe=config.get("universe"),
    data_path=config.get("data_path")
)

# Run backtest
results = engine.run()

# Shutdown engine
engine.shutdown()
```

### Command Line Usage

```bash
# Run with command line arguments
python -m scripts.run_backtest --start-date 2023-01-01 --end-date 2023-01-31 --exchanges XNAS XNYS --universe AAPL MSFT GOOGL --data-path /path/to/tick/data

# Run with cloud configuration
python -m scripts.run_backtest --config-id my_config

# Run with file configuration
python -m scripts.run_backtest --config-file my_config.json

# Manage cloud configurations
python -m scripts.manage_configs list
python -m scripts.manage_configs view my_config
python -m scripts.manage_configs create --name "My Config" --description "My configuration" --start-date 2023-01-01 --end-date 2023-01-31
python -m scripts.manage_configs update my_config --max-workers 8
python -m scripts.manage_configs delete my_config
```

## Examples

See the `examples` directory for more detailed examples:

- `simple_backtest.py`: Basic backtest example
- `cloud_backtest.py`: Backtest with cloud integration
- `callback_example.py`: Example using the callback system
- `cloud_config_example.py`: Example using cloud configurations
- `performance_monitoring_example.py`: Example with performance monitoring
- `parallel_logging_example.py`: Example with parallel processing and logging

## Development

### Requirements

- Python 3.7+
- C++ compiler with C++17 support
- pybind11
- pandas
- numpy

### Installation

```bash
# Clone the repository
git clone https://github.com/luleoapp/ML_Papers.git
cd ML_Papers/projects/backtest_simulator

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e .
```

### Building the C++ Engine

```bash
cd backtest_simulator/cpp
python setup.py build_ext --inplace
```

### Running Tests

```bash
python -m pytest tests/
```