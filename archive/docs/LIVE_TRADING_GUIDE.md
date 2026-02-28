# Complete Guide: FIX API Live Trading Implementation

This guide shows you how to use the newly implemented paper trading infrastructure and proceed with FIX integration.

---

## Part 1: Installation & Testing (Do This First)

### Step 1: Install Dependencies

```bash
cd /home/ghost/fx-quant-research

# Try QuickFIX first (may need system packages on Kali)
sudo apt-get update
sudo apt-get install -y libquickfix-dev python3-dev
pip install quickfix-python

# If QuickFIX fails, use simplefix (simpler but adequate)
pip install simplefix

# Install other dependencies
pip install -r requirements.txt
```

### Step 2: Verify Installation

```bash
# Check if quickfix installed
python -c "import quickfix; print('QuickFIX:', quickfix.VERSION)"

# If quickfix fails, verify simplefix
python -c "import simplefix; print('SimpleFIX: OK')"
```

### Step 3: Test Paper Trading Infrastructure

```bash
# Run the demo (uses synthetic data, no broker connection)
python examples/paper_trading_demo.py
```

**Expected output:**

- Portfolio initialized with $100,000
- Strategy generates signals (may be zero if data doesn't trigger thresholds)
- No errors or crashes
- Final equity shown

### Step 4: Test Individual Components

```python
# Test event system
from src.events import EventQueue, TickEvent

queue = EventQueue()
tick = TickEvent('EURUSD', bid=1.08450, ask=1.08452)
queue.put(tick)
event = queue.get()
print(event)  # Should print TickEvent
```

```python
# Test portfolio
from src.portfolio import Portfolio
from src.events import FillEvent, OrderSide
from datetime import datetime

portfolio = Portfolio(initial_capital=100000)
fill = FillEvent(
    order_id='TEST123',
    symbol='EURUSD',
    side=OrderSide.BUY,
    quantity=10000,
    fill_price=1.08500,
    commission=0.0,
    slippage=0.0,
    timestamp=datetime.now()
)
portfolio.on_fill(fill)
print(portfolio)  # Should show position
```

---

## Part 2: What's Been Built

### ✅ Core Components (Ready to Use)

1. **Event System** (`src/events/`)
   - All event types defined
   - Thread-safe queue
   - Ready for async processing

2. **Paper Trading Simulator** (`src/execution/simulator.py`)
   - Simulates fills with realistic costs
   - No broker connection needed
   - Safe for testing strategies

3. **Strategy Framework** (`src/strategies/`)
   - BaseStrategy class (extend this for custom strategies)
   - ThresholdStrategy (SMA crossover)
   - MomentumStrategy (momentum-based)

4. **Portfolio Manager** (`src/portfolio/portfolio.py`)
   - Tracks positions and PnL in real-time
   - Handles position reversals and pyramiding
   - Generates equity curve

5. **Configuration** (`config/brokers/pepperstone_fix.yaml`)
   - Your Pepperstone credentials pre-configured
   - Paper trading enabled by default
   - Risk limits from project_charter.md

### ⚠️ Missing Components (Need Implementation)

1. **Risk Management** (`src/risk/` - empty)
   - Pre-trade checks
   - Stop-loss management
   - Drawdown monitoring

2. **FIX Client** (`src/execution/fix_client.py` - not created)
   - FIX session management
   - Market data subscription
   - Order routing

3. **Trading Engine** (`src/execution/trading_engine.py` - not created)
   - Main event loop
   - Component orchestration
   - State persistence

4. **Monitoring** (`services/monitoring/` - empty)
   - Live metrics tracking
   - Alert system
   - Performance dashboard

---

## Part 3: Next Steps (Implementation Roadmap)

### Priority 1: Risk Management (Essential for Safety)

Create `src/risk/risk_manager.py`:

```python
"""
Risk Manager

Pre-trade checks before orders are sent.
"""

class RiskManager:
    def validate_order(self, order, portfolio):
        # Check position limits
        # Check max drawdown
        # Validate stop-loss distance
        # Return True/False
        pass
```

**Why first:** Safety before connecting to real market

### Priority 2: FIX Client (Enables Real Market Data)

Create `src/execution/fix_client.py`:

```python
"""
FIX Session Manager

Handles FIX protocol communication with Pepperstone.
"""

import quickfix as fix  # or simplefix

class FIXClient:
    def __init__(self, config_path):
        # Initialize FIX sessions (price + trade)
        pass

    def connect(self):
        # Logon to both sessions
        pass

    def subscribe_market_data(self, symbols):
        # Send MarketDataRequest
        pass

    def on_market_data(self, message):
        # Parse MarketDataSnapshot
        # Create TickEvent
        pass
```

**Implementation options:**

- **QuickFIX**: More complex but feature-complete (if installed)
- **SimpleFIX**: Simpler API, manual session management

### Priority 3: Market Data Aggregator

Create `src/execution/market_data.py`:

```python
"""
Market Data Handler

Aggregates ticks into bars for strategy consumption.
"""

class MarketDataHandler:
    def __init__(self, timeframe='4H'):
        self.current_bars = {}  # {symbol: partial bar}

    def on_tick(self, tick_event):
        # Aggregate into current bar
        # When bar completes, emit BarEvent
        pass
```

### Priority 4: Trading Engine (Ties Everything Together)

Create `src/execution/trading_engine.py`:

```python
"""
Main Trading Engine

Event loop coordinating all components.
"""

class TradingEngine:
    def __init__(self, config_path):
        self.event_queue = EventQueue()
        self.portfolio = Portfolio(100000)
        self.fix_client = FIXClient(config_path)
        self.strategy = ThresholdStrategy(...)
        self.risk_manager = RiskManager(...)
        self.simulator = PaperTradingSimulator(...)  # or FIX adapter

    def run(self):
        while self.running:
            event = self.event_queue.get(timeout=1.0)
            self.process_event(event)

    def process_event(self, event):
        if isinstance(event, BarEvent):
            signal = self.strategy.on_bar(event)
            if signal:
                order = self.create_order(signal)
                if self.risk_manager.validate_order(order):
                    self.simulator.execute_order(order)

        elif isinstance(event, FillEvent):
            self.portfolio.on_fill(event)
```

---

## Part 4: Testing Workflow

### Phase 1: Paper Trading with Synthetic Data (Current)

```bash
python examples/paper_trading_demo.py
```

- ✅ No broker connection
- ✅ Safe to iterate on strategies
- ✅ Validate event flow

### Phase 2: Paper Trading with Real FIX Data (Next)

1. Implement FIX client
2. Connect to Pepperstone demo (price feed only)
3. Run strategy with real ticks
4. Compare vs backtest

```bash
python examples/live_paper_trading.py  # TODO: create this
```

### Phase 3: Paper Trading with Full FIX (Almost Live)

1. Enable trade connection (still paper trading mode)
2. Orders simulated but market data real
3. Run for 1 week continuously
4. Validate Sharpe > 1.0, drawdown < 15%

### Phase 4: Live Trading (Final)

1. Set `paper_trading: false` in config
2. Set `live_trading: true` in config
3. Start with minimum position size
4. Monitor for slippage, execution quality
5. Gradually increase size

---

## Part 5: Configuration

### Paper Trading Mode (Current - Safe)

```yaml
# config/brokers/pepperstone_fix.yaml

trading:
  paper_trading: true # Simulator fills orders
  live_trading: false # No real broker connection
```

### Live Paper Trading (Next - Real Data, Simulated Fills)

```yaml
trading:
  paper_trading: true # Still simulator
  live_trading: false # But real market data via FIX
```

### Live Trading (Final - Real Money)

```yaml
trading:
  paper_trading: false # Real orders to broker
  live_trading: true # Full FIX integration

risk:
  max_drawdown_pct: 15.0 # Kill switch
  max_position_exposure: 2.0
```

---

## Part 6: Debugging

### Common Issues

**1. "ModuleNotFoundError: No module named 'quickfix'"**

```bash
# On Kali, may need:
sudo apt-get install libquickfix-dev
pip install quickfix-python

# Or use simplefix instead:
pip install simplefix
```

**2. "No trades in paper trading demo"**

- Synthetic data may not trigger strategy thresholds
- Adjust strategy parameters in demo (lower thresholds)
- Or use real historical data instead

**3. "Event queue empty"**

- Simulator delay may be too long
- Check `simulated_fill_delay_max` in config
- Increase `timeout` in `queue.get()`

### Logging

Enable detailed logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Check logs in: `logs/` directory (after creating trading engine)

---

## Part 7: Performance Validation

### Before Enabling Live Trading, Verify:

1. **Backtest Equivalence**
   - Run same strategy in backtest vs paper trading
   - Metrics should match within slippage tolerance
   - File: `tests/test_backtest_vs_live.py` (TODO)

2. **Risk Limits Work**
   - Manually trigger 15% drawdown
   - Verify trading stops automatically
   - File: `tests/test_risk_limits.py` (TODO)

3. **1-Bar Lag Enforced**
   - Signal from bar T executes at bar T+1
   - Check event timestamps in logs
   - File: `tests/test_signal_lag.py` (TODO)

4. **Continuous Uptime**
   - Paper trading runs 1+ week without crashes
   - Monitor with: `systemd` service or `screen` session

5. **FIX Connection Stability**
   - Reconnects on disconnect
   - No sequence number gaps
   - Check FIX logs: `logs/fix/`

---

## Part 8: Security Checklist

Before live trading:

- [ ] Credentials stored securely (not in git)
- [ ] Paper trading tested thoroughly (1+ week)
- [ ] Risk limits configured and tested
- [ ] Stop-loss placement validated (10+ pips)
- [ ] Max drawdown trigger tested (15%)
- [ ] Position size limits enforced
- [ ] Slippage monitoring in place (alert > 2 pips)
- [ ] FIX message logging enabled (audit trail)
- [ ] Emergency kill switch ready (manual override)
- [ ] Backtest results match live paper trading
- [ ] Sharpe > 1.0 confirmed on OOS data
- [ ] Can explain every trade (no black box)

---

## Part 9: Quick Reference

### File Structure

```
fx-quant-research/
├── config/
│   ├── brokers/
│   │   └── pepperstone_fix.yaml      ← Your credentials
│   └── fix_sessions.cfg              ← QuickFIX config
├── src/
│   ├── events/                       ← ✅ Event system
│   ├── execution/
│   │   ├── simulator.py              ← ✅ Paper trading
│   │   ├── fix_client.py             ← ⚠️ TODO
│   │   ├── market_data.py            ← ⚠️ TODO
│   │   └── trading_engine.py         ← ⚠️ TODO
│   ├── strategies/                   ← ✅ Strategy framework
│   ├── portfolio/                    ← ✅ Portfolio manager
│   └── risk/                         ← ⚠️ TODO
├── examples/
│   ├── paper_trading_demo.py         ← ✅ Test this
│   └── live_paper_trading.py         ← ⚠️ TODO (with FIX)
└── tests/                            ← ⚠️ Need unit tests
```

### Commands

```bash
# Test current implementation
python examples/paper_trading_demo.py

# Run backtest (compare vs live later)
python examples/backtest_demo.py

# Check config
cat config/brokers/pepperstone_fix.yaml

# View logs (after implementing logging)
tail -f logs/trading.log
tail -f logs/fix/FIX.4.4-*.messages.log
```

### API Examples

**Create custom strategy:**

```python
from src.strategies import BaseStrategy

class MyStrategy(BaseStrategy):
    def calculate_signal(self, symbol):
        closes = self.get_close_prices(symbol, n=20)
        if len(closes) < 20:
            return None

        # Your logic here
        if closes[-1] > np.mean(closes):
            return 1.0  # Long
        return -1.0  # Short
```

**Run paper trading:**

```python
from src.events import EventQueue
from src.execution.simulator import PaperTradingSimulator
from src.portfolio import Portfolio

queue = EventQueue()
portfolio = Portfolio(100000)
simulator = PaperTradingSimulator('config/brokers/pepperstone_fix.yaml', queue)
strategy = MyStrategy(['EURUSD'], {})

# Feed bars, get signals, execute, update portfolio
# See examples/paper_trading_demo.py for full workflow
```

---

## Part 10: Support & Resources

- **Project charter**: `docs/project_charter.md` (success criteria, risk triggers)
- **Backtest guide**: `docs/backtest_guide.md` (how backtest works)
- **FX microstructure**: `reports/fx_microstructure.md` (execution best practices)
- **Implementation status**: `IMPLEMENTATION_STATUS.md` (what's done)

**Pepperstone FIX API:**

- Check their website for FIX 4.4 specification
- Demo account: 5227001 (from your screenshot)
- Support: Contact Pepperstone if connection issues

**QuickFIX:**

- Docs: http://www.quickfixengine.org/
- Python: https://github.com/quickfix/quickfix
- SimpleFIX (alternative): https://github.com/da4089/simplefix

---

**You are here:** Phase 1 complete ✅  
**Next milestone:** Implement FIX client and risk management  
**End goal:** Automated FX trading with Sharpe > 1.0, drawdown < 15%
