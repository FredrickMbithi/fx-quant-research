"""
Main Trading Engine

Orchestrates all components for live FX trading:
- FIX connection management
- Event-driven execution loop
- Strategy management
- Risk enforcement
- Portfolio tracking
"""

import logging
import signal
import sys
import time
from typing import Dict, List, Optional
from datetime import datetime
from threading import Thread
import yaml
import queue

from ..events import EventQueue, EventType, BarEvent, SignalEvent, OrderEvent, FillEvent
from ..execution.simulator import PaperTradingSimulator
from ..strategies import BaseStrategy
from ..portfolio import Portfolio
from ..risk import RiskManager

logger = logging.getLogger(__name__)


class TradingEngine:
    """
    Main trading engine for live FX trading.
    
    Workflow:
    1. Initialize all components
    2. Start FIX connections (or use simulator in paper mode)
    3. Run event loop:
       - Process market data → BarEvents
       - Strategy generates SignalEvents
       - Risk validates signals
       - Create OrderEvents
       - Execute via simulator or FIX
       - Process FillEvents
       - Update portfolio
    4. Graceful shutdown on signal
    """
    
    def __init__(self, config_path: str, strategy: BaseStrategy):
        """
        Initialize trading engine.
        
        Args:
            config_path: Path to broker config YAML
            strategy: Strategy instance to use
        """
        self.config_path = config_path
        self.strategy = strategy
        
        # Load configuration
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        # Core components
        self.event_queue = EventQueue(maxsize=1000)
        self.portfolio = Portfolio(
            initial_capital=self.config.get('trading', {}).get('initial_capital', 100000.0)
        )
        self.risk_manager = RiskManager(config_path, self.portfolio)
        
        # Execution (paper trading or live)
        self.paper_trading = self.config.get('trading', {}).get('paper_trading', True)
        
        if self.paper_trading:
            logger.info("📄 Paper trading mode enabled")
            self.simulator = PaperTradingSimulator(config_path, self.event_queue)
            self.fix_client = None
        else:
            logger.warning("⚠️  LIVE TRADING MODE - Real money at risk!")
            self.simulator = None
            # FIX client would be initialized here
            # self.fix_client = FIXSessionManager(config_path)
            raise NotImplementedError("Live trading not implemented yet - use paper_trading: true")
        
        # Engine state
        self.running = False
        self.start_time = None
        
        # Statistics
        self.stats = {
            'events_processed': 0,
            'signals_generated': 0,
            'orders_placed': 0,
            'fills_received': 0,
        }
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info(f"Trading engine initialized: {strategy.name}")
        
        # Event loop thread
        self.event_thread: Optional[Thread] = None
    
    def start(self):
        """Start the trading engine in a background thread."""
        self.running = True
        self.start_time = datetime.utcnow()
        
        logger.info("=" * 70)
        logger.info("TRADING ENGINE STARTED")
        logger.info("=" * 70)
        logger.info(f"Strategy: {self.strategy.name}")
        logger.info(f"Symbols: {self.strategy.symbols}")
        logger.info(f"Mode: {'PAPER TRADING' if self.paper_trading else 'LIVE TRADING'}")
        logger.info(f"Initial capital: ${self.portfolio.initial_capital:,.2f}")
        logger.info("=" * 70)
        
        # In a real implementation, we would:
        # 1. Connect to FIX
        # 2. Subscribe to market data
        # 3. Wait for tick/bar events
        #
        # For now, this is a framework - market data would come from external source
        
        logger.info("Engine running... (Ctrl+C to stop)")
        logger.info("Waiting for market data events...")
        
        # Start event loop in background thread
        self.event_thread = Thread(target=self._run_event_loop, daemon=True)
        self.event_thread.start()
    
    def _run_event_loop(self):
        """Main event processing loop."""
        while self.running:
            try:
                # Get next event from queue (block with timeout)
                event = self.event_queue.get(block=True, timeout=1.0)
                
                # Process event
                self._process_event(event)
                self.stats['events_processed'] += 1
                
            except queue.Empty:
                # Timeout is normal, continue loop
                continue
                
            except Exception as e:
                logger.error(f"Error processing event: {e}", exc_info=True)
                continue
    
    def _process_event(self, event):
        """
        Process a single event.
        
        Args:
            event: Event to process
        """
        if event.event_type == EventType.TICK:
            # Update market prices
            if self.simulator:
                self.simulator.update_market_price(
                    event.symbol, event.bid, event.ask, event.timestamp
                )
            self.portfolio.update_market_price(event.symbol, event.bid, event.ask)
            
        elif event.event_type == EventType.BAR:
            self._process_bar(event)
            
        elif event.event_type == EventType.SIGNAL:
            self._process_signal(event)
            
        elif event.event_type == EventType.ORDER:
            self._process_order(event)
            
        elif event.event_type == EventType.FILL:
            self._process_fill(event)
    
    def _process_bar(self, bar: BarEvent):
        """
        Process bar event - run strategy.
        
        Args:
            bar: BarEvent
        """
        logger.info(f"Bar: {bar.symbol} {bar.timeframe} close={bar.close:.5f}")
        
        # Update market price
        mid = bar.close
        bid = mid - 0.00010  # 1 pip spread
        ask = mid + 0.00010
        
        if self.simulator:
            self.simulator.update_market_price(bar.symbol, bid, ask, bar.timestamp)
        self.portfolio.update_market_price(bar.symbol, bid, ask)
        
        # Strategy processes bar
        signal = self.strategy.on_bar(bar)
        
        if signal:
            # Put signal on queue for processing
            self.event_queue.put(signal)
            self.stats['signals_generated'] += 1
    
    def _process_signal(self, signal: SignalEvent):
        """
        Process signal event - validate and create order.
        
        Args:
            signal: SignalEvent
        """
        logger.info(f"Signal: {signal.symbol} strength={signal.signal_strength:+.2f}")
        
        # Validate signal through risk manager
        is_valid, reason = self.risk_manager.validate_signal(signal)
        if not is_valid:
            logger.warning(f"Signal rejected by risk manager: {reason}")
            return
        
        # Determine target position based on signal
        current_position = self.portfolio.get_position_quantity(signal.symbol)
        
        # Convert signal strength to position size
        # signal_strength is -1.0 to +1.0
        # Scale to position size (e.g., 10000 units = 0.1 lot per 1.0 signal)
        position_scale = self.config.get('trading', {}).get('default_position_size', 10000)
        target_position = signal.signal_strength * position_scale
        
        # Calculate position change needed
        position_change = target_position - current_position
        
        # Minimum trade size (100 units)
        if abs(position_change) < 100:
            logger.debug(f"Position change too small: {position_change:.0f} units")
            return
        
        # Create order
        from ..events import OrderType, OrderSide
        
        order = OrderEvent(
            symbol=signal.symbol,
            order_type=OrderType.MARKET,
            side=OrderSide.BUY if position_change > 0 else OrderSide.SELL,
            quantity=abs(position_change)
        )
        
        # Put order on queue
        self.event_queue.put(order)
    
    def _process_order(self, order: OrderEvent):
        """
        Process order event - validate and execute.
        
        Args:
            order: OrderEvent
        """
        logger.info(f"Order: {order.side.value} {order.quantity} {order.symbol}")
        
        # Get current market price
        if order.symbol not in self.portfolio.current_prices:
            logger.error(f"No market price for {order.symbol}")
            return
        
        market_data = self.portfolio.current_prices[order.symbol]
        current_price = (market_data['bid'] + market_data['ask']) / 2
        
        # Validate through risk manager
        is_valid, reason = self.risk_manager.validate_order(order, current_price)
        if not is_valid:
            logger.warning(f"Order rejected by risk manager: {reason}")
            return
        
        # Execute order
        if self.simulator:
            self.simulator.execute_order(order)
        else:
            # Would send to FIX broker here
            pass
        
        self.stats['orders_placed'] += 1
    
    def _process_fill(self, fill: FillEvent):
        """
        Process fill event - update portfolio.
        
        Args:
            fill: FillEvent
        """
        logger.info(f"Fill: {fill.side.value} {fill.quantity} {fill.symbol} @ {fill.fill_price:.5f}")
        
        # Update portfolio
        self.portfolio.on_fill(fill)
        
        # Update strategy position
        new_position = self.portfolio.get_position_quantity(fill.symbol)
        self.strategy.update_position(fill.symbol, new_position)
        
        self.stats['fills_received'] += 1
        
        # Log portfolio status
        logger.info(f"Portfolio: {self.portfolio}")
    
    def stop(self):
        """Stop the trading engine gracefully."""
        logger.info("Stopping trading engine...")
        self.running = False
        
        # Wait for event thread to finish (with timeout)
        if self.event_thread and self.event_thread.is_alive():
            self.event_thread.join(timeout=3.0)
        
        # Close any open positions (optional - comment out to keep positions)
        # self._close_all_positions()
        
        # Disconnect FIX if connected
        if self.fix_client:
            self.fix_client.disconnect_all()
        
        # Print final statistics
        self._print_statistics()
        
        logger.info("Trading engine stopped")
    
    def _signal_handler(self, signum, frame):
        """Handle SIGINT/SIGTERM for graceful shutdown."""
        logger.warning(f"\nReceived signal {signum}, initiating shutdown...")
        self.stop()
        sys.exit(0)
    
    def _print_statistics(self):
        """Print session statistics."""
        runtime = datetime.utcnow() - self.start_time if self.start_time else None
        
        print("\n" + "=" * 70)
        print("TRADING SESSION STATISTICS")
        print("=" * 70)
        print(f"Runtime:           {runtime}")
        print(f"Events processed:  {self.stats['events_processed']}")
        print(f"Signals generated: {self.stats['signals_generated']}")
        print(f"Orders placed:     {self.stats['orders_placed']}")
        print(f"Fills received:    {self.stats['fills_received']}")
        print()
        
        # Portfolio summary
        summary = self.portfolio.get_summary()
        print("PORTFOLIO SUMMARY")
        print("-" * 70)
        print(f"Initial capital:   ${summary['initial_capital']:,.2f}")
        print(f"Final equity:      ${summary['equity']:,.2f}")
        print(f"Total return:      {summary['total_return_pct']:+.2f}%")
        print(f"Cash:              ${summary['cash']:,.2f}")
        print(f"Positions value:   ${summary['positions_value']:,.2f}")
        print(f"Open positions:    {summary['num_open_positions']}")
        print(f"Total trades:      {summary['num_trades']}")
        print()
        
        # Risk metrics
        risk_status = self.risk_manager.get_risk_status()
        print("RISK METRICS")
        print("-" * 70)
        print(f"Trading halted:    {risk_status['trading_halted']}")
        if risk_status['halt_reason']:
            print(f"Halt reason:       {risk_status['halt_reason']}")
        print(f"Current drawdown:  {risk_status['current_drawdown_pct']:.2f}%")
        print(f"Max drawdown:      {risk_status['max_drawdown_pct']:.2f}%")
        print(f"Peak equity:       ${risk_status['peak_equity']:,.2f}")
        print("=" * 70)
    
    def inject_bar(self, bar: BarEvent):
        """
        Manually inject a bar event (for testing/backtesting).
        
        Args:
            bar: BarEvent to inject
        """
        self.event_queue.put(bar)
