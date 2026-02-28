"""
Order Events

Order placement requests after passing risk management checks.
"""

from enum import Enum
from datetime import datetime
from typing import Dict, Any, Optional
from .event import Event, EventType


class OrderType(Enum):
    """Order type enumeration."""
    MARKET = 'MARKET'  # Execute at current market price
    LIMIT = 'LIMIT'    # Execute at specific price or better
    STOP = 'STOP'      # Stop-loss order


class OrderSide(Enum):
    """Order side enumeration."""
    BUY = 'BUY'
    SELL = 'SELL'


class OrderEvent(Event):
    """
    Order placement request.
    
    Generated after signal passes through portfolio/risk management.
    Ready to be sent to broker (or simulator in paper trading).
    """
    
    def __init__(self, symbol: str, order_type: OrderType, side: OrderSide,
                 quantity: float, price: Optional[float] = None,
                 stop_loss: Optional[float] = None,
                 take_profit: Optional[float] = None,
                 order_id: Optional[str] = None,
                 timestamp: datetime = None):
        """
        Initialize order event.
        
        Args:
            symbol: Currency pair
            order_type: Market, limit, or stop order
            side: Buy or sell
            quantity: Position size (in units, not lots)
            price: Limit price (required for LIMIT orders)
            stop_loss: Optional stop-loss price
            take_profit: Optional take-profit price
            order_id: Unique order identifier (generated if not provided)
            timestamp: Order creation timestamp
        """
        super().__init__(EventType.ORDER, timestamp)
        self.symbol = symbol
        self.order_type = order_type
        self.side = side
        self.quantity = abs(quantity)  # Ensure positive
        self.price = price
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.order_id = order_id or self._generate_order_id()
        
        # Validate
        if order_type == OrderType.LIMIT and price is None:
            raise ValueError("LIMIT orders require a price")
        if quantity <= 0:
            raise ValueError(f"Quantity must be positive, got {quantity}")
    
    def _generate_order_id(self) -> str:
        """Generate unique order ID."""
        import uuid
        return f"ORD_{self.timestamp.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        d = super().to_dict()
        d.update({
            'order_id': self.order_id,
            'symbol': self.symbol,
            'order_type': self.order_type.value,
            'side': self.side.value,
            'quantity': self.quantity,
            'price': self.price,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
        })
        return d
    
    def __repr__(self) -> str:
        return (f"OrderEvent(id={self.order_id[:12]}, {self.side.value} {self.quantity} "
                f"{self.symbol} @ {self.order_type.value})")
