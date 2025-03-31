"""Trade metrics calculation module for backtest analysis."""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Union, Tuple
from datetime import datetime, timedelta


class TradeMetricsCalculator:
    """Calculator for trade-based metrics and features."""
    
    def __init__(self):
        """Initialize the trade metrics calculator."""
        self.metrics = {}
    
    def calculate_imbalance_ratio(self, 
                                 buy_volume: Union[float, np.ndarray], 
                                 sell_volume: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
        """Calculate the imbalance ratio (Bx-Sx)/(Bx+Sx).
        
        Args:
            buy_volume: Buy volume
            sell_volume: Sell volume
            
        Returns:
            Imbalance ratio
        """
        total_volume = buy_volume + sell_volume
        
        # Avoid division by zero
        if isinstance(total_volume, np.ndarray):
            # For arrays, replace zeros with NaN
            mask = total_volume != 0
            result = np.zeros_like(total_volume, dtype=float)
            result[mask] = (buy_volume[mask] - sell_volume[mask]) / total_volume[mask]
            return result
        else:
            # For scalar values
            if total_volume == 0:
                return 0.0
            return (buy_volume - sell_volume) / total_volume
    
    def aggregate_minutely_data(self, 
                               trades: pd.DataFrame, 
                               marked_trades: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """Aggregate trade data to minutely bars with metrics.
        
        Args:
            trades: DataFrame with trade data (must have 'symbol', 'trade_time', 
                   'trade_price', 'trade_size', 'trade_side')
            marked_trades: Optional DataFrame with marked trades (subset of trades)
                           If None, all trades are considered unmarked.
            
        Returns:
            DataFrame with minutely aggregated data and metrics
        """
        # Ensure trade_time is datetime
        if not pd.api.types.is_datetime64_any_dtype(trades['trade_time']):
            trades = trades.copy()
            trades['trade_time'] = pd.to_datetime(trades['trade_time'])
        
        # Add minute column for aggregation
        trades['minute'] = trades['trade_time'].dt.floor('1min')
        
        # Split trades by side
        buy_trades = trades[trades['trade_side'] == 'buy']
        sell_trades = trades[trades['trade_side'] == 'sell']
        
        # Prepare marked trades if provided
        if marked_trades is not None:
            if not pd.api.types.is_datetime64_any_dtype(marked_trades['trade_time']):
                marked_trades = marked_trades.copy()
                marked_trades['trade_time'] = pd.to_datetime(marked_trades['trade_time'])
            
            # Add minute column for aggregation
            marked_trades['minute'] = marked_trades['trade_time'].dt.floor('1min')
            
            # Split marked trades by side
            marked_buy_trades = marked_trades[marked_trades['trade_side'] == 'buy']
            marked_sell_trades = marked_trades[marked_trades['trade_side'] == 'sell']
        
        # Group by symbol and minute
        result_dfs = []
        
        for symbol in trades['symbol'].unique():
            # Filter trades for this symbol
            symbol_trades = trades[trades['symbol'] == symbol]
            
            # Prepare aggregation for all trades
            symbol_buy = buy_trades[buy_trades['symbol'] == symbol]
            symbol_sell = sell_trades[sell_trades['symbol'] == symbol]
            
            # Aggregate volumes by minute
            buy_volume_by_min = symbol_buy.groupby('minute')['trade_size'].sum().to_frame('B')
            sell_volume_by_min = symbol_sell.groupby('minute')['trade_size'].sum().to_frame('S')
            
            # Merge buy and sell volumes
            agg_df = pd.merge(
                buy_volume_by_min, 
                sell_volume_by_min, 
                how='outer',
                left_index=True, 
                right_index=True
            ).fillna(0)
            
            # Add price data
            price_data = symbol_trades.groupby('minute').agg({
                'trade_price': ['first', 'last', 'min', 'max', 'mean']
            })
            price_data.columns = ['open', 'close', 'low', 'high', 'vwap']
            
            agg_df = pd.merge(
                agg_df,
                price_data,
                how='outer',
                left_index=True,
                right_index=True
            )
            
            # Calculate total volume
            agg_df['volume'] = agg_df['B'] + agg_df['S']
            
            # If we have marked trades, calculate marked volumes
            if marked_trades is not None:
                # Filter marked trades for this symbol
                symbol_marked_trades = marked_trades[marked_trades['symbol'] == symbol]
                symbol_marked_buy = marked_buy_trades[marked_buy_trades['symbol'] == symbol]
                symbol_marked_sell = marked_sell_trades[marked_sell_trades['symbol'] == symbol]
                
                # Aggregate marked volumes by minute
                marked_buy_volume = symbol_marked_buy.groupby('minute')['trade_size'].sum().to_frame('Bx')
                marked_sell_volume = symbol_marked_sell.groupby('minute')['trade_size'].sum().to_frame('Sx')
                
                # Merge marked volumes
                agg_df = pd.merge(
                    agg_df,
                    marked_buy_volume,
                    how='left',
                    left_index=True,
                    right_index=True
                ).fillna(0)
                
                agg_df = pd.merge(
                    agg_df,
                    marked_sell_volume,
                    how='left',
                    left_index=True,
                    right_index=True
                ).fillna(0)
                
                # Calculate imbalance ratio for marked trades
                agg_df['marked_imbalance'] = self.calculate_imbalance_ratio(
                    agg_df['Bx'], 
                    agg_df['Sx']
                )
            
            # Calculate imbalance ratio for all trades
            agg_df['imbalance'] = self.calculate_imbalance_ratio(
                agg_df['B'], 
                agg_df['S']
            )
            
            # Add symbol column
            agg_df['symbol'] = symbol
            
            # Reset index to make minute a column
            agg_df = agg_df.reset_index()
            
            result_dfs.append(agg_df)
        
        # Combine all symbols
        if result_dfs:
            return pd.concat(result_dfs, ignore_index=True)
        else:
            return pd.DataFrame()
    
    def get_trade_direction_features(self, 
                                    trades: pd.DataFrame, 
                                    window_size: str = '5min') -> pd.DataFrame:
        """Calculate trade direction features.
        
        Args:
            trades: DataFrame with trade data
            window_size: Size of the rolling window
            
        Returns:
            DataFrame with trade direction features
        """
        # Ensure trade_time is datetime
        if not pd.api.types.is_datetime64_any_dtype(trades['trade_time']):
            trades = trades.copy()
            trades['trade_time'] = pd.to_datetime(trades['trade_time'])
        
        # Sort by trade time
        trades = trades.sort_values(['symbol', 'trade_time'])
        
        # Create directional indicators
        trades['is_buy'] = (trades['trade_side'] == 'buy').astype(int)
        trades['is_sell'] = (trades['trade_side'] == 'sell').astype(int)
        
        # Create volume-weighted indicators
        trades['buy_volume'] = trades['trade_size'] * trades['is_buy']
        trades['sell_volume'] = trades['trade_size'] * trades['is_sell']
        
        # Set datetime index for rolling operations
        trades = trades.set_index('trade_time')
        
        # Calculate features per symbol
        result_dfs = []
        
        for symbol in trades.index.get_level_values('symbol').unique():
            symbol_trades = trades[trades['symbol'] == symbol]
            
            # Rolling window statistics
            rolling = symbol_trades.rolling(window=window_size)
            
            features = pd.DataFrame(index=symbol_trades.index)
            features['symbol'] = symbol
            
            # Count of trades
            features['trade_count'] = rolling['trade_price'].count()
            
            # Buy/sell counts and volumes
            features['buy_count'] = rolling['is_buy'].sum()
            features['sell_count'] = rolling['is_sell'].sum()
            features['buy_volume'] = rolling['buy_volume'].sum()
            features['sell_volume'] = rolling['sell_volume'].sum()
            
            # Trade direction metrics
            with np.errstate(divide='ignore', invalid='ignore'):
                features['buy_ratio'] = features['buy_count'] / features['trade_count']
                features['volume_imbalance'] = self.calculate_imbalance_ratio(
                    features['buy_volume'], 
                    features['sell_volume']
                )
            
            # Replace NaNs with 0
            features = features.fillna(0)
            
            # Add to results
            result_dfs.append(features)
        
        # Combine all symbols
        if result_dfs:
            result = pd.concat(result_dfs)
            return result.reset_index()
        else:
            return pd.DataFrame()