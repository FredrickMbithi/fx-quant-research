"""
Example Strategy Implementations

Concrete strategies ready for live trading (paper trading first!).
"""

import numpy as np
from typing import Optional, Dict, Any
import logging

from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)


class ThresholdStrategy(BaseStrategy):
    """
    Threshold-based strategy (matches backtest examples).
    
    Logic:
    - Goes long when signal > threshold_long
    - Goes short when signal < threshold_short
    - Closes position when signal between thresholds (neutral zone)
    
    Signal generation (simple moving average crossover):
    - Signal = (SMA_short - SMA_long) / SMA_long (normalized)
    """
    
    def __init__(self, symbols: list, config: Dict[str, Any]):
        """
        Initialize threshold strategy.
        
        Config:
            - sma_short: Short SMA period (default: 20)
            - sma_long: Long SMA period (default: 50)
            - threshold_long: Enter long threshold (default: 0.5)
            - threshold_short: Enter short threshold (default: -0.5)
            - position_long: Long position size (default: 1.0)
            - position_short: Short position size (default: -1.0)
        """
        super().__init__('ThresholdStrategy', symbols, config)
        
        # Strategy parameters
        self.sma_short_period = config.get('sma_short', 20)
        self.sma_long_period = config.get('sma_long', 50)
        self.threshold_long = config.get('threshold_long', 0.5)
        self.threshold_short = config.get('threshold_short', -0.5)
        self.position_long = config.get('position_long', 1.0)
        self.position_short = config.get('position_short', -1.0)
        
        logger.info(f"ThresholdStrategy initialized: SMA({self.sma_short_period}, "
                   f"{self.sma_long_period}), thresholds=({self.threshold_short}, "
                   f"{self.threshold_long})")
    
    def calculate_signal(self, symbol: str) -> Optional[float]:
        """
        Calculate threshold-based signal.
        
        Returns:
            Signal strength or None if not enough data
        """
        closes = self.get_close_prices(symbol)
        
        # Need enough bars for long SMA
        if len(closes) < self.sma_long_period:
            logger.debug(f"Not enough bars for {symbol}: {len(closes)} < {self.sma_long_period}")
            return None
        
        # Calculate SMAs
        sma_short = np.mean(closes[-self.sma_short_period:])
        sma_long = np.mean(closes[-self.sma_long_period:])
        
        # Normalized difference (raw signal)
        raw_signal = (sma_short - sma_long) / sma_long if sma_long != 0 else 0.0
        
        # Apply thresholds
        if raw_signal > self.threshold_long:
            signal_strength = self.position_long
        elif raw_signal < self.threshold_short:
            signal_strength = self.position_short
        else:
            # Neutral zone - signal to close position if we have one
            signal_strength = 0.0 if self.positions[symbol] != 0 else None
        
        logger.debug(f"{symbol}: SMA_short={sma_short:.5f}, SMA_long={sma_long:.5f}, "
                    f"raw_signal={raw_signal:.3f}, signal_strength={signal_strength}")
        
        return signal_strength
    
    def _get_signal_metadata(self, symbol: str) -> Dict[str, Any]:
        """Include SMA values in metadata."""
        metadata = super()._get_signal_metadata(symbol)
        
        closes = self.get_close_prices(symbol)
        if len(closes) >= self.sma_long_period:
            metadata['sma_short'] = float(np.mean(closes[-self.sma_short_period:]))
            metadata['sma_long'] = float(np.mean(closes[-self.sma_long_period:]))
            metadata['raw_signal'] = (metadata['sma_short'] - metadata['sma_long']) / metadata['sma_long']
        
        return metadata


class MomentumStrategy(BaseStrategy):
    """
    Momentum-based strategy.
    
    Logic:
    - Calculate price momentum over window
    - Go long/short based on momentum strength
    """
    
    def __init__(self, symbols: list, config: Dict[str, Any]):
        """
        Initialize momentum strategy.
        
        Config:
            - lookback: Momentum lookback period (default: 20)
            - threshold: Minimum momentum for signal (default: 0.02 = 2%)
        """
        super().__init__('MomentumStrategy', symbols, config)
        
        self.lookback = config.get('lookback', 20)
        self.threshold = config.get('threshold', 0.02)
        
        logger.info(f"MomentumStrategy initialized: lookback={self.lookback}, "
                   f"threshold={self.threshold:.1%}")
    
    def calculate_signal(self, symbol: str) -> Optional[float]:
        """Calculate momentum-based signal."""
        closes = self.get_close_prices(symbol)
        
        if len(closes) < self.lookback + 1:
            return None
        
        # Calculate momentum (percentage change over lookback period)
        current_price = closes[-1]
        past_price = closes[-(self.lookback + 1)]
        momentum = (current_price - past_price) / past_price if past_price != 0 else 0.0
        
        # Generate signal based on momentum threshold
        if momentum > self.threshold:
            signal_strength = min(momentum / self.threshold, 1.0)  # Cap at 1.0
        elif momentum < -self.threshold:
            signal_strength = max(momentum / self.threshold, -1.0)  # Cap at -1.0
        else:
            signal_strength = None  # No signal in neutral zone
        
        logger.debug(f"{symbol}: momentum={momentum:.2%}, signal={signal_strength}")
        
        return signal_strength
    
    def _get_signal_metadata(self, symbol: str) -> Dict[str, Any]:
        """Include momentum in metadata."""
        metadata = super()._get_signal_metadata(symbol)
        
        closes = self.get_close_prices(symbol)
        if len(closes) >= self.lookback + 1:
            current_price = closes[-1]
            past_price = closes[-(self.lookback + 1)]
            metadata['momentum'] = (current_price - past_price) / past_price if past_price != 0 else 0.0
        
        return metadata
