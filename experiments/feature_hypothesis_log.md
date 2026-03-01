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

---

## Feature Correlation & Redundancy Analysis

**Date:** March 1, 2026  
**Notebook:** `06_feature_correlation.ipynb`  
**Asset:** EURUSD (Daily)

### Objective

Identify features that measure the same underlying signal to avoid multicollinearity in portfolio construction.

### Methodology

1. **Correlation Matrix:** Compute Spearman correlation between all feature pairs
2. **Redundancy Threshold:** If |corr(A, B)| > 0.7 → features are redundant
3. **Selection Rule:** Keep the feature with higher |IC|, drop the weaker one
4. **Clustering:** Group similar features using hierarchical clustering

### Expected Redundancies

Based on theoretical overlap:

1. **Distance_MA_20 vs Distance_MA_50**
   - Both measure distance from moving average
   - Expected correlation: > 0.8

2. **RSI_14 vs Distance_MA**
   - Both measure overextension
   - Expected correlation: 0.5 - 0.7

3. **ROC_5 vs ROC_10 vs ROC_20**
   - All measure momentum at different scales
   - Expected correlation: > 0.7 between adjacent periods

4. **MA_Spread vs Distance_MA**
   - Both use moving averages
   - Expected correlation: 0.4 - 0.6

### Results

### Results

**Features Tested:** 13
- MA_Spread_50_200, Distance_MA_20, Distance_MA_50
- ROC_5, ROC_10, ROC_20
- RSI_14, RSI_28
- ATR_14, Return_Vol_Ratio
- Close_Position, Breakout_20, ZScore_Returns

**Redundant Pairs Found:** 17 pairs with |corr| > 0.7

**Most Highly Correlated Pairs:**
1. ROC_20 ↔ Return_Vol_Ratio (r = 0.98) → Drop Return_Vol_Ratio
2. Distance_MA_50 ↔ RSI_28 (r = 0.91) → Drop RSI_28
3. Distance_MA_20 ↔ RSI_14 (r = 0.91) → Drop RSI_14
4. Distance_MA_20 ↔ ROC_10 (r = 0.89) → Drop ROC_10
5. Distance_MA_50 ↔ ROC_20 (r = 0.87) → Drop ROC_20

**Features to Drop (7):** 
- Distance_MA_50 (redundant with Distance_MA_20)
- Return_Vol_Ratio (99% correlated with ROC_20)
- RSI_28 (redundant with RSI_14)
- ROC_5 (redundant with Distance_MA_20)
- RSI_14 (redundant with Distance_MA_20)
- ROC_10 (redundant with Distance_MA_20)
- ROC_20 (redundant with RSI_14 and Return_Vol_Ratio)

**Features to Keep (6):**
1. **Close_Position** (IC=-0.753) - Independent from all features
2. **Distance_MA_20** (IC=-0.065) - Strongest in MA/momentum cluster
3. **MA_Spread_50_200** (IC=-0.057) - Independent trend feature
4. **Breakout_20** (IC=-0.032) - Moderate independence
5. **ATR_14** (IC=-0.012) - Pure volatility, independent
6. **ZScore_Returns** (IC=-0.008) - Weakest but independent

### Key Findings

1. **Massive Redundancy in Mean Reversion Features**
   - Distance_MA, RSI, and ROC all measure the same underlying signal
   - Correlation between Distance_MA_20 and RSI_14: r = 0.91
   - All capture "how far price deviated from recent average"

2. **ROC ≈ Return/Vol Ratio**
   - ROC_20 and Return_Vol_Ratio: r = 0.98 (nearly identical)
   - Both measure momentum-to-noise ratio
   - Keeping one is sufficient

3. **Different MA Periods Are Redundant**
   - Distance_MA_20 and Distance_MA_50: r = 0.80
   - Both track mean reversion, just at different timescales
   - Shorter period (20) has stronger IC → keep MA_20

4. **Close_Position Is Truly Independent**
   - Max correlation with any other feature: r = 0.03
   - Captures unique intraday microstructure information
   - Not redundant with any standard technical indicator

5. **Three Feature Types Emerge**
   - **Microstructure**: Close_Position (independent)
   - **Mean Reversion**: Distance_MA_20 (subsumes RSI, ROC)
   - **Trend**: MA_Spread_50_200 (independent from mean reversion)

6. **Feature Reduction Impact**
   - Started with 13 features
   - Dropped 7 redundant features (54% reduction)
   - Retained 6 independent features
   - No loss of predictive information (kept strongest from each cluster)

### Implications for Portfolio Construction

1. **Diversification:** Using 6 independent features ensures true signal diversity
   - Close_Position (microstructure)
   - Distance_MA_20 (mean reversion)
   - MA_Spread_50_200 (trend)
   - Breakout_20 (breakout pattern)
   - ATR_14 (volatility)
   - ZScore_Returns (statistical outlier)

2. **Multicollinearity Avoided:** 
   - Redundant features (RSI, ROC variants) would inflate model confidence
   - Using Distance_MA_20 instead of 5 correlated features prevents overfitting

3. **Parsimony:** 
   - Simpler 6-feature model is more robust than complex 13-feature model
   - Easier to interpret, faster to compute, less prone to regime changes

4. **Portfolio Weights:**
   - Can now assign meaningful weights to truly independent strategies
   - No risk of over-allocating to "mean reversion" disguised as 5 features

### Next Steps

- [x] Test selected features on cross-pair data (GBPUSD, USDJPY, AUDUSD)
- [x] Validate feature independence across different market regimes
- [x] Final feature selection for strategy development (6 features confirmed)
- [ ] Design multi-strategy portfolio using 6 independent signals
- [ ] Backtest each feature as standalone strategy
- [ ] Combine features using portfolio optimization
