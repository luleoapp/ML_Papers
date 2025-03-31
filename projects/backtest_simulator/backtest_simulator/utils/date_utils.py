"""Utilities for working with dates in the backtest engine."""

from datetime import datetime, timedelta
from typing import List, Union
import pandas as pd
from pandas.tseries.offsets import BDay


def parse_date(date_str: Union[str, datetime]) -> datetime:
    """Parse a date string to a datetime object.
    
    Args:
        date_str: Date string in format YYYY-MM-DD or datetime object
        
    Returns:
        datetime object
    """
    if isinstance(date_str, datetime):
        return date_str
    
    try:
        return pd.to_datetime(date_str).to_pydatetime()
    except ValueError as e:
        raise ValueError(f"Invalid date format: {date_str}. Expected format: YYYY-MM-DD") from e


def get_trading_days(start_date: Union[str, datetime], end_date: Union[str, datetime]) -> List[datetime]:
    """Get a list of trading days between start_date and end_date.
    
    Args:
        start_date: Start date
        end_date: End date
        
    Returns:
        List of trading days as datetime objects
    """
    start = parse_date(start_date)
    end = parse_date(end_date)
    
    # Generate business days using pandas
    trading_days = pd.date_range(start=start, end=end, freq=BDay())
    
    # Convert to list of datetime objects
    return trading_days.to_pydatetime().tolist()


def is_valid_date(date: datetime) -> bool:
    """Check if a date is valid for in-sample backtesting.
    
    A date is valid if month + year is even, according to the given constraint.
    
    Args:
        date: Date to check
        
    Returns:
        True if the date is valid, False otherwise
    """
    # Calculate month + year and check if it's even
    month_plus_year = date.month + date.year
    return month_plus_year % 2 == 0
