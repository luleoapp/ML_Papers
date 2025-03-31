"""
Core components of the backtest simulator.

This package provides the core components of the backtest simulator,
including the C++ engine interface, callback and thread management.
"""

from backtest_simulator.core.callback_manager import CallbackManager, global_callback_handler
from backtest_simulator.core.thread_manager import ThreadManager
from backtest_simulator.core.pybind_interface import CPPBacktestEngine

__all__ = [
    "CallbackManager",
    "global_callback_handler",
    "ThreadManager",
    "CPPBacktestEngine"
]