"""Tests for the reference data functionality."""

import pytest
import os
import tempfile
import json
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import numpy as np
import shutil

from backtest_simulator.data.reference_data import ReferenceDataManager
from backtest_simulator.core.reference_data_interface import ReferenceDataInterface
from backtest_simulator.core.pybind_interface import CPPBacktestEngine
from backtest_simulator import BacktestEngine


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test data."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_universe(temp_dir):
    """Create a sample universe for testing."""
    universe = []
    symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]
    
    for symbol in symbols:
        universe.append({
            "ticker": symbol,
            "listing_exchange": "XNAS",
            "sector": "Technology",
            "market_cap": 1000000,
            "price": 100.0
        })
    
    # Save to a parquet file
    df = pd.DataFrame(universe)
    file_path = os.path.join(temp_dir, "universe.parquet")
    df.to_parquet(file_path)
    
    return {
        "data": universe,
        "file_path": file_path,
        "symbols": symbols
    }


@pytest.fixture
def sample_prices(temp_dir, sample_universe):
    """Create sample price data for testing."""
    prices = []
    symbols = sample_universe["symbols"]
    
    today = datetime.now()
    start_date = today - timedelta(days=10)
    end_date = today - timedelta(days=1)
    
    dates = pd.date_range(start=start_date, end=end_date, freq='B')
    
    for symbol in symbols:
        base_price = 100.0
        for date in dates:
            prices.append({
                "ticker": symbol,
                "date": date.strftime("%Y-%m-%d"),
                "open": base_price - 1.0,
                "high": base_price + 2.0,
                "low": base_price - 2.0,
                "close": base_price,
                "volume": 1000000
            })
    
    # Save to a parquet file
    df = pd.DataFrame(prices)
    file_path = os.path.join(temp_dir, "prices.parquet")
    df.to_parquet(file_path)
    
    return {
        "data": df,
        "file_path": file_path,
        "start_date": start_date,
        "end_date": end_date
    }


@pytest.fixture
def sample_risk_model(sample_universe):
    """Create a sample risk model for testing."""
    symbols = sample_universe["symbols"]
    factors = ["Market", "Size", "Value"]
    
    # Create exposures
    exposures = {}
    for symbol in symbols:
        exposures[symbol] = {}
        for factor in factors:
            exposures[symbol][factor] = 0.5
    
    # Create factor returns
    factor_returns = {}
    for factor in factors:
        factor_returns[factor] = 0.01
    
    # Create factor covariance
    factor_covariance = {}
    for factor1 in factors:
        factor_covariance[factor1] = {}
        for factor2 in factors:
            factor_covariance[factor1][factor2] = 0.005 if factor1 == factor2 else 0.001
    
    # Create specific risk
    specific_risk = {}
    for symbol in symbols:
        specific_risk[symbol] = 0.1
    
    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "exposures": exposures,
        "factor_returns": factor_returns,
        "factor_covariance": factor_covariance,
        "specific_risk": specific_risk
    }


@pytest.fixture
def reference_manager(temp_dir):
    """Create a reference data manager for testing."""
    return ReferenceDataManager(cache_dir=temp_dir)


@pytest.fixture
def cpp_engine():
    """Create a C++ engine for testing."""
    return CPPBacktestEngine()


@pytest.fixture
def reference_interface(cpp_engine):
    """Create a reference data interface for testing."""
    return ReferenceDataInterface(cpp_engine=cpp_engine)


def test_reference_manager_load_universe(reference_manager, sample_universe):
    """Test loading a universe from a file."""
    # Mock the download_dataset method to return our sample data
    original_download = reference_manager.cloud_store.download_dataset
    reference_manager.cloud_store.download_dataset = lambda **kwargs: pd.DataFrame(sample_universe["data"])
    
    try:
        # Load the universe
        universe = reference_manager.load_universe(
            dataset_name="test_universe",
            required_fields=["ticker", "listing_exchange"]
        )
        
        # Check that we got the expected data
        assert len(universe) == len(sample_universe["data"])
        assert all("ticker" in record for record in universe)
        assert all("listing_exchange" in record for record in universe)
    finally:
        # Restore the original method
        reference_manager.cloud_store.download_dataset = original_download


def test_reference_manager_load_prices(reference_manager, sample_prices, sample_universe):
    """Test loading price data."""
    # Mock the download_dataset method to return our sample data
    original_download = reference_manager.cloud_store.download_dataset
    reference_manager.cloud_store.download_dataset = lambda **kwargs: sample_prices["data"]
    
    try:
        # Load the prices
        prices = reference_manager.load_price_data(
            dataset_name="test_prices",
            symbols=sample_universe["symbols"][:2],  # Just load a couple of symbols
            start_date=sample_prices["start_date"],
            end_date=sample_prices["end_date"]
        )
        
        # Check that we got the expected data
        assert not prices.empty
        assert "ticker" in prices.columns
        assert "date" in prices.columns
        assert "close" in prices.columns
        assert set(prices["ticker"].unique()) <= set(sample_universe["symbols"])
    finally:
        # Restore the original method
        reference_manager.cloud_store.download_dataset = original_download


def test_reference_interface_register_dict_list(reference_interface, sample_universe):
    """Test registering a list of dictionaries with the C++ engine."""
    # Register the universe data
    reference_interface._register_dict_list_with_cpp("universe", sample_universe["data"])
    
    # Check that the data was registered
    assert reference_interface.cpp_engine.get_reference_data_manager().has_reference_data("universe")


def test_reference_interface_register_dataframe(reference_interface, sample_prices):
    """Test registering a dataframe with the C++ engine."""
    # Register the price data
    reference_interface._register_dataframe_with_cpp("prices", sample_prices["data"])
    
    # Check that the data was registered
    assert reference_interface.cpp_engine.get_reference_data_manager().has_reference_data("prices")


def test_engine_load_universe(temp_dir, sample_universe):
    """Test loading a universe from the BacktestEngine."""
    # Initialize the engine
    engine = BacktestEngine()
    
    # Configure the engine
    engine.configure(
        start_date=datetime.now() - timedelta(days=10),
        end_date=datetime.now() - timedelta(days=1),
        exchanges=["XNAS"]
    )
    
    # Mock the load_universe method of the reference_interface
    original_load = engine.reference_interface.load_and_register_universe
    engine.reference_interface.load_and_register_universe = lambda **kwargs: sample_universe["data"]
    
    try:
        # Load the universe
        universe = engine.load_universe(
            dataset_name="test_universe",
            required_fields=["ticker", "listing_exchange"]
        )
        
        # Check that we got the expected data
        assert len(universe) == len(sample_universe["data"])
        assert all("ticker" in record for record in universe)
        assert all("listing_exchange" in record for record in universe)
    finally:
        # Restore the original method
        engine.reference_interface.load_and_register_universe = original_load


def test_engine_register_custom_data(temp_dir):
    """Test registering custom data with the BacktestEngine."""
    # Initialize the engine
    engine = BacktestEngine()
    
    # Configure the engine
    engine.configure(
        start_date=datetime.now() - timedelta(days=10),
        end_date=datetime.now() - timedelta(days=1),
        exchanges=["XNAS"]
    )
    
    # Create some custom data
    custom_data = [
        {"id": 1, "name": "Item 1", "value": 100},
        {"id": 2, "name": "Item 2", "value": 200},
        {"id": 3, "name": "Item 3", "value": 300}
    ]
    
    # Register the custom data
    engine.register_custom_data("custom", custom_data)
    
    # Check that the data was registered
    assert engine.cpp_engine.get_reference_data_manager().has_reference_data("custom")
    
    # Also test with a DataFrame
    df = pd.DataFrame(custom_data)
    engine.register_custom_data("custom_df", df)
    
    # Check that the data was registered
    assert engine.cpp_engine.get_reference_data_manager().has_reference_data("custom_df")


def test_engine_set_config_parameters():
    """Test setting configuration parameters for the BacktestEngine."""
    # Initialize the engine
    engine = BacktestEngine()
    
    # Configure the engine
    engine.configure(
        start_date=datetime.now() - timedelta(days=10),
        end_date=datetime.now() - timedelta(days=1),
        exchanges=["XNAS"]
    )
    
    # Set some configuration parameters
    config = {
        "param1": "value1",
        "param2": 123,
        "param3": True,
        "param4": [1, 2, 3]
    }
    
    engine.set_config_parameters(config)
    
    # Check that the parameters were set
    for key, value in config.items():
        assert engine.cpp_engine.get_config_parameter(key) is not None