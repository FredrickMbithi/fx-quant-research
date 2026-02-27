# Feature Hypothesis Log

## Purpose
Document every feature tested, with rationale and outcome.

## Format
### Feature: [Name]
- **Category:** [Trend/Mean Reversion/etc]
- **Hypothesis:** [Why this might predict returns]
- **Lookback Period:** [X bars]
- **Expected Stationarity:** [Yes/No]
- **Test Date:** [YYYY-MM-DD]
- **Outcome:** [Predictive/Not Predictive/Inconclusive]
- **Notes:** [Key findings]

---

### Feature: MA Spread (50/200)
- **Category:** Trend
- **Hypothesis:** Positive spread (50MA > 200MA) indicates persistent uptrend due to slow-moving institutional capital
- **Lookback Period:** 50, 200
- **Expected Stationarity:** Yes (spread should mean-revert long-term)
- **Test Date:** 2025-02-23
- **Outcome:** [To be filled after testing]
- **Notes:** 

---

### Feature: Distance from 20MA
- **Category:** Mean Reversion
- **Hypothesis:** Extreme distance from MA indicates temporary mispricing, should revert
- **Lookback Period:** 20
- **Expected Stationarity:** Yes
- **Test Date:** 2025-02-23
- **Outcome:** [To be filled]
- **Notes:**

---

### Feature: ATR (14-period)
- **Category:** Volatility
- **Hypothesis:** Volatility expansion precedes trend continuation; contractions precede breakouts
- **Lookback Period:** 14
- **Expected Stationarity:** No (volatility clusters)
- **Test Date:** 2025-02-23
- **Outcome:** [To be filled]
- **Notes:**

---

### Feature: RSI (14-period)
- **Category:** Mean Reversion
- **Hypothesis:** RSI < 30 indicates oversold conditions (potential bounce); RSI > 70 indicates overbought (potential reversal)
- **Lookback Period:** 14
- **Expected Stationarity:** Yes (bounded 0-100)
- **Test Date:** 2025-02-23
- **Outcome:** [To be filled]
- **Notes:**

---

### Feature: Return/Vol Ratio
- **Category:** Trend
- **Hypothesis:** High return/volatility ratio indicates strong directional move with conviction (risk-adjusted momentum)
- **Lookback Period:** [To be determined]
- **Expected Stationarity:** Yes
- **Test Date:** 2025-02-23
- **Outcome:** [To be filled]
- **Notes:**

---

### Feature: Close Position in Range
- **Category:** Microstructure
- **Hypothesis:** Close near high of bar indicates buying pressure and potential continuation; near low indicates selling pressure
- **Lookback Period:** 1 (per-bar)
- **Expected Stationarity:** Yes (bounded 0-1)
- **Test Date:** 2025-02-23
- **Outcome:** [To be filled]
- **Notes:**
