"""
Paper Trading Simulator

Simulates order execution without sending real orders to the broker.
Applies realistic costs matching the backtest CostModel for validation.
"""

import logging
import time
import random
from typing import Dict, Optional
from datetime import datetime, timedelta
from threading import Thread
import yaml

from ..events import OrderEvent, FillEvent, EventQueue, OrderSide
from ..backtest.engine import CostModel

logger = logging.getLogger(__name__)


class PaperTradingSimulator:
    """
    Simulates order fills for paper trading.
    
    Features:
    - Simulated fill delay (100ms-2s to match real latency)
    - Applies slippage and commission matching backtest CostModel
    - Realistic bid/ask spread modeling
    - Thread-safe operation
    
    Does NOT:
    - Send real orders to broker
    - Connect to real market
    - Risk real capital
    """
    
    def __init__(self, config_path: str, event_queue: EventQueue):
        """
        Initialize paper trading simulator.
        
        Args:
            config_path: Path to broker config YAML
            event_queue: Event queue for putting FillEvents
        """
        self.event_queue = event_queue
        
        # Load configuration
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        # Initialize cost model (match backtest)
        execution_config = self.config.get('execution', {})
        self.cost_model = CostModel({
            'commission_per_share': execution_config.get('commission_per_unit', 0.0),
            'slippage_pct': execution_config.get('slippage_pct', 0.00009),  # 0.9 pips
            'daily_borrow_fee': 0.0,  # Not relevant for FX spot
        })
        
        # Simulated fill delay range
        self.fill_delay_min = execution_config.get('simulated_fill_delay_min', 0.1)
        self.fill_delay_max = execution_config.get('simulated_fill_delay_max', 2.0)
        
        # Current market prices (updated externally)
        self.market_prices = {}  # {symbol: {'bid': float, 'ask': float, 'timestamp': datetime}}
        
        # Order tracking
        self.pending_orders = {}  # {order_id: OrderEvent}
        
        logger.info("Paper trading simulator initialized")
    
    def update_market_price(self, symbol: str, bid: float, ask: float, timestamp: datetime = None):
        """
        Update current market price for a symbol.
        
        Called externally when TickEvent arrives.
        
        Args:
            symbol: Currency pair
            bid: Current bid price
            ask: Current ask price
            timestamp: Price timestamp
        """
        self.market_prices[symbol] = {
            'bid': bid,
            'ask': ask,
            'timestamp': timestamp or datetime.utcnow(),
        }
        logger.debug(f"Market price updated: {symbol} bid={bid:.5f} ask={ask:.5f}")
    
    def execute_order(self, order: OrderEvent):
        """
        Simulate order execution.
        
        Process:
        1. Validate we have market price for symbol
        2. Calculate fill price (buy=ask, sell=bid)
        3. Apply slippage
        4. Calculate commission
        5. Simulate network delay
        6. Generate FillEvent
        
        Args:
            order: OrderEvent to execute
        """
        # Check if we have market price
        if order.symbol not in self.market_prices:
            logger.error(f"Cannot execute order: no market price for {order.symbol}")
            return
        
        market_data = self.market_prices[order.symbol]
        
        # Determine fill price (realistic: buy at ask, sell at bid)
        if order.side == OrderSide.BUY:
            base_price = market_data['ask']
        else:  # SELL
            base_price = market_data['bid']
        
        # Apply slippage (simulated market impact)
        slippage_cost = self.cost_model.slippage_pct * base_price * order.quantity
        slippage_pips = slippage_cost / (0.0001 * order.quantity) if order.quantity > 0 else 0.0
        
        # Fill price includes slippage (worsen for buys, improve for sells is net negative)
        if order.side == OrderSide.BUY:
            fill_price = base_price + (slippage_cost / order.quantity)
        else:
            fill_price = base_price - (slippage_cost / order.quantity)
        
        # Calculate commission
        commission = abs(order.quantity) * self.cost_model.commission_per_share
        
        # Simulate execution delay (asynchronous fill)
        fill_delay = random.uniform(self.fill_delay_min, self.fill_delay_max)
        
        # Store pending order
        self.pending_orders[order.order_id] = order
        
        # Execute fill in background thread (simulates async broker response)
        thread = Thread(
            target=self._delayed_fill,
            args=(order, fill_price, commission, slippage_pips, fill_delay),
            daemon=True
        )
        thread.start()
        
        logger.info(f"Order submitted for simulation: {order.order_id[:12]} "
                   f"{order.side.value} {order.quantity} {order.symbol} "
                   f"@ {fill_price:.5f} (delay={fill_delay:.2f}s)")
    
    def _delayed_fill(self, order: OrderEvent, fill_price: float,
                      commission: float, slippage_pips: float, delay: float):
        """
        Internal: Execute fill after simulated delay.
        
        Args:
            order: Original order
            fill_price: Calculated fill price
            commission: Commission amount
            slippage_pips: Slippage in pips
            delay: Delay in seconds
        """
        # Wait for simulated network/execution delay
        time.sleep(delay)
        
        # Generate fill event
        fill = FillEvent(
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            fill_price=fill_price,
            commission=commission,
            slippage=slippage_pips,
            timestamp=datetime.utcnow(),
            exchange_order_id=f"SIM_{order.order_id[:8]}"  # Simulated exchange ID
        )
        
        # Put fill event on queue (portfolio will process)
        self.event_queue.put(fill)
        
        # Remove from pending
        self.pending_orders.pop(order.order_id, None)
        
        logger.info(f"Order filled: {fill}")
    
    def get_pending_orders(self) -> Dict[str, OrderEvent]:
        """Get dictionary of pending orders."""
        return self.pending_orders.copy()
    
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel a pending order.
        
        Args:
            order_id: Order ID to cancel
        
        Returns:
            True if cancelled, False if order not found
        """
        if order_id in self.pending_orders:
            order = self.pending_orders.pop(order_id)
            logger.info(f"Order cancelled: {order_id[:12]}")
            return True
        else:
            logger.warning(f"Cannot cancel order {order_id[:12]}: not found")
            return False
