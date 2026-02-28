"""
Market Data Aggregator - Convert ticks to bars

Handles:
- Tick buffering
- Bar aggregation (M1, M5, M15, H1)
- Real-time bar completion detection
"""

from datetime import datetime, UTC, timedelta
from typing import Optional, Dict, List, Callable
from collections import deque
import logging

logger = logging.getLogger(__name__)


class TickAggregator:
    """Aggregate ticks into OHLC bars."""
    
    def __init__(self, timeframe_minutes: int = 5, on_bar_complete: Optional[Callable] = None):
        """
        Initialize tick aggregator.
        
        Args:
            timeframe_minutes: Bar timeframe in minutes (1, 5, 15, 60)
            on_bar_complete: Callback function when bar completes
        """
        self.timeframe_minutes = timeframe_minutes
        self.on_bar_complete = on_bar_complete
        
        # Current bar being built
        self.current_bar: Optional[Dict] = None
        self.current_bar_start: Optional[datetime] = None
        
        # Tick buffer
        self.tick_buffer = deque(maxlen=1000)
        
        # Latest price
        self.latest_bid: Optional[float] = None
        self.latest_ask: Optional[float] = None
        self.latest_mid: Optional[float] = None
        self.latest_timestamp: Optional[datetime] = None
        
        # Statistics
        self.ticks_processed = 0
        self.bars_completed = 0
        
        logger.info(f"Tick aggregator initialized: {timeframe_minutes}-minute bars")
    
    def on_tick(self, bid: float, ask: float, timestamp: Optional[datetime] = None) -> Optional[Dict]:
        """
        Process incoming tick.
        
        Args:
            bid: Bid price
            ask: Ask price
            timestamp: Tick timestamp (UTC)
        
        Returns:
            Completed bar if bar closed, None otherwise
        """
        if timestamp is None:
            timestamp = datetime.now(UTC)
        
        # Update latest prices
        self.latest_bid = bid
        self.latest_ask = ask
        self.latest_mid = (bid + ask) / 2.0
        self.latest_timestamp = timestamp
        self.ticks_processed += 1
        
        # Store tick
        self.tick_buffer.append({
            'timestamp': timestamp,
            'bid': bid,
            'ask': ask,
            'mid': self.latest_mid
        })
        
        # Determine bar boundaries
        bar_start = self._get_bar_start(timestamp)
        bar_end = bar_start + timedelta(minutes=self.timeframe_minutes)
        
        # Check if we need to start a new bar
        if self.current_bar_start is None or bar_start > self.current_bar_start:
            # Complete previous bar if exists
            completed_bar = None
            if self.current_bar is not None:
                completed_bar = self._complete_bar()
            
            # Start new bar
            self._start_new_bar(bar_start, self.latest_mid)
            
            if completed_bar:
                return completed_bar
        
        # Update current bar
        self._update_bar(self.latest_mid)
        
        return None
    
    def _get_bar_start(self, timestamp: datetime) -> datetime:
        """
        Get bar start time for given timestamp.
        
        Args:
            timestamp: Current timestamp
        
        Returns:
            Bar start timestamp (rounded down to timeframe)
        """
        # Round down to nearest timeframe interval
        minutes = timestamp.minute
        rounded_minute = (minutes // self.timeframe_minutes) * self.timeframe_minutes
        
        return timestamp.replace(minute=rounded_minute, second=0, microsecond=0)
    
    def _start_new_bar(self, bar_start: datetime, price: float) -> None:
        """Start new bar."""
        self.current_bar_start = bar_start
        self.current_bar = {
            'timestamp': bar_start,
            'open': price,
            'high': price,
            'low': price,
            'close': price,
            'volume': 1,
            'tick_count': 1
        }
    
    def _update_bar(self, price: float) -> None:
        """Update current bar with new tick."""
        if self.current_bar is None:
            return
        
        self.current_bar['high'] = max(self.current_bar['high'], price)
        self.current_bar['low'] = min(self.current_bar['low'], price)
        self.current_bar['close'] = price
        self.current_bar['volume'] += 1
        self.current_bar['tick_count'] += 1
    
    def _complete_bar(self) -> Dict:
        """Mark current bar as complete and return it."""
        if self.current_bar is None:
            return None
        
        completed = self.current_bar.copy()
        self.bars_completed += 1
        
        logger.info(
            f"Bar complete: {completed['timestamp'].strftime('%Y-%m-%d %H:%M')} | "
            f"O:{completed['open']:.5f} H:{completed['high']:.5f} "
            f"L:{completed['low']:.5f} C:{completed['close']:.5f} | "
            f"Ticks:{completed['tick_count']}"
        )
        
        # Trigger callback if provided
        if self.on_bar_complete:
            self.on_bar_complete(completed)
        
        return completed
    
    def force_complete_current_bar(self) -> Optional[Dict]:
        """Force completion of current bar (for shutdown)."""
        if self.current_bar is None:
            return None
        
        return self._complete_bar()
    
    def get_latest_price(self) -> Dict:
        """Get latest tick prices."""
        return {
            'bid': self.latest_bid,
            'ask': self.latest_ask,
            'mid': self.latest_mid,
            'timestamp': self.latest_timestamp
        }
    
    def get_stats(self) -> Dict:
        """Get aggregator statistics."""
        return {
            'ticks_processed': self.ticks_processed,
            'bars_completed': self.bars_completed,
            'timeframe_minutes': self.timeframe_minutes,
            'tick_buffer_size': len(self.tick_buffer),
            'latest_timestamp': self.latest_timestamp.isoformat() if self.latest_timestamp else None
        }
