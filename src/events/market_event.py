"""
Market Data Events

TickEvent: Real-time price ticks from FIX market data feed
BarEvent: Aggregated OHLC bars (4H/daily timeframes)
"""

from datetime import datetime
from typing import Dict, Any
from .event import Event, EventType


class TickEvent(Event):
    """
    Real-time price tick from FIX market data feed.
    
    Represents a single bid/ask quote update.
    """
    
    def __init__(self, symbol: str, bid: float, ask: float, 
                 timestamp: datetime = None):
        """
        Initialize tick event.
        
        Args:
            symbol: Currency pair (e.g., 'EURUSD')
            bid: Bid price
            ask: Ask price
            timestamp: Tick timestamp (UTC)
        """
        super().__init__(EventType.TICK, timestamp)
        self.symbol = symbol
        self.bid = bid
        self.ask = ask
        self.mid = (bid + ask) / 2.0
        self.spread = ask - bid
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        d = super().to_dict()
        d.update({
            'symbol': self.symbol,
            'bid': self.bid,
            'ask': self.ask,
            'mid': self.mid,
            'spread': self.spread,
        })
        return d
    
    def __repr__(self) -> str:
        return (f"TickEvent(symbol={self.symbol}, bid={self.bid:.5f}, "
                f"ask={self.ask:.5f}, spread={self.spread:.5f})")


class BarEvent(Event):
    """
    Aggregated OHLC bar for strategy consumption.
    
    Created when a time period completes (e.g., 4H bar closes).
    Matches backtest data format for consistency.
    """
    
    def __init__(self, symbol: str, timeframe: str,
                 open_price: float, high: float, low: float, close: float,
                 volume: int, timestamp: datetime):
        """
        Initialize bar event.
        
        Args:
            symbol: Currency pair
            timeframe: '4H', 'D' (daily)
            open_price: Bar open price
            high: Bar high price
            low: Bar low price
            close: Bar close price
            volume: Tick volume (number of ticks)
            timestamp: Bar close timestamp (UTC)
        """
        super().__init__(EventType.BAR, timestamp)
        self.symbol = symbol
        self.timeframe = timeframe
        self.open = open_price
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        d = super().to_dict()
        d.update({
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume,
        })
        return d
    
    def __repr__(self) -> str:
        return (f"BarEvent(symbol={self.symbol}, timeframe={self.timeframe}, "
                f"close={self.close:.5f}, ts={self.timestamp})")
