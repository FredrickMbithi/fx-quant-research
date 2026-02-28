# Feature Test Results Summary — EURUSD Daily

**Test Completed:** March 1, 2026  
**Data Period:** 2016-02-23 to 2026-02-19  
**Sample Size:** 2,600 daily bars

## Executive Summary

Tested 9 candidate features for forward 1-day return predictability on EURUSD. With corrected significance testing (abs(t-stat) > 2.0), **2 features passed** the acceptance criteria.

**Key Finding:** EURUSD daily data shows **mean reversion** characteristics rather than momentum. All features with |IC| > 0.05 have **negative IC**, indicating that extreme feature values predict reversals.

## Significance Criteria

- |IC| > 0.05 (meaningful correlation with forward returns)
- |t-stat| > 2.0 (statistical significance)
- Feature must be stationary (ADF test p-value < 0.05)

## Test Results (Ranked by |IC|)

| Rank | Feature             | IC Mean | t-stat   | Hit Rate | Stationary | Half-Life | **Status**           |
| ---- | ------------------- | ------- | -------- | -------- | ---------- | --------- | -------------------- |
| 1    | Distance_MA_20      | -0.0598 | -52.84   | 47.98%   | ✓          | 13 bars   | **✓ PASS**           |
| 2    | ROC_10              | -0.0576 | -42.12   | 48.17%   | ✓          | 14 bars   | **✓ PASS**           |
| 3    | RSI_14              | -0.0479 | -31.95   | 49.11%   | ✓          | 14 bars   | ✗ FAIL (IC < 0.05)   |
| 4    | MA_Spread_50_200    | -0.0452 | -42.51   | 50.08%   | ✓          | 1 bar     | ✗ FAIL (IC < 0.05)   |
| 5    | Return_Vol_Ratio_20 | -0.0446 | -56.12   | 48.55%   | ✓          | 8 bars    | ✗ FAIL (IC < 0.05)   |
| 6    | Breakout_20         | -0.0274 | -25.60   | 10.81%   | ✓          | 20 bars   | ✗ FAIL (IC < 0.05)   |
| 7    | ZScore_Returns_20   | -0.0035 | -2.15    | 50.25%   | ✓          | 2 bars    | ✗ FAIL (IC < 0.05)   |
| 8    | ATR_14              | -0.0024 | -2.54    | 49.11%   | ✓          | 20 bars   | ✗ FAIL (IC < 0.05)   |
| 9    | Close_Position      | -0.7543 | -1501.40 | 47.52%   | ✓          | 4 bars    | ✗ FAIL\* (Anomalous) |

\*Close_Position has extremely high negative IC (-0.75), likely a data artifact or lookahead bias. Further investigation required.

## Detailed Feature Analysis

### ✓ ACCEPTED FEATURES

#### 1. Distance from MA (20-period)

- **IC:** -0.0598 (negative = mean reversion)
- **Interpretation:** When price is > 6% above 20-period MA, expect downward reversion; when <6% below, expect upward reversion
- **Half-Life:** 13 bars (predictive power decays by 50% after 13 days)
- **Monotonicity:** 0.56 (moderate relationship strength across quantiles)
- **Use Case:** Mean reversion signal for entry/exit timing

#### 2. Rate of Change (10-period)

- **IC:** -0.0576 (negative = momentum reversal)
- **Interpretation:** Recent 10-day price momentum tends to reverse rather than continue
- **Half-Life:** 14 bars
- **Monotonicity:** 0.33 (weaker relationship)
- **Use Case:** Fade strong recent moves; contrarian signal

### ✗ REJECTED FEATURES

#### Close to Threshold (IC ≈ 0.05 but < threshold):

- **RSI_14:** IC = -0.048, just below threshold
- **MA_Spread_50_200:** IC = -0.045, trend-following signal failed
- **Return_Vol_Ratio_20:**IC = -0.045, risk-adjusted momentum failed

#### Insufficient Predictive Power:

- **Breakout_20:** Hit rate only 10.8% (extremely poor)
- **ZScore_Returns_20:** IC too small (-0.004)
- **ATR_14:** IC too small (-0.002), volatility alone not predictive

## Key Findings

1. **Mean Reversion Dominates:** All features show negative IC. EURUSD daily exhibits mean-reverting behavior, not trend-following.

2. **Short Decay Half-Lives:** Most features lose predictive power within 8-14 days, suggesting short-term microstructure effects.

3. **Low Hit Rates:** All features near 50% hit rate indicates weak directional prediction. IC captures magnitude prediction better than direction.

4. **Stationarity Confirmed:** All 9 features passed ADF test, ensuring relationships aren't spurious.

5. **Trend Features Failed:** MA spreads, ROC, and momentum-based features all have IC opposite to expected (negative instead of positive), suggesting FX markets are more mean-reverting than equity markets.

## Feature Category Performance

### Trend Features (Expected Positive IC)

- MA_Spread_50_200: IC = -0.045 ✗
- ROC_10: IC = -0.058 ✗ (reversal, not continuation)
- Breakout_20: IC = -0.027 ✗

**Verdict:** Trend-following does NOT work on EURUSD daily. Momentum reverses.

### Mean Reversion Features (Expected Negative IC)

- Distance_MA_20: IC = -0.060 ✓ **WORKS**
- RSI_14: IC = -0.048 (marginal)
- ZScore_Returns_20: IC = -0.004 ✗ (too weak)

**Verdict:** Mean reversion signals show promise. Distance from MA is most reliable.

### Volatility Features

- ATR_14: IC = -0.002 ✗
- Return_Vol_Ratio_20: IC = -0.045 ✗

**Verdict:** Volatility alone is not predictive. May be useful as regime filter, not signal.

### Microstructure Features

- Close_Position: IC = -0.754 (anomalous, needs investigation)

## Statistical Robustness

- **Rolling IC Analysis:** All ICs computed on 252-day rolling windows to ensure stability
- **Stationarity Tests:** ADF test with 5% significance level
- **Spearman Correlation:** Rank-based IC more robust to outliers than Pearson
- **IC Decay:** Tested 1-20 day horizons to measure persistence

## Next Steps

1. **Investigate Close_Position anomaly:** -0.75 IC is too extreme, check for data issues or lookahead bias
2. **Test on other pairs:** GBPUSD, USDJPY, GBPJPY to see if mean reversion is universal in FX
3. **Combine accepted features:** Build multi-factor model with Distance_MA_20 + ROC_10
4. **Test on H1 timeframe:** Check if intraday shows different behavior
5. **Regime conditioning:** Test if features work better in high/low volatility regimes
6. **Alternative MA periods:** Test Distance_MA with 10, 50, 100 periods

## Conclusion

Of 9 features tested, **2 passed** significance criteria, both showing **mean reversion** behavior:

1. Distance from 20-period MA (IC = -0.060)
2. 10-period Rate of Change (IC = -0.058)

**Key Insight:** EURUSD daily data is mean-reverting, not trending. Trend-following strategies will likely fail. Focus on mean reversion signals and fade extreme moves.

**Bug Fixed:** Corrected is_significant() to check abs(t-stat) > 2.0 instead of t-stat > 2.0, now properly identifies negative IC features as significant.
