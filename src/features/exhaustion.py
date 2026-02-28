"""
Exhaustion Bar Detection
Implements the mean reversion exhaustion pattern logic for H1 timeframe
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple


class ExhaustionDetector:
    """
    Detect exhaustion bars and confirmation patterns for mean reversion.
    
    Exhaustion criteria (ALL must be true):
    1. Directional pressure: sum of sign(close-open) over last 2 bars = ±2
    2. Range expansion: current range > 0.8 × median(range[t-10:t-1])
    3. Extreme close: bullish ≥ 0.65 percentile, bearish ≤ 0.35 percentile
    
    Confirmation criteria:
    - LONG: bearish exhaustion + bullish bar + no new high
    - SHORT: bullish exhaustion + bearish bar + no new low
    """
    
    def __init__(
        self,
        pressure_threshold: int = 2,
        range_expansion_factor: float = 0.8,
        range_lookback: int = 10,
        percentile_high: float = 0.65,
        percentile_low: float = 0.35,
        percentile_window: int = 10
    ):
        """
        Initialize the exhaustion detector.
        
        Args:
            pressure_threshold: Required directional pressure (default 2)
            range_expansion_factor: Range must exceed this × median (default 0.8)
            range_lookback: Periods for range median calculation (default 10)
            percentile_high: High percentile threshold for bullish exhaustion (default 0.65)
            percentile_low: Low percentile threshold for bearish exhaustion (default 0.35)
            percentile_window: Window for percentile calculation (default 10)
        """
        self.pressure_threshold = pressure_threshold
        self.range_expansion_factor = range_expansion_factor
        self.range_lookback = range_lookback
        self.percentile_high = percentile_high
        self.percentile_low = percentile_low
        self.percentile_window = percentile_window
    
    def calculate_directional_pressure(self, df: pd.DataFrame) -> pd.Series:
        """
        Calculate directional pressure as sum of sign(close-open) over last 2 bars.
        
        Args:
            df: DataFrame with 'open' and 'close' columns
        
        Returns:
            Series with values in {-2, -1, 0, 1, 2}
        """
        # Bar direction: +1 if bullish, -1 if bearish, 0 if doji
        bar_direction = np.sign(df['close'] - df['open'])
        
        # Sum of last 2 bars (current + previous)
        pressure = bar_direction.rolling(window=2, min_periods=2).sum()
        
        return pressure
    
    def calculate_range_expansion(self, df: pd.DataFrame) -> pd.Series:
        """
        Detect range expansion: current range > threshold × median of last N ranges.
        
        Args:
            df: DataFrame with 'high' and 'low' columns
        
        Returns:
            Boolean Series (True if range expanded)
        """
        # Calculate range for each bar
        bar_range = df['high'] - df['low']
        
        # Rolling median of previous N bars (excluding current bar)
        # Shift by 1 to avoid lookahead bias
        median_range = bar_range.shift(1).rolling(
            window=self.range_lookback,
            min_periods=self.range_lookback
        ).median()
        
        # Check if current range exceeds threshold
        threshold = median_range * self.range_expansion_factor
        range_expanded = bar_range > threshold
        
        return range_expanded
    
    def calculate_close_percentile(self, df: pd.DataFrame) -> pd.Series:
        """
        Calculate the percentile rank of close within recent N-bar window.
        
        Args:
            df: DataFrame with 'close', 'high', 'low' columns
        
        Returns:
            Series with percentile rank [0, 1]
        """
        # Use range of recent bars (high and low) for percentile calculation
        # This is more robust than using just closes
        
        # Get rolling window of highs and lows
        rolling_high = df['high'].shift(1).rolling(
            window=self.percentile_window,
            min_periods=self.percentile_window
        ).max()
        
        rolling_low = df['low'].shift(1).rolling(
            window=self.percentile_window,
            min_periods=self.percentile_window
        ).min()
        
        # Calculate percentile: where does current close sit in the range?
        # percentile = (close - low) / (high - low)
        # 0 = at bottom, 1 = at top, 0.5 = middle
        percentile = (df['close'] - rolling_low) / (rolling_high - rolling_low + 1e-10)
        
        # Clip to [0, 1] in case of outliers
        percentile = percentile.clip(0, 1)
        
        return percentile
    
    def detect_exhaustion_bars(self, df: pd.DataFrame) -> Dict[str, pd.Series]:
        """
        Detect exhaustion bars (both bullish and bearish).
        
        Args:
            df: DataFrame with OHLC columns
        
        Returns:
            Dictionary with:
                'bullish_exhaustion': Boolean series (strong upward pressure)
                'bearish_exhaustion': Boolean series (strong downward pressure)
                'pressure': Directional pressure values
                'range_expanded': Boolean series
                'percentile': Close percentile values
        """
        # Calculate all components
        pressure = self.calculate_directional_pressure(df)
        range_expanded = self.calculate_range_expansion(df)
        percentile = self.calculate_close_percentile(df)
        
        # Bullish exhaustion: strong buying (pressure = +2), range expanded, close near top
        bullish_exhaustion = (
            (pressure == self.pressure_threshold) &
            range_expanded &
            (percentile >= self.percentile_high)
        )
        
        # Bearish exhaustion: strong selling (pressure = -2), range expanded, close near bottom
        bearish_exhaustion = (
            (pressure == -self.pressure_threshold) &
            range_expanded &
            (percentile <= self.percentile_low)
        )
        
        return {
            'bullish_exhaustion': bullish_exhaustion,
            'bearish_exhaustion': bearish_exhaustion,
            'pressure': pressure,
            'range_expanded': range_expanded,
            'percentile': percentile
        }
    
    def detect_confirmation_bars(
        self,
        df: pd.DataFrame,
        exhaustion_signals: Dict[str, pd.Series]
    ) -> Dict[str, pd.Series]:
        """
        Detect confirmation bars that follow exhaustion bars.
        
        Confirmation logic:
        - LONG setup (after bearish exhaustion):
          * Current bar is bullish (close > open)
          * Current high does NOT exceed previous high (no new high)
        
        - SHORT setup (after bullish exhaustion):
          * Current bar is bearish (close < open)
          * Current low does NOT break previous low (no new low)
        
        Args:
            df: DataFrame with OHLC columns
            exhaustion_signals: Output from detect_exhaustion_bars()
        
        Returns:
            Dictionary with:
                'long_setup': Boolean series (enter long)
                'short_setup': Boolean series (enter short)
        """
        # Get exhaustion signals from previous bar
        prev_bullish_exhaustion = exhaustion_signals['bullish_exhaustion'].shift(1)
        prev_bearish_exhaustion = exhaustion_signals['bearish_exhaustion'].shift(1)
        
        # Current bar direction
        current_bullish = df['close'] > df['open']
        current_bearish = df['close'] < df['open']
        
        # No new high/low conditions
        prev_high = df['high'].shift(1)
        prev_low = df['low'].shift(1)
        
        no_new_high = df['high'] <= prev_high
        no_new_low = df['low'] >= prev_low
        
        # LONG confirmation: bearish exhaustion + bullish reversal bar + no new high
        long_setup = (
            prev_bearish_exhaustion &
            current_bullish &
            no_new_high
        )
        
        # SHORT confirmation: bullish exhaustion + bearish reversal bar + no new low
        short_setup = (
            prev_bullish_exhaustion &
            current_bearish &
            no_new_low
        )
        
        return {
            'long_setup': long_setup,
            'short_setup': short_setup
        }
    
    def detect_momentum_confirmation_bars(
        self,
        df: pd.DataFrame,
        exhaustion_signals: Dict[str, pd.Series]
    ) -> Dict[str, pd.Series]:
        """
        Detect momentum confirmation bars (INVERTED LOGIC from mean reversion).
        
        This tests the hypothesis that exhaustion indicates trend strength,
        not reversal.
        
        Confirmation logic (MOMENTUM):
        - LONG setup (after bullish exhaustion):
          * Current bar is bullish (close > open) - momentum continues
          * Current low does NOT break previous low (no reversal down)
        
        - SHORT setup (after bearish exhaustion):
          * Current bar is bearish (close < open) - momentum continues
          * Current high does NOT exceed previous high (no reversal up)
        
        Args:
            df: DataFrame with OHLC columns
            exhaustion_signals: Output from detect_exhaustion_bars()
        
        Returns:
            Dictionary with:
                'long_setup': Boolean series (enter long - momentum up)
                'short_setup': Boolean series (enter short - momentum down)
        """
        # Get exhaustion signals from previous bar
        prev_bullish_exhaustion = exhaustion_signals['bullish_exhaustion'].shift(1)
        prev_bearish_exhaustion = exhaustion_signals['bearish_exhaustion'].shift(1)
        
        # Current bar direction
        current_bullish = df['close'] > df['open']
        current_bearish = df['close'] < df['open']
        
        # No reversal conditions (opposite of mean reversion)
        prev_high = df['high'].shift(1)
        prev_low = df['low'].shift(1)
        
        no_reversal_down = df['low'] >= prev_low   # Not breaking previous low
        no_reversal_up = df['high'] <= prev_high    # Not breaking previous high
        
        # LONG confirmation: bullish exhaustion + bullish continuation + no reversal down
        long_setup = (
            prev_bullish_exhaustion &
            current_bullish &
            no_reversal_down
        )
        
        # SHORT confirmation: bearish exhaustion + bearish continuation + no reversal up
        short_setup = (
            prev_bearish_exhaustion &
            current_bearish &
            no_reversal_up
        )
        
        return {
            'long_setup': long_setup,
            'short_setup': short_setup
        }
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Complete signal generation pipeline.
        
        Args:
            df: DataFrame with OHLC columns
        
        Returns:
            DataFrame with all signals and intermediate values
        """
        df = df.copy()
        
        # Step 1: Detect exhaustion bars
        exhaustion = self.detect_exhaustion_bars(df)
        
        # Add exhaustion components to DataFrame
        for key, value in exhaustion.items():
            df[key] = value
        
        # Step 2: Detect confirmation bars
        confirmation = self.detect_confirmation_bars(df, exhaustion)
        
        # Add confirmation signals
        for key, value in confirmation.items():
            df[key] = value
        
        # Step 3: Generate trading signal
        # +1.0 = LONG, -1.0 = SHORT, 0 = No position
        df['signal'] = 0.0
        df.loc[df['long_setup'], 'signal'] = 1.0
        df.loc[df['short_setup'], 'signal'] = -1.0
        
        return df
    
    def get_signal_summary(self, df: pd.DataFrame) -> Dict:
        """
        Generate summary statistics of detected signals.
        
        Args:
            df: DataFrame with signals (output from generate_signals)
        
        Returns:
            Dictionary with signal statistics
        """
        return {
            'total_bars': len(df),
            'bullish_exhaustion_count': df['bullish_exhaustion'].sum(),
            'bearish_exhaustion_count': df['bearish_exhaustion'].sum(),
            'long_setups': df['long_setup'].sum(),
            'short_setups': df['short_setup'].sum(),
            'total_signals': (df['signal'] != 0).sum(),
            'signal_frequency_pct': (df['signal'] != 0).sum() / len(df) * 100,
            'long_short_ratio': df['long_setup'].sum() / (df['short_setup'].sum() + 1e-10)
        }


if __name__ == "__main__":
    # Test the exhaustion detector
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    
    from src.data.h1_loader import load_processed_data
    
    print("Loading processed data...")
    df = load_processed_data()
    
    # Use recent 3 years for testing
    df_recent = df['2023-01-01':]
    print(f"Testing on {len(df_recent)} bars from {df_recent.index[0]} to {df_recent.index[-1]}")
    
    # Initialize detector
    detector = ExhaustionDetector()
    
    # Generate signals
    print("\nGenerating signals...")
    df_signals = detector.generate_signals(df_recent)
    
    # Get summary
    summary = detector.get_signal_summary(df_signals)
    
    print("\n" + "="*60)
    print("SIGNAL SUMMARY")
    print("="*60)
    for key, value in summary.items():
        if isinstance(value, float):
            print(f"{key:30s}: {value:10.2f}")
        else:
            print(f"{key:30s}: {value:10d}")
    
    print("\n" + "="*60)
    print("SAMPLE SIGNALS")
    print("="*60)
    
    # Show some long setups
    long_signals = df_signals[df_signals['long_setup']]
    if len(long_signals) > 0:
        print(f"\nFirst 5 LONG setups:")
        print(long_signals[['open', 'high', 'low', 'close', 'pressure', 'percentile', 'signal']].head())
    
    # Show some short setups
    short_signals = df_signals[df_signals['short_setup']]
    if len(short_signals) > 0:
        print(f"\nFirst 5 SHORT setups:")
        print(short_signals[['open', 'high', 'low', 'close', 'pressure', 'percentile', 'signal']].head())
