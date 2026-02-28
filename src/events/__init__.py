"""
Event System for Live Trading

Event-driven architecture components for real-time trading:
- TickEvent: Real-time price ticks from FIX feed
- BarEvent: Aggregated OHLC bars (4H/daily)
- SignalEvent: Trading signals from strategies
- OrderEvent: Order placement requests
- FillEvent: Execution confirmations from broker/simulator
"""

from .event import Event, EventType
from .market_event import TickEvent, BarEvent
from .signal_event import SignalEvent
from .order_event import OrderEvent, OrderType, OrderSide
from .fill_event import FillEvent
from .event_queue import EventQueue

__all__ = [
    'Event',
    'EventType',
    'TickEvent',
    'BarEvent',
    'SignalEvent',
    'OrderEvent',
    'OrderType',
    'OrderSide',
    'FillEvent',
    'EventQueue',
]
