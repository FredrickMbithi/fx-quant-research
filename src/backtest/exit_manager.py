"""
Exit Manager for Complex Exit Logic in Vectorized Backtesting
Handles trailing stops, profit targets, and time-based exits
"""

import numpy as np
import pandas as pd
from typing import Dict, Tuple, Optional
from dataclasses import dataclass


@dataclass
class ExitConfig:
    """Configuration for exit management."""
    hard_stop_pips: float = 10.0  # Hard stop loss
    profit_trigger_pips: float = 4.0  # Profit level to activate trailing stop
    trailing_distance_pips: float = 3.0  # Trailing stop distance
    max_hold_bars: int = 5  # Maximum bars to hold position
    pip_size: float = 0.0001  # For 4-decimal pairs like GBPUSD


class TrailingStopManager:
    """
    Manage complex exit logic for vectorized backtests.
    
    Exit conditions:
    1. Hard stop: Exit if loss exceeds N pips from entry
    2. Profit trigger: Once profit reaches M pips, activate trailing stop
    3. Trailing stop: Trail by K pips from highest favorable price  
    4. Max hold: Exit after L bars regardless of P&L
    
    All conditions checked bar-by-bar in chronological order.
    """
    
    def __init__(self, config: ExitConfig):
        """
        Initialize trailing stop manager.
        
        Args:
            config: ExitConfig with stop/target parameters
        """
        self.config = config
    
    def apply_exits(
        self,
        prices: pd.DataFrame,
        signals: np.ndarray,
        positions: np.ndarray
    ) -> Tuple[np.ndarray, pd.DataFrame]:
        """
        Apply exit logic to modify positions based on stop/target rules.
        
        Args:
            prices: DataFrame with columns: open, high, low, close
            signals: Array of entry signals (+1 long, -1 short, 0 none)
            positions: Initial position array from entry signals
        
        Returns:
            Tuple of:
                - Modified positions array (with exits applied)
                - DataFrame with exit tracking info (for analysis)
        """
        n_bars = len(prices)
        
        # Initialize tracking
        exit_info = {
            'entry_bar': np.full(n_bars, -1, dtype=int),
            'entry_price': np.full(n_bars, np.nan),
            'bars_held': np.zeros(n_bars, dtype=int),
            'exit_reason': np.full(n_bars, '', dtype=object),
            'trailing_stop_price': np.full(n_bars, np.nan),
            'highest_favorable': np.full(n_bars, np.nan),
            'lowest_favorable': np.full(n_bars, np.nan),
        }
        
        # Work on a copy
        positions_modified = positions.copy()
        
        # Process bar-by-bar
        active_position = False
        position_direction = 0  # +1 long, -1 short
        entry_bar = -1
        entry_price = np.nan
        bars_held = 0
        highest_favorable = np.nan
        lowest_favorable = np.nan
        trailing_active = False
        trailing_stop_price = np.nan
        
        for i in range(n_bars):
            # Check if new position entered (based on entry signal, not position)
            if signals[i] != 0 and not active_position:
                # New position entry
                active_position = True
                position_direction = np.sign(signals[i])
                entry_bar = i
                entry_price = prices['close'].iloc[i]
                bars_held = 1
                highest_favorable = prices['high'].iloc[i]
                lowest_favorable = prices['low'].iloc[i]
                trailing_active = False
                trailing_stop_price = np.nan
                
                # Keep the position from entry signal
                # (don't modify positions_modified[i] here)
                
                # Record entry
                exit_info['entry_bar'][i] = entry_bar
                exit_info['entry_price'][i] = entry_price
                exit_info['bars_held'][i] = bars_held
                
                continue
            
            # If position active, check exit conditions
            if active_position:
                bars_held += 1
                
                # Update favorable price tracking
                if position_direction > 0:  # LONG
                    highest_favorable = max(highest_favorable, prices['high'].iloc[i])
                else:  # SHORT
                    lowest_favorable = min(lowest_favorable, prices['low'].iloc[i])
                
                # Current bar prices
                bar_high = prices['high'].iloc[i]
                bar_low = prices['low'].iloc[i]
                bar_close = prices['close'].iloc[i]
                
                # Calculate current P&L in pips
                if position_direction > 0:  # LONG
                    current_pnl_pips = (bar_close - entry_price) / self.config.pip_size
                    worst_pnl_pips = (bar_low - entry_price) / self.config.pip_size
                    best_pnl_pips = (bar_high - entry_price) / self.config.pip_size
                else:  # SHORT
                    current_pnl_pips = (entry_price - bar_close) / self.config.pip_size
                    worst_pnl_pips = (entry_price - bar_high) / self.config.pip_size
                    best_pnl_pips = (entry_price - bar_low) / self.config.pip_size
                
                exit_triggered = False
                exit_reason = ''
                
                # Check exits in priority order
                
                # 1. Hard stop loss (checked first - safety)
                if worst_pnl_pips < -self.config.hard_stop_pips:
                    exit_triggered = True
                    exit_reason = 'hard_stop'
                
                # 2. Trailing stop (if active)
                elif trailing_active and not np.isnan(trailing_stop_price):
                    if position_direction > 0:  # LONG
                        if bar_low <= trailing_stop_price:
                            exit_triggered = True
                            exit_reason = 'trailing_stop'
                    else:  # SHORT
                        if bar_high >= trailing_stop_price:
                            exit_triggered = True
                            exit_reason = 'trailing_stop'
                
                # 3. Max hold time
                elif bars_held >= self.config.max_hold_bars:
                    exit_triggered = True
                    exit_reason = 'max_hold'
                
                # 4. Check if profit target reached (activate trailing)
                if not trailing_active and best_pnl_pips >= self.config.profit_trigger_pips:
                    trailing_active = True
                    # Set initial trailing stop
                    if position_direction > 0:  # LONG
                        trailing_stop_price = highest_favorable - (self.config.trailing_distance_pips * self.config.pip_size)
                    else:  # SHORT
                        trailing_stop_price = lowest_favorable + (self.config.trailing_distance_pips * self.config.pip_size)
                
                # Update trailing stop if active
                if trailing_active:
                    if position_direction > 0:  # LONG
                        new_trailing_stop = highest_favorable - (self.config.trailing_distance_pips * self.config.pip_size)
                        trailing_stop_price = max(trailing_stop_price, new_trailing_stop)
                    else:  # SHORT
                        new_trailing_stop = lowest_favorable + (self.config.trailing_distance_pips * self.config.pip_size)
                        trailing_stop_price = min(trailing_stop_price, new_trailing_stop)
                
                # Record tracking info
                exit_info['entry_bar'][i] = entry_bar
                exit_info['entry_price'][i] = entry_price
                exit_info['bars_held'][i] = bars_held
                exit_info['trailing_stop_price'][i] = trailing_stop_price
                exit_info['highest_favorable'][i] = highest_favorable
                exit_info['lowest_favorable'][i] = lowest_favorable
                
                # Execute exit if triggered
                if exit_triggered:
                    positions_modified[i] = 0
                    exit_info['exit_reason'][i] = exit_reason
                    
                    # Reset state
                    active_position = False
                    position_direction = 0
                    entry_bar = -1
                    entry_price = np.nan
                    bars_held = 0
                    highest_favorable = np.nan
                    lowest_favorable = np.nan
                    trailing_active = False
                    trailing_stop_price = np.nan
                    
                    # Zero out all future positions until next entry signal
                    # (position should stay flat after exit until new signal)
                    for j in range(i + 1, n_bars):
                        if signals[j] != 0:  # New entry signal
                            break
                        positions_modified[j] = 0
        
        # Convert exit_info to DataFrame
        exit_df = pd.DataFrame(exit_info, index=prices.index)
        
        return positions_modified, exit_df
    
    def get_exit_statistics(self, exit_df: pd.DataFrame) -> Dict:
        """
        Calculate exit statistics for analysis.
        
        Args:
            exit_df: DataFrame returned from apply_exits()
        
        Returns:
            Dictionary with exit statistics
        """
        exits = exit_df[exit_df['exit_reason'] != '']
        
        if len(exits) == 0:
            return {
                'total_exits': 0,
                'hard_stop_exits': 0,
                'trailing_stop_exits': 0,
                'max_hold_exits': 0,
            }
        
        exit_counts = exits['exit_reason'].value_counts()
        
        return {
            'total_exits': len(exits),
            'hard_stop_exits': exit_counts.get('hard_stop', 0),
            'trailing_stop_exits': exit_counts.get('trailing_stop', 0),
            'max_hold_exits': exit_counts.get('max_hold', 0),
            'hard_stop_pct': exit_counts.get('hard_stop', 0) / len(exits) * 100,
            'trailing_stop_pct': exit_counts.get('trailing_stop', 0) / len(exits) * 100,
            'max_hold_pct': exit_counts.get('max_hold', 0) / len(exits) * 100,
            'avg_bars_held': exit_df[exit_df['bars_held'] > 0]['bars_held'].mean(),
        }


if __name__ == "__main__":
    # Test the trailing stop manager
    print("="*60)
    print("TESTING TRAILING STOP MANAGER")
    print("="*60)
    
    # Create synthetic data
    n_bars = 20
    dates = pd.date_range('2024-01-01', periods=n_bars, freq='H')
    
    # Simulate a winning long trade
    prices_data = {
        'open': [1.2600 + i * 0.0010 for i in range(n_bars)],
        'high': [1.2610 + i * 0.0010 for i in range(n_bars)],
        'low': [1.2590 + i * 0.0010 for i in range(n_bars)],
        'close': [1.2600 + i * 0.0010 for i in range(n_bars)],
    }
    
    prices = pd.DataFrame(prices_data, index=dates)
    
    # Entry signal at bar 0, hold position
    signals = np.zeros(n_bars)
    signals[0] = 1.0  # LONG entry
    
    positions = np.zeros(n_bars)
    positions[0:] = 1.0  # Initial position: hold long
    
    # Configure exit manager
    config = ExitConfig(
        hard_stop_pips=10.0,
        profit_trigger_pips=4.0,
        trailing_distance_pips=3.0,
        max_hold_bars=5,
        pip_size=0.0001
    )
    
    manager = TrailingStopManager(config)
    
    # Apply exits
    positions_modified, exit_df = manager.apply_exits(prices, signals, positions)
    
    # Display results
    print("\nOriginal positions:", positions[:10])
    print("Modified positions:", positions_modified[:10])
    
    print("\nExit Info:")
    print(exit_df[exit_df['exit_reason'] != ''][['entry_bar', 'bars_held', 'exit_reason', 'trailing_stop_price']].head(10))
    
    # Statistics
    stats = manager.get_exit_statistics(exit_df)
    print("\nExit Statistics:")
    for key, value in stats.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.2f}")
        else:
            print(f"  {key}: {value}")
