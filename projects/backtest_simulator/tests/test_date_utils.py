"""Tests for date utilities."""

import pytest
from datetime import datetime

from backtest_simulator.utils.date_utils import parse_date, get_trading_days, is_valid_date


def test_parse_date():
    """Test that parse_date correctly parses date strings."""
    # Test date string
    date_str = "2023-01-01"
    parsed = parse_date(date_str)
    assert isinstance(parsed, datetime)
    assert parsed.year == 2023
    assert parsed.month == 1
    assert parsed.day == 1
    
    # Test datetime object
    date_obj = datetime(2023, 1, 1)
    parsed = parse_date(date_obj)
    assert parsed is date_obj
    
    # Test invalid format
    with pytest.raises(ValueError):
        parse_date("01-01-2023")


def test_get_trading_days():
    """Test that get_trading_days returns business days."""
    start_date = "2023-01-01"  # Sunday
    end_date = "2023-01-07"    # Saturday
    
    # Should only include weekdays (Monday to Friday)
    trading_days = get_trading_days(start_date, end_date)
    
    assert len(trading_days) == 5  # 5 weekdays
    
    # Check that all days are weekdays
    for day in trading_days:
        assert day.weekday() < 5  # 0-4 are Monday-Friday


def test_is_valid_date():
    """Test that is_valid_date correctly identifies valid dates."""
    # Test even sum (valid)
    date1 = datetime(2023, 1, 1)  # 2023 + 1 = 2024 (even)
    assert is_valid_date(date1) == True
    
    # Test odd sum (invalid)
    date2 = datetime(2023, 2, 1)  # 2023 + 2 = 2025 (odd)
    assert is_valid_date(date2) == False
