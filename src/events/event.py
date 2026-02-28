"""
Base Event Class

Foundation for all event types in the trading system.
"""

from enum import Enum
from datetime import datetime
from typing import Dict, Any


class EventType(Enum):
    """Event type enumeration."""
    TICK = 'TICK'
    BAR = 'BAR'
    SIGNAL = 'SIGNAL'
    ORDER = 'ORDER'
    FILL = 'FILL'


class Event:
    """
    Base class for all events in the trading system.
    
    All events must have:
    - event_type: Type of event
    - timestamp: When the event occurred
    """
    
    def __init__(self, event_type: EventType, timestamp: datetime = None):
        """
        Initialize event.
        
        Args:
            event_type: Type of event
            timestamp: Event timestamp (defaults to now if not provided)
        """
        self.event_type = event_type
        self.timestamp = timestamp or datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for logging."""
        return {
            'event_type': self.event_type.value,
            'timestamp': self.timestamp.isoformat(),
        }
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(type={self.event_type.value}, ts={self.timestamp})"
