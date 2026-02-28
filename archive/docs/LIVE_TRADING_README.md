# FX Live Trading System - Complete Implementation

## 🎯 System Overview

A production-ready automated FX trading system with:

- **Event-driven architecture** for real-time execution
- **Paper trading simulator** for safe testing
- **FIX protocol support** for Pepperstone cTrader
- **Risk management** with kill switches
- **Portfolio tracking** with PnL calculation
- **Strategy framework** for custom algorithms

---

## ✅ Implementation Status

### Completed Components

| Component          | Status | File                              | Description                            |
| ------------------ | ------ | --------------------------------- | -------------------------------------- |
| **Event System**   | ✅     | `src/events/`                     | Thread-safe event queue, 5 event types |
| **Paper Trading**  | ✅     | `src/execution/simulator.py`      | Simulates fills with realistic costs   |
| **Strategies**     | ✅     | `src/strategies/`                 | BaseStrategy + 2 implementations       |
| **Portfolio**      | ✅     | `src/portfolio/portfolio.py`      | Real-time position tracking            |
| **Risk Manager**   | ✅     | `src/risk/risk_manager.py`        | Pre-trade validation, limits           |
| **FIX Client**     | ✅     | `src/execution/fix_client.py`     | Session management (simplefix)         |
| **Trading Engine** | ✅     | `src/execution/trading_engine.py` | Main orchestration                     |
| **Configuration**  | ✅     | `config/brokers/`                 | Pepperstone credentials                |
| **Tests**          | ✅     | `tests/test_live_system.py`       | Integration tests                      |
| **Examples**       | ✅     | `examples/*.py`                   | 3 demo scripts                         |

### Pending (Optional Enhancements)

- [ ] FIX Market Data Handler (real-time tick aggregation)
- [ ] Full Pepperstone FIX adapter (order execution via FIX)
- [ ] Monitoring dashboard (live metrics, alerts)
- [ ] Database persistence (trade history, state recovery)
- [ ] Multi-strategy support (run multiple strategies simultaneously)

---

## 🚀 Quick Start

### 1. Installation

```bash
cd /home/ghost/fx-quant-research

# Install dependencies
pip install -r requirements.txt

# Install FIX library (choose one)
pip install simplefix  # Recommended for Kali Linux
# OR
pip install quickfix-python  # More features, harder to install
```

### 2. Configuration

Edit `config/brokers/pepperstone_fix.yaml`:

```yaml
trading:
  paper_trading: true # ← Keep true for testing
  live_trading: false # ← Enable only after validation
  initial_capital: 100000.0

risk:
  max_drawdown_pct: 15.0 # Kill switch
  max_daily_loss_pct: 5.0
```

### 3. Run Tests

```bash
# Test complete system
python tests/test_live_system.py

# Or use pytest
pytest tests/test_live_system.py -v
```

### 4. Run Demo

```bash
# Paper trading demo (simple)
python examples/paper_trading_demo.py

# Complete trading engine demo
python examples/trading_engine_demo.py
```

---

## 📋 Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     Trading Engine                            │
│  ┌────────────────────────────────────────────────────────┐  │
│  │          Event Queue (Thread-Safe FIFO)                 │  │
│  └────────────────────────────────────────────────────────┘  │
│         ↓              ↓              ↓              ↓        │
│  ┌──────────┐   ┌──────────┐   ┌─────────┐   ┌──────────┐  │
│  │ Market   │   │ Strategy │   │  Risk   │   │ Executor │  │
│  │ Data     │→  │ (Signals)│→  │ Manager │→  │(Sim/FIX) │  │
│  └──────────┘   └──────────┘   └─────────┘   └──────────┘  │
│       ↓              ↓               ↓              ↓        │
│   TickEvent    SignalEvent     OrderEvent     FillEvent     │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │       Portfolio (Positions, Cash, PnL, Equity)          │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

---

## 📊 Event Flow

```
1. Market Data → TickEvent → Price Update
                ↓
2. Bar Completed → BarEvent → Strategy
                               ↓
3. Signal Generated → SignalEvent → Risk Validation
                                    ↓
4. Risk Approved → OrderEvent → Execution (Sim or FIX)
                                ↓
5. Order Filled → FillEvent → Portfolio Update
                              ↓
6. Position/Cash Updated → Equity Recalculated
```

---

## 🛡️ Safety Features

### Risk Limits (Enforced Pre-Trade)

| Limit                  | Default       | Configured In                         |
| ---------------------- | ------------- | ------------------------------------- |
| Max Drawdown           | 15%           | `config/brokers/pepperstone_fix.yaml` |
| Max Daily Loss         | 5%            | Same                                  |
| Max Position Size      | 100,000 units | Same                                  |
| Max Exposure           | 2x capital    | Same                                  |
| Stop-Loss Min Distance | 10 pips       | Same                                  |
| Max Orders/Day         | 50            | Same                                  |

### Kill Switches

1. **Drawdown Breached**: Halts all trading if equity drops >15% from peak
2. **Daily Loss Limit**: Stops trading for the day if daily loss >5%
3. **Risk Validation Failed**: Rejects orders that violate limits
4. **Manual Override**: `engine.risk_manager.resume_trading()` required

### Paper Trading Mode

- **Default**: All orders simulated (no real broker connection)
- **Safety**: Zero financial risk during testing
- **Realism**: Simulates slippage, commission, delays matching backtest

---

## 📈 Strategy Examples

### Threshold Strategy (SMA Crossover)

```python
from src.strategies import ThresholdStrategy

strategy = ThresholdStrategy(
    symbols=['EURUSD', 'GBPUSD'],
    config={
        'sma_short': 20,
        'sma_long': 50,
        'threshold_long': 0.01,   # 1% crossover
        'threshold_short': -0.01,
        'position_long': 1.0,
        'position_short': -1.0,
    }
)
```

### Custom Strategy

```python
from src.strategies import BaseStrategy

class MyStrategy(BaseStrategy):
    def calculate_signal(self, symbol: str) -> Optional[float]:
        closes = self.get_close_prices(symbol, n=20)

        # Your logic here
        if len(closes) < 20:
            return None

        # Return signal: -1.0 to +1.0 or None
        return 0.5 if closes[-1] > closes[-20] else None
```

---

## 🔌 FIX Connection (Real Market Data)

### Pepperstone cTrader Credentials

Your configuration (`config/brokers/pepperstone_fix.yaml`):

- **Account**: demo.pepperstone.5227001
- **Price Connection**: demo-us-eqx-01.p.c-trader.com:5211 (SSL)
- **Trade Connection**: demo-us-eqx-01.p.c-trader.com:5212 (SSL)
- **Protocol**: FIX 4.4

### Test Connection

```python
from src.execution.fix_client import FIXSessionManager

# Initialize
fix = FIXSessionManager('config/brokers/pepperstone_fix.yaml')

# Connect
success = fix.connect_all(
    price_handler=your_price_callback,
    trade_handler=your_trade_callback
)

if success:
    print("✓ Connected to Pepperstone FIX")
    # Subscribe to market data, send orders, etc.

# Disconnect when done
fix.disconnect_all()
```

---

## 📝 Usage Examples

### Simple Paper Trading

```python
from src.execution.trading_engine import TradingEngine
from src.strategies import ThresholdStrategy

# Create strategy
strategy = ThresholdStrategy(symbols=['EURUSD'], config={...})

# Create engine (paper trading by default)
engine = TradingEngine(
    config_path='config/brokers/pepperstone_fix.yaml',
    strategy=strategy
)

# Start
engine.start()

# Feed market data (bars)
# engine.inject_bar(bar)  # Manual injection
# OR connect to FIX for real-time data

# Stop (prints statistics)
engine.stop()
```

### With Risk Monitoring

```python
# Check risk status
risk_status = engine.risk_manager.get_risk_status()
print(f"Drawdown: {risk_status['current_drawdown_pct']:.2f}%")
print(f"Halted: {risk_status['trading_halted']}")

# Manual halt
if some_condition:
    engine.risk_manager._halt_trading("Manual intervention")

# Resume
engine.risk_manager.resume_trading()
```

---

## 🧪 Testing

### Run All Tests

```bash
# System tests
python tests/test_live_system.py

# Original backtest tests
pytest tests/test_backtest.py -v

# End-to-end tests
pytest tests/test_end_to_end.py -v
```

### Test Coverage

- ✅ Event queue thread-safety
- ✅ Portfolio position tracking
- ✅ Risk limit enforcement
- ✅ Strategy signal generation
- ✅ Paper trading execution
- ✅ Trading engine integration
- ⏸️ FIX protocol (requires broker connection)

---

## 🚦 Deployment Checklist

### Before Live Trading

- [ ] **Week 1**: Run paper trading continuously (no crashes)
- [ ] **Week 2**: Validate metrics match backtest (Sharpe, drawdown)
- [ ] **Test**: Manually trigger 15% drawdown (verify kill switch)
- [ ] **Test**: Breach daily loss limit (verify trading halts)
- [ ] **Test**: Send extreme order (verify risk rejection)
- [ ] **Review**: Check all trade logs for anomalies
- [ ] **Compare**: Paper trading vs backtest results (< 2% divergence)
- [ ] **FIX**: Test real connection to Pepperstone demo
- [ ] **Monitor**: Slippage stays < 2 pips for 20+ trades

### Enable Live Trading

```yaml
# config/brokers/pepperstone_fix.yaml
trading:
  paper_trading: false # ← Disable simulator
  live_trading: true # ← Enable real orders
```

**⚠️ WARNING**: Live trading uses real money. Start with minimum position sizes.

---

## 📄 Key Files

| File                                  | Purpose                                       |
| ------------------------------------- | --------------------------------------------- |
| `src/events/`                         | Event system (Tick, Bar, Signal, Order, Fill) |
| `src/execution/simulator.py`          | Paper trading engine                          |
| `src/execution/fix_client.py`         | FIX protocol session manager                  |
| `src/execution/trading_engine.py`     | Main orchestration                            |
| `src/strategies/base_strategy.py`     | Custom strategy base class                    |
| `src/strategies/strategies.py`        | Pre-built strategies                          |
| `src/portfolio/portfolio.py`          | Position/PnL tracking                         |
| `src/risk/risk_manager.py`            | Risk limits, validation                       |
| `config/brokers/pepperstone_fix.yaml` | Credentials, settings                         |
| `examples/trading_engine_demo.py`     | Complete demo                                 |
| `tests/test_live_system.py`           | Integration tests                             |

---

## 🐛 Troubleshooting

### `ImportError: No module named 'simplefix'`

```bash
pip install simplefix
```

### `FIX connection fails`

- Check credentials in `config/brokers/pepperstone_fix.yaml`
- Verify Pepperstone demo account is active
- Test with `openssl s_client -connect demo-us-eqx-01.p.c-trader.com:5211`

### `Risk manager rejects all orders`

- Check `risk_status['trading_halted']`
- Verify equity hasn't breached drawdown limit
- Call `engine.risk_manager.resume_trading()` if needed

### `No trades executing in demo`

- Verify `paper_trading: true` in config
- Check strategy is generating signals (low thresholds)
- Ensure enough bars fed to strategy (need >SMA period)

---

## 📞 Support

- **Pepperstone cTrader FIX Docs**: Contact Pepperstone support
- **FIX Protocol**: http://www.fixprotocol.org/
- **simplefix Library**: https://github.com/da4089/simplefix
- **Project Issues**: Document in `docs/` folder

---

## 🎓 Next Steps

1. **Install**: `pip install simplefix`
2. **Test**: `python tests/test_live_system.py`
3. **Demo**: `python examples/trading_engine_demo.py`
4. **Connect**: Test FIX connection to Pepperstone demo
5. **Paper Trade**: Run for 1 week continuously
6. **Validate**: Compare metrics vs backtest
7. **Go Live**: Enable live trading (with caution!)

---

**Status**: ✅ Complete and ready for paper trading  
**Last Updated**: 2026-02-24  
**Version**: 1.0
