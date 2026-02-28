"""
Thread-Safe Event Queue

Manages event flow in the trading system with thread-safe operations.
"""

import queue
import logging
from typing import Optional
from .event import Event

logger = logging.getLogger(__name__)


class EventQueue:
    """
    Thread-safe FIFO queue for events.
    
    Manages event flow between components:
    - FIX client puts TickEvents/FillEvents
    - Market data handler puts BarEvents
    - Strategies put SignalEvents
    - Portfolio/risk puts OrderEvents
    - Main trading loop gets events and dispatches to handlers
    """
    
    def __init__(self, maxsize: int = 0):
        """
        Initialize event queue.
        
        Args:
            maxsize: Maximum queue size (0 = unlimited)
        """
        self._queue = queue.Queue(maxsize=maxsize)
        self._event_count = 0
    
    def put(self, event: Event, block: bool = True, timeout: Optional[float] = None):
        """
        Add event to queue.
        
        Args:
            event: Event to add
            block: Block if queue is full
            timeout: Timeout in seconds (None = wait forever)
        
        Raises:
            queue.Full: If queue is full and block=False or timeout expires
        """
        try:
            self._queue.put(event, block=block, timeout=timeout)
            self._event_count += 1
            logger.debug(f"Event queued: {event}")
        except queue.Full:
            logger.error(f"Queue full, dropping event: {event}")
            raise
    
    def get(self, block: bool = True, timeout: Optional[float] = None) -> Event:
        """
        Get next event from queue.
        
        Args:
            block: Block if queue is empty
            timeout: Timeout in seconds (None = wait forever)
        
        Returns:
            Next event in queue
        
        Raises:
            queue.Empty: If queue is empty and block=False or timeout expires
        """
        try:
            event = self._queue.get(block=block, timeout=timeout)
            logger.debug(f"Event dequeued: {event}")
            return event
        except queue.Empty:
            raise
    
    def empty(self) -> bool:
        """Check if queue is empty."""
        return self._queue.empty()
    
    def qsize(self) -> int:
        """Get approximate queue size."""
        return self._queue.qsize()
    
    def get_event_count(self) -> int:
        """Get total number of events processed."""
        return self._event_count
    
    def clear(self):
        """Clear all events from queue (for testing/shutdown)."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        logger.info("Event queue cleared")
