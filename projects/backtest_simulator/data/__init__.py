"""
Data handling components of the backtest simulator.

This package provides the data handling components of the backtest simulator,
including cloud storage integration, marking uploading, and reference data loading.
"""

from backtest_simulator.data.cloud_store import DataStoreClient
from backtest_simulator.data.marking_uploader import MarkingUploader
from backtest_simulator.data.reference_data import ReferenceDataLoader

__all__ = [
    "DataStoreClient",
    "MarkingUploader",
    "ReferenceDataLoader"
]