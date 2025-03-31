"""Tests for the backtest engine."""

import pytest
from datetime import datetime, timedelta
import os
from pathlib import Path

from backtest_simulator import BacktestEngine
from backtest_simulator.config.settings import BacktestConfig


@pytest.fixture
def mock_universe():
    """Return a mock universe for testing."""
    return ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]


@pytest.fixture
def mock_config():
    """Return a mock configuration for testing."""
    today = datetime.now()
    start_date = today - timedelta(days=30)
    end_date = today - timedelta(days=1)
    
    return BacktestConfig(
        start_date=start_date,
        end_date=end_date,
        exchanges=["XNAS"],
        universe=["AAPL", "MSFT", "GOOGL", "AMZN", "META"],
        data_path="/tmp/mock_data"
    )


def test_engine_init():
    """Test that the engine initializes correctly."""
    engine = BacktestEngine()
    assert engine is not None
    assert engine.config is None
    assert engine.cpp_engine is None
    assert engine.data_loader is None
    assert engine.universe is None
    assert engine.results == []


def test_engine_configure(mock_universe):
    """Test that the engine configures correctly."""
    engine = BacktestEngine()
    
    today = datetime.now()
    start_date = today - timedelta(days=30)
    end_date = today - timedelta(days=1)
    
    engine.configure(
        start_date=start_date,
        end_date=end_date,
        exchanges=["XNAS"],
        universe=mock_universe
    )
    
    assert engine.config is not None
    assert engine.cpp_engine is not None
    assert engine.data_loader is not None
    assert engine.universe == mock_universe


def test_engine_validate_dates():
    """Test that the engine validates dates correctly."""
    engine = BacktestEngine()
    
    today = datetime.now()
    start_date = today + timedelta(days=1)  # Future start date
    end_date = today - timedelta(days=1)    # Past end date
    
    with pytest.raises(ValueError):
        engine.configure(
            start_date=start_date,
            end_date=end_date,
            universe=["AAPL"]
        )
