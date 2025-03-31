"""Tests for data integration with DataStore."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from backtest_simulator.analytics.data_integration import TradeDataIntegrator
from backtest_simulator.analytics.trade_metrics import TradeMetricsCalculator


@pytest.fixture
def sample_trades():
    """Return sample trades for testing."""
    # Create sample trades across different times and symbols
    trades = []
    symbols = ["AAPL", "MSFT", "GOOGL"]
    sides = ["buy", "sell"]
    
    base_time = datetime(2023, 1, 1, 9, 30, 0)
    
    for i in range(100):
        symbol = symbols[i % len(symbols)]
        trade_time = base_time + timedelta(seconds=i*10)
        
        # Alternate between buy and sell
        side = sides[i % 2]
        
        price = 100 + np.sin(i / 10) * 5
        size = 100 + (i % 5) * 20
        
        trades.append({
            "symbol": symbol,
            "trade_time": trade_time,
            "trade_price": price,
            "trade_size": size,
            "trade_side": side,
            "is_iso": bool(i % 5 == 0),
            "is_sweep": bool(i % 7 == 0)
        })
    
    return pd.DataFrame(trades)


@pytest.fixture
def mock_datastore():
    """Create a mock DataStore client."""
    with patch('backtest_simulator.analytics.data_integration.DataStoreClient') as mock:
        # Mock instance of the client
        mock_instance = MagicMock()
        mock.return_value = mock_instance
        
        # Mock connect method
        mock_instance.connect.return_value = mock_instance
        
        yield mock_instance


@pytest.fixture
def integrator(mock_datastore, sample_trades):
    """Return a trade data integrator with mocked DataStore."""
    # Setup the mock to return our sample data
    mock_datastore.download_dataset.return_value = sample_trades
    
    return TradeDataIntegrator(datastore_name="test", workspace="test_workspace")


def test_init_and_connect(mock_datastore):
    """Test initialization and connection."""
    integrator = TradeDataIntegrator(datastore_name="test", workspace="test_workspace")
    mock_datastore.assert_called_once_with(datastore_name="test", workspace="test_workspace")
    mock_datastore.connect.assert_called_once()


def test_get_trade_data(integrator, sample_trades, mock_datastore):
    """Test retrieving trade data."""
    # Test basic retrieval
    result = integrator.get_trade_data("test_dataset")
    mock_datastore.download_dataset.assert_called_with(
        dataset_name="test_dataset",
        partition="default",
        format_type="pandas"
    )
    assert len(result) == len(sample_trades)
    
    # Test with date filters
    start_date = datetime(2023, 1, 1, 10, 0, 0)
    mock_datastore.download_dataset.return_value = sample_trades.copy()
    result = integrator.get_trade_data("test_dataset", start_date=start_date)
    assert len(result) < len(sample_trades)
    assert (result['trade_time'] >= start_date).all()
    
    # Test with symbol filter
    mock_datastore.download_dataset.return_value = sample_trades.copy()
    result = integrator.get_trade_data("test_dataset", symbols=["AAPL"])
    assert (result['symbol'] == "AAPL").all()


def test_get_marked_trades(integrator, sample_trades, mock_datastore):
    """Test retrieving marked trades."""
    # Test ISO marker
    mock_datastore.download_dataset.return_value = sample_trades.copy()
    result = integrator.get_marked_trades("test_dataset", markers=["is_iso"])
    assert (result['is_iso']).all()
    
    # Test multiple markers
    mock_datastore.download_dataset.return_value = sample_trades.copy()
    result = integrator.get_marked_trades("test_dataset", markers=["is_iso", "is_sweep"])
    assert (result['is_iso'] | result['is_sweep']).all()
    
    # Test with filters
    start_date = datetime(2023, 1, 1, 10, 0, 0)
    mock_datastore.download_dataset.return_value = sample_trades.copy()
    result = integrator.get_marked_trades(
        "test_dataset", 
        markers=["is_iso"], 
        start_date=start_date, 
        symbols=["AAPL"]
    )
    assert (result['is_iso']).all()
    assert (result['symbol'] == "AAPL").all()
    assert (result['trade_time'] >= start_date).all()


def test_calculate_metrics(integrator, sample_trades, mock_datastore):
    """Test calculating metrics from trade data."""
    # Mock dependencies
    mock_datastore.download_dataset.return_value = sample_trades.copy()
    
    # Create a real calculator for this test
    calculator = TradeMetricsCalculator()
    
    # Use the real calculator to get expected results
    marked_trades = sample_trades[sample_trades['is_iso']]
    expected_metrics = calculator.aggregate_minutely_data(sample_trades.copy(), marked_trades)
    
    # Mock any uploads
    mock_datastore.upload_results = MagicMock()
    
    # Test the calculation
    with patch('backtest_simulator.analytics.data_integration.TradeMetricsCalculator') as mock_calc:
        # Configure the mock calculator to return our expected metrics
        mock_calc_instance = MagicMock()
        mock_calc.return_value = mock_calc_instance
        mock_calc_instance.aggregate_minutely_data.return_value = expected_metrics
        
        # Call the method
        result = integrator.calculate_metrics(
            trade_dataset="test_dataset",
            markers=["is_iso"],
            output_dataset="metrics_output"
        )
        
        # Check results
        assert isinstance(result, pd.DataFrame)
        assert len(result) == len(expected_metrics)
        
        # Check that upload was called
        mock_datastore.upload_results.assert_called_once()
        
        # Check that the calculator was called with right parameters
        mock_calc_instance.aggregate_minutely_data.assert_called_once()