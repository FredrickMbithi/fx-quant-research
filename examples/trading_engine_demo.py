"""
Complete Live Trading Demo

Demonstrates the full trading engine with strategy execution.
This simulates a complete trading session with synthetic data.
"""

import sys
import time
from datetime import datetime, timedelta
import random

sys.path.insert(0, '/home/ghost/fx-quant-research')

from src.events import BarEvent
from src.execution.trading_engine import TradingEngine
from src.strategies import ThresholdStrategy


def generate_bars(symbol: str, n_bars: int = 100):
    """Generate synthetic bars for testing."""
    bars = []
    current_price = 1.0850
    timestamp = datetime.utcnow() - timedelta(hours=4 * n_bars)
    
    for i in range(n_bars):
        # Random walk with trend
        trend = 0.00001 * (i - n_bars/2)  # Slight trend
        change = random.uniform(-0.0020, 0.0020) + trend
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
    """Run complete trading engine demo."""
    print("\n" + "=" * 70)
    print("COMPLETE TRADING ENGINE DEMO")
    print("=" * 70)
    print()
    
    # Initialize strategy
    strategy = ThresholdStrategy(
        symbols=['EURUSD'],
        config={
            'sma_short': 10,
            'sma_long': 20,
            'threshold_long': 0.003,
            'threshold_short': -0.003,
            'position_long': 1.0,
            'position_short': -1.0,
        }
    )
    
    # Initialize trading engine
    engine = TradingEngine(
        config_path='config/brokers/pepperstone_fix.yaml',
        strategy=strategy
    )
    
    # Start engine
    engine.start()
    
    print("\nGenerating market data...")
    print("-" * 70)
    
    # Generate and inject bars
    bars = generate_bars('EURUSD', n_bars=50)
    
    for i, bar in enumerate(bars):
        # Inject bar into event queue
        engine.inject_bar(bar)
        
        # Small delay to simulate real-time
        time.sleep(0.1)
        
        # Process events (would happen in background in real system)
        # The event loop will pick these up
        
        if (i + 1) % 10 == 0:
            print(f"Bar {i+1}/{len(bars)} - Equity: ${engine.portfolio.get_equity():,.2f}")
    
    # Wait for final fills to process
    print("\nWaiting for pending orders to fill...")
    time.sleep(3)
    
    # Stop engine (prints statistics)
    print()
    engine.stop()
    
    print("\n✓ Trading engine demo completed!")
    print("\nNext steps:")
    print("  1. pip install simplefix")
    print("  2. Test FIX connection to Pepperstone demo")
    print("  3. Run with real market data feed")
    print("  4. Monitor for 1 week (paper trading)")
    print("  5. Compare metrics vs backtest")
    print("  6. Enable live trading (with caution!)")
    print()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(0)
