"""
Portfolio State Manager

Tracks positions, cash, and PnL in real-time for live trading.
"""

import logging
from typing import Dict, Optional
from datetime import datetime
import pandas as pd

from ..events import FillEvent, OrderSide

logger = logging.getLogger(__name__)


class Position:
    """
    Represents a position in a single instrument.
    
    Tracks entry details and calculates unrealized PnL.
    """
    
    def __init__(self, symbol: str, quantity: float, entry_price: float,
                 entry_time: datetime, side: OrderSide):
        """
        Initialize position.
        
        Args:
            symbol: Currency pair
            quantity: Position size (positive for both long/short)
            entry_price: Average entry price
            entry_time: Position entry timestamp
            side: BUY (long) or SELL (short)
        """
        self.symbol = symbol
        self.quantity = abs(quantity)
        self.entry_price = entry_price
        self.entry_time = entry_time
        self.side = side
        
        # Realized PnL from partial closes
        self.realized_pnl = 0.0
        
        # Transaction costs
        self.total_commission = 0.0
        self.total_slippage = 0.0
    
    def unrealized_pnl(self, current_price: float) -> float:
        """
        Calculate unrealized PnL at current price.
        
        Args:
            current_price: Current market price
        
        Returns:
            Unrealized PnL (positive = profit, negative = loss)
        """
        if self.side == OrderSide.BUY:
            # Long: profit when price goes up
            pnl = (current_price - self.entry_price) * self.quantity
        else:  # SELL
            # Short: profit when price goes down
            pnl = (self.entry_price - current_price) * self.quantity
        
        return pnl
    
    def total_pnl(self, current_price: float) -> float:
        """Total PnL (realized + unrealized)."""
        return self.realized_pnl + self.unrealized_pnl(current_price)
    
    def update(self, quantity_change: float, price: float, commission: float,
               slippage: float, is_closing: bool = False):
        """
        Update position (for pyramiding or partial closes).
        
        Args:
            quantity_change: Change in quantity (positive = add, negative = reduce)
            price: Trade execution price
            commission: Commission paid
            slippage: Slippage cost
            is_closing: True if reducing position
        """
        self.total_commission += commission
        self.total_slippage += slippage
        
        if is_closing:
            # Realize PnL for the closed portion
            if self.side == OrderSide.BUY:
                realized = (price - self.entry_price) * abs(quantity_change)
            else:
                realized = (self.entry_price - price) * abs(quantity_change)
            
            self.realized_pnl += realized - commission - abs(slippage)
            self.quantity -= abs(quantity_change)
        else:
            # Pyramiding: update average entry price
            total_cost = (self.entry_price * self.quantity + price * abs(quantity_change))
            self.quantity += abs(quantity_change)
            self.entry_price = total_cost / self.quantity if self.quantity > 0 else price
    
    def __repr__(self) -> str:
        return (f"Position({self.side.value} {self.quantity} {self.symbol} @ "
                f"{self.entry_price:.5f}, realized_pnl={self.realized_pnl:.2f})")


class Portfolio:
    """
    Portfolio state manager for live trading.
    
    Tracks:
    - Cash balance
    - Open positions
    - Realized/unrealized PnL
    - Equity curve
    """
    
    def __init__(self, initial_capital: float):
        """
        Initialize portfolio.
        
        Args:
            initial_capital: Starting cash balance
        """
        self.initial_capital = initial_capital
        self.cash = initial_capital
        
        # Positions: {symbol: Position}
        self.positions = {}
        
        # Current market prices {symbol: {'bid': float, 'ask': float}}
        self.current_prices = {}
        
        # Equity history for curve
        self.equity_history = []  # [(timestamp, equity, cash, positions_value)]
        
        # Trade history
        self.trade_history = []  # List of FillEvents
        
        logger.info(f"Portfolio initialized with ${initial_capital:,.2f}")
    
    def update_market_price(self, symbol: str, bid: float, ask: float):
        """
        Update current market price.
        
        Args:
            symbol: Currency pair
            bid: Current bid
            ask: Current ask
        """
        self.current_prices[symbol] = {'bid': bid, 'ask': ask}
    
    def on_fill(self, fill: FillEvent):
        """
        Process fill event and update portfolio state.
        
        Args:
            fill: FillEvent from execution
        """
        symbol = fill.symbol
        
        # Record trade
        self.trade_history.append(fill)
        
        # Determine if opening/closing/reversing position
        existing_position = self.positions.get(symbol)
        
        if existing_position is None:
            # Opening new position
            self._open_position(fill)
        elif existing_position.side == fill.side:
            # Pyramiding (adding to existing position)
            self._pyramid_position(fill, existing_position)
        else:
            # Closing or reversing position
            self._close_or_reverse_position(fill, existing_position)
        
        # Update cash (cost includes commission and slippage)
        self.cash -= fill.total_cost
        
        # Record equity snapshot
        self._record_equity(fill.timestamp)
        
        logger.info(f"Fill processed: {fill.symbol} {fill.side.value} {fill.quantity} @ "
                   f"{fill.fill_price:.5f}, cash=${self.cash:,.2f}, "
                   f"equity=${self.get_equity():.2f}")
    
    def _open_position(self, fill: FillEvent):
        """Open new position."""
        position = Position(
            symbol=fill.symbol,
            quantity=fill.quantity,
            entry_price=fill.fill_price,
            entry_time=fill.timestamp,
            side=fill.side
        )
        position.total_commission = fill.commission
        position.total_slippage = abs(fill.slippage)
        
        self.positions[fill.symbol] = position
        logger.info(f"Opened position: {position}")
    
    def _pyramid_position(self, fill: FillEvent, position: Position):
        """Add to existing position (pyramiding)."""
        position.update(
            quantity_change=fill.quantity,
            price=fill.fill_price,
            commission=fill.commission,
            slippage=abs(fill.slippage),
            is_closing=False
        )
        logger.info(f"Pyramided position: {position}")
    
    def _close_or_reverse_position(self, fill: FillEvent, position: Position):
        """Close or reverse existing position."""
        if fill.quantity >= position.quantity:
            # Full close or reverse
            close_quantity = position.quantity
            position.update(
                quantity_change=close_quantity,
                price=fill.fill_price,
                commission=fill.commission * (close_quantity / fill.quantity),
                slippage=abs(fill.slippage) * (close_quantity / fill.quantity),
                is_closing=True
            )
            
            logger.info(f"Closed position: {position.symbol}, "
                       f"realized_pnl=${position.realized_pnl:.2f}")
            
            # Position is closed
            del self.positions[fill.symbol]
            
            # If reversing (fill quantity > position quantity), open opposite position
            if fill.quantity > close_quantity:
                reverse_quantity = fill.quantity - close_quantity
                reverse_fill = FillEvent(
                    order_id=fill.order_id,
                    symbol=fill.symbol,
                    side=fill.side,
                    quantity=reverse_quantity,
                    fill_price=fill.fill_price,
                    commission=fill.commission * (reverse_quantity / fill.quantity),
                    slippage=fill.slippage * (reverse_quantity / fill.quantity),
                    timestamp=fill.timestamp,
                    exchange_order_id=fill.exchange_order_id
                )
                self._open_position(reverse_fill)
                logger.info(f"Reversed to opposite position")
        else:
            # Partial close
            position.update(
                quantity_change=fill.quantity,
                price=fill.fill_price,
                commission=fill.commission,
                slippage=abs(fill.slippage),
                is_closing=True
            )
            logger.info(f"Partially closed position: {position}")
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """Get current position for symbol."""
        return self.positions.get(symbol)
    
    def get_position_quantity(self, symbol: str) -> float:
        """
        Get current position quantity (signed).
        
        Returns:
            Positive for long, negative for short, 0 for no position
        """
        position = self.positions.get(symbol)
        if position is None:
            return 0.0
        return position.quantity if position.side == OrderSide.BUY else -position.quantity
    
    def get_positions_value(self) -> float:
        """Calculate total value of all open positions at current market prices."""
        total = 0.0
        for symbol, position in self.positions.items():
            if symbol in self.current_prices:
                # Use bid for long, ask for short (realistic exit price)
                if position.side == OrderSide.BUY:
                    current_price = self.current_prices[symbol]['bid']
                else:
                    current_price = self.current_prices[symbol]['ask']
                
                total += position.unrealized_pnl(current_price)
        
        return total
    
    def get_equity(self) -> float:
        """Calculate total portfolio equity (cash + positions value)."""
        return self.cash + self.get_positions_value()
    
    def get_total_return(self) -> float:
        """Calculate total return percentage."""
        return (self.get_equity() - self.initial_capital) / self.initial_capital
    
    def _record_equity(self, timestamp: datetime):
        """Record equity snapshot for curve."""
        equity = self.get_equity()
        positions_value = self.get_positions_value()
        
        self.equity_history.append({
            'timestamp': timestamp,
            'equity': equity,
            'cash': self.cash,
            'positions_value': positions_value,
            'total_return': self.get_total_return()
        })
    
    def get_equity_curve(self) -> pd.DataFrame:
        """Get equity curve as DataFrame."""
        return pd.DataFrame(self.equity_history)
    
    def get_summary(self) -> Dict:
        """Get portfolio summary statistics."""
        return {
            'initial_capital': self.initial_capital,
            'cash': self.cash,
            'positions_value': self.get_positions_value(),
            'equity': self.get_equity(),
            'total_return': self.get_total_return(),
            'total_return_pct': self.get_total_return() * 100,
            'num_open_positions': len(self.positions),
            'num_trades': len(self.trade_history),
        }
    
    def __repr__(self) -> str:
        return (f"Portfolio(equity=${self.get_equity():,.2f}, cash=${self.cash:,.2f}, "
                f"positions={len(self.positions)}, return={self.get_total_return():.2%})")
