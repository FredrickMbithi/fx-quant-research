"""
Paper Trading Demo

Demonstrates the complete paper trading pipeline without real market connection.
Tests: Events → Strategy → Portfolio → Simulator → Fill → Update

Run this to validate the infrastructure before connecting to FIX.
"""

import sys
import time
from datetime import datetime, timedelta
import random

# Add src to path
sys.path.insert(0, '/home/ghost/fx-quant-research')

from src.events import (
    EventQueue, BarEvent, OrderEvent, OrderType, OrderSide
)
from src.execution.simulator import PaperTradingSimulator
from src.strategies import ThresholdStrategy
from src.portfolio import Portfolio


def generate_synthetic_bars(symbol: str, n_bars: int = 100, start_price: float = 1.0850):
    """Generate synthetic OHLC bars for testing."""
    bars = []
    current_price = start_price
    timestamp = datetime.utcnow() - timedelta(days=n_bars)
    
    for i in range(n_bars):
        # Random walk
        change = random.uniform(-0.0020, 0.0020)  # +/- 20 pips
        current_price += change
        
        high = current_price + random.uniform(0, 0.0010)
        low = current_price - random.uniform(0, 0.0010)
        open_price = current_price + random.uniform(-0.0005, 0.0005)
        close = current_price
        
        bar = BarEvent(
            symbol=symbol,
            timeframe='4H',
            open_price=open_price,
            high=high,
            low=low,
            close=close,
            volume=random.randint(100, 1000),
            timestamp=timestamp
        )
        bars.append(bar)
        
        timestamp += timedelta(hours=4)
    
    return bars


def main():
    """Run paper trading demo."""
    print("=" * 70)
    print("PAPER TRADING DEMO")
    print("=" * 70)
    print()
    
    # Initialize components
    print("Initializing components...")
    event_queue = EventQueue()
    portfolio = Portfolio(initial_capital=100000.0)
    simulator = PaperTradingSimulator(
        'config/brokers/pepperstone_fix.yaml',
        event_queue
    )
    
    # Initialize strategy
    strategy = ThresholdStrategy(
        symbols=['EURUSD'],
        config={
            'sma_short': 10,
            'sma_long': 20,
            'threshold_long': 0.005,  # 0.5% crossover
            'threshold_short': -0.005,
            'position_long': 1.0,
            'position_short': -1.0,
        }
    )
    
    print(f"✓ Portfolio: ${portfolio.initial_capital:,.2f}")
    print(f"✓ Strategy: {strategy.name}")
    print(f"✓ Simulator: Paper trading enabled")
    print()
    
    # Generate synthetic bars
    print("Generating synthetic market data...")
    bars = generate_synthetic_bars('EURUSD', n_bars=50)
    print(f"✓ Generated {len(bars)} bars")
    print()
    
    # Simulate trading
    print("Running strategy...")
    print("-" * 70)
    
    for i, bar in enumerate(bars):
        # Update simulator and portfolio with current price
        mid_price = (bar.high + bar.low) / 2
        bid = mid_price - 0.00010  # 1 pip spread
        ask = mid_price + 0.00010
        
        simulator.update_market_price('EURUSD', bid, ask, bar.timestamp)
        portfolio.update_market_price('EURUSD', bid, ask)
        
        # Strategy processes bar and generates signal
        signal = strategy.on_bar(bar)
        
        if signal:
            print(f"\nBar {i+1}: Signal generated")
            print(f"  Price: {bar.close:.5f}")
            print(f"  Signal strength: {signal.signal_strength:+.2f}")
            
            # Determine order side and quantity based on signal
            current_position = portfolio.get_position_quantity('EURUSD')
            target_position = signal.signal_strength * 10000  # 0.1 lot per 1.0 signal
            
            # Calculate position change needed
            position_change = target_position - current_position
            
            if abs(position_change) > 100:  # Minimum 100 units to trade
                # Create order
                order = OrderEvent(
                    symbol='EURUSD',
                    order_type=OrderType.MARKET,
                    side=OrderSide.BUY if position_change > 0 else OrderSide.SELL,
                    quantity=abs(position_change)
                )
                
                print(f"  Order: {order.side.value} {order.quantity} units")
                
                # Execute order with simulator
                simulator.execute_order(order)
                
                # Wait for fill (check queue)
                try:
                    fill = event_queue.get(timeout=3.0)
                    print(f"  Fill: {fill.quantity} @ {fill.fill_price:.5f}")
                    print(f"  Commission: ${fill.commission:.2f}")
                    print(f"  Slippage: {fill.slippage:.2f} pips")
                    
                    # Update portfolio
                    portfolio.on_fill(fill)
                    
                    # Update strategy position
                    strategy.update_position('EURUSD', portfolio.get_position_quantity('EURUSD'))
                    
                    print(f"  Portfolio: {portfolio}")
                except Exception as e:
                    print(f"  Error getting fill: {e}")
        
        # Small delay to simulate real-time
        if i % 10 == 0 and i > 0:
            print(f"\n[Bar {i+1}/{len(bars)}] Equity: ${portfolio.get_equity():,.2f}")
    
    # Final results
    print()
    print("=" * 70)
    print("FINAL RESULTS")
    print("=" * 70)
    
    summary = portfolio.get_summary()
    print(f"Initial Capital:    ${summary['initial_capital']:,.2f}")
    print(f"Final Equity:       ${summary['equity']:,.2f}")
    print(f"Cash:               ${summary['cash']:,.2f}")
    print(f"Positions Value:    ${summary['positions_value']:,.2f}")
    print(f"Total Return:       {summary['total_return_pct']:+.2f}%")
    print(f"Number of Trades:   {summary['num_trades']}")
    print(f"Open Positions:     {summary['num_open_positions']}")
    print()
    
    # Show open positions
    if portfolio.positions:
        print("Open Positions:")
        for symbol, position in portfolio.positions.items():
            print(f"  {position}")
    
    print()
    print("✓ Paper trading demo completed successfully!")
    print()
    print("Next steps:")
    print("  1. Implement FIX client for real market data")
    print("  2. Add risk management layer")
    print("  3. Run paper trading for 1 week")
    print("  4. Compare vs backtest results")
    print("  5. Enable live trading (after validation)")


if __name__ == '__main__':
    main()
