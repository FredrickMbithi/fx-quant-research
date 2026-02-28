# Backtest Engine

A comprehensive, vectorized backtesting engine for quantitative trading strategies.

## Features

### Core Components

1. **CostModel** - Models transaction and holding costs
   - Commission fees
   - Slippage
   - Borrow fees for short positions

2. **PositionSizer** - Converts signals into position weights
   - Threshold-based (binary or ternary)
   - Linear scaling
   - Volatility-adjusted (risk parity)

3. **VectorizedBacktest** - Main backtesting engine
   - Applies 1-bar signal lag (realistic execution)
   - Vectorized operations for performance
   - Comprehensive metrics calculation

4. **PerformanceMetrics** - Calculate performance statistics
   - Returns: Total, annualized, CAGR
   - Risk: Volatility, downside deviation, max drawdown
   - Risk-adjusted: Sharpe, Sortino, Calmar ratios
   - Drawdown analysis

5. **TradeAnalyzer** - Extract and analyze individual trades
   - Trade entry/exit tracking
   - Win rate, profit factor
   - Average trade metrics

6. **BacktestAnalyzer** - Comprehensive analysis and reporting
   - Summary statistics
   - Trade analysis
   - Rolling metrics
   - Validation checks
   - Formatted reports

## Installation

No additional dependencies beyond the project requirements:

```bash
pip install -r requirements.txt
```

## Quick Start

```python
import numpy as np
from src.backtest.engine import (
    CostModel,
    PositionSizer,
    VectorizedBacktest,
    BacktestAnalyzer,
)

# 1. Prepare data
price = np.array([100, 101, 102, 103, 104, 105])
signal = np.array([0, 1, 1, 0, -1, -1])

# 2. Configure cost model
cost_model = CostModel({
    'commission_per_share': 0.001,
    'slippage_pct': 0.0005,
    'daily_borrow_fee': 0.0001,
})

# 3. Configure position sizing
position_sizer = PositionSizer({
    'strategy': 'threshold',
    'threshold_long': 0.5,
    'threshold_short': -0.5,
    'position_long': 1.0,
    'position_short': -1.0,
})

# 4. Run backtest
backtest = VectorizedBacktest(
    data=price,
    signal=signal,
    cost_model=cost_model,
    position_sizer=position_sizer,
    initial_capital=100000,
)

results = backtest.run()

# 5. Analyze results
analyzer = BacktestAnalyzer(results)
analyzer.print_report(include_trades=True)
```

## Position Sizing Strategies

### Threshold-Based

Binary or ternary position based on signal thresholds:

```python
position_sizer = PositionSizer({
    'strategy': 'threshold',
    'threshold_long': 0.5,      # Enter long if signal > 0.5
    'threshold_short': -0.5,    # Enter short if signal < -0.5
    'position_long': 1.0,       # 100% long
    'position_short': -1.0,     # 100% short
})
```

### Linear Scaling

Position proportional to signal strength:

```python
position_sizer = PositionSizer({
    'strategy': 'linear',
    'scale_factor': 2.0,  # signal / 2.0, clipped to [-1, 1]
})
```

### Volatility-Adjusted

Risk parity approach (inverse volatility weighting):

```python
position_sizer = PositionSizer({
    'strategy': 'volatility',
    'vol_window': 20,           # Rolling volatility window
    'target_volatility': 0.02,  # Target 2% volatility
})

# Requires lookback data with returns
import pandas as pd
lookback_data = pd.DataFrame({'returns': return_series})
position = position_sizer.size(signal, lookback_data=lookback_data)
```

## Cost Modeling

### Entry/Exit Costs

Applied when position changes:

```python
cost_model = CostModel({
    'commission_per_share': 0.001,  # $0.001 per unit
    'slippage_pct': 0.0005,         # 0.05% slippage
})
```

### Holding Costs

Applied to short positions:

```python
cost_model = CostModel({
    'daily_borrow_fee': 0.0001,  # 0.01% per day for shorts
})
```

## Performance Metrics

The backtest automatically calculates:

### Return Metrics

- Total Return
- Annualized Return
- CAGR (Compound Annual Growth Rate)

### Risk Metrics

- Volatility (annualized)
- Downside Deviation
- Maximum Drawdown
- Average Drawdown
- Drawdown Duration

### Risk-Adjusted Metrics

- Sharpe Ratio
- Sortino Ratio
- Calmar Ratio (return / max drawdown)

### Trading Metrics

- Total Trades
- Win Rate
- Profit Factor
- Average Win/Loss
- Expectancy
- Turnover

## Trade Analysis

Extract and analyze individual trades:

```python
analyzer = BacktestAnalyzer(results)
trades_df = analyzer.analyze_trades()

# DataFrame with columns:
# - entry_bar, exit_bar
# - entry_price, exit_price
# - position_size
# - pnl, pnl_pct
# - duration

print(trades_df.head())
```

## Validation

Validate backtest results for common issues:

```python
validations = analyzer.validate()

# Checks:
# - no_nan_equity: No NaN in equity curve
# - no_nan_results: No NaN in returns
# - positive_equity: All equity values > 0
# - reasonable_costs: Non-negative costs
# - position_in_range: Positions in [-1, 1]
# - signal_lag_applied: 1-bar lag verified

if validations['all_passed']:
    print("✓ All validations passed")
else:
    print("✗ Some validations failed")
```

## Rolling Metrics

Calculate rolling performance over time:

```python
rolling = analyzer.get_rolling_metrics(window=252)

# Returns DataFrame with:
# - rolling_return (annualized)
# - rolling_volatility (annualized)
# - rolling_sharpe
```

## Architecture

### Execution Model

**Signal Lag (Realistic Execution):**

- Signal calculated at bar T close
- Position change occurs at bar T+1 open
- Models realistic trading constraint

**Timeline:**

```
T:   Signal generated → Position decision
T+1: Order execution → PnL starts accruing
```

### Vectorized Operations

The engine uses NumPy vectorization for performance:

```python
# Signal lag (vectorized)
lagged_signal = np.roll(signal, 1)
lagged_signal[0] = 0

# Position changes
position_change = np.diff(position, prepend=0)

# Costs
costs = np.abs(position_change) * commission + slippage

# Equity curve
equity = initial_capital + np.cumsum(pnl - costs)
```

## Examples

See comprehensive examples in:

- `examples/backtest_demo.py` - Full demonstration of all features
- `src/backtest/engine.py` - Simple example in `__main__`

Run examples:

```bash
python examples/backtest_demo.py
python src/backtest/engine.py
```

## Testing

Comprehensive test suite included:

```bash
# Run all tests
python -m pytest tests/test_backtest.py -v

# Run specific test class
python -m pytest tests/test_backtest.py::TestVectorizedBacktest -v

# Run with coverage
python -m pytest tests/test_backtest.py --cov=src.backtest
```

## Best Practices

1. **Signal Validation**
   - Ensure no look-ahead bias
   - Verify signals use only past data
   - Test with out-of-sample data

2. **Cost Modeling**
   - Use realistic cost estimates
   - Include slippage and commissions
   - Model borrow fees for shorts

3. **Position Sizing**
   - Start conservative (smaller positions)
   - Consider volatility scaling
   - Respect risk limits

4. **Performance Analysis**
   - Focus on risk-adjusted metrics (Sharpe, Sortino)
   - Analyze drawdown characteristics
   - Check win rate and profit factor
   - Validate with rolling metrics

5. **Validation**
   - Always run validation checks
   - Verify signal lag is applied
   - Check for NaN values
   - Ensure equity stays positive

## Limitations

The current implementation assumes:

- **Continuous positions** (fractional shares allowed)
- **Full fills** (no partial execution)
- **No leverage constraints** (can go 100% long or short)
- **No intraday volatility** (uses OHLC only)
- **No liquidity constraints** (infinite liquidity)
- **No corporate actions** (splits, dividends)

For more realistic modeling, extend the engine with:

- Order execution models
- Liquidity/volume checks
- Intraday data processing
- Margin requirements

## API Reference

### CostModel

```python
CostModel(config: Dict)
    .cost_entry(position_change, price) -> cost
    .cost_hold(position, period_days) -> cost
```

### PositionSizer

```python
PositionSizer(config: Dict)
    .size(signal, params=None, lookback_data=None) -> position
```

### VectorizedBacktest

```python
VectorizedBacktest(
    data: np.ndarray,
    signal: np.ndarray,
    cost_model: CostModel,
    position_sizer: PositionSizer,
    initial_capital: float = 100000.0,
    trading_starts_at_bar: int = 2
)
    .run() -> Dict[str, Any]
```

### BacktestAnalyzer

```python
BacktestAnalyzer(results: Dict)
    .analyze_trades(timestamps=None) -> pd.DataFrame
    .get_summary(include_trades=True) -> Dict
    .print_report(include_trades=True) -> None
    .get_rolling_metrics(window=252) -> pd.DataFrame
    .validate() -> Dict[str, bool]
```

## Contributing

To add new position sizing strategies:

1. Add method to `PositionSizer` class
2. Update `size()` method to call your strategy
3. Add tests in `tests/test_backtest.py`
4. Update documentation

## License

Part of the fx-quant-research project.

## References

- Specification: `reports/backtest_spec.md`
- Architecture notes: `docs/day9_summary.md`
- Vectorized vs Event-driven: `reports/vectorized_vs_eventdriven.md`
