#!/usr/bin/env python
"""
LIVE PAPER TRADING - Exhaustion + Failure Pattern (H1)
Connects to Pepperstone via FIX for real-time market data

🚀 FEATURES:
- Real-time H1 bar building from FIX tick stream
- NZDJPY + GBPUSD simultaneous monitoring
- ExhaustionStrategy signal generation
- Paper trading mode (logs trades, no real orders)
- Live mode ready (can execute real orders when validated)
- Risk management (position limits, drawdown limits, consecutive loss halt)
- SQLite trade logging with full audit trail
- Dashboard export every 24 hours

USAGE:
    python deploy_exhaustion_live_paper.py --mode paper
    python deploy_exhaustion_live_paper.py --mode live  # (after validation!)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import os
import logging
import time
import signal
import argparse
from datetime import datetime, UTC, timedelta
from queue import Queue, Empty
from typing import Optional, Dict, List
from collections import defaultdict
from dotenv import load_dotenv

from src.strategies.exhaustion_strategy import ExhaustionStrategy
from src.execution.fix_client_v2 import PepperstoneFIXClient
from src.portfolio.portfolio import Portfolio
from src.events import (
    EventQueue, BarEvent, SignalEvent, OrderEvent, FillEvent,
    OrderType, OrderSide
)
from src.utils.trade_database import TradeDatabase
from src.utils.tick_aggregator import TickAggregator

# Load environment
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'logs/live_exhaustion_{datetime.now(UTC).strftime("%Y%m%d_%H%M%S")}.log')
    ]
)
logger = logging.getLogger(__name__)


class LiveExhaustionTrader:
    """
    Live paper trading engine for exhaustion+failure pattern.
    Connects to Pepperstone FIX for real-time H1 data.
    """
    
    def __init__(
        self,
        symbols: List[str] = ['NZDJPY', 'GBPUSD'],
        mode: str = 'paper',
        initial_capital: float = 100000.0,
        risk_per_trade_pct: float = 0.01,
        db_path: str = 'state/live_trades.db'
    ):
        """
        Initialize live trading engine.
        
        Args:
            symbols: List of pairs to trade
            mode: 'paper' (log only) or 'live' (real orders)
            initial_capital: Starting capital
            risk_per_trade_pct: Risk per trade (default 1%)
            db_path: SQLite database path
        """
        self.symbols = symbols
        self.mode = mode
        self.initial_capital = initial_capital
        self.risk_per_trade_pct = risk_per_trade_pct
        self.session_id = f"live_exhaustion_{int(datetime.now(UTC).timestamp())}"
        self.running = False
        
        # Load FIX credentials
        fix_password = os.getenv('FIX_PASSWORD')
        if not fix_password and mode == 'live':
            raise ValueError(
                "FIX_PASSWORD not set in environment.\n"
                "Create .env file with: FIX_PASSWORD=your_password"
            )
        
        # FIX configuration
        self.config = {
            'sender_comp_id': os.getenv('FIX_SENDER_COMP_ID', 'demo.pepperstone.5227001'),
            'target_comp_id': os.getenv('FIX_TARGET_COMP_ID', 'cServer'),
            'username': os.getenv('FIX_USERNAME', '5227001'),
            'password': fix_password or 'dummy',
            'price_host': os.getenv('FIX_PRICE_HOST', 'demo-us-eqx-01.p.c-trader.com'),
            'price_port_ssl': int(os.getenv('FIX_PRICE_PORT', '5211')),
            'trade_host': os.getenv('FIX_TRADE_HOST', 'demo-us-eqx-01.p.c-trader.com'),
            'trade_port_ssl': int(os.getenv('FIX_TRADE_PORT', '5212')),
        }
        
        # Initialize database
        logger.info(f"📊 Initializing trade database: {db_path}")
        self.db = TradeDatabase(db_path)
        
        # Initialize strategies (one per symbol)
        logger.info("🎯 Initializing ExhaustionStrategy for each pair...")
        self.strategies = {}
        
        for symbol in symbols:
            # Load config from paper trading configs
            config_path = f'config/paper_exhaustion_{symbol.lower()}.json'
            if Path(config_path).exists():
                import json
                with open(config_path, 'r') as f:
                    cfg = json.load(f)
                    strategy_params = cfg['strategy_params']
                    self.exit_params = cfg.get('exit_params', {})
                    self.monitoring = cfg.get('monitoring', {})
            else:
                # Default params from backtest
                strategy_params = {
                    'max_bars': 50,
                    'pressure_threshold': 2,
                    'range_expansion_factor': 0.8,
                    'range_lookback': 10,
                    'percentile_high': 0.65,
                    'percentile_low': 0.35,
                    'percentile_window': 10
                }
            
            self.strategies[symbol] = ExhaustionStrategy(
                name=f'Exhaustion_{symbol}',
                symbols=[symbol],
                config=strategy_params
            )
            logger.info(f"  ✓ {symbol}: ExhaustionStrategy ready")
        
        # Portfolio
        logger.info("💰 Initializing portfolio...")
        self.portfolio = Portfolio(initial_capital=initial_capital)
        
        # Tick aggregators (convert ticks → H1 bars)
        logger.info("📈 Initializing H1 bar aggregators...")
        self.tick_aggregators = {}
        for symbol in symbols:
            self.tick_aggregators[symbol] = TickAggregator(
                symbol=symbol,
                timeframe='H1',  # Hourly bars
                on_bar_complete=self._on_bar_complete
            )
        
        # Position tracking
        self.open_positions = {}  # {symbol: position_data}
        self.pending_orders = {}  # {cl_ord_id: order_data}
        
        # Risk management
        self.consecutive_losses = defaultdict(int)  # per symbol
        self.peak_equity = initial_capital
        self.current_equity = initial_capital
        self.realized_pnl = 0.0  # Track realized PnL separately
        self.daily_pnl = 0.0
        self.trades_today = 0
        self.last_reset_date = datetime.now(UTC).date()
        
        # Risk limits (from configs)
        self.risk_limits = {
            'max_drawdown_pct': 0.10,  # 10% max drawdown
            'max_position_size_units': 10000,  # 1 mini lot
            'max_daily_loss': 5000.0,  # $5k daily loss limit
            'max_trades_per_day': 10,
            'halt_on_consecutive_losses': {
                'NZDJPY': 5,
                'GBPUSD': 7
            }
        }
        
        # Exit parameters (from configs)
        self.exit_params = {
            'stop_loss_pips': 10,
            'profit_trigger_pips': 4,
            'trailing_distance_pips': 3,
            'max_hold_bars': 5
        }
        
        # FIX client
        self.fix_client: Optional[PepperstoneFIXClient] = None
        
        # Statistics
        self.stats = {
            'bars_processed': defaultdict(int),
            'signals_generated': defaultdict(int),
            'orders_placed': defaultdict(int),
            'fills_received': defaultdict(int),
            'start_time': None
        }
        
        # Create database session
        self.db.create_session(
            session_id=self.session_id,
            strategy='ExhaustionFailure_H1',
            config={
                'symbols': symbols,
                'initial_capital': initial_capital,
                'risk_per_trade_pct': risk_per_trade_pct,
                'mode': mode,
                'exit_params': self.exit_params,
                'risk_limits': self.risk_limits
            }
        )
        
        # Signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info(f"✅ Trading engine initialized")
        logger.info(f"   Mode: {mode.upper()}")
        logger.info(f"   Symbols: {', '.join(symbols)}")
        logger.info(f"   Session: {self.session_id}")
    
    def connect(self) -> bool:
        """Connect to Pepperstone FIX API"""
        logger.info("="*70)
        logger.info("CONNECTING TO PEPPERSTONE FIX API")
        logger.info("="*70)
        
        try:
            self.fix_client = PepperstoneFIXClient(self.config)
            
            # Set callbacks
            self.fix_client.on_market_data = self._on_tick
            self.fix_client.on_execution_report = self._on_execution_report
            self.fix_client.on_position_report = self._on_position_report
            
            # Connect to price server
            logger.info("📡 Connecting to price server...")
            if not self.fix_client.connect_price():
                logger.error("❌ Failed to connect to price server")
                return False
            
            # Connect to trade server (needed for position reconciliation even in paper mode)
            logger.info("📡 Connecting to trade server...")
            if not self.fix_client.connect_trade():
                logger.error("❌ Failed to connect to trade server")
                return False
            
            # Request position reconciliation
            logger.info("📊 Requesting position reconciliation...")
            self.fix_client.request_positions()
            time.sleep(2)
            
            # Subscribe to market data for all symbols
            logger.info(f"📈 Subscribing to market data: {', '.join(self.symbols)}")
            md_req_id = self.fix_client.subscribe_market_data(self.symbols, depth=1)
            
            if md_req_id:
                logger.info(f"✅ Market data subscription successful (MDReqID: {md_req_id})")
            else:
                logger.warning("⚠️  Market data subscription may have failed")
            
            logger.info("✅ Connected to Pepperstone")
            self.db.log_event(self.session_id, 'CONNECTION', 'Connected to Pepperstone FIX API')
            return True
            
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}", exc_info=True)
            self.db.log_event(self.session_id, 'CONNECTION', f'Connection failed: {e}', 'ERROR')
            return False
    
    def disconnect(self):
        """Disconnect from FIX API"""
        if self.fix_client:
            logger.info("Disconnecting from Pepperstone...")
            self.fix_client.disconnect()
            self.db.log_event(self.session_id, 'CONNECTION', 'Disconnected')
            logger.info("✅ Disconnected")
    
    def _on_tick(self, symbol: str, bid: float, ask: float, timestamp: datetime):
        """Callback for incoming tick data"""
        # Feed tick to aggregator
        if symbol in self.tick_aggregators:
            mid = (bid + ask) / 2
            self.tick_aggregators[symbol].on_tick(symbol, mid, timestamp)
    
    def _on_bar_complete(self, bar: BarEvent):
        """Callback when H1 bar is complete"""
        symbol = bar.symbol
        self.stats['bars_processed'][symbol] += 1
        
        logger.info(f"📊 [{symbol}] H1 Bar Complete: {bar.timestamp} | "
                   f"O={bar.open:.5f} H={bar.high:.5f} L={bar.low:.5f} C={bar.close:.5f}")
        
        # Log bar to database
        self.db.log_market_data(
            session_id=self.session_id,
            instrument=symbol,
            data_type='bar_h1',
            data={
                'timestamp': bar.timestamp.isoformat(),
                'open': bar.open,
                'high': bar.high,
                'low': bar.low,
                'close': bar.close,
                'volume': bar.volume
            }
        )
        
        # Monitor open positions for exits
        self._monitor_positions(bar)
        
        # Process bar with strategy
        if symbol in self.strategies:
            signal = self.strategies[symbol].on_bar(bar)
            
            if signal:
                self._process_signal(signal, bar)
    
    def _process_signal(self, signal: SignalEvent, bar: BarEvent):
        """Process trading signal"""
        symbol = signal.symbol
        self.stats['signals_generated'][symbol] += 1
        
        direction = "LONG" if signal.signal_strength > 0 else "SHORT"
        signal_time = datetime.now(UTC)
        
        logger.info(f"🎯 SIGNAL: {symbol} {direction} @ {bar.close:.5f} | Strength: {signal.signal_strength:.2f}")
        
        # Check risk limits
        allowed, reason = self._check_risk_limits(symbol)
        if not allowed:
            logger.warning(f"⛔ Signal BLOCKED: {reason}")
            self.db.log_event(
                self.session_id,
                'SIGNAL_BLOCKED',
                f'{symbol} {direction} blocked: {reason}',
                'WARNING'
            )
            return
        
        # Check if already in position
        if symbol in self.open_positions:
            logger.warning(f"⛔ Already in {symbol} position, skipping signal")
            return
        
        # Calculate position size
        position_size = self._calculate_position_size(symbol, bar.close)
        
        # Create order
        side = OrderSide.BUY if signal.signal_strength > 0 else OrderSide.SELL
        order = OrderEvent(
            symbol=symbol,
            order_type=OrderType.MARKET,
            side=side,
            quantity=position_size
        )
        
        # Log signal to database
        self.db.log_signal(
            session_id=self.session_id,
            instrument=symbol,
            signal_type=direction,
            signal_strength=signal.signal_strength,
            price=bar.close,
            metadata={
                'strategy': signal.strategy_name,
                'timestamp': bar.timestamp.isoformat(),
                'signal_time': signal_time.isoformat()
            }
        )
        
        # Execute order
        order_send_time = datetime.now(UTC)
        if self.mode == 'paper':
            # Paper trading: simulate instant fill
            self._simulate_fill(order, bar, signal_time, order_send_time)
        elif self.mode == 'live':
            # Live trading: send real order
            self._send_order(order, bar, signal_time, order_send_time)
        
        self.stats['orders_placed'][symbol] += 1
    
    def _simulate_fill(self, order: OrderEvent, bar: BarEvent, signal_time: datetime, order_send_time: datetime):
        """Simulate order fill for paper trading"""
        fill_time = datetime.now(UTC)
        
        # Apply slippage using centralized model
        fill_price = self._apply_slippage(bar.close, order.side, order.symbol, is_exit=False)
        
        # Create fill event
        fill = FillEvent(
            order_id=f"PAPER_{int(time.time()*1000)}",
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            fill_price=fill_price,
            commission=0.0,
            slippage=abs(fill_price - bar.close) * order.quantity
        )
        
        logger.info(f"📝 PAPER FILL: {order.symbol} {order.side.name} {order.quantity} @ {fill_price:.5f}")
        
        # Calculate latency
        signal_to_fill = (fill_time - signal_time).total_seconds() * 1000  # ms
        
        self._process_fill(fill, bar.timestamp, signal_time, order_send_time, fill_time)
    
    def _send_order(self, order: OrderEvent, bar: BarEvent, signal_time: datetime, order_send_time: datetime):
        """Send real order to broker via FIX"""
        if not self.fix_client or not self.fix_client.is_trade_logged_in:
            logger.error("❌ Cannot send order: Not connected to trade server")
            return
        
        try:
            # Send NewOrderSingle via FIX
            cl_ord_id = self.fix_client.send_market_order(
                symbol=order.symbol,
                side='1' if order.side == OrderSide.BUY else '2',
                quantity=order.quantity
            )
            
            if cl_ord_id:
                self.pending_orders[cl_ord_id] = {
                    'order': order,
                    'timestamp': bar.timestamp,
                    'signal_time': signal_time,
                    'order_send_time': order_send_time,
                    'status': 'PENDING'
                }
                logger.info(f"📤 Order sent: {cl_ord_id}")
            else:
                logger.error("❌ Failed to send order")
                
        except Exception as e:
            logger.error(f"❌ Order send failed: {e}", exc_info=True)
    
    def _on_execution_report(self, fields: Dict[str, str]):
        """Callback for FIX execution reports"""
        try:
            report = self.fix_client.parse_execution_report(fields)
            
            exec_type = report['exec_type']
            ord_status = report['ord_status']
            cl_ord_id = report['cl_ord_id']
            fill_time = datetime.now(UTC)
            
            logger.info(f"📬 ExecutionReport: {cl_ord_id} | Type={exec_type} | Status={ord_status}")
            
            if exec_type == '2' or ord_status == '2':  # Filled
                fill = FillEvent(
                    order_id=cl_ord_id,
                    symbol=report['symbol'],
                    side=OrderSide.BUY if report['side'] == '1' else OrderSide.SELL,
                    quantity=int(report['cum_qty']),
                    fill_price=report['price'],
                    commission=0.0,
                    slippage=0.0
                )
                
                # Get timing data
                timestamp = datetime.now(UTC)
                signal_time = timestamp
                order_send_time = timestamp
                if cl_ord_id in self.pending_orders:
                    pending = self.pending_orders[cl_ord_id]
                    timestamp = pending['timestamp']
                    signal_time = pending.get('signal_time', timestamp)
                    order_send_time = pending.get('order_send_time', timestamp)
                
                self._process_fill(fill, timestamp, signal_time, order_send_time, fill_time)
                
            elif exec_type == '8' or ord_status == '8':  # Rejected
                logger.error(f"❌ Order REJECTED: {report['text']}")
                if cl_ord_id in self.pending_orders:
                    del self.pending_orders[cl_ord_id]
                    
        except Exception as e:
            logger.error(f"❌ Error processing execution report: {e}", exc_info=True)
    
    def _process_fill(self, fill: FillEvent, entry_time: datetime, 
                     signal_time: datetime, order_send_time: datetime, fill_time: datetime):
        """Process filled order"""
        symbol = fill.symbol
        self.stats['fills_received'][symbol] += 1
        
        # Calculate latency metrics
        signal_to_order = (order_send_time - signal_time).total_seconds() * 1000
        order_to_fill = (fill_time - order_send_time).total_seconds() * 1000
        total_latency = (fill_time - signal_time).total_seconds() * 1000
        
        logger.info(f"✅ FILL: {symbol} {fill.side.name} {fill.quantity} @ {fill.fill_price:.5f}")
        logger.info(f"   Latency: Signal→Order {signal_to_order:.0f}ms, Order→Fill {order_to_fill:.0f}ms, Total {total_latency:.0f}ms")
        
        # Calculate stop loss and take profit levels
        pip_value = 0.01 if 'JPY' in symbol else 0.0001
        
        if fill.side == OrderSide.BUY:
            stop_loss = fill.fill_price - (self.exit_params['stop_loss_pips'] * pip_value)
            profit_trigger = fill.fill_price + (self.exit_params['profit_trigger_pips'] * pip_value)
            best_price = fill.fill_price  # Initialize to entry price
        else:
            stop_loss = fill.fill_price + (self.exit_params['stop_loss_pips'] * pip_value)
            profit_trigger = fill.fill_price - (self.exit_params['profit_trigger_pips'] * pip_value)
            best_price = fill.fill_price  # Initialize to entry price
        
        # Track position
        self.open_positions[symbol] = {
            'order_id': fill.order_id,
            'side': fill.side,
            'quantity': fill.quantity,
            'entry_price': fill.fill_price,
            'entry_time': entry_time,
            'stop_loss': stop_loss,
            'profit_trigger': profit_trigger,
            'trailing_active': False,
            'best_price': best_price,  # Track best price for trailing stop
            'bars_held': 0
        }
        
        # Log to database
        self.db.log_order(
            session_id=self.session_id,
            instrument=symbol,
            order_type=fill.side.name,
            quantity=fill.quantity,
            price=fill.fill_price,
            status='FILLED',
            metadata={
                'order_id': fill.order_id,
                'entry_time': entry_time.isoformat(),
                'stop_loss': stop_loss,
                'profit_trigger': profit_trigger,
                'latency_signal_to_order_ms': signal_to_order,
                'latency_order_to_fill_ms': order_to_fill,
                'latency_total_ms': total_latency
            }
        )
        
        logger.info(f"   SL: {stop_loss:.5f} | Profit Trigger: {profit_trigger:.5f}")
    
    def _check_risk_limits(self, symbol: str) -> tuple:
        """Check if trading is allowed"""
        # Daily reset
        today = datetime.now(UTC).date()
        if today != self.last_reset_date:
            logger.info("📅 New trading day - resetting counters")
            self.daily_pnl = 0.0
            self.trades_today = 0
            self.last_reset_date = today
        
        # Check drawdown (includes unrealized PnL)
        current_dd_pct = (self.peak_equity - self.current_equity) / self.peak_equity
        if current_dd_pct >= self.risk_limits['max_drawdown_pct']:
            return False, f"Max drawdown {current_dd_pct*100:.1f}% >= {self.risk_limits['max_drawdown_pct']*100:.0f}%"
        
        # Check consecutive losses
        max_consec = self.risk_limits['halt_on_consecutive_losses'].get(symbol, 10)
        if self.consecutive_losses[symbol] >= max_consec:
            return False, f"Consecutive losses {self.consecutive_losses[symbol]} >= {max_consec}"
        
        # Check daily loss
        if self.daily_pnl <= -self.risk_limits['max_daily_loss']:
            return False, f"Daily loss ${abs(self.daily_pnl):.0f} >= ${self.risk_limits['max_daily_loss']:.0f}"
        
        # Check daily trade limit
        if self.trades_today >= self.risk_limits['max_trades_per_day']:
            return False, f"Daily trade limit {self.trades_today} >= {self.risk_limits['max_trades_per_day']}"
        
        return True, ""
    
    def _calculate_position_size(self, symbol: str, price: float) -> int:
        """Calculate position size based on risk percentage"""
        # Calculate position size based on risk amount and stop distance
        risk_amount = self.current_equity * self.risk_per_trade_pct
        stop_pips = self.exit_params['stop_loss_pips']
        pip_value = 0.01 if 'JPY' in symbol else 0.0001
        
        # Position size = risk amount / (stop distance in price units)
        # For forex: 1 pip = pip_value, so stop_distance = stop_pips * pip_value
        # Position size calculation: risk_amount / stop_distance
        position_size = int(risk_amount / (stop_pips * pip_value))
        
        # Clamp to maximum allowed
        max_size = self.risk_limits['max_position_size_units']
        position_size = min(position_size, max_size)
        
        # Ensure minimum viable position
        position_size = max(position_size, 1000)  # Minimum 0.01 lot
        
        logger.info(f"Position sizing: Risk ${risk_amount:.2f}, Stop {stop_pips} pips → {position_size} units")
        
        return position_size
    
    def _apply_slippage(self, price: float, side: OrderSide, symbol: str, is_exit: bool = False) -> float:
        """
        Apply realistic slippage model.
        
        Args:
            price: Base price
            side: Order side
            symbol: Trading symbol
            is_exit: True if closing position, False if opening
            
        Returns:
            Price with slippage applied
        """
        pip_value = 0.01 if 'JPY' in symbol else 0.0001
        slippage_pips = 1.0
        
        if is_exit:
            # Exit (closing position)
            if side == OrderSide.BUY:
                # Closing LONG → selling → worse price (subtract)
                return price - (slippage_pips * pip_value)
            else:
                # Closing SHORT → buying → worse price (add)
                return price + (slippage_pips * pip_value)
        else:
            # Entry (opening position)
            if side == OrderSide.BUY:
                # Opening LONG → buying → worse price (add)
                return price + (slippage_pips * pip_value)
            else:
                # Opening SHORT → selling → worse price (subtract)
                return price - (slippage_pips * pip_value)
    
    def _calculate_pnl(self, symbol: str, side: OrderSide, entry_price: float, 
                      exit_price: float, quantity: int) -> float:
        """
        Calculate realistic Forex PnL.
        
        Args:
            symbol: Trading symbol
            side: Position side
            entry_price: Entry price
            exit_price: Exit price
            quantity: Position quantity in units
            
        Returns:
            PnL in account currency
        """
        # For forex, 1 unit = 1 base currency unit
        # PnL = price difference × quantity
        if side == OrderSide.BUY:
            pnl = (exit_price - entry_price) * quantity
        else:  # SHORT
            pnl = (entry_price - exit_price) * quantity
        
        return pnl
    
    def _on_position_report(self, positions: List[dict]):
        """
        Callback for position reconciliation on startup.
        Auto-populates internal state from broker positions.
        """
        logger.info(f"📊 Position report: {len(positions)} open positions")
        
        if not positions:
            logger.info("   No open positions to reconcile")
            return
        
        # Reconcile broker positions with internal state
        for pos in positions:
            logger.info(f"   Broker position: {pos}")
            
            # Extract position details (format depends on broker's FIX response)
            # Adjust field names based on actual FIX PositionReport format
            symbol = pos.get('symbol')
            quantity = pos.get('quantity', 0)
            side_str = pos.get('side')  # '1' = BUY, '2' = SELL
            avg_price = pos.get('avg_price', 0.0)
            
            if not symbol or quantity == 0:
                continue
            
            # Convert side
            if side_str == '1':
                side = OrderSide.BUY
            elif side_str == '2':
                side = OrderSide.SELL
            else:
                logger.warning(f"   Unknown side: {side_str}, skipping")
                continue
            
            # Populate position if not already tracked
            if symbol not in self.open_positions:
                logger.info(f"   Restoring {symbol} position from broker")
                
                # Calculate stops based on exit params
                pip_value = 0.01 if 'JPY' in symbol else 0.0001
                
                if side == OrderSide.BUY:
                    stop_loss = avg_price - (self.exit_params['stop_loss_pips'] * pip_value)
                    profit_trigger = avg_price + (self.exit_params['profit_trigger_pips'] * pip_value)
                    best_price = avg_price
                else:
                    stop_loss = avg_price + (self.exit_params['stop_loss_pips'] * pip_value)
                    profit_trigger = avg_price - (self.exit_params['profit_trigger_pips'] * pip_value)
                    best_price = avg_price
                
                self.open_positions[symbol] = {
                    'order_id': f"RESTORED_{int(time.time()*1000)}",
                    'side': side,
                    'quantity': quantity,
                    'entry_price': avg_price,
                    'entry_time': datetime.now(UTC),  # Unknown, use current time
                    'stop_loss': stop_loss,
                    'profit_trigger': profit_trigger,
                    'trailing_active': False,
                    'best_price': best_price,
                    'bars_held': 0
                }
                
                logger.info(f"   ✅ Restored: {symbol} {side.name} {quantity} @ {avg_price:.5f}")
            else:
                logger.info(f"   ✓ {symbol} position already tracked")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info("\n⚠️  Shutdown signal received")
        self.stop()
    
    def _monitor_positions(self, bar: BarEvent):
        """Monitor open positions for exit conditions and update mark-to-market equity"""
        symbol = bar.symbol
        
        # Calculate unrealized PnL for all positions
        total_unrealized = 0.0
        for sym, pos in self.open_positions.items():
            # Use current bar close if it's this symbol, else use last known price
            if sym == symbol:
                current_price = bar.close
            else:
                # Use entry price as proxy (ideally track last price per symbol)
                current_price = pos['entry_price']
            
            unrealized = self._calculate_pnl(
                sym, pos['side'], pos['entry_price'], current_price, pos['quantity']
            )
            total_unrealized += unrealized
        
        # Update current equity with mark-to-market
        self.current_equity = self.initial_capital + self.realized_pnl + total_unrealized
        
        # Update peak equity if new high
        if self.current_equity > self.peak_equity:
            self.peak_equity = self.current_equity
        
        # Check if max drawdown breached
        current_dd_pct = (self.peak_equity - self.current_equity) / self.peak_equity
        if current_dd_pct >= self.risk_limits['max_drawdown_pct']:
            self._halt_trading(f"Max drawdown {current_dd_pct*100:.1f}% breached")
            return
        
        # Check equity safety
        if self.current_equity <= 0:
            self._halt_trading("Equity <= 0")
            return
        
        # Now monitor the specific symbol's position
        if symbol not in self.open_positions:
            return
        
        pos = self.open_positions[symbol]
        pos['bars_held'] += 1
        
        # Get current price
        current_price = bar.close
        pip_value = 0.01 if 'JPY' in symbol else 0.0001
        
        # Calculate unrealized profit in pips
        if pos['side'] == OrderSide.BUY:
            profit_pips = (current_price - pos['entry_price']) / pip_value
            # Check stop loss
            if bar.low <= pos['stop_loss']:
                self._close_position(symbol, pos['stop_loss'], 'SL', bar.timestamp)
                return
        else:  # SHORT
            profit_pips = (pos['entry_price'] - current_price) / pip_value
            # Check stop loss
            if bar.high >= pos['stop_loss']:
                self._close_position(symbol, pos['stop_loss'], 'SL', bar.timestamp)
                return
        
        # Activate trailing stop when profit trigger reached
        if not pos['trailing_active'] and profit_pips >= self.exit_params['profit_trigger_pips']:
            pos['trailing_active'] = True
            logger.info(f"🎯 Trailing stop ACTIVATED for {symbol} (profit: {profit_pips:.1f} pips)")
        
        # Update trailing stop
        if pos['trailing_active']:
            trailing_dist = self.exit_params['trailing_distance_pips']
            
            if pos['side'] == OrderSide.BUY:
                # Update best price reached
                if bar.high > pos['best_price']:
                    pos['best_price'] = bar.high
                    new_trail = pos['best_price'] - (trailing_dist * pip_value)
                    pos['stop_loss'] = max(pos['stop_loss'], new_trail)
                    logger.info(f"📈 Trailing stop updated for {symbol}: {pos['stop_loss']:.5f}")
                
                # Check if trailing stop hit
                if bar.low <= pos['stop_loss']:
                    self._close_position(symbol, pos['stop_loss'], 'TRAIL', bar.timestamp)
                    return
            else:  # SHORT
                # Update best price reached
                if bar.low < pos['best_price']:
                    pos['best_price'] = bar.low
                    new_trail = pos['best_price'] + (trailing_dist * pip_value)
                    pos['stop_loss'] = min(pos['stop_loss'], new_trail)
                    logger.info(f"📉 Trailing stop updated for {symbol}: {pos['stop_loss']:.5f}")
                
                # Check if trailing stop hit
                if bar.high >= pos['stop_loss']:
                    self._close_position(symbol, pos['stop_loss'], 'TRAIL', bar.timestamp)
                    return
        
        # Check max hold time
        if pos['bars_held'] >= self.exit_params['max_hold_bars']:
            # Apply slippage using centralized model
            exit_price = self._apply_slippage(bar.close, pos['side'], symbol, is_exit=True)
            self._close_position(symbol, exit_price, 'TIME', bar.timestamp)
            return
    
    def _close_position(self, symbol: str, exit_price: float, reason: str, timestamp: datetime):
        """Close position and update accounting"""
        if symbol not in self.open_positions:
            logger.error(f"❌ Attempted to close non-existent {symbol} position")
            return
        
        pos = self.open_positions[symbol]
        
        # Calculate PnL using centralized helper
        pnl = self._calculate_pnl(symbol, pos['side'], pos['entry_price'], exit_price, pos['quantity'])
        
        # Calculate PnL in pips for logging
        pip_value = 0.01 if 'JPY' in symbol else 0.0001
        pnl_pips = pnl / (pip_value * pos['quantity'])
        
        # Update realized PnL (for mark-to-market calculation)
        self.realized_pnl += pnl
        
        # Update daily PnL and trade counter
        self.daily_pnl += pnl
        self.trades_today += 1
        
        # Update consecutive losses
        if pnl < 0:
            self.consecutive_losses[symbol] += 1
            logger.warning(f"⚠️  {symbol} consecutive losses: {self.consecutive_losses[symbol]}")
        else:
            self.consecutive_losses[symbol] = 0
        
        # Log exit with clean format
        logger.info(f"EXIT: {symbol} {pos['side'].name} {pos['quantity']} "
                   f"{pos['entry_price']:.5f} -> {exit_price:.5f} | "
                   f"PnL ${pnl:+,.2f} | {reason} | Held {pos['bars_held']} bars")
        
        # Log to database
        self.db.log_order(
            session_id=self.session_id,
            instrument=symbol,
            order_type=f"CLOSE_{pos['side'].name}",
            quantity=pos['quantity'],
            price=exit_price,
            status='CLOSED',
            metadata={
                'entry_price': pos['entry_price'],
                'entry_time': pos['entry_time'].isoformat(),
                'exit_time': timestamp.isoformat(),
                'exit_reason': reason,
                'pnl': pnl,
                'pnl_pips': pnl_pips,
                'bars_held': pos['bars_held']
            }
        )
        
        # Send close order in live mode
        if self.mode == 'live' and self.fix_client and self.fix_client.is_trade_logged_in:
            try:
                # Send opposite side order to close position
                close_side = '2' if pos['side'] == OrderSide.BUY else '1'  # Opposite
                cl_ord_id = self.fix_client.send_market_order(
                    symbol=symbol,
                    side=close_side,
                    quantity=pos['quantity']
                )
                if cl_ord_id:
                    logger.info(f"📤 Close order sent: {cl_ord_id}")
                else:
                    logger.error(f"❌ Failed to send close order for {symbol}")
            except Exception as e:
                logger.error(f"❌ Error sending close order: {e}", exc_info=True)
        
        # Remove from open positions
        del self.open_positions[symbol]
        
        # Recalculate equity (remove unrealized PnL for this closed position)
        total_unrealized = 0.0
        for sym, p in self.open_positions.items():
            unrealized = self._calculate_pnl(
                sym, p['side'], p['entry_price'], p['entry_price'], p['quantity']
            )
            total_unrealized += unrealized
        
        self.current_equity = self.initial_capital + self.realized_pnl + total_unrealized
        
        # Log equity update
        logger.info(f"💰 Equity: ${self.current_equity:,.2f} | Daily PnL: ${self.daily_pnl:+,.2f}")
    
    def _halt_trading(self, reason: str):
        """
        Immediately halt trading engine due to critical failure.
        
        Args:
            reason: Reason for halt
        """
        logger.error(f"🛑 CRITICAL HALT: {reason}")
        self.db.log_event(self.session_id, 'HALT', f'Trading halted: {reason}', 'CRITICAL')
        
        # Stop accepting new orders
        self.running = False
        
        # Close all open positions in live mode
        if self.mode == 'live' and self.open_positions:
            logger.info(f"⚠️  Closing {len(self.open_positions)} open positions...")
            for symbol in list(self.open_positions.keys()):
                pos = self.open_positions[symbol]
                # Use last known price (this is emergency close)
                self._close_position(symbol, pos['entry_price'], 'HALT', datetime.now(UTC))
        
        # Disconnect from FIX
        if self.fix_client:
            self.disconnect()
        
        logger.error(f"❌ Trading engine HALTED: {reason}")
    
    def run(self):
        """Main event loop"""
        logger.info("="*70)
        logger.info("🚀 STARTING LIVE EXHAUSTION PAPER TRADING")
        logger.info("="*70)
        logger.info(f"Mode: {self.mode.upper()}")
        logger.info(f"Symbols: {', '.join(self.symbols)}")
        logger.info(f"Capital: ${self.initial_capital:,.0f}")
        logger.info(f"Risk/trade: {self.risk_per_trade_pct*100:.1f}%")
        logger.info("="*70)
        
        # Connect to FIX
        if not self.connect():
            logger.error("❌ Failed to connect. Exiting.")
            return
        
        self.running = True
        self.stats['start_time'] = datetime.now(UTC)
        
        logger.info("✅ Engine running. Waiting for H1 bars...")
        logger.info("   (Press Ctrl+C to stop)")
        
        try:
            # Main loop - just keep alive, bar processing happens in callbacks
            while self.running:
                time.sleep(1)
                
                # Periodic status update
                if int(time.time()) % 300 == 0:  # Every 5 minutes
                    self._print_status()
                
        except KeyboardInterrupt:
            logger.info("\n⚠️  Keyboard interrupt received")
        finally:
            self.stop()
    
    def stop(self):
        """Stop trading engine"""
        if not self.running:
            return
        
        logger.info("🛑 Stopping trading engine...")
        self.running = False
        
        # Close any open positions (in live mode)
        if self.mode == 'live' and self.open_positions:
            logger.info(f"⚠️  Closing {len(self.open_positions)} open positions...")
            for symbol in list(self.open_positions.keys()):
                pos = self.open_positions[symbol]
                self._close_position(symbol, pos['entry_price'], 'SHUTDOWN', datetime.now(UTC))
        
        # Disconnect
        self.disconnect()
        
        # Final statistics
        self._print_final_summary()
        
        logger.info("✅ Trading engine stopped")
    
    def _print_status(self):
        """Print current status"""
        uptime = datetime.now(UTC) - self.stats['start_time'] if self.stats['start_time'] else timedelta(0)
        
        logger.info("\n" + "="*70)
        logger.info("STATUS UPDATE")
        logger.info("="*70)
        logger.info(f"Uptime: {uptime}")
        logger.info(f"Equity: ${self.current_equity:,.2f} (Realized: ${self.realized_pnl:+,.2f})")
        logger.info(f"Daily PnL: ${self.daily_pnl:+,.2f}")
        logger.info(f"Peak Equity: ${self.peak_equity:,.2f}")
        
        current_dd_pct = (self.peak_equity - self.current_equity) / self.peak_equity * 100
        logger.info(f"Drawdown: {current_dd_pct:.2f}%")
        
        for symbol in self.symbols:
            logger.info(f"\n{symbol}:")
            logger.info(f"  Bars: {self.stats['bars_processed'][symbol]}")
            logger.info(f"  Signals: {self.stats['signals_generated'][symbol]}")
            logger.info(f"  Orders: {self.stats['orders_placed'][symbol]}")
            logger.info(f"  Fills: {self.stats['fills_received'][symbol]}")
            logger.info(f"  Consec Losses: {self.consecutive_losses[symbol]}")
            
            if symbol in self.open_positions:
                pos = self.open_positions[symbol]
                unrealized = self._calculate_pnl(
                    symbol, pos['side'], pos['entry_price'], pos['entry_price'], pos['quantity']
                )
                pip_value = 0.01 if 'JPY' in symbol else 0.0001
                unrealized_pips = unrealized / (pip_value * pos['quantity'])
                logger.info(f"  🔥 OPEN: {pos['side'].name} {pos['quantity']} @ {pos['entry_price']:.5f} "
                          f"(Unrealized: {unrealized_pips:+.1f} pips)")
        
        logger.info("="*70)
    
    def _print_final_summary(self):
        """Print final summary"""
        logger.info("\n" + "="*70)
        logger.info("FINAL SUMMARY")
        logger.info("="*70)
        
        if self.stats['start_time']:
            runtime = datetime.now(UTC) - self.stats['start_time']
            logger.info(f"Runtime: {runtime}")
        
        logger.info(f"\nFinal Equity: ${self.current_equity:,.2f}")
        logger.info(f"Realized PnL: ${self.realized_pnl:+,.2f}")
        logger.info(f"Total PnL: ${self.current_equity - self.initial_capital:+,.2f}")
        logger.info(f"Peak Equity: ${self.peak_equity:,.2f}")
        
        for symbol in self.symbols:
            logger.info(f"\n{symbol} Statistics:")
            logger.info(f"  Bars Processed: {self.stats['bars_processed'][symbol]}")
            logger.info(f"  Signals Generated: {self.stats['signals_generated'][symbol]}")
            logger.info(f"  Orders Placed: {self.stats['orders_placed'][symbol]}")
            logger.info(f"  Fills Received: {self.stats['fills_received'][symbol]}")
        
        logger.info("="*70)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Live exhaustion+failure paper trading')
    parser.add_argument('--mode', type=str, choices=['paper', 'live'], default='paper',
                       help='Trading mode: paper (simulate) or live (real orders)')
    parser.add_argument('--symbols', type=str, default='NZDJPY,GBPUSD',
                       help='Comma-separated list of symbols')
    parser.add_argument('--capital', type=float, default=100000.0,
                       help='Initial capital')
    
    args = parser.parse_args()
    
    symbols = [s.strip() for s in args.symbols.split(',')]
    
    # Create and run trader
    trader = LiveExhaustionTrader(
        symbols=symbols,
        mode=args.mode,
        initial_capital=args.capital
    )
    
    trader.run()


if __name__ == '__main__':
    main()
