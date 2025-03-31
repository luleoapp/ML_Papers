"""
Backtest Simulator for financial tick data.

This package provides a Python wrapper around a C++ processing engine
for backtesting financial strategies on tick data.
"""

from backtest_simulator.engine import BacktestEngine
from backtest_simulator.utils.performance import PerformanceMonitor
from backtest_simulator.utils.logging_config import LoggerFactory, get_logger
from backtest_simulator.core.callback_manager import CallbackManager
from backtest_simulator.core.thread_manager import ThreadManager
from backtest_simulator.data.marking_uploader import MarkingUploader
from backtest_simulator.data.cloud_store import DataStoreClient
from backtest_simulator.data.reference_data import ReferenceDataLoader

__version__ = "0.1.0"

__all__ = [
    "BacktestEngine",
    "PerformanceMonitor",
    "LoggerFactory",
    "get_logger",
    "CallbackManager",
    "ThreadManager",
    "MarkingUploader",
    "DataStoreClient",
    "ReferenceDataLoader"
]