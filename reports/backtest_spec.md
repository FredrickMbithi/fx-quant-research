# Vectorized Backtest Engine Specification

## Overview

This document defines the architecture for a vectorized backtesting engine that models realistic trading conditions while maintaining computational efficiency. The engine processes signals across historical data, applies realistic execution and cost assumptions, and produces an equity curve with detailed transaction records.

## 1. Execution Model

### 1.1 Signal Generation and Lag

Signals are generated at the end of bar `T` based on prices and indicators available at that time. However, execution occurs at the **next bar open (T+1)**, modeling the realistic constraint that traders cannot execute within the bar that generates the signal.

**Timeline:**
- T: Signal calculation complete at bar close
- T: Position change decision made based on signal
- T+1: Order execution at next bar's open price
- T+1 onwards: Position carries PnL based on realized entry price

**Implementation:**
```python
# Signal at time t (using data up to t)
signal[t] = compute_signal(returns[t], indicators[t])

# Position at time t+1 (signal applied with 1-bar lag)
position[t+1] = apply_signal(signal[t])

# PnL computation starts at t+1 using price from next bar
pnl[t+1] = position[t+1] * (price[t+1] - execution_price[t])
```

### 1.2 Execution Price

- **Entry/rebalancing:** Next bar's open price
- **Partial fills:** Not modeled; all shares execute at open
- **Slippage:** Captured via cost model (see Section 3)

### 1.3 Position Constraints

- **Range:** Unbounded long/short (no explicit leverage constraint modeled here)
- **Position sizing:** Determined by position sizing logic (see Section 2)
- **Fractional shares:** Allowed (continuous units, not discrete)

## 2. Position Sizing Logic

### 2.1 Interface

Position sizing translates raw signals into portfolio-weighted positions. The interface accepts:

- `signal`: Raw signal value (often unnormalized)
- `params`: Configuration dict with position sizing parameters
- `lookback_data`: Historical data for risk calculation (optional)

Returns a normalized position weight in `[-1, 1]` where:
- `1.0` = fully long (e.g., 100% of capital)
- `-1.0` = fully short (e.g., 100% of capital)
- `0.0` = flat

### 2.2 Common Strategies

**Strategy A: Threshold-based**
```
if signal > threshold_long:
    position = position_long
elif signal < threshold_short:
    position = position_short
else:
    position = 0
```

**Strategy B: Linear scaling**
```
position = clip(signal / scale_factor, -1, 1)
```

**Strategy C: Volatility-adjusted**
```
vol = rolling_std(returns)
target_notional = target_volatility / vol
position = clip(signal * target_notional, -1, 1)
```

### 2.3 Implementation Pattern

```python
class PositionSizer:
    def __init__(self, config):
        """config: dict with strategy-specific parameters"""
        self.config = config
    
    def size(self, signal, params=None, lookback_data=None):
        """
        Args:
            signal: scalar or array of signal values
            params: dict of optional runtime parameters
            lookback_data: pd.DataFrame with columns ['returns', 'price']
        
        Returns:
            position: scalar or array in [-1, 1]
        """
        pass
```

## 3. Cost Model

### 3.1 Cost Components

Costs represent all frictions between signal and net return:

1. **Transaction costs (commissions, fees)**
   - Per-share or percentage-based
   - Paid on entry and exit

2. **Slippage (market impact, bid-ask spread)**
   - Entry: paid on direction change or new entry
   - Exit: paid when reducing position
   - Modeled as percentage of entry price

3. **Holding costs**
   - Financing charges for leverage
   - Borrow fees for shorts
   - Applied daily or per-bar

### 3.2 Cost Types: Entry vs. Maintenance

**Entry costs** (paid once per position change):
```
cost_entry = abs(position_change) * slippage_pct * price + abs(position_change) * commission_per_share
```

**Maintenance costs** (paid every bar while holding):
```
cost_hold = abs(position) * daily_borrow_fee * holding_period
```

### 3.3 Interface

```python
class CostModel:
    def __init__(self, config):
        """
        config dict may include:
        - commission_per_share: float
        - slippage_pct: float (entry/exit)
        - daily_borrow_fee: float (for shorts)
        - intraday_cost: bool (apply costs intrabar or interbar)
        """
        self.config = config
    
    def cost_entry(self, position_change, price):
        """Cost of changing position (abs value of cost in dollars)"""
        pass
    
    def cost_hold(self, position, period_days=1):
        """Cost of holding position for given period (in dollars)"""
        pass
```

### 3.4 Implementation Details

- Costs are **dollar amounts**, not percentages
- They reduce equity in the calculation: `equity -= cost`
- Cost impacts PnL line-by-line, not amortized
- Default: Model costs at **position change**, not continuously
- Optional: Track costs separately for analysis (total commission, slippage, borrow fees)

## 4. Equity Curve Calculation

### 4.1 Computation Loop

For each bar `t`:

1. **Apply signal lag**
   - Read signal value generated at bar `t-1`
   - Compute target position based on signal

2. **Calculate position changes**
   - `position_change = target_position[t] - position[t-1]`
   - Identify entries, exits, pyramiding, and reductions

3. **Apply entry costs**
   - If `position_change != 0`:
     - `entry_cost = cost_model.cost_entry(position_change, price[t])`
     - `equity -= entry_cost`

4. **Update position**
   - `position[t] = target_position[t]`

5. **Calculate PnL**
   - Mark-to-market: `unrealized_pnl[t] = position[t] * (price[t] - entry_price[t])`
   - Or equivalently: `equity[t] = equity[t-1] - entry_cost + daily_pnl[t]`

6. **Apply holding costs** (optional)
   - `hold_cost = cost_model.cost_hold(position[t])`
   - `equity -= hold_cost`

### 4.2 Return Calculation

**Cumulative return:**
```
return[t] = (equity[t] - equity[0]) / equity[0]
```

**Period return:**
```
period_return = equity[t_end] / equity[t_start] - 1
```

**Log return (for analysis):**
```
log_return[t] = log(equity[t]) - log(equity[t-1])
```

## 5. Data Flow and Interfaces

### 5.1 Input Data

```
├── price (OHLCV)
│   ├── open
│   ├── high
│   ├── low
│   ├── close
│   └── volume
├── signal
│   └── scalar or array
└── additional indicators (optional)
    └── RSI, MA, volatility, etc.
```

Data requirements:
- **Minimum 2 bars:** Bar 0 for signal, Bar 1 for execution
- **Alignment:** All arrays must be same length
- **No gaps:** Missing data should be forward-filled or interpolated upstream

### 5.2 Output: Equity Curve

```python
{
    'timestamp': datetime array,
    'equity': numpy array (starting at initial_capital),
    'position': numpy array (portfolio weight, [-1, 1]),
    'price': numpy array (closing price),
    'returns': numpy array (log returns),
    'costs': numpy array (transaction costs per bar),
    'entry_prices': numpy array (execution prices),
    'cumulative_return': float
}
```

Optional detailed output:
```python
{
    'trades': pd.DataFrame with columns [
        'entry_time', 'exit_time', 'entry_price', 'exit_price',
        'position_size', 'pnl', 'pnl_pct', 'duration_bars'
    ],
    'cost_breakdown': {
        'total_commission': float,
        'total_slippage': float,
        'total_borrow_fees': float
    }
}
```

## 6. Vectorized Implementation

### 6.1 Why Vectorization?

- **Speed:** NumPy/Pandas operations on entire arrays vs. Python loops
- **Memory:** Single data structure vs. N containers
- **Simplicity:** Cleaner code for cumulative operations (cumsum, cumprod)

### 6.2 Key Operations (Vectorized)

```python
import numpy as np

# Lag signal by 1 bar
lagged_signal = np.roll(signal, 1)
lagged_signal[0] = 0  # First bar has no prior signal

# Position changes
position_change = np.diff(position, prepend=0)

# Costs (scalar multiplication)
entry_costs = np.abs(position_change) * slippage_pct * price + commission_per_share

# PnL per bar
daily_pnl = position[:-1] * np.diff(price)

# Cumulative equity
equity = initial_capital + np.cumsum(daily_pnl - entry_costs)

# Returns
returns = np.log(equity[1:] / equity[:-1])
```

### 6.3 When NOT to Vectorize

- **Complex conditional logic:** Per-bar rules (e.g., "if drawdown > X, stop trading")
- **Feedback loops:** Position depends on equity (e.g., Kelly criterion)
- **Event-driven logic:** Triggers based on cumulative state

In these cases, use an event-driven loop but keep vectorized operations inside the loop for speed.

## 7. Assumptions and Limitations

### 7.1 Assumed Realistic

- Signal lag (T to T+1)
- Transaction costs and slippage
- Next-bar-open execution
- No flash crashes or gap fills beyond OHLC

### 7.2 Simplified (Not Modeled)

- **Discrete order sizes:** All positions are continuous
- **Partial fills:** Orders execute in full at open
- **Intrabar volatility:** PnL calculated on OHLC only
- **Liquidity constraints:** No volume checks or market depth
- **Margin calls:** Leverage assumed available
- **Corporate actions:** No splits, dividends, or delistings

### 7.3 Data Quality Assumptions

- No missing bars (use ffill or interpolation upstream)
- No look-ahead bias (signal uses only data available at time t-1)
- Prices are mid-prices or closing prices (not bid/ask)

## 8. Validation Checklist

Before running live backtests:

- [ ] Signal is not look-ahead biased (verify lookback period)
- [ ] Cost model parameters are realistic for asset class
- [ ] Initial capital is non-zero
- [ ] Data has no gaps or NaN values in critical columns
- [ ] Equity curve is monotonically increasing or decreasing (no sudden jumps)
- [ ] Position changes align with signal changes (with 1-bar lag)
- [ ] Total costs are positive and reasonable relative to capital
- [ ] No division by zero or NaN propagation in returns

## 9. Example Workflow

```python
# 1. Initialize data
prices = pd.read_csv('data.csv')['close'].values
signal = compute_signal(prices)

# 2. Initialize components
cost_model = CostModel({
    'commission_per_share': 0.001,
    'slippage_pct': 0.001,
    'daily_borrow_fee': 0.0005
})

position_sizer = PositionSizer({
    'threshold_long': 0.5,
    'threshold_short': -0.5,
    'position_long': 1.0,
    'position_short': -1.0
})

# 3. Run backtest
backtest = VectorizedBacktest(
    data=prices,
    signal=signal,
    cost_model=cost_model,
    position_sizer=position_sizer,
    initial_capital=100000
)

results = backtest.run()

# 4. Analyze
print(f"Total Return: {results['cumulative_return']:.2%}")
print(f"Sharpe Ratio: {calculate_sharpe(results['returns']):.2f}")
```

---

**Version:** 0.1  
**Status:** Architecture specification (implementation TBD)  
**Last Updated:** 2025-02-21
