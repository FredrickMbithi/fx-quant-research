'

# Data Pipeline Specification

## Overview

Production-grade data engineering pipeline for FX OHLC data, designed to prevent common pitfalls including lookahead bias, data corruption, and forward bias in backtests.

**Key Principle: Data flows one direction only—from raw to processed. No future data ever touches past decisions.**

---

## Data Flow Architecture

```
RAW DATA
  ↓
  ├─ Load raw files (CSV, Parquet, HDF5)
  ├─ Normalize timestamps to UTC
  ├─ Handle duplicates (keep last)
  ├─ Sort by timestamp
  ├─ Validate OHLC relationships
  │
INTERIM DATA (validated, UTC-normalized)
  ↓
  ├─ Detect missing bars
  ├─ Choose fill strategy (forward fill, interpolate, or drop)
  ├─ Run anomaly detection (spikes, volume, stale data)
  │
PROCESSED DATA (ready for backtesting/trading)
```

### Strict Separation of Concerns

| Stage        | Purpose                           | Input         | Output                     |
| ------------ | --------------------------------- | ------------- | -------------------------- |
| **Load**     | Parse files, normalize timestamps | Raw files     | DataFrame with UTC index   |
| **Validate** | Check integrity, OHLC logic       | DataFrame     | Pass/Fail report           |
| **Clean**    | Handle missing data               | Gaps detected | Filled or dropped data     |
| **Analyze**  | Feature engineering               | Cleaned data  | Features (no future data!) |

---

## Validation Rules

### 1. Timestamp Normalization (CRITICAL)

**Rule**: All timestamps must be UTC.

```python
# ✓ CORRECT
df.index = df.index.tz_localize('UTC')

# ✗ WRONG (lookahead bias!)
df.index = pd.to_datetime(df['timestamp'])  # Naive timestamps
```

**Enforcement**:

- Naive timestamps → assume UTC with warning
- Localized timestamps → convert to UTC
- No datetime conversions after load
- Index is immutable after validation

**Why**: Different timezones = different "current time". UTC prevents timezone confusion and ensures reproducible backtests.

---

### 2. OHLC Relationship Validation

**Rule**: For each bar, High ≥ Max(Open, Close) and Low ≤ Min(Open, Close)

```
High ────┐
         ├─ Valid bar
Low  ────┘

    Open ─┬─ Max(O,C)
          │
    Close ┴─ Min(O,C)
```

**Checks Enforced**:

1. High ≥ Low
2. High ≥ Open AND High ≥ Close
3. Low ≤ Open AND Low ≤ Close
4. All prices > 0

**Failure Action**: Reject entire dataset (data integrity failure, not recoverable)

**Why**: Invalid OHLC reveals data corruption, feed errors, or feed misconfiguration. Better to fail loudly than silently.

---

### 3. Duplicate Handling

**Rule**: One timestamp = one bar. Keep last occurrence.

```
Timestamp  Close  (Action)
───────────────────────────
2023-01-01 1.0500  Keep
2023-01-01 1.0501  ← Replaced (amendment)
```

**Rationale**: Data feeds sometimes send corrections/amendments. Latest = most correct.

**Detection**:

```python
duplicates = df.index.duplicated(keep=False)
```

**Resolution**: Drop all but last per timestamp.

---

### 4. Monotonic Index

**Rule**: df.index must be strictly increasing (no duplicates, no out-of-order).

```python
assert df.index.is_monotonic_increasing
```

**Why**: Backtests assume time moves forward. Non-monotonic data breaks causality assumptions.

---

### 5. No Future Data (Lookahead Bias Prevention) — CRITICAL

**Rule**: No timestamp > now.

```python
now = pd.Timestamp.now(tz='UTC')
assert (df.index <= now).all()
```

**Failure Mode**: Accidentally using tomorrow's close in today's strategy = inflated backtest returns.

**Examples of Lookahead Bias**:

1. Loading end-of-month data before month ends
2. Using settlement prices (known at EOD) in intraday strategy
3. Forward-testing before backtest period ends

**Prevention**:

- Load validation checks this
- Never load future data
- Backtest end-date < data end-date (hold out recent data)

---

## Missing Bar Handling

### Detection

```python
expected_index = pd.date_range(start, end, freq='D')
missing = expected_index.difference(df.index)
coverage = len(df) / len(expected_index)
```

### Strategies

| Strategy         | Use Case               | Pros                         | Cons                |
| ---------------- | ---------------------- | ---------------------------- | ------------------- |
| **Forward Fill** | Daily FX with weekends | Conservative, no assumptions | Repeats stale price |
| **Interpolate**  | Minute-level data      | Smooth transitions           | Assumes linear path |
| **Drop**         | Strict backtests       | No artificial data           | Loses time periods  |

### Example: Forward Fill (Most Common for FX)

```python
# Before: Weekends missing
# Friday:  OHLC = [1.0500, 1.0505, 1.0495, 1.0502]
# Monday:  OHLC = [1.0501, 1.0510, 1.0498, 1.0508]

# After forward fill:
# Saturday: OHLC = [1.0502, 1.0502, 1.0502, 1.0502]  (Friday's close)
# Sunday:   OHLC = [1.0502, 1.0502, 1.0502, 1.0502]  (Friday's close)
# Monday:   OHLC = [1.0501, 1.0510, 1.0498, 1.0508]  (actual)
```

**Why Forward Fill?** FX doesn't trade weekends—repeating Friday's close is most honest representation of "no price discovery."

---

## Anomaly Detection

### Extreme Spikes (> N-Sigma)

```python
threshold = 5  # 5-sigma event
returns = df['close'].pct_change()
sigma_moves = returns.rolling(20).std()
```

**Action**: Log and flag (don't auto-reject; could be real market event).

**Interpretation**:

- 3-sigma: Rare but plausible (~0.27%)
- 5-sigma: Extremely rare; likely data error

### Low-Volume Bars

```python
vol_threshold = quantile(5th percentile)
low_vol_bars = df[df['volume'] < threshold]
```

**Action**: Log warning. Could indicate thin trading or data feed gap.

### Stale Data

```python
last_update = df.index[-1]
now = pd.Timestamp.now(tz='UTC')
hours_stale = (now - last_update).total_seconds() / 3600
```

**Action**: Critical alert if data > 24h old (live trading killer).

---

## Data Quality Report

Every load should produce:

```json
{
  "symbol": "EURUSD",
  "bar_count": 252,
  "date_range": {
    "start": "2023-01-02",
    "end": "2023-12-29"
  },
  "checks": {
    "missing_bars": {
      "has_gaps": false,
      "coverage": 1.0,
      "passed": true
    },
    "extreme_spikes": {
      "spike_count": 0,
      "passed": true
    },
    "ohlc_sanity": {
      "issues": [],
      "passed": true
    },
    "stale_data": {
      "hours_old": 72,
      "passed": true
    }
  },
  "status": "PASS"
}
```

---

## Common Pitfalls & Fixes

### Pitfall 1: Timezone Confusion

**Problem**: Load data in broker's timezone, forget to convert.

```python
# ✗ WRONG
df.index = df.index.tz_localize('America/New_York')  # Forgot to convert to UTC
```

**Fix**: Always convert to UTC immediately.

```python
# ✓ CORRECT
df.index = df.index.dt.tz_convert('UTC')
```

### Pitfall 2: Forward-Filling Too Aggressively

**Problem**: Fill gaps over weekends with forward fill, but backtest uses Friday data for Monday decision.

```python
# ✗ WRONG
df_filled = df.reindex(expected_index).fillna(method='ffill')
# Now Monday's "open" is actually Friday's close!
```

**Fix**: Explicitly handle weekend/holiday logic.

```python
# ✓ CORRECT
# Only fill within trading day gaps, not overnight
df = df[df.index.dayofweek < 5]  # FX: Mon-Fri only
```

### Pitfall 3: Lookahead Bias in Backtests

**Problem**: Load data through today, backtest last month.

```python
# ✗ WRONG
df = loader.load('EURUSD', start='2023-11-01', end='2023-11-30')
# Run strategy that buys/sells based on 'today's' data
# But 'today' might be Dec 31, and you're testing Nov!
```

**Fix**: Ensure backtest end-date < last available data.

```python
# ✓ CORRECT
df = loader.load('EURUSD', start='2023-01-01', end='2023-12-31')
# Backtest: 2023-01-01 to 2023-11-30 (holdout Dec for validation)
```

### Pitfall 4: Silent NaN Propagation

**Problem**: Missing values sneak into calculations.

```python
# ✗ WRONG
returns = df['close'].pct_change()  # NaN at first row
signal = returns.rolling(5).mean()  # Propagates NaN silently
```

**Fix**: Validate and handle explicitly.

```python
# ✓ CORRECT
returns = df['close'].pct_change().dropna()
assert not signal.isna().any(), "Unexpected NaN in signal"
```

---

## Implementation Checklist

### Loading Phase

- [ ] Read raw files (CSV, Parquet, or HDF5)
- [ ] Detect timestamp column or index
- [ ] Normalize all timestamps to UTC
- [ ] Sort by timestamp ascending
- [ ] Remove duplicate timestamps (keep last)

### Validation Phase

- [ ] Confirm datetime index
- [ ] Check all required columns present (O, H, L, C, V)
- [ ] No NaN in OHLCV
- [ ] Validate OHLC relationships (H ≥ L, etc.)
- [ ] Monotonic increasing index
- [ ] **No future timestamps** ← CRITICAL

### Quality Checks

- [ ] Missing bar detection & reporting
- [ ] Spike detection (> 3σ)
- [ ] Volume anomalies (< 5th percentile)
- [ ] Stale data check (< 24h old)
- [ ] Generate validation report

### Documentation

- [ ] Log all transformations
- [ ] Include data quality metrics in logs
- [ ] Document fill strategy if gaps handled
- [ ] Version control validation thresholds

---

## Code Examples

### Load Data Safely

```python
from src.data.loader import FXDataLoader

loader = FXDataLoader('data/raw')
df = loader.load('EURUSD', start_date='2023-01-01', end_date='2023-12-31')
# Returns fully validated DataFrame with UTC index
```

### Validate Data Quality

```python
from src.data.validator import validate_full_suite

report = validate_full_suite(df, symbol='EURUSD')

if report['passed']:
    print(f"✓ Data validated: {report['bar_count']} bars")
else:
    print(f"✗ Validation failed: {report['checks']}")
    exit(1)
```

### Handle Missing Bars

```python
from src.data.loader import MissingBarHandler

df_filled, gap_report = MissingBarHandler.check_and_fill(
    df,
    expected_freq='D',
    strategy='forward_fill'
)

print(f"Coverage: {gap_report['coverage']:.1%}")
```

---

## Testing Strategy

### Unit Tests

- Timestamp normalization (naive, localized)
- Duplicate removal
- OHLC validation
- Date range filtering

### Integration Tests

- Full pipeline: raw → interim → processed
- No lookahead bias detection
- Gap handling with multiple strategies
- Anomaly detection accuracy

### Regression Tests

- Historical data consistency
- Re-running with same inputs = same outputs
- Validation thresholds don't silently change

---

## References

### External Resources

- [Pandas datetime handling](https://pandas.pydata.org/docs/user_guide/timeseries.html)
- [OHLC data validation](https://en.wikipedia.org/wiki/Open-high-low-close_chart)
- [Lookahead bias in backtesting](https://en.wikipedia.org/wiki/Look-ahead_bias)
- [Timezone handling best practices](https://en.wikipedia.org/wiki/ISO_8601)

### Common Data Sources

- Alpha Vantage (minute/daily)
- OANDA (FX native)
- FRED (macro)
- Quandl (alternative data)

---

## Versioning

| Version | Date    | Changes                         |
| ------- | ------- | ------------------------------- |
| 1.0     | 2023-02 | Initial spec                    |
| 1.1     | 2023-03 | Added extreme spike detection   |
| 1.2     | 2023-05 | Enhanced missing bar strategies |

---

**Last Updated**: 2023-05-15  
**Status**: PRODUCTION  
**Owner**: Data Engineering  
**Review Cycle**: Quarterly
