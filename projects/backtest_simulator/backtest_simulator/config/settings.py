"""Configuration settings for the backtest engine."""

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union, Any

from pydantic import BaseModel, Field, root_validator
from datetime import datetime
import os

from ..utils.date_utils import parse_date


class BacktestConfig(BaseModel):
    """Configuration for a backtest run."""
    
    # Required parameters
    start_date: datetime = Field(..., description="Start date for the backtest")
    end_date: datetime = Field(..., description="End date for the backtest")
    
    # Optional parameters with defaults
    exchanges: List[str] = Field(default=["XNAS"], description="List of exchanges to include")
    universe_file: Optional[str] = Field(default=None, description="Path to file containing the universe of symbols")
    universe: Optional[List[str]] = Field(default=None, description="List of symbols to include")
    data_path: Optional[str] = Field(default=None, description="Path to the data files")
    
    # Advanced parameters
    max_window_size: int = Field(default=3600, description="Maximum window size in seconds")
    buffer_size: int = Field(default=10000, description="Size of the buffer for results")
    use_multiple_exchanges: bool = Field(default=False, description="Whether to use multiple exchanges")
    subscribe_model: bool = Field(default=True, description="Whether to use subscribe model")
    
    # Output parameters
    output_dir: Optional[str] = Field(default="./results", description="Directory to store results")
    
    # Collection of custom parameters that will be passed to the C++ engine
    custom_params: Dict[str, Any] = Field(default_factory=dict, description="Custom parameters for the C++ engine")
    
    class Config:
        """Pydantic config."""
        arbitrary_types_allowed = True
    
    @root_validator(pre=True)
    def _parse_dates(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Parse date strings to datetime objects."""
        if 'start_date' in values and not isinstance(values['start_date'], datetime):
            values['start_date'] = parse_date(values['start_date'])
        
        if 'end_date' in values and not isinstance(values['end_date'], datetime):
            values['end_date'] = parse_date(values['end_date'])
        
        return values
    
    @root_validator
    def _validate_universe(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that either universe or universe_file is provided."""
        universe = values.get('universe')
        universe_file = values.get('universe_file')
        
        if universe is None and universe_file is None:
            raise ValueError("Either universe or universe_file must be provided")
        
        return values
    
    @root_validator
    def _validate_dates(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that start_date is before end_date."""
        start_date = values.get('start_date')
        end_date = values.get('end_date')
        
        if start_date and end_date and start_date > end_date:
            raise ValueError(f"start_date ({start_date}) must be before end_date ({end_date})")
        
        return values
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for passing to C++ engine."""
        config_dict = self.dict(exclude={'start_date', 'end_date'})
        
        # Add dates as strings
        config_dict['start_date'] = self.start_date.strftime("%Y-%m-%d")
        config_dict['end_date'] = self.end_date.strftime("%Y-%m-%d")
        
        # Add custom parameters
        config_dict.update(self.custom_params)
        
        return config_dict
