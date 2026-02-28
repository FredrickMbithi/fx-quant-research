# Feature Test Results — EURUSD Daily

**Test Date:** 2026-03-01  
**Data Period:** 2016-02-23 to 2026-02-19  
**Sample Size:** 2,600 bars

## Summary

Tested 9 candidate features for forward return predictability.

**Significance Criteria:**

- |IC| > 0.05
- t-stat > 2.0
- Stationarity: Yes

## Results

### 1. MA Spread (50/200)

- **IC Mean:** [To be filled]
- **IC Std:** [To be filled]
- **IC t-stat:** [To be filled]
- **Hit Rate:** [To be filled]
- **Monotonicity:** [To be filled]
- **Stationary:** [Yes/No]
- **Decay Half-Life:** [X bars]
- **Verdict:** [Pass/Fail]
- **Notes:** Moving average spread tests trend persistence hypothesis. Expected positive IC if momentum exists.

### 2. Distance from 20 MA

- **IC Mean:** [To be filled]
- **IC Std:** [To be filled]
- **IC t-stat:** [To be filled]
- **Hit Rate:** [To be filled]
- **Monotonicity:** [To be filled]
- **Stationary:** [Yes/No]
- **Decay Half-Life:** [X bars]
- **Verdict:** [Pass/Fail]
- **Notes:** Mean reversion hypothesis—large distances should predict reversals.

### 3. ATR (14-period)

- **IC Mean:** [To be filled]
- **IC Std:** [To be filled]
- **IC t-stat:** [To be filled]
- **Hit Rate:** [To be filled]
- **Monotonicity:** [To be filled]
- **Stationary:** [Yes/No]
- **Decay Half-Life:** [X bars]
- **Verdict:** [Pass/Fail]
- **Notes:** Volatility expansion as trend continuation signal.

### 4. RSI (14-period)

- **IC Mean:** [To be filled]
- **IC Std:** [To be filled]
- **IC t-stat:** [To be filled]
- **Hit Rate:** [To be filled]
- **Monotonicity:** [To be filled]
- **Stationary:** [Yes/No]
- **Decay Half-Life:** [X bars]
- **Verdict:** [Pass/Fail]
- **Notes:** Classic mean reversion indicator. Should be stationary (bounded).

### 5. Return/Vol Ratio (20-period)

- **IC Mean:** [To be filled]
- **IC Std:** [To be filled]
- **IC t-stat:** [To be filled]
- **Hit Rate:** [To be filled]
- **Monotonicity:** [To be filled]
- **Stationary:** [Yes/No]
- **Decay Half-Life:** [X bars]
- **Verdict:** [Pass/Fail]
- **Notes:** Risk-adjusted momentum—high ratio indicates strong trend with low noise.

### 6. Close Position in Range

- **IC Mean:** [To be filled]
- **IC Std:** [To be filled]
- **IC t-stat:** [To be filled]
- **Hit Rate:** [To be filled]
- **Monotonicity:** [To be filled]
- **Stationary:** [Yes/No]
- **Decay Half-Life:** [X bars]
- **Verdict:** [Pass/Fail]
- **Notes:** Microstructure signal—close near high indicates buying pressure.

### 7. Rate of Change (10-period)

- **IC Mean:** [To be filled]
- **IC Std:** [To be filled]
- **IC t-stat:** [To be filled]
- **Hit Rate:** [To be filled]
- **Monotonicity:** [To be filled]
- **Stationary:** [Yes/No]
- **Decay Half-Life:** [X bars]
- **Verdict:** [Pass/Fail]
- **Notes:** Simple momentum indicator—tests if recent momentum persists.

### 8. Z-Score Returns (20-period)

- **IC Mean:** [To be filled]
- **IC Std:** [To be filled]
- **IC t-stat:** [To be filled]
- **Hit Rate:** [To be filled]
- **Monotonicity:** [To be filled]
- **Stationary:** [Yes/No]
- **Decay Half-Life:** [X bars]
- **Verdict:** [Pass/Fail]
- **Notes:** Standardized mean reversion signal—extreme z-scores predict reversals.

### 9. Breakout Indicator (20-period)

- **IC Mean:** [To be filled]
- **IC Std:** [To be filled]
- **IC t-stat:** [To be filled]
- **Hit Rate:** [To be filled]
- **Monotonicity:** [To be filled]
- **Stationary:** [Yes/No]
- **Decay Half-Life:** [X bars]
- **Verdict:** [Pass/Fail]
- **Notes:** Tests if breakouts predict trend continuation.

## Key Findings

1. [Feature X] shows strongest predictive power (IC = Y, t-stat = Z)
2. [Feature A] is not stationary → reject despite high IC
3. [Feature B] has insufficient IC (< 0.05) → reject
4. Mean reversion features have shorter half-life than trend features
5. Hit rates above 52% indicate directional predictability

## Feature Categories Analysis

### Trend Features

- Expected: Positive IC in trending markets
- Findings: [To be filled]

### Mean Reversion Features

- Expected: Negative IC for extreme values
- Findings: [To be filled]

### Volatility Features

- Expected: Regime detection capability
- Findings: [To be filled]

### Microstructure Features

- Expected: Short-term predictability
- Findings: [To be filled]

## Statistical Robustness

- **IC Stability:** Assessed via rolling 1-year windows
- **Stationarity:** ADF test with 5% significance
- **Decay Analysis:** IC measured at 1-20 bar horizons

## Next Steps

1. Test accepted features on other FX pairs (GBPUSD, USDJPY, GBPJPY)
2. Investigate time-varying IC for top features
3. Combine top 2-3 features in multi-factor model
4. Test feature interactions (e.g., trend + volatility regime)
5. Reject features with IC < 0.03 or non-stationary

## References

- Aronson, D. (2006). _Evidence-Based Technical Analysis_
- Lopez de Prado, M. (2018). _Advances in Financial Machine Learning_, Chapter 5
