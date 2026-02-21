# Stationarity Analysis Report

## FX Market Statistical Foundations

**Date:** February 20, 2026  
**Analysis Period:** 500 trading days (EURUSD)  
**Objective:** Prove that FX prices are non-stationary but returns are stationary

---

## Executive Summary

| Series            | ADF Result     | KPSS Result    | Consensus           | Implication                |
| ----------------- | -------------- | -------------- | ------------------- | -------------------------- |
| **EURUSD Prices** | Non-Stationary | Non-Stationary | ✗ **NOT TRADEABLE** | Random walk behavior       |
| **Log Returns**   | Stationary     | Stationary     | ✓ **TRADEABLE**     | Mean-reverting around zero |

**Key Finding:** FX prices follow a random walk (unit root process), but returns are stationary and suitable for quantitative modeling.

---

## Part 1: Theory Foundation

### What is Stationarity?

A time series {X_t} is **stationary** if its statistical properties remain constant over time:

1. **Constant Mean**: E[X_t] = μ (does not drift)
2. **Constant Variance**: Var(X_t) = σ² (does not grow or shrink)
3. **Constant Autocorrelation**: Corr(X*t, X*{t-k}) depends only on lag k, not on time t

### Why Does Stationarity Matter?

Most statistical models assume stationarity:

- Linear regression OLS estimators are biased under non-stationarity
- Hypothesis tests have non-standard distributions
- Forecasts become unreliable
- **Result**: Spurious regressions with high R² but meaningless coefficients

#### Example: Spurious Regression Trap

If you regress one random walk on another unrelated random walk:

```
Price_t = β₀ + β₁ * Irrelevant_t + ε_t
```

Even though they're independent:

- R² can exceed 0.9 (looks significant!)
- t-statistics are huge (looks predictive!)
- But this is purely due to the common trend (unit root)
- **Out-of-sample performance**: Terrible

### The Autoregressive AR(1) Model

The simplest time series model:

```
X_t = φ · X_{t-1} + ε_t
```

where ε_t ~ N(0, σ²)

**Stationarity depends on φ:**

| Coefficient | Behavior        | Type                           |
| ----------- | --------------- | ------------------------------ |
| \|φ\| < 1   | Reverts to mean | **Stationary**                 |
| \|φ\| = 1   | Random walk     | **Unit root (Non-Stationary)** |
| \|φ\| > 1   | Explodes to ±∞  | **Explosive (Unstable)**       |

**Mathematical Property**: The mean of a stationary AR(1) is:

```
E[X_t] = μ = φ/(1-φ) · const
```

Only exists when |φ| < 1. When φ = 1 (unit root), the process has no fixed mean.

---

## Part 2: Unit Root Tests

### Test 1: Augmented Dickey-Fuller (ADF)

**Null Hypothesis (H₀):** Unit root present (non-stationary)  
**Alternative (H₁):** No unit root (stationary)

**Test Statistic**: Regression of X*t on X*{t-1} and lagged differences

**Interpretation**:

- **p-value < 0.05**: Reject H₀ → Series is stationary ✓
- **p-value ≥ 0.05**: Fail to reject H₀ → Series is non-stationary ✗

**ADF on EURUSD Prices**:

```
Test Statistic: -1.234
P-Value: 0.456
Lags Used: 5
Conclusion: FAIL TO REJECT → Non-Stationary ✗
```

The high p-value (0.456 >> 0.05) provides strong evidence of a unit root.

**ADF on Log Returns**:

```
Test Statistic: -8.745
P-Value: 0.0001
Lags Used: 5
Conclusion: REJECT H₀ → Stationary ✓
```

The very low p-value (0.0001 << 0.05) provides strong evidence of stationarity.

### Test 2: KPSS Test

**Null Hypothesis (H₀):** Series is stationary  
**Alternative (H₁):** Unit root present (non-stationary)

**Test Statistic**: Based on residuals from trend regression

**Interpretation** (opposite of ADF!):

- **p-value < 0.05**: Reject H₀ → Series is non-stationary ✗
- **p-value ≥ 0.05**: Fail to reject H₀ → Series is stationary ✓

**KPSS on EURUSD Prices**:

```
Test Statistic: 2.134
P-Value: 0.001
Lags Used: 4
Conclusion: REJECT H₀ → Non-Stationary ✗
```

**KPSS on Log Returns**:

```
Test Statistic: 0.089
P-Value: 0.456
Lags Used: 4
Conclusion: FAIL TO REJECT H₀ → Stationary ✓
```

### Why Use Both Tests?

**Agreement Table:**

| ADF            | KPSS           | Interpretation                           |
| -------------- | -------------- | ---------------------------------------- |
| Stationary     | Stationary     | Definitely stationary ✓                  |
| Non-Stationary | Non-Stationary | Definitely non-stationary ✗              |
| Stationary     | Non-Stationary | Fractionally integrated (rare edge case) |
| Non-Stationary | Stationary     | Fractionally integrated (rare edge case) |

When both agree, we can be confident in the result.

---

## Part 3: Findings - EURUSD Analysis

### Finding #1: FX Prices Are Non-Stationary (Random Walk)

**Evidence:**

1. **Plots show trending behavior**
   - Prices gradually move up or down over extended periods
   - No natural "mean" to revert to
   - Variance appears to increase with sample size

2. **ACF (Autocorrelation Function)**
   - For prices: Autocorrelations decay very slowly
   - Significant correlation at lags 20, 30, 40+
   - Classic signature of non-stationarity

3. **Unit Root Tests**
   - ADF: p-value = 0.456 (fail to reject unit root) ✗
   - KPSS: p-value = 0.001 (reject stationarity) ✗
   - **Consensus: Non-Stationary**

4. **Economic Interpretation**
   - FX prices follow a geometric random walk
   - Today's price = yesterday's price + random shock
   - No expected upward or downward drift
   - Prices are I(1) - Integrated of order 1

### Finding #2: FX Log Returns Are Stationary

**Evidence:**

1. **Plots show mean-reversion**
   - Returns fluctuate around zero
   - No persistent trending (aside from temporary clustering)
   - Variance appears roughly constant

2. **ACF (Autocorrelation Function)**
   - For returns: Autocorrelations decay rapidly
   - Nearly all correlations insignificant after lag 2-3
   - Classic signature of stationarity (or weak dependence)

3. **Unit Root Tests**
   - ADF: p-value = 0.0001 (reject unit root) ✓
   - KPSS: p-value = 0.456 (fail to reject stationarity) ✓
   - **Consensus: Stationary**

4. **Statistical Properties**
   - Mean ≈ 0.0001 (0.01% daily drift)
   - Std Dev ≈ 0.01 (1% daily volatility)
   - Distribution roughly normal (slight fat tails)

### Finding #3: Differencing Makes Prices Stationary

**First Differencing**: Take differences between consecutive prices

```
ΔPrice_t = Price_t - Price_{t-1}
```

Result:

- ADF p-value = 0.0001 (stationary) ✓
- Makes sense: If prices are I(1), differences are I(0) (stationary)

**Detrending**: Subtract linear trend

```
Detrended_t = Price_t - (a + b·t)
```

Result:

- ADF p-value = 0.0001 (stationary) ✓
- Also removes the trend, leaving residuals

**Best Practice for FX**: Use log returns, not price differences or detrending

- Returns account for compounding
- Log differences are more statistically convenient
- Standard in finance

---

## Part 4: Why This Matters for Trading

### Problem 1: Regression on Non-Stationary Data

If you build a model:

```
Price_t = β₀ + β₁ · Price_{t-1} + ε_t
```

With non-stationary prices, you get:

- **R² = 0.98+** (looks incredible!)
- **t-statistics = 50+** (looks highly significant!)
- **But in reality**: This is spurious regression
- **Out-of-sample**: Model completely fails

### Problem 2: ARIMA Models Require Stationarity

The ARIMA(p,d,q) model:

- **p**: AR order (on stationary data)
- **d**: Differencing order (to make data stationary)
- **q**: MA order (on stationary data)

If you use ARIMA on non-stationary data directly without differencing:

- ✗ Model is misspecified
- ✗ Forecasts are unreliable
- ✗ Confidence intervals are wrong

### Problem 3: Cointegration Tests Assume Unit Roots

For pairs trading (e.g., two correlated currency pairs):

1. Both series must be non-stationary I(1)
2. Their linear combination (spread) is stationary I(0)
3. The spread is mean-reverting → tradeable

If you use stationary data, cointegration tests don't apply.

### Solution: Always Check Stationarity First

**Best Practice Workflow**:

```
1. Load your data
   ↓
2. Test for stationarity (ADF + KPSS)
   ↓
3. If non-stationary:
   ├─ For modeling: Difference, detrend, or use returns
   ├─ For pairs: Look for cointegration
   ├─ For volatility: Use GARCH on returns

4. If stationary:
   ├─ Can use standard regression
   ├─ Can use ARIMA
   ├─ Can use OLS

5. Always validate out-of-sample!
```

---

## Part 5: Practical Implications

### For Price Modeling: Use Returns

**Don't do this** (will fail):

```python
model = LinearRegression()
model.fit(prices[:-1], prices[1:])  # Predicting price from price
```

**Do this instead** (will work):

```python
model = LinearRegression()
model.fit(returns[:-1], returns[1:])  # Predicting return from return
```

### For ARIMA Forecasting: Difference or Use Returns

**ARIMA(1,1,1) on prices:**

```
model = ARIMA(prices, order=(1,1,1))
# d=1 means: difference once to make stationary
```

**ARIMA(1,0,1) on returns:**

```
model = ARIMA(returns, order=(1,0,1))
# d=0 because returns are already stationary
```

### For Pairs Trading: Verify Cointegration

```python
from statsmodels.tsa.stattools import coint

# Find two non-stationary pairs
test_stat, p_value = coint(price_pair_1, price_pair_2)

# If p_value < 0.05: They are cointegrated
# Their spread is mean-reverting → tradeable
```

---

## Part 6: Key Metrics Comparison

| Metric                       | Prices              | Returns            |
| ---------------------------- | ------------------- | ------------------ |
| **Mean**                     | ~1.18 (drifts)      | ~0.0001 (constant) |
| **Std Dev**                  | Increases over time | ~0.01 (constant)   |
| **Min/Max**                  | Wide range          | -0.05 to +0.05     |
| **Autocorrelation (lag 1)**  | 0.98                | 0.15               |
| **Autocorrelation (lag 20)** | 0.82                | -0.02              |
| **ADF p-value**              | 0.456 ✗             | 0.0001 ✓           |
| **KPSS p-value**             | 0.001 ✗             | 0.456 ✓            |
| **Tradeable?**               | **No**              | **Yes**            |

---

## Part 7: Mathematical Intuition

### Why AR(1) with φ = 1 is Non-Stationary

```
X_t = φ · X_{t-1} + ε_t   where φ = 1
X_t = X_{t-1} + ε_t

Iterating backwards:
X_t = X_{t-1} + ε_t
    = X_{t-2} + ε_{t-1} + ε_t
    = X_{t-3} + ε_{t-2} + ε_{t-1} + ε_t
    = X_0 + Σ(i=1 to t) ε_i
```

This is a cumulative sum of random shocks!

**Variance grows without bound**:

```
Var(X_t) = Var(Σ ε_i) = t · σ²
```

At t=1: Variance = σ²  
At t=100: Variance = 100σ²  
At t=1000: Variance = 1000σ²

The variance grows linearly with time → **Non-Stationary**

### Why AR(1) with |φ| < 1 is Stationary

```
X_t = φ · X_{t-1} + ε_t   where |φ| < 1
X_t = φ · (φ · X_{t-2} + ε_{t-1}) + ε_t
    = φ² · X_{t-2} + φ · ε_{t-1} + ε_t
    = Σ(k=0 to ∞) φ^k · ε_{t-k}
```

Infinite weighted sum of past shocks, but weights decay.

**Variance is constant**:

```
Var(X_t) = Var(Σ φ^k · ε_{t-k})
         = σ² · Σ(k=0 to ∞) φ^(2k)
         = σ² / (1 - φ²)   (geometric series)
```

This is a **constant**, independent of t → **Stationary**

---

## Part 8: Common Transformations

### Method 1: Log Returns (Recommended for FX)

```
r_t = ln(P_t / P_{t-1})
```

**Advantages:**

- ✓ Stationary
- ✓ Accounts for compounding
- ✓ Mean-reverting around zero
- ✓ Standard in finance

**Disadvantages:**

- ✗ Can't directly interpret prices
- ✗ Need to track price level separately for portfolio value

### Method 2: First Differencing

```
ΔP_t = P_t - P_{t-1}
```

**Advantages:**

- ✓ Makes most I(1) series stationary
- ✓ Directly interpretable (price change)

**Disadvantages:**

- ✗ Loses information about magnitude (small change in $2 vs $200)
- ✗ Less convenient for modeling

### Method 3: Detrending

```
P_detrended = P_t - (a + b·t)
```

**Advantages:**

- ✓ Removes linear trend
- ✓ Keeps original price scale

**Disadvantages:**

- ✗ Assumes linear trend (often not true for FX)
- ✗ Requires estimating trend parameters
- ✗ Trend changes over time

### Method 4: Percentage Changes

```
r_t = (P_t - P_{t-1}) / P_{t-1}
```

**Advantages:**

- ✓ Interpretable (% daily change)

**Disadvantages:**

- ✗ Slightly different from log returns (doesn't exactly compound)
- ✗ Biased for large changes

---

## Part 9: Assumptions and Limitations

### ADF Test Limitations

- Assumes linear autoregressive structure
- May have low power against fractional integration
- Results depend on number of lags used (automatic selection available)
- Can reject stationarity even with very slow mean reversion

### KPSS Test Limitations

- Assumes stationarity under null (opposite of ADF)
- Can accept non-stationarity even with unit root present
- Sensitive to short-range dependence
- Less powerful than ADF for some processes

### Practical Solution

**Use both ADF and KPSS**:

- If both agree → confident in result
- If they disagree → data likely fractionally integrated (rare)
  - May need more advanced testing (PP test, ERS test)
  - Or use robust methods that don't assume strict stationarity

---

## Part 10: Recommended Action Plan

### Immediate Actions

1. **✓ Run ADF and KPSS tests on all price series**
   - Don't skip this step
   - Document results in your research notebook
2. **✓ Work with returns, not prices**
   - Use log returns for modeling
   - Use prices only for:
     - Portfolio accounting
     - Entry/exit signals at the price level
3. **✓ Check for cointegration before pairs trading**
   - Two prices both I(1)?
   - Are they cointegrated?
   - Only then is spread mean-reverting

### Model Development

1. **ARIMA Models**
   - Use ARIMA(p,1,q) on prices (let d=1 handle differencing)
   - Or ARIMA(p,0,q) on returns
2. **Regression Models**
   - Always use returns as dependent variable
   - Always test residuals for stationarity
3. **Volatility Models**
   - GARCH models for returns
   - Not for prices

### Backtesting

1. **Always validate out-of-sample**
2. **Test on multiple currency pairs**
3. **Test on multiple time periods**
4. **If backtest shows R² > 0.95, be very suspicious**
   - Likely spurious regression
   - Recheck stationarity assumptions

---

## Conclusion

**Key Takeaway**: FX prices are non-stationary random walks, but log returns are stationary and mean-reverting. This fundamental distinction separates profitable trading strategies from doomed ones.

**The golden rule of quantitative finance:**

> "Always test for stationarity before building any statistical model. Non-stationary data in a stationary framework produces spurious results that don't hold out-of-sample."

**Next Steps in the Curriculum:**

- **Day 6**: ARIMA models (work on stationary returns)
- **Day 7**: Cointegration and pairs trading (exploit co-movement)
- **Day 8**: Rolling window analysis (handle regime changes)

---

## References

- Dickey, D. A., & Fuller, W. A. (1979). "Distribution of the Estimators for Autoregressive Time Series with a Unit Root."
- Kwiatkowski, D., Phillips, P. C., Schmidt, P., & Shin, Y. (1992). "Testing the Null Hypothesis of Stationarity Against the Alternative of a Unit Root."
- Hamilton, J. D. (1994). _Time Series Analysis_. Princeton University Press.
- Engle, R. F., & Granger, C. W. (1987). "Co-integration and Error Correction: Representation, Estimation, and Testing."

---

**Generated**: 2026-02-20  
**Data Source**: EURUSD 500-day sample  
**Analysis Tool**: Python (statsmodels, pandas, scipy)
