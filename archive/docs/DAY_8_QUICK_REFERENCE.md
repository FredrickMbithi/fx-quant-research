# Day 8 Quick Reference Cheat Sheet
## Feature Engineering for Trading Signals

---

## 🚀 5-Minute Quickstart

### Import & Initialize
```python
import pandas as pd
from library import FeatureLibrary
from returns import compute_log_returns, compute_rolling_volatility

# Load prices (must have DatetimeIndex)
prices = pd.read_csv('data.csv', index_col='date', parse_dates=True)['close']

# Create feature library
lib = FeatureLibrary(prices)
```

### Generate All Features at Once
```python
features = lib.generate_all_features()
# Returns DataFrame with 10 features
```

### Access Individual Features
```python
momentum = lib.momentum(period=20)           # 20-day return
volatility = lib.volatility(window=20)       # 20-day rolling vol
zscore = lib.zscore(window=20)                # Deviation from mean
rsi = lib.rsi(period=14)                      # Relative Strength Index (0-100)
ma_ratio = lib.moving_average_ratio()         # Short MA / Long MA
trend_strength = lib.trend_strength()         # Return per unit volatility
```

---

## 📊 Feature Quick Reference

| Feature | Type | Range | Signal | Use Case |
|---------|------|-------|--------|----------|
| momentum | Trend | Any | > 0: up, < 0: down | Trend-following |
| momentum_zscore | Trend | Any | > 1.5: extreme | Momentum reversal |
| volatility | Risk | 0+ | High vol: uncertainty | Risk scaling |
| vol_regime | Regime | {0,1} | 1: high, 0: low | Market regime |
| zscore | Stat | Any | > 1.5: overbought | Mean reversion |
| rsi_14 | Momentum | 0-100 | > 70: overbought, < 30: oversold | Extremes |
| ma_ratio | Trend | 0+ | > 1: uptrend, < 1: downtrend | Trend confirmation |
| trend_strength | Stat | Any | High: strong trend | Trend quality |
| ema_20 | Trend | Price units | Above/below price | Trend following |

---

## 🎯 Common Signal Patterns

### Mean Reversion (Stationary Features)
```python
buy_signal = features['zscore'] < -1.5      # Oversold
sell_signal = features['zscore'] > 1.5      # Overbought

# Or using RSI
buy_signal = features['rsi_14'] < 30        # Oversold
sell_signal = features['rsi_14'] > 70       # Overbought
```

### Momentum (Trend-Following)
```python
buy_signal = features['momentum_20d'] > 0   # Positive momentum
sell_signal = features['momentum_20d'] < 0  # Negative momentum

# Or using MA ratio
buy_signal = features['ma_ratio'] > 1.0     # Above long-term average
sell_signal = features['ma_ratio'] < 1.0    # Below long-term average
```

### Combined Signal (Majority Vote)
```python
signal_score = (
    (features['zscore'] < -1.5).astype(int) +
    (features['momentum_20d'] > 0).astype(int) +
    (features['rsi_14'] < 30).astype(int)
)

buy_signal = signal_score >= 2    # 2+ indicators agree
sell_signal = signal_score <= -2  # Reverse
```

---

## 🔧 Parameter Tuning

### For Daily Data
```python
# Most common parameters (defaults)
lib.momentum(period=20)           # ~1 month
lib.volatility(window=20)         # ~1 month rolling
lib.zscore(window=20)             # ~1 month lookback
lib.rsi(period=14)                # Standard technical level
```

### For Weekly Data
```python
# Scale parameters by ~5x (252 trading days / 52 weeks ≈ 5)
lib.momentum(period=100)          # ~5 months (100 weeks ≈ 2 years)
lib.volatility(window=100)        # ~5 months rolling
lib.zscore(window=100)            # ~5 months lookback
```

### Aggressive Trading (Shorter Windows)
```python
# Faster signals, more false signals
lib.momentum(period=5)            # ~1 week
lib.volatility(window=5)          # ~1 week
lib.zscore(window=5)              # ~1 week
```

### Conservative Trading (Longer Windows)
```python
# Slower signals, fewer false signals
lib.momentum(period=60)           # ~3 months
lib.volatility(window=60)         # ~3 months
lib.zscore(window=60)             # ~3 months
```

---

## ⚠️ Common Pitfalls

### ❌ Don't: Assume stationarity without testing
```python
# BAD: Using trend feature for mean reversion
buy_signal = features['ema_20'] < price    # ema_20 is NON-stationary!
```

### ✅ Do: Check stationarity first
```python
# GOOD: Use stationary features for mean reversion
buy_signal = features['zscore'] < -1.5     # zscore IS stationary
```

### ❌ Don't: Use correlated features together
```python
# BAD: trend_strength and momentum highly correlated (+0.98)
signal = buy when (momentum > 0) AND (trend_strength > 2)  # Redundant!
```

### ✅ Do: Remove or combine correlated features
```python
# GOOD: Use one or the other
signal_a = buy when momentum > 0            # Use momentum
signal_b = buy when trend_strength > 2     # Or trend_strength, not both
```

### ❌ Don't: Ignore NaN values
```python
# BAD: First 60 values are NaN (not enough history)
signal = features['zscore']  # First 60 rows are NaN!
signal[0:60] will error in backtest
```

### ✅ Do: Handle NaN explicitly
```python
# GOOD: Only trade when feature is valid
valid_idx = features['zscore'].notna()
signal = features.loc[valid_idx, 'zscore'] < -1.5
```

---

## 📈 Key Metrics to Calculate

### After Generating Signals

```python
# Signal frequency
n_buy_signals = (signal == 1).sum()
n_sell_signals = (signal == -1).sum()
signal_frequency = (n_buy_signals + n_sell_signals) / len(signal)

# Feature statistics
mean_return = features['momentum_20d'].mean()
std_return = features['momentum_20d'].std()
sharpe_ratio = mean_return / std_return * np.sqrt(252)

# Correlation check (watch for > 0.8)
correlation = features.corr()
high_corr = correlation[correlation > 0.8]  # Flag problematic pairs

# Stationarity (variance ratio should be ~1.0)
first_half_var = features['zscore'].iloc[:len(features)//2].var()
second_half_var = features['zscore'].iloc[len(features)//2:].var()
variance_ratio = first_half_var / second_half_var
is_stationary = 0.5 < variance_ratio < 2.0
```

---

## 🧪 Testing Your Features

### Sanity Check 1: Shape & NaN
```python
features_df = lib.generate_all_features()
print(features_df.shape)      # Should match price series length
print(features_df.isnull().sum())  # First ~60 values typically NaN (expected!)
```

### Sanity Check 2: Value Ranges
```python
print(features_df.describe())
# Momentum: unbounded
# RSI: 0-100
# Z-score: typically -3 to +3
# Volatility: should be > 0
# MA ratio: > 0
```

### Sanity Check 3: Correlation
```python
corr = features_df.corr()
print(corr)  # Look for > 0.8 (redundancy warning)
```

### Sanity Check 4: Signal Frequency
```python
signals = features_df['zscore'] < -1.5
print(f"Buy signals: {signals.sum()} ({signals.sum()/len(signals)*100:.1f}%)")
# If > 50%, threshold too loose; if < 1%, too tight
```

---

## 💡 Strategy Examples

### Example 1: Simple Mean Reversion
```python
# Buy oversold, sell overbought
buy = lib.zscore(window=20) < -1.5
sell = lib.zscore(window=20) > 1.5

# Exit after N bars (not shown) or on opposite signal
```

### Example 2: Momentum With Volatility Filter
```python
# Trade momentum only in low volatility regime
momentum_signal = lib.momentum(period=20) > 0
low_vol = lib.volatility(window=20) < lib.volatility(window=20).median()

buy = momentum_signal & low_vol  # Only buy if momentum AND low vol
```

### Example 3: RSI Divergence (Advanced)
```python
# Buy if price makes new low but RSI doesn't (bullish divergence)
# Note: Requires tracking highs/lows separately
rsi = lib.rsi(period=14)
price_new_low = price < price.rolling(30).min()
rsi_higher = rsi > rsi.shift(30)

divergence_signal = price_new_low & rsi_higher  # Bullish divergence
```

### Example 4: Trend Following With Confirmation
```python
# Buy on momentum, but only confirm if trend is strong
ma_ratio = lib.moving_average_ratio(short_window=20, long_window=60)
momentum = lib.momentum(period=20)
trend_strong = ma_ratio > 1.02  # Price > 2% above long MA

buy = (momentum > 0) & trend_strong
```

---

## 📊 Visualization Quick Commands

```python
import matplotlib.pyplot as plt

# Plot any feature over time
fig, ax = plt.subplots(figsize=(14, 4))
ax.plot(features['momentum_20d'])
ax.axhline(0, color='r', linestyle='--')
ax.set_title('20-Day Momentum')
ax.grid(True)
plt.show()

# Compare two features
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
ax1.plot(features['momentum_20d'], label='Momentum')
ax2.plot(features['rsi_14'], label='RSI (0-100 scale)')
plt.show()

# Scatter plot: RSI vs Returns
fig, ax = plt.subplots(figsize=(10, 6))
ax.scatter(features['rsi_14'], lib.returns.compute_log_returns(prices) * 100, alpha=0.5)
ax.set_xlabel('RSI')
ax.set_ylabel('Daily Return (%)')
ax.axvline(30, color='r', linestyle='--', alpha=0.5)
ax.axvline(70, color='r', linestyle='--', alpha=0.5)
plt.show()
```

---

## 🎯 Optimization Tips

### Speed Up Feature Generation
```python
# For backtesting loops, pre-compute features once
features = lib.generate_all_features()  # Compute once

# Then reuse in backtest
for date in date_range:
    signal = features.loc[date, 'momentum_20d']
    # Trade based on signal
```

### Memory Efficiency
```python
# Only compute features you need (not all 10)
momentum = lib.momentum(20)
zscore = lib.zscore(20)
# Instead of: features = lib.generate_all_features()
```

### Reduce Lookback Bias
```python
# Warm up features before backtesting
lookback_period = 100  # ~5 months
features = lib.generate_all_features()
valid_features = features.iloc[lookback_period:]  # Start trading after warm-up
```

---

## ✅ Checklist Before Backtesting

- [ ] Features have DatetimeIndex
- [ ] No look-ahead bias (features use t-1 data, not t+1)
- [ ] NaN values handled (first 60 typically NaN)
- [ ] Feature ranges sensible (RSI 0-100, volatility > 0)
- [ ] Correlation checked (no > 0.8 redundancy)
- [ ] Stationarity verified for mean reversion (variance ratio ~1)
- [ ] Signal frequency reasonable (not 0-trades or 100-trades/day)
- [ ] Parameters documented (window=20, period=14, etc.)
- [ ] Edge cases tested (start of series, gaps in data, extreme prices)

---

**Quick Links:**
- Full Guide: `DAY_8_FEATURE_ENGINEERING_GUIDE.md`
- Code: `returns.py`, `library.py`
- Notebook: `feature_engineering_notebook.py`
- Plots: `feature_*.png`, `trading_signals.png`

**Created:** Feb 24, 2025 | Phase 1, Day 8
**Next:** Day 9 - Backtesting Framework
