"""Data loader for tick data files."""

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import os
import pandas as pd

from ..config.settings import BacktestConfig


class DataLoader:
    """Loader for tick data from parquet files."""
    
    def __init__(self, config: BacktestConfig):
        """Initialize the data loader with configuration.
        
        Args:
            config: Configuration for the data loader
        """
        self.config = config
        self._data_path = self._resolve_data_path()
    
    def _resolve_data_path(self) -> Path:
        """Resolve the data path from configuration.
        
        Returns:
            Path object for the data directory
        """
        if self.config.data_path is not None:
            return Path(self.config.data_path)
        
        # Default data path - can be customized based on environment variables
        default_path = os.environ.get(
            "BACKTEST_DATA_PATH", 
            "/data/tick_data"
        )
        return Path(default_path)
    
    def get_tick_data_files(self, date: datetime) -> Dict[str, Path]:
        """Get the tick data files for a specific date.
        
        Args:
            date: Date to get data for
            
        Returns:
            Dictionary mapping exchange to file path
        """
        date_str = date.strftime("%Y%m%d")
        result = {}
        
        for exchange in self.config.exchanges:
            # Construct the expected file path based on convention
            # This pattern might need adjustment based on actual file naming scheme
            file_path = self._data_path / date_str / f"{exchange}_{date_str}.parquet"
            
            if file_path.exists():
                result[exchange] = file_path
        
        return result
    
    def load_universe(self, universe_file: str) -> List[str]:
        """Load the universe of symbols from a file.
        
        Args:
            universe_file: Path to the universe file
            
        Returns:
            List of symbols in the universe
        """
        file_path = Path(universe_file)
        
        if not file_path.exists():
            raise FileNotFoundError(f"Universe file not found: {universe_file}")
        
        # Handle different file formats
        if file_path.suffix.lower() == '.csv':
            df = pd.read_csv(file_path)
        elif file_path.suffix.lower() == '.parquet':
            df = pd.read_parquet(file_path)
        else:
            raise ValueError(f"Unsupported universe file format: {file_path.suffix}")
        
        # Extract the symbol column (adjust column name as needed)
        symbol_column = 'symbol'
        if symbol_column not in df.columns:
            # Try to find a column that might contain symbols
            potential_columns = [col for col in df.columns 
                               if any(name in col.lower() 
                                     for name in ['symbol', 'ticker', 'instrument'])]
            
            if not potential_columns:
                raise ValueError(f"Could not find symbol column in {universe_file}")
            
            symbol_column = potential_columns[0]
        
        # Return unique symbols as a list
        return df[symbol_column].unique().tolist()
