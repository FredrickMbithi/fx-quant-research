"""
Base Strategy Class for Live Trading

Abstract base class for implementing trading strategies in event-driven mode.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging
from datetime import datetime

from ..events import BarEvent, SignalEvent

logger = logging.getLogger(__name__)


class BaseStrategy(ABC):
    """
    Abstract base class for trading strategies.
    
    Strategies process BarEvents and emit SignalEvents when conditions are met.
    Unlike backtesting (vectorized), strategies process one bar at a time.
    """
    
    def __init__(self, name: str, symbols: list, config: Dict[str, Any] = None):
        """
        Initialize strategy.
        
        Args:
            name: Strategy name (for logging/identification)
            symbols: List of symbols this strategy trades
            config: Optional strategy-specific configuration
        """
        self.name = name
        self.symbols = symbols
        self.config = config or {}
        
        # Historical data for indicator calculation
        # {symbol: {'timestamp': [...], 'close': [...], 'high': [...], 'low': [...]}}
        self.bar_history = {symbol: {
            'timestamp': [],
            'open': [],
            'high': [],
            'low': [],
            'close': [],
            'volume': []
        } for symbol in symbols}
        
        # Maximum bars to keep in memory (for indicator calculation)
        self.max_bars = config.get('max_bars', 500)
        
        # Current positions (tracked externally but strategy can access)
        self.positions = {symbol: 0.0 for symbol in symbols}
        
        logger.info(f"Strategy initialized: {self.name} for {symbols}")
    
    @abstractmethod
    def calculate_signal(self, symbol: str) -> Optional[float]:
        """
        Calculate trading signal for a symbol.
        
        Called after each bar update. Implement strategy logic here.
        
        Args:
            symbol: Currency pair
        
        Returns:
            Signal strength (-1.0 to 1.0) or None if no signal
            - None: No signal (don't trade)
            - -1.0: Strong short signal
            - 0.0: Neutral (close position)
            - +1.0: Strong long signal
        """
        pass
    
    def on_bar(self, bar: BarEvent) -> Optional[SignalEvent]:
        """
        Process incoming bar and generate signal if needed.
        
        This is the main entry point called by the trading engine.
        
        Args:
            bar: BarEvent with OHLC data
        
        Returns:
            SignalEvent if signal generated, else None
        """
        # Update bar history
        self._update_history(bar)
        
        # Calculate signal
        signal_strength = self.calculate_signal(bar.symbol)
        
        # Generate signal event if signal exists
        if signal_strength is not None:
            signal = SignalEvent(
                symbol=bar.symbol,
                signal_strength=signal_strength,
                strategy_name=self.name,
                timestamp=bar.timestamp,
                metadata=self._get_signal_metadata(bar.symbol)
            )
            logger.info(f"{self.name} generated signal: {signal}")
            return signal
        
        return None
    
    def _update_history(self, bar: BarEvent):
        """
        Update historical bar data.
        
        Maintains a sliding window of bars for indicator calculation.
        
        Args:
            bar: New bar to append
        """
        if bar.symbol not in self.bar_history:
            logger.warning(f"Received bar for untracked symbol: {bar.symbol}")
            return
        
        history = self.bar_history[bar.symbol]
        
        # Append new bar
        history['timestamp'].append(bar.timestamp)
        history['open'].append(bar.open)
        history['high'].append(bar.high)
        history['low'].append(bar.low)
        history['close'].append(bar.close)
        history['volume'].append(bar.volume)
        
        # Trim to max_bars
        if len(history['close']) > self.max_bars:
            for key in history:
                history[key] = history[key][-self.max_bars:]
        
        logger.debug(f"Updated history for {bar.symbol}: {len(history['close'])} bars")
    
    def _get_signal_metadata(self, symbol: str) -> Dict[str, Any]:
        """
        Get metadata to attach to signal (for logging/analysis).
        
        Override this to include indicator values, confidence scores, etc.
        
        Args:
            symbol: Currency pair
        
        Returns:
            Dict with metadata
        """
        return {
            'bars_available': len(self.bar_history[symbol]['close']),
        }
    
    def get_last_close(self, symbol: str) -> Optional[float]:
        """Get most recent close price for a symbol."""
        closes = self.bar_history[symbol]['close']
        return closes[-1] if closes else None
    
    def get_close_prices(self, symbol: str, n: int = None) -> list:
        """
        Get recent close prices.
        
        Args:
            symbol: Currency pair
            n: Number of prices to return (None = all available)
        
        Returns:
            List of close prices (most recent last)
        """
        closes = self.bar_history[symbol]['close']
        if n is None:
            return closes
        return closes[-n:] if len(closes) >= n else closes
    
    def update_position(self, symbol: str, position: float):
        """
        Update current position (called externally by portfolio).
        
        Args:
            symbol: Currency pair
            position: Current position size
        """
        self.positions[symbol] = position
        logger.debug(f"Strategy {self.name} position updated: {symbol} = {position}")
