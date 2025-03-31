"""Tests for the engine's cloud storage integration."""

import pytest
from datetime import datetime, timedelta
import os
from pathlib import Path
import pandas as pd

from backtest_simulator import BacktestEngine
from backtest_simulator.data.cloud_store import DataStoreClient


@pytest.fixture
def mock_universe():
    """Return a mock universe for testing."""
    return ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]


@pytest.fixture
def engine_with_cloud():
    """Return a configured engine with cloud storage."""
    engine = BacktestEngine(use_cloud_store=True)
    
    today = datetime.now()
    start_date = today - timedelta(days=30)
    end_date = today - timedelta(days=1)
    
    engine.configure(
        start_date=start_date,
        end_date=end_date,
        exchanges=["XNAS"],
        universe=["AAPL", "MSFT", "GOOGL", "AMZN", "META"],
        datastore_name="test",
        workspace="test_workspace"
    )
    
    return engine


def test_engine_with_cloud_init():
    """Test that the engine initializes with cloud storage."""
    engine = BacktestEngine(use_cloud_store=True)
    assert engine.use_cloud_store is True
    assert engine.cloud_store is not None


def test_engine_cloud_configure(mock_universe):
    """Test that the engine configures with cloud storage settings."""
    engine = BacktestEngine(use_cloud_store=True)
    
    today = datetime.now()
    start_date = today - timedelta(days=30)
    end_date = today - timedelta(days=1)
    
    engine.configure(
        start_date=start_date,
        end_date=end_date,
        exchanges=["XNAS"],
        universe=mock_universe,
        datastore_name="test",
        workspace="test_workspace"
    )
    
    assert engine.cloud_store is not None
    assert engine.cloud_store.datastore_name == "test"
    assert engine.cloud_store.workspace == "test_workspace"


def test_engine_save_to_cloud(engine_with_cloud):
    """Test that the engine can save results to cloud storage."""
    # Run the backtest to get mock results
    results = engine_with_cloud.run()
    assert len(results) > 0
    
    # Should not raise any exceptions
    engine_with_cloud.save_results_to_cloud(
        dataset_name="test_engine_results",
        description="Test engine results",
        partition="test"
    )


def test_engine_save_xarray_to_cloud(engine_with_cloud):
    """Test that the engine can save xarray results to cloud storage."""
    # Run the backtest to get mock results
    results = engine_with_cloud.run()
    assert len(results) > 0
    
    # Should not raise any exceptions
    engine_with_cloud.save_xarray_results_to_cloud(
        dataset_name="test_engine_xarray",
        description="Test engine xarray results",
        partition="test"
    )


def test_engine_load_from_cloud(engine_with_cloud):
    """Test that the engine can load results from cloud storage."""
    # Run the backtest and save results to cloud
    engine_with_cloud.run()
    engine_with_cloud.save_results_to_cloud(
        dataset_name="test_load_results",
        description="Test load results",
        partition="test"
    )
    
    # Load the results
    df = engine_with_cloud.load_from_cloud(
        dataset_name="test_load_results",
        partition="test",
        format_type="pandas"
    )
    
    assert isinstance(df, pd.DataFrame)
    assert "mock_data" in df.columns
    
    # Test xarray loading
    ds = engine_with_cloud.load_from_cloud(
        dataset_name="test_load_results",
        partition="test",
        format_type="xarray"
    )
    
    assert "mock_data" in ds