"""
Exhaustion Mean Reversion Strategy
Event-driven implementation for live/paper trading
"""

import sys
from pathlib import Path
# Add project root to path for imports
if __name__ == "__main__" or not __package__:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import numpy as np
import pandas as pd
from typing import Optional, Dict, Any
import logging

from src.strategies.base_strategy import BaseStrategy

logger = logging.getLogger(__name__)


class ExhaustionStrategy(BaseStrategy):
    """
    H1 GBP/USD Exhaustion Mean Reversion Strategy.
    
    Detects exhaustion bars (strong directional pressure + range expansion + extreme close)
    followed by confirmation bars (reversal without new high/low).
    
    Entry: Close of confirmation bar
    Exit: Managed by TrailingStopManager (10 pip hard stop, 4 pip profit trigger, 3 pip trail, 5 bar max hold)
    """
    
    def __init__(
        self,
        name: str = "ExhaustionH1",
        symbols: list = ['GBPUSD'],
        config: Dict[str, Any] = None
    ):
        """
        Initialize exhaustion strategy.
        
        Args:
            name: Strategy name
            symbols: List of symbols to trade (default: ['GBPUSD'])
            config: Strategy configuration parameters
        """
        # Default configuration
        default_config = {
            'max_bars': 50,  # Need at least 10-20 bars for indicators
            'pressure_threshold': 2,
            'range_expansion_factor': 0.8,
            'range_lookback': 10,
            'percentile_high': 0.65,
            'percentile_low': 0.35,
            'percentile_window': 10,
        }
        
        # Merge with user config
        if config:
            default_config.update(config)
        
        super().__init__(name, symbols, default_config)
        
        # Track previous bar exhaustion state (for confirmation detection)
        self.prev_exhaustion = {symbol: {'bullish': False, 'bearish': False} for symbol in symbols}
    
    def calculate_signal(self, symbol: str) -> Optional[float]:
        """
        Calculate trading signal based on exhaustion pattern.
        
        Returns:
            +1.0 for LONG setup
            -1.0 for SHORT setup
            None for no signal
        """
        # Need minimum bars for indicators
        min_bars = max(self.config['range_lookback'], self.config['percentile_window']) + 5
        if len(self.bar_history[symbol]['close']) < min_bars:
            return None
        
        # Convert bar history to DataFrame for easier processing
        history = self.bar_history[symbol]
        df = pd.DataFrame({
            'timestamp': history['timestamp'],
            'open': history['open'],
            'high': history['high'],
            'low': history['low'],
            'close': history['close'],
            'volume': history['volume']
        })
        
        # Current bar index (most recent)
        current_idx = len(df) - 1
        
        # Step 1: Check if current bar is an exhaustion bar
        current_exhaustion = self._detect_exhaustion(df, current_idx)
        
        # Step 2: Check if current bar confirms previous exhaustion
        signal = self._detect_confirmation(
            df,
            current_idx,
            self.prev_exhaustion[symbol]
        )
        
        # Update previous exhaustion state for next bar
        self.prev_exhaustion[symbol] = current_exhaustion
        
        return signal
    
    def _detect_exhaustion(self, df: pd.DataFrame, idx: int) -> Dict[str, bool]:
        """
        Detect if current bar is an exhaustion bar.
        
        Args:
            df: Historical DataFrame
            idx: Index of current bar
        
        Returns:
            Dict with 'bullish' and 'bearish' exhaustion flags
        """
        # Need at least 2 bars for pressure calculation
        if idx < 2:
            return {'bullish': False, 'bearish': False}
        
        # 1. Calculate directional pressure (sum of last 2 bar directions)
        bar_direction_current = np.sign(df['close'].iloc[idx] - df['open'].iloc[idx])
        bar_direction_prev = np.sign(df['close'].iloc[idx-1] - df['open'].iloc[idx-1])
        pressure = bar_direction_current + bar_direction_prev
        
        # 2. Check range expansion
        current_range = df['high'].iloc[idx] - df['low'].iloc[idx]
        
        # Calculate median range of previous N bars (excluding current)
        lookback = self.config['range_lookback']
        if idx < lookback + 1:
            return {'bullish': False, 'bearish': False}
        
        prev_ranges = []
        for i in range(idx - lookback, idx):
            prev_ranges.append(df['high'].iloc[i] - df['low'].iloc[i])
        
        median_range = np.median(prev_ranges)
        threshold = median_range * self.config['range_expansion_factor']
        range_expanded = current_range > threshold
        
        # 3. Calculate close percentile
        percentile_window = self.config['percentile_window']
        if idx < percentile_window + 1:
            return {'bullish': False, 'bearish': False}
        
        # Get recent highs and lows (excluding current bar)
        recent_high = df['high'].iloc[idx - percentile_window:idx].max()
        recent_low = df['low'].iloc[idx - percentile_window:idx].min()
        
        # Where does current close sit in the range?
        current_close = df['close'].iloc[idx]
        if recent_high > recent_low:
            percentile = (current_close - recent_low) / (recent_high - recent_low)
        else:
            percentile = 0.5  # Neutral if no range
        
        # Bullish exhaustion: pressure +2, range expanded, close at top
        bullish_exhaustion = (
            pressure == self.config['pressure_threshold'] and
            range_expanded and
            percentile >= self.config['percentile_high']
        )
        
        # Bearish exhaustion: pressure -2, range expanded, close at bottom
        bearish_exhaustion = (
            pressure == -self.config['pressure_threshold'] and
            range_expanded and
            percentile <= self.config['percentile_low']
        )
        
        return {
            'bullish': bullish_exhaustion,
            'bearish': bearish_exhaustion
        }
    
    def _detect_confirmation(
        self,
        df: pd.DataFrame,
        idx: int,
        prev_exhaustion: Dict[str, bool]
    ) -> Optional[float]:
        """
        Detect if current bar confirms previous exhaustion (reversal setup).
        
        Args:
            df: Historical DataFrame
            idx: Index of current bar
            prev_exhaustion: Exhaustion state from previous bar
        
        Returns:
            +1.0 for LONG, -1.0 for SHORT, None for no signal
        """
        if idx < 1:
            return None
        
        # Current bar direction
        current_close = df['close'].iloc[idx]
        current_open = df['open'].iloc[idx]
        current_bullish = current_close > current_open
        current_bearish = current_close < current_open
        
        # Previous bar high/low
        prev_high = df['high'].iloc[idx - 1]
        prev_low = df['low'].iloc[idx - 1]
        
        # Current bar high/low
        current_high = df['high'].iloc[idx]
        current_low = df['low'].iloc[idx]
        
        # No new high/low conditions
        no_new_high = current_high <= prev_high
        no_new_low = current_low >= prev_low
        
        # LONG setup: previous bearish exhaustion + current bullish bar + no new high
        if prev_exhaustion['bearish'] and current_bullish and no_new_high:
            logger.info(f"LONG setup confirmed at {df['timestamp'].iloc[idx]}")
            return 1.0
        
        # SHORT setup: previous bullish exhaustion + current bearish bar + no new low
        if prev_exhaustion['bullish'] and current_bearish and no_new_low:
            logger.info(f"SHORT setup confirmed at {df['timestamp'].iloc[idx]}")
            return -1.0
        
        return None
    
    def _get_signal_metadata(self, symbol: str) -> Dict[str, Any]:
        """
        Get metadata for signal logging.
        
        Returns:
            dict with exhaustion state and indicator values
        """
        metadata = super()._get_signal_metadata(symbol)
        
        # Add exhaustion state
        metadata.update({
            'prev_bullish_exhaustion': self.prev_exhaustion[symbol]['bullish'],
            'prev_bearish_exhaustion': self.prev_exhaustion[symbol]['bearish'],
        })
        
        return metadata


if __name__ == "__main__":
    # Test the strategy with simulated bars
    from src.events.market_event import BarEvent
    from datetime import datetime
    
    print("="*60)
    print("TESTING EXHAUSTION STRATEGY (Event-Driven Mode)")
    print("="*60)
    
    # Initialize strategy
    strategy = ExhaustionStrategy(symbols=['GBPUSD'])
    
    # Create sample bars (simulate exhaustion pattern)
    # Bar 1: Strong down move
    bar1 = BarEvent(
        symbol='GBPUSD',
        timeframe='H1',
        timestamp=datetime(2024, 1, 1, 10, 0),
        open_price=1.2700,
        high=1.2705,
        low=1.2680,
        close=1.2682,
        volume=5000
    )
    
    # Bar 2: Another strong down move (exhaustion building)
    bar2 = BarEvent(
        symbol='GBPUSD',
        timeframe='H1',
        timestamp=datetime(2024, 1, 1, 11, 0),
        open_price=1.2682,
        high=1.2685,
        low=1.2655,
        close=1.2660,
        volume=6000
    )
    
    # Process bars
    print("\nProcessing bars...")
    for i, bar in enumerate([bar1, bar2], 1):
        signal = strategy.on_bar(bar)
        if signal:
            print(f"Bar {i}: SIGNAL GENERATED - {signal.signal_strength}")
        else:
            print(f"Bar {i}: No signal")
    
    print("\nStrategy test complete.")
    print(f"Bar history length: {len(strategy.bar_history['GBPUSD']['close'])}")
