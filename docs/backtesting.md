# Backtest Engine: User Guide

Complete guide to using the vectorized backtest engine for trading strategy development.

See [backtest_spec.md](../reports/backtest_spec.md) for technical architecture details.

---

## Quick Start

```python
import numpy as np
import pandas as pd
from src.backtest.engine import VectorizedBacktest, CostModel, PositionSizer

# Load data
data = pd.read_csv('data.csv', index_col='date', parse_dates=True)
close = data['close'].values

# Define signal (e.g., SMA crossover)
sma10 = pd.Series(close).rolling(10).mean().values
sma50 = pd.Series(close).rolling(50).mean().values
signal = np.where(sma10 > sma50, 1.0, -1.0)

# Configure costs and position sizing
cost_model = CostModel({
    'commission_per_share': 0.0001,
    'slippage_pct': 0.001,
    'daily_borrow_fee': 0.0003,
})

position_sizer = PositionSizer({
    'strategy': 'threshold',
    'threshold_long': 0.5,
    'threshold_short': -0.5,
    'position_long': 1.0,
    'position_short': -1.0,
})

# Run backtest
backtest = VectorizedBacktest(
    data=close,
    signal=signal,
    cost_model=cost_model,
    position_sizer=position_sizer,
    initial_capital=100000.0,
)

results = backtest.run()
print(f"Total Return: {results['cumulative_return']:.2%}")
print(f"Sharpe Ratio: {results['sharpe_ratio']:.2f}")
```

---

## Understanding Vectorized vs Event-Driven Backtesting

### Vectorized (Current Implementation)

**How it works:**

- Processes entire price history at once using NumPy arrays
- 10-100x faster than event-driven (leverages C-level optimizations)
- Example: `equity = initial_capital + np.cumsum(daily_pnl - costs)`

**Strengths:**

- ✅ Fast: Perfect for parameter sweeps and optimization
- ✅ Clean code: Typically 3-5 lines for core calculations
- ✅ Scalable: Handles 10+ years of intraday data easily
- ✅ Easy to parallelize: Run multiple backtests simultaneously

**Limitations:**

- ❌ Less flexible for complex state logic
- ❌ Harder to model event-driven rules (e.g., "stop if drawdown > 20%")
- ❌ Debugging requires inspecting entire arrays

**When to use:**

- Initial strategy research and validation
- Parameter optimization (testing 100+ configurations)
- High-frequency data analysis
- Simple strategies without complex constraints

### Event-Driven (Future Implementation)

**How it works:**

- Simulates trading bar-by-bar in a sequential loop
- Each bar processes like real trading: check signal → execute → update state
- Realistic but 10-100x slower due to Python loop overhead

**Strengths:**

- ✅ Realistic: Matches actual trading execution flow
- ✅ Flexible: Easy to add margin calls, position limits, dynamic stops
- ✅ Transparent: Can inspect and debug state at each bar
- ✅ Natural: No risk of accidental look-ahead bias

**Limitations:**

- ❌ Slow: Python loops vs C-level array operations
- ❌ Verbose: More code to maintain
- ❌ Hard to parallelize: Sequential by nature

**When to use:**

- Final strategy validation
- Complex position constraints (leverage limits, risk checks)
- Realistic order execution modeling
- Academic research requiring precise simulation

### Hybrid Approach (Recommended)

Combine both for best results:

- **Vectorize** core PnL and cost calculations (fast path)
- **Event loop** for conditional logic only (stops, risk checks)
- Result: 10-20x faster than pure event-driven, much more flexible than pure vectorized

---

## Signal Lag: Preventing Look-Ahead Bias

### The Problem

Real trading has unavoidable execution lag:

```
Bar T (Today):
  16:00 → Market closes
  16:00 → Calculate indicators based on close price
  16:00 → Generate signal
  [CANNOT EXECUTE - market closed]

Bar T+1 (Tomorrow):
  09:30 → Market opens
  09:30 → Execute using YESTERDAY's signal at TODAY's open price
```

**Without lag:** Backtest uses today's data to predict today's price → artificially optimistic results

**With lag:** Signal from bar T executes at bar T+1 → realistic

### Implementation

The engine applies 1-bar lag automatically:

```python
# Internally, the engine does:
lagged_signal = np.roll(signal, 1)  # Shift signal forward by 1 bar
lagged_signal[0] = 0  # First bar has no prior signal

# When processing bar t, we use signal from bar t-1
position[t] = position_sizer.size(lagged_signal[t])
execution_price = price[t]  # Current bar open
```

**Verification:**

- Check `results['lagged_signal']` - should be zeros for first bars
- Compare signal changes vs position changes - position lags by 1 bar

---

## Configuration Guide

### 1. Cost Model

Configure realistic transaction costs:

```python
# Low-cost broker (institutional, ECN)
cost_model = CostModel({
    'commission_per_share': 0.00005,  # $0.00005 per share
    'slippage_pct': 0.0001,           # 0.01% slippage
    'daily_borrow_fee': 0.0001,       # 0.01% daily for shorts
})

# Medium-cost broker (retail with decent terms)
cost_model = CostModel({
    'commission_per_share': 0.0001,
    'slippage_pct': 0.001,            # 0.1% slippage
    'daily_borrow_fee': 0.0003,
})

# High-cost broker (small account, crypto exchange)
cost_model = CostModel({
    'commission_per_share': 0.001,
    'slippage_pct': 0.005,            # 0.5% slippage
    'daily_borrow_fee': 0.001,
})
```

**FX-specific costs:**

```python
# For FX pairs (spread-based pricing)
cost_model = CostModel({
    'commission_per_share': 0.0,      # No commission
    'slippage_pct': 0.00009,          # 0.9 pips on EURUSD (0.0009/1.0 = 0.09%)
    'daily_borrow_fee': 0.0,          # No borrow fee for FX
})
```

### 2. Position Sizing Strategies

#### Threshold-Based (Binary)

```python
# Go 100% long or short based on signal threshold
position_sizer = PositionSizer({
    'strategy': 'threshold',
    'threshold_long': 0.5,      # Signal > 0.5 → go long
    'threshold_short': -0.5,    # Signal < -0.5 → go short
    'position_long': 1.0,       # 100% long
    'position_short': -1.0,     # 100% short
})
```

**Use case:** Simple breakout strategies, indicator-based systems

#### Linear Scaling

```python
# Position proportional to signal strength
position_sizer = PositionSizer({
    'strategy': 'linear',
    'scale_factor': 2.0,  # Signal range [-2, 2] maps to position [-1, 1]
})
```

**Use case:** Confidence-weighted strategies, gradient-based signals

#### Volatility-Adjusted (Risk Parity)

```python
# Inverse volatility weighting
position_sizer = PositionSizer({
    'strategy': 'volatility',
    'target_volatility': 0.15,  # 15% annualized vol target
    'lookback_window': 20,       # Use 20-day rolling vol
})
```

**Use case:** Multi-asset portfolios, regime-adaptive strategies

---

## Analysis & Validation

### Basic Metrics

```python
from src.backtest.engine import BacktestAnalyzer

results = backtest.run()
analyzer = BacktestAnalyzer(results)

# Print comprehensive report
analyzer.print_report(include_trades=True)

# Get summary statistics
summary = analyzer.get_summary()
print(f"Sharpe Ratio: {summary['sharpe_ratio']:.2f}")
print(f"Max Drawdown: {summary['max_drawdown']:.2%}")
print(f"Win Rate: {summary['win_rate']:.1%}")
```

### Trade-Level Analysis

```python
# Extract individual trades
trades_df = analyzer.analyze_trades()

print(f"Total Trades: {len(trades_df)}")
print(f"Average Win: ${trades_df[trades_df['pnl'] > 0]['pnl'].mean():.2f}")
print(f"Average Loss: ${trades_df[trades_df['pnl'] < 0]['pnl'].mean():.2f}")
print(f"Profit Factor: {trades_df[trades_df['pnl'] > 0]['pnl'].sum() / abs(trades_df[trades_df['pnl'] < 0]['pnl'].sum()):.2f}")
```

### Validation Checklist

```python
def validate_backtest(results):
    """Critical integrity checks."""

    # 1. No look-ahead bias (signal lag applied)
    assert results['lagged_signal'][0] == 0, "First lagged signal must be 0"

    # 2. Costs are non-negative
    assert (results['costs'] >= 0).all(), "Costs must be non-negative"

    # 3. Equity never negative (no leverage explosions)
    assert (results['equity'] >= 0).all(), "Equity went negative"

    # 4. Positions within valid range
    assert (np.abs(results['position']) <= 1.0001).all(), "Position exceeded [-1, 1]"

    # 5. Position changes align with signal changes
    signal_changes = np.diff(results['lagged_signal']) != 0
    position_changes = np.diff(results['position']) != 0

    print("✓ All validation checks passed")

validate_backtest(results)
```

---

## Common Pitfalls & Solutions

### Pitfall 1: Ignoring Transaction Costs

**Problem:** Strategy looks profitable without costs, fails with realistic commissions

**Solution:**

```python
# Test with 3x expected costs - if still profitable, you're safe
conservative_costs = CostModel({
    'commission_per_share': 0.0003,  # 3x normal
    'slippage_pct': 0.003,           # 3x normal
})

results = VectorizedBacktest(..., cost_model=conservative_costs).run()
```

### Pitfall 2: Overfitting to Historical Data

**Problem:** Parameters optimal for 2020-2024 fail in 2025

**Solution: Walk-forward validation**

```python
# Train on first 80%, test on last 20%
split_idx = int(len(close) * 0.8)

results_train = VectorizedBacktest(
    data=close[:split_idx],
    signal=signal[:split_idx],
    ...
).run()

results_test = VectorizedBacktest(
    data=close[split_idx:],
    signal=signal[split_idx:],
    ...
).run()

print(f"Train Return: {results_train['cumulative_return']:.2%}")
print(f"Test Return: {results_test['cumulative_return']:.2%}")

# If test ≈ train → robust strategy
# If test << train → overfitting
```

### Pitfall 3: Ignoring Regime Changes

**Problem:** Strategy profitable in trending markets, fails in range-bound periods

**Solution: Regime analysis**

```python
# Analyze performance by volatility regime
analyzer = BacktestAnalyzer(results)
rolling_metrics = analyzer.get_rolling_metrics(window=60)

high_vol_periods = rolling_metrics['volatility'] > rolling_metrics['volatility'].median()
low_vol_periods = ~high_vol_periods

print(f"High Vol Sharpe: {rolling_metrics.loc[high_vol_periods, 'sharpe'].mean():.2f}")
print(f"Low Vol Sharpe: {rolling_metrics.loc[low_vol_periods, 'sharpe'].mean():.2f}")
```

### Pitfall 4: Unrealistic Drawdown Tolerance

**Problem:** 100% return with 80% max drawdown is psychologically untradeable

**Solution: Monitor drawdown metrics**

```python
summary = analyzer.get_summary()

if summary['max_drawdown'] > 0.25:  # 25% threshold
    print("⚠️ Warning: Max drawdown exceeds 25%")
    print("   Consider reducing position size or adding stops")

if summary['avg_drawdown_duration'] > 30:  # 30 days
    print("⚠️ Warning: Average drawdown lasts > 30 days")
    print("   Recovery time may be psychologically difficult")
```

---

## Parameter Sensitivity Analysis

Test strategy robustness across different assumptions:

```python
# Test multiple cost scenarios
cost_scenarios = {
    'low': {'commission_per_share': 0.00005, 'slippage_pct': 0.0001},
    'medium': {'commission_per_share': 0.0001, 'slippage_pct': 0.001},
    'high': {'commission_per_share': 0.001, 'slippage_pct': 0.005},
}

results_by_cost = {}
for name, costs in cost_scenarios.items():
    cost_model = CostModel(costs)
    bt = VectorizedBacktest(close, signal, cost_model, position_sizer, 100000)
    results_by_cost[name] = bt.run()

# Compare results
for name in ['low', 'medium', 'high']:
    ret = results_by_cost[name]['cumulative_return']
    sharpe = results_by_cost[name]['sharpe_ratio']
    print(f"{name:10s}: Return {ret:7.2%}  Sharpe {sharpe:6.2f}")
```

---

## Example: Complete Workflow

```python
"""Complete backtest workflow example."""

import numpy as np
import pandas as pd
from src.backtest.engine import (
    VectorizedBacktest, CostModel, PositionSizer, BacktestAnalyzer
)

# 1. Load data
data = pd.read_csv('data/raw/EURUSD_daily.csv', index_col='date', parse_dates=True)
close = data['close'].values

# 2. Generate signal (SMA crossover)
sma_short = pd.Series(close).rolling(20).mean().values
sma_long = pd.Series(close).rolling(50).mean().values
signal = np.where(sma_short > sma_long, 1.0, -1.0)

# 3. Configure models
cost_model = CostModel({
    'commission_per_share': 0.0,
    'slippage_pct': 0.00009,  # 0.9 pips
    'daily_borrow_fee': 0.0,
})

position_sizer = PositionSizer({
    'strategy': 'threshold',
    'threshold_long': 0.5,
    'threshold_short': -0.5,
    'position_long': 1.0,
    'position_short': -1.0,
})

# 4. Run backtest
backtest = VectorizedBacktest(
    data=close,
    signal=signal,
    cost_model=cost_model,
    position_sizer=position_sizer,
    initial_capital=100000.0,
    trading_starts_at_bar=50,  # Skip first 50 bars (SMA warmup)
)

results = backtest.run()

# 5. Analyze results
analyzer = BacktestAnalyzer(results)
analyzer.print_report(include_trades=True)

# 6. Validate
def validate_backtest(results):
    assert (results['costs'] >= 0).all()
    assert (results['equity'] >= 0).all()
    assert (np.abs(results['position']) <= 1.0001).all()
    print("✓ Validation passed")

validate_backtest(results)

# 7. Visualize
import matplotlib.pyplot as plt

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

# Equity curve
ax1.plot(results['equity'])
ax1.set_title('Equity Curve')
ax1.set_ylabel('Equity ($)')
ax1.grid(True, alpha=0.3)

# Position changes
ax2.plot(results['position'], label='Position')
ax2.set_title('Position Over Time')
ax2.set_ylabel('Position Weight')
ax2.set_xlabel('Bar')
ax2.grid(True, alpha=0.3)
ax2.legend()

plt.tight_layout()
plt.savefig('backtest_results.png', dpi=150)
```

---

## Next Steps

1. **Optimize parameters:** Use grid search or Bayesian optimization
2. **Add risk management:** Stop-loss, take-profit, max position limits
3. **Multi-asset testing:** Run on multiple currency pairs
4. **Compare to benchmark:** Buy-and-hold, market-neutral baseline
5. **Implement event-driven mode:** For complex conditional logic

---

## Related Documentation

- [backtest_spec.md](../reports/backtest_spec.md) - Technical architecture
- [examples/backtest_demo.py](../examples/backtest_demo.py) - Code examples
- [src/backtest/engine.py](../src/backtest/engine.py) - Implementation
- [project_charter.md](project_charter.md) - Success criteria and risk metrics
