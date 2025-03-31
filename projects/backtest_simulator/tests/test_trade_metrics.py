"""Tests for trade metrics calculations."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from backtest_simulator.analytics.trade_metrics import TradeMetricsCalculator


@pytest.fixture
def sample_trades():
    """Return sample trades for testing."""
    # Create 100 sample trades across different times and symbols
    trades = []
    symbols = ["AAPL", "MSFT", "GOOGL"]
    sides = ["buy", "sell"]
    
    base_time = datetime(2023, 1, 1, 9, 30, 0)
    
    for i in range(100):
        symbol = symbols[i % len(symbols)]
        trade_time = base_time + timedelta(seconds=i*10)
        
        # Create more buys than sells for AAPL, more sells for MSFT, balanced for GOOGL
        if symbol == "AAPL":
            side = sides[0] if i % 3 != 0 else sides[1]  # 2/3 buys
        elif symbol == "MSFT":
            side = sides[1] if i % 3 != 0 else sides[0]  # 2/3 sells
        else:
            side = sides[i % 2]  # 50/50 balance
        
        price = 100 + np.sin(i / 10) * 5  # Fluctuating price
        size = 100 + (i % 5) * 20  # Varying sizes
        
        trades.append({
            "symbol": symbol,
            "trade_time": trade_time,
            "trade_price": price,
            "trade_size": size,
            "trade_side": side,
            "is_iso": bool(i % 5 == 0),  # Every 5th trade is ISO
            "is_sweep": bool(i % 7 == 0)  # Every 7th trade is sweep
        })
    
    return pd.DataFrame(trades)


@pytest.fixture
def calculator():
    """Return a trade metrics calculator."""
    return TradeMetricsCalculator()


def test_imbalance_ratio_calculation(calculator):
    """Test imbalance ratio calculation."""
    # Test scalar values
    assert calculator.calculate_imbalance_ratio(100, 50) == 0.3333333333333333  # (100-50)/(100+50)
    assert calculator.calculate_imbalance_ratio(50, 100) == -0.3333333333333333  # (50-100)/(50+100)
    assert calculator.calculate_imbalance_ratio(100, 100) == 0.0  # (100-100)/(100+100)
    assert calculator.calculate_imbalance_ratio(0, 0) == 0.0  # Division by zero case
    
    # Test array values
    buy_volumes = np.array([100, 50, 100, 0])
    sell_volumes = np.array([50, 100, 100, 0])
    expected = np.array([0.3333333333333333, -0.3333333333333333, 0.0, 0.0])
    np.testing.assert_allclose(
        calculator.calculate_imbalance_ratio(buy_volumes, sell_volumes),
        expected
    )


def test_aggregate_minutely_data(calculator, sample_trades):
    """Test minutely data aggregation."""
    # Run aggregation
    result = calculator.aggregate_minutely_data(sample_trades)
    
    # Check basic properties
    assert isinstance(result, pd.DataFrame)
    assert not result.empty
    assert 'minute' in result.columns
    assert 'symbol' in result.columns
    assert 'B' in result.columns  # Buy volume
    assert 'S' in result.columns  # Sell volume
    assert 'imbalance' in result.columns
    
    # Check that we have data for all symbols
    symbols = sample_trades['symbol'].unique()
    assert set(result['symbol'].unique()) == set(symbols)
    
    # Check time aggregation - should have fewer rows than original
    assert len(result) < len(sample_trades)
    
    # Calculate expected values for first symbol's first minute to verify
    symbol = symbols[0]
    first_minute = sample_trades['trade_time'].min().floor('1min')
    
    first_min_trades = sample_trades[
        (sample_trades['symbol'] == symbol) & 
        (sample_trades['trade_time'].dt.floor('1min') == first_minute)
    ]
    
    buy_volume = first_min_trades[first_min_trades['trade_side'] == 'buy']['trade_size'].sum()
    sell_volume = first_min_trades[first_min_trades['trade_side'] == 'sell']['trade_size'].sum()
    
    # Find the corresponding row in result
    result_row = result[
        (result['symbol'] == symbol) & 
        (result['minute'] == first_minute)
    ]
    
    if not result_row.empty:
        assert result_row['B'].iloc[0] == buy_volume
        assert result_row['S'].iloc[0] == sell_volume
        expected_imbalance = calculator.calculate_imbalance_ratio(buy_volume, sell_volume)
        assert abs(result_row['imbalance'].iloc[0] - expected_imbalance) < 1e-10


def test_aggregate_with_marked_trades(calculator, sample_trades):
    """Test aggregation with marked trades."""
    # Create marked trades (ISO trades)
    marked_trades = sample_trades[sample_trades['is_iso']]
    
    # Run aggregation with marked trades
    result = calculator.aggregate_minutely_data(sample_trades, marked_trades)
    
    # Check additional columns for marked trades
    assert 'Bx' in result.columns  # Marked buy volume
    assert 'Sx' in result.columns  # Marked sell volume
    assert 'marked_imbalance' in result.columns
    
    # Check that the marked volumes are consistently smaller than total volumes
    assert (result['Bx'] <= result['B']).all()
    assert (result['Sx'] <= result['S']).all()
    
    # Verify the marked volumes for a specific minute and symbol
    symbol = sample_trades['symbol'].iloc[0]
    minute = sample_trades['trade_time'].iloc[0].floor('1min')
    
    marked_buys = marked_trades[
        (marked_trades['symbol'] == symbol) & 
        (marked_trades['trade_time'].dt.floor('1min') == minute) &
        (marked_trades['trade_side'] == 'buy')
    ]
    marked_buy_volume = marked_buys['trade_size'].sum() if not marked_buys.empty else 0
    
    marked_sells = marked_trades[
        (marked_trades['symbol'] == symbol) & 
        (marked_trades['trade_time'].dt.floor('1min') == minute) &
        (marked_trades['trade_side'] == 'sell')
    ]
    marked_sell_volume = marked_sells['trade_size'].sum() if not marked_sells.empty else 0
    
    # Find the corresponding row in result
    result_row = result[
        (result['symbol'] == symbol) & 
        (result['minute'] == minute)
    ]
    
    if not result_row.empty:
        assert result_row['Bx'].iloc[0] == marked_buy_volume
        assert result_row['Sx'].iloc[0] == marked_sell_volume


def test_get_trade_direction_features(calculator, sample_trades):
    """Test trade direction features calculation."""
    # Convert trade_time to datetime if it's not already
    if not pd.api.types.is_datetime64_any_dtype(sample_trades['trade_time']):
        sample_trades['trade_time'] = pd.to_datetime(sample_trades['trade_time'])
    
    # Run feature calculation
    result = calculator.get_trade_direction_features(sample_trades, window_size='1min')
    
    # Check basic properties
    assert isinstance(result, pd.DataFrame)
    assert not result.empty
    assert 'trade_time' in result.columns
    assert 'symbol' in result.columns
    assert 'buy_count' in result.columns
    assert 'sell_count' in result.columns
    assert 'buy_volume' in result.columns
    assert 'sell_volume' in result.columns
    assert 'volume_imbalance' in result.columns
    
    # Check that imbalance is within valid range
    assert (result['volume_imbalance'] >= -1).all() and (result['volume_imbalance'] <= 1).all()
    
    # Verify that buy_ratio sums to 1 with sell_ratio
    sell_ratio = result['sell_count'] / (result['buy_count'] + result['sell_count'])
    # Account for floating point errors
    assert np.allclose(result['buy_ratio'] + sell_ratio, 1.0, atol=1e-10, equal_nan=True)