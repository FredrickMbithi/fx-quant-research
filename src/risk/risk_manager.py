"""
Risk Management Layer

Pre-trade validation and risk limits enforcement for live trading.
"""

import logging
from typing import Dict, Optional, List
from datetime import datetime, timedelta
import yaml

from ..events import OrderEvent, SignalEvent
from ..portfolio import Portfolio

logger = logging.getLogger(__name__)


class RiskManager:
    """
    Risk management for live trading.
    
    Enforces:
    - Maximum drawdown limits (kill switch)
    - Position size limits
    - Maximum exposure
    - Stop-loss distance requirements
    - Daily loss limits
    
    All orders must pass risk checks before execution.
    """
    
    def __init__(self, config_path: str, portfolio: Portfolio):
        """
        Initialize risk manager.
        
        Args:
            config_path: Path to broker config YAML
            portfolio: Portfolio instance for state access
        """
        self.portfolio = portfolio
        
        # Load configuration
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        self.risk_config = config.get('risk', {})
        self.trading_config = config.get('trading', {})
        
        # Risk limits
        self.max_drawdown_pct = self.risk_config.get('max_drawdown_pct', 15.0)
        self.max_position_exposure = self.risk_config.get('max_position_exposure', 2.0)
        self.stop_loss_min_pips = self.risk_config.get('stop_loss_min_pips', 10)
        self.max_position_size = self.trading_config.get('max_position_size', 100000)
        
        # Daily limits
        self.max_daily_loss_pct = self.risk_config.get('max_daily_loss_pct', 5.0)
        self.daily_loss_tracking = {}  # {date: loss_amount}
        
        # Trading limits
        self.max_orders_per_day = self.risk_config.get('max_orders_per_day', 50)
        self.order_count_tracking = {}  # {date: count}
        
        # Emergency shutdown flag
        self.trading_halted = False
        self.halt_reason = None
        
        # Peak equity for drawdown calculation
        self.peak_equity = portfolio.initial_capital
        
        logger.info(f"Risk manager initialized: max_dd={self.max_drawdown_pct}%, "
                   f"max_exposure={self.max_position_exposure}x")
    
    def validate_signal(self, signal: SignalEvent) -> tuple[bool, Optional[str]]:
        """
        Validate if signal should be acted upon.
        
        Args:
            signal: SignalEvent to validate
        
        Returns:
            (is_valid, reason) - True if signal passes checks, False with reason if rejected
        """
        # Check if trading is halted
        if self.trading_halted:
            return False, f"Trading halted: {self.halt_reason}"
        
        # Check if signal strength is actionable
        if abs(signal.signal_strength) < 0.01:
            return False, "Signal too weak (< 1%)"
        
        return True, None
    
    def validate_order(self, order: OrderEvent, current_price: float) -> tuple[bool, Optional[str]]:
        """
        Validate order before execution.
        
        Args:
            order: OrderEvent to validate
            current_price: Current market price
        
        Returns:
            (is_valid, reason) - True if order passes checks, False with reason if rejected
        """
        # Check if trading is halted
        if self.trading_halted:
            return False, f"Trading halted: {self.halt_reason}"
        
        # Check drawdown limit
        current_drawdown = self._calculate_drawdown()
        if current_drawdown > self.max_drawdown_pct:
            self._halt_trading(f"Max drawdown exceeded: {current_drawdown:.2f}% > {self.max_drawdown_pct}%")
            return False, self.halt_reason
        
        # Check position size limit
        if order.quantity > self.max_position_size:
            return False, f"Order size {order.quantity} exceeds max {self.max_position_size}"
        
        # Check total exposure limit
        new_exposure = self._calculate_new_exposure(order, current_price)
        max_allowed = self.portfolio.initial_capital * self.max_position_exposure
        if new_exposure > max_allowed:
            return False, f"Total exposure ${new_exposure:,.0f} exceeds limit ${max_allowed:,.0f}"
        
        # Check daily loss limit
        if not self._check_daily_loss_limit():
            return False, f"Daily loss limit exceeded ({self.max_daily_loss_pct}%)"
        
        # Check daily order count
        if not self._check_daily_order_count():
            return False, f"Daily order limit exceeded ({self.max_orders_per_day} orders)"
        
        # Check stop-loss distance if provided
        if order.stop_loss is not None:
            stop_distance_pips = abs(current_price - order.stop_loss) / 0.0001
            if stop_distance_pips < self.stop_loss_min_pips:
                return False, f"Stop-loss too tight: {stop_distance_pips:.1f} pips < {self.stop_loss_min_pips} pips"
        
        # All checks passed
        logger.info(f"Order validated: {order.order_id[:12]} {order.symbol} {order.side.value} {order.quantity}")
        return True, None
    
    def _calculate_drawdown(self) -> float:
        """
        Calculate current drawdown percentage.
        
        Returns:
            Drawdown as percentage (e.g., 10.5 for 10.5%)
        """
        current_equity = self.portfolio.get_equity()
        
        # Update peak equity
        if current_equity > self.peak_equity:
            self.peak_equity = current_equity
        
        # Calculate drawdown
        if self.peak_equity > 0:
            drawdown = ((self.peak_equity - current_equity) / self.peak_equity) * 100
        else:
            drawdown = 0.0
        
        return drawdown
    
    def _calculate_new_exposure(self, order: OrderEvent, current_price: float) -> float:
        """
        Calculate total exposure if order is executed.
        
        Args:
            order: Proposed order
            current_price: Current market price
        
        Returns:
            Total notional exposure across all positions
        """
        # Current exposure from existing positions
        current_exposure = 0.0
        for symbol, position in self.portfolio.positions.items():
            if symbol in self.portfolio.current_prices:
                mid_price = (self.portfolio.current_prices[symbol]['bid'] + 
                           self.portfolio.current_prices[symbol]['ask']) / 2
                current_exposure += position.quantity * mid_price
        
        # Add new order exposure
        new_order_exposure = order.quantity * current_price
        
        return current_exposure + new_order_exposure
    
    def _check_daily_loss_limit(self) -> bool:
        """Check if daily loss limit has been exceeded."""
        today = datetime.now().date()
        
        # Calculate today's PnL
        daily_return = self._calculate_daily_return()
        
        # Check against limit
        if daily_return < -self.max_daily_loss_pct:
            logger.warning(f"Daily loss limit reached: {daily_return:.2f}% < -{self.max_daily_loss_pct}%")
            return False
        
        return True
    
    def _calculate_daily_return(self) -> float:
        """Calculate return since start of day."""
        # Simplified: calculate from equity history
        # In production, track daily starting equity properly
        if len(self.portfolio.equity_history) == 0:
            return 0.0
        
        # Use first equity of the day as baseline
        today = datetime.now().date()
        today_entries = [e for e in self.portfolio.equity_history 
                        if e['timestamp'].date() == today]
        
        if not today_entries:
            return 0.0
        
        start_equity = today_entries[0]['equity']
        current_equity = self.portfolio.get_equity()
        
        daily_return = ((current_equity - start_equity) / start_equity) * 100
        return daily_return
    
    def _check_daily_order_count(self) -> bool:
        """Check if daily order limit has been exceeded."""
        today = datetime.now().date()
        
        # Initialize counter for today if needed
        if today not in self.order_count_tracking:
            self.order_count_tracking[today] = 0
        
        # Check limit
        if self.order_count_tracking[today] >= self.max_orders_per_day:
            logger.warning(f"Daily order limit reached: {self.order_count_tracking[today]}")
            return False
        
        # Increment counter
        self.order_count_tracking[today] += 1
        return True
    
    def _halt_trading(self, reason: str):
        """Emergency halt all trading."""
        self.trading_halted = True
        self.halt_reason = reason
        logger.critical(f"🚨 TRADING HALTED: {reason}")
    
    def resume_trading(self):
        """Resume trading after manual review."""
        self.trading_halted = False
        self.halt_reason = None
        logger.warning("Trading resumed (manual override)")
    
    def get_risk_status(self) -> Dict:
        """Get current risk metrics."""
        return {
            'trading_halted': self.trading_halted,
            'halt_reason': self.halt_reason,
            'current_drawdown_pct': self._calculate_drawdown(),
            'max_drawdown_pct': self.max_drawdown_pct,
            'daily_return_pct': self._calculate_daily_return(),
            'max_daily_loss_pct': self.max_daily_loss_pct,
            'peak_equity': self.peak_equity,
            'current_equity': self.portfolio.get_equity(),
        }
