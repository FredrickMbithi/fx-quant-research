"""
Exhaustion Momentum Strategy

INVERTED HYPOTHESIS: Trade WITH exhaustion bars (momentum continuation)
- LONG on bullish exhaustion (strong upward pressure = trend strength)
- SHORT on bearish exhaustion (strong downward pressure = trend strength)

This is the inverse of mean reversion - testing if exhaustion indicates
trend continuation rather than reversal.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
from src.strategies.base_strategy import BaseStrategy
from src.events.signal_event import SignalEvent
from src.events.event import EventType
from src.features.exhaustion import ExhaustionDetector


class ExhaustionMomentumStrategy(BaseStrategy):
    """
    Momentum strategy based on exhaustion bars.
    
    Entry Logic (INVERTED from mean reversion):
    - LONG: Bullish exhaustion detected → trade WITH momentum
    - SHORT: Bearish exhaustion detected → trade WITH momentum
    
    Exit Logic: 
    - Handled by TrailingStopManager (hard stop, trailing, max hold)
    """
    
    def __init__(
        self,
        instrument: str,
        detector_params: dict = None,
        use_confirmation: bool = True
    ):
        """
        Args:
            instrument: Currency pair symbol (e.g., 'GBPUSD')
            detector_params: Parameters for ExhaustionDetector
            use_confirmation: Whether to require confirmation bar
        """
        # Initialize base with proper signature
        super().__init__(
            name="ExhaustionMomentum",
            symbols=[instrument],
            config={}
        )
        
        self.instrument = instrument
        
        # Initialize exhaustion detector
        if detector_params is None:
            detector_params = {}
        self.detector = ExhaustionDetector(**detector_params)
        self.use_confirmation = use_confirmation
        
        # State tracking for confirmation bars
        self.bullish_exhaustion_bar = None  # Store bar index of bullish exhaustion
        self.bearish_exhaustion_bar = None  # Store bar index of bearish exhaustion
        
        # Historical data buffer
        self.price_history = []
    
    def calculate_signal(self, symbol: str) -> float:
        """
        Calculate signal for a symbol (required by BaseStrategy).
        
        This is a stub - actual signal generation happens in
        calculate_signals() for event-driven mode or
        generate_signals_vectorized() for backtesting.
        
        Returns:
            0.0 (no signal) - signals generated via event queue
        """
        return 0.0
        
    def _detect_exhaustion(self, bar_data: dict) -> tuple:
        """
        Detect exhaustion using current bar data.
        
        Returns:
            (is_bullish_exhaustion, is_bearish_exhaustion)
        """
        # Build DataFrame from history
        if len(self.price_history) < 20:
            return False, False
        
        df = pd.DataFrame(self.price_history)
        
        # Calculate exhaustion signals
        signals = self.detector.detect_exhaustion_bars(df)
        
        # Get current bar signal
        bullish = signals['bullish_exhaustion'].iloc[-1]
        bearish = signals['bearish_exhaustion'].iloc[-1]
        
        return bullish, bearish
    
    def _detect_confirmation(self, bar_data: dict, bar_idx: int) -> tuple:
        """
        Check for confirmation bars following exhaustion.
        
        INVERTED LOGIC:
        - After bullish exhaustion: Look for continued bullish bar (close > open)
        - After bearish exhaustion: Look for continued bearish bar (close < open)
        
        Returns:
            (is_long_setup, is_short_setup)
        """
        long_setup = False
        short_setup = False
        
        current_bar = bar_data
        
        # Check LONG setup: bullish exhaustion + bullish confirmation
        if self.bullish_exhaustion_bar == bar_idx - 1:
            # Confirmation: another bullish bar (momentum continuation)
            if current_bar['close'] > current_bar['open']:
                # No new low (not reversing down)
                if len(self.price_history) >= 2:
                    prev_low = self.price_history[-2]['low']
                    if current_bar['low'] >= prev_low:
                        long_setup = True
            # Reset after checking
            self.bullish_exhaustion_bar = None
        
        # Check SHORT setup: bearish exhaustion + bearish confirmation
        if self.bearish_exhaustion_bar == bar_idx - 1:
            # Confirmation: another bearish bar (momentum continuation)
            if current_bar['close'] < current_bar['open']:
                # No new high (not reversing up)
                if len(self.price_history) >= 2:
                    prev_high = self.price_history[-2]['high']
                    if current_bar['high'] <= prev_high:
                        short_setup = True
            # Reset after checking
            self.bearish_exhaustion_bar = None
        
        return long_setup, short_setup
    
    def calculate_signals(self, event):
        """
        Generate trading signals based on exhaustion momentum.
        
        EVENT-DRIVEN MODE (for live/paper trading)
        """
        if event.event_type != EventType.BAR:
            return
        
        # Build bar data dict
        bar_data = {
            'timestamp': event.timestamp,
            'open': event.open,
            'high': event.high,
            'low': event.low,
            'close': event.close,
            'volume': event.volume
        }
        
        # Add to history
        self.price_history.append(bar_data)
        bar_idx = len(self.price_history) - 1
        
        # Detect exhaustion on current bar
        is_bullish_exhaustion, is_bearish_exhaustion = self._detect_exhaustion(bar_data)
        
        # Store exhaustion bar indices for next bar confirmation
        if is_bullish_exhaustion:
            self.bullish_exhaustion_bar = bar_idx
        if is_bearish_exhaustion:
            self.bearish_exhaustion_bar = bar_idx
        
        # Check for confirmation setups
        if self.use_confirmation:
            long_setup, short_setup = self._detect_confirmation(bar_data, bar_idx)
        else:
            # Direct entry on exhaustion (no confirmation required)
            long_setup = is_bullish_exhaustion
            short_setup = is_bearish_exhaustion
        
        # Generate signals
        if long_setup:
            signal = SignalEvent(
                strategy_name=self.name,
                instrument=self.instrument,
                timestamp=event.timestamp,
                signal_type='LONG',
                strength=1.0
            )
            self.events.put(signal)
            
        elif short_setup:
            signal = SignalEvent(
                strategy_name=self.name,
                instrument=self.instrument,
                timestamp=event.timestamp,
                signal_type='SHORT',
                strength=-1.0
            )
            self.events.put(signal)
    
    def generate_signals_vectorized(self, data: pd.DataFrame) -> pd.Series:
        """
        Generate signals for vectorized backtesting.
        
        INVERTED LOGIC (MOMENTUM):
        - Signal = +1.0 where bullish exhaustion + bullish continuation
        - Signal = -1.0 where bearish exhaustion + bearish continuation
        
        Args:
            data: DataFrame with OHLCV columns
            
        Returns:
            Series with signals (+1.0 LONG, -1.0 SHORT, 0.0 neutral)
        """
        # Detect exhaustion bars
        exhaustion_signals = self.detector.detect_exhaustion_bars(data)
        
        if self.use_confirmation:
            # Use MOMENTUM confirmation (trade WITH exhaustion)
            # Note: correct parameter order is (df, exhaustion_signals)
            confirmed_signals = self.detector.detect_momentum_confirmation_bars(data, exhaustion_signals)
            
            # MOMENTUM: LONG on bullish exhaustion, SHORT on bearish exhaustion
            signals = pd.Series(0.0, index=data.index)
            signals[confirmed_signals['long_setup']] = 1.0   # LONG (momentum up)
            signals[confirmed_signals['short_setup']] = -1.0  # SHORT (momentum down)
        else:
            # Direct signals without confirmation
            signals = pd.Series(0.0, index=data.index)
            signals[exhaustion_signals['bullish_exhaustion']] = 1.0
            signals[exhaustion_signals['bearish_exhaustion']] = -1.0
        
        return signals
