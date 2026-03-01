# Exhaustion Reversal Hypothesis Decomposition

**Date:** March 1, 2026  
**Instrument:** GBP/USD H1  
**Strategy:** Mean reversion after exhaustion failure-to-continue

---

## Null Hypothesis (H0)

Each feature component has **no predictive power** over forward returns in the next 1–5 bars.  
Expected mean return = 0 bps after transaction costs.

---

## Sub-Hypotheses (Independent Tests)

### Sub-H1: Directional Pressure Alone

**Feature:** `dir_pressure_2` (rolling 2-bar direction sum)  
**Hypothesis:** When directional pressure reaches ±2, the next bar shows directional bias.  
**Null:** dir_pressure_2 == ±2 has no effect on next-bar direction (IC ≈ 0)  
**Alternative:** dir_pressure_2 == ±2 predicts next-bar direction (|IC| > 0.03, p < 0.05)  
**Test:** Binary signal (pressure ≥2 or ≤-2) vs next-bar return, t-test

---

### Sub-H2: Range Expansion Alone

**Feature:** `range_expansion_10` (current range > 0.8× rolling 10-bar median)  
**Hypothesis:** Range expansion alone predicts mean reversion (negative forward returns).  
**Null:** Range expansion has no effect on forward returns  
**Alternative:** Range expansion → mean reversion, mean return < 0 (p < 0.05)  
**Test:** Binary signal (range expanded) vs forward returns 1-5h

---

### Sub-H3: Close Extreme Alone

**Feature:** `close_extreme_35` (close in top 35% for shorts, bottom 35% for longs)  
**Hypothesis:** Extreme close position predicts mean reversion.  
**Null:** Close extreme position has no predictive power  
**Alternative:** Close at extreme → reversion, mean return directionally biased (p < 0.05)  
**Test:** Binary signal vs forward returns

---

### Sub-H4: Combined Exhaustion (Without Confirmation)

**Feature:** `dir_pressure_2 AND range_expansion_10 AND close_extreme_35`  
**Hypothesis:** All 3 conditions together create exhaustion candidate that predicts reversion.  
**Null:** Combined signal no better than random (mean return ≈ 0)  
**Alternative:** Combined exhaustion → mean reversion > 10 bps (p < 0.05 post-MTC)  
**Test:** Full exhaustion signal vs forward returns, N_signals > 300 required

---

### Sub-H5: Adding Failure-to-Continue Confirmation

**Feature:** Full exhaustion + `failure_to_continue` on next bar  
**Hypothesis:** Confirmation bar improves edge over exhaustion alone.  
**Null:** Adding confirmation doesn't improve mean return  
**Alternative:** With confirmation, mean return > exhaustion alone + 3 bps (p < 0.05)  
**Test:** Compare mean returns: exhaustion+confirmation vs exhaustion-only

---

### Sub-H6: Transaction Cost Hurdle

**Feature:** Full signal (Sub-H5)  
**Hypothesis:** Edge survives realistic transaction costs (1.0 pip spread + 0.2 pip slippage).  
**Null:** Mean return after costs ≤ 0  
**Alternative:** Mean return > 10 bps after 1.2 pips round-trip cost (p < 0.05)  
**Test:** Net return = gross return - 12 bps per round trip

---

### Sub-H7: Session Filter Improves Edge

**Feature:** Full signal restricted to London (8-16 UTC) or London/NY overlap (12-16 UTC)  
**Hypothesis:** London and overlap sessions show stronger edge than NY or Asia.  
**Null:** No difference in edge across sessions  
**Alternative:** London/overlap mean return > 15 bps, NY/Asia < 8 bps (p < 0.10)  
**Test:** Stratified analysis by session, compare mean returns

---

## Acceptance Criteria (Pass/Fail Decision Gates)

### To Proceed to Full Backtest (Day 14+):

**Required (ALL must pass):**

1. ✓ At least **2 of 3** individual features (Sub-H1, Sub-H2, Sub-H3) show directional bias with p < 0.10
2. ✓ Combined exhaustion signal (Sub-H4): **mean return > 10 bps** with p < 0.05 (post-MTC)
3. ✓ **N_signals > 300** across in-sample period (10+ years H1 data)
4. ✓ Edge holds in at least **London OR overlap** sessions (p < 0.10)
5. ✓ Signal autocorrelation ACF[1] < 0.30 (signals not excessively clustered)

**Flags (Document but Continue):**

- ⚠ EUR/USD shows similar edge with signal correlation > 0.65 → USD contamination present
- ⚠ One feature interaction dominates in 2×2×2 grid → simplify hypothesis

**Critical Failures (STOP and Revise Day 11):**

- ✗ All 3 individual features show IC < 0.03 or p > 0.10
- ✗ Combined exhaustion mean return < 5 bps
- ✗ N_signals < 200 (insufficient sample size)
- ✗ EUR/GBP shows same edge as GBP/USD → signal not pair-specific
- ✗ All features VIF > 10 → redundant measurement

---

## Multiple Testing Correction

**Method:** Benjamini-Hochberg FDR correction  
**Justification:** Testing 7 hypotheses; Bonferroni too conservative for exploratory research  
**Threshold:** Adjusted p-values < 0.05 for significance

---

## Forward Return Definitions

For each horizon h ∈ {1, 2, 3, 4, 5} bars:

**SHORT signal (bearish exhaustion):**

```
forward_return = entry_price - close[t+h]
# Positive if price falls
```

**LONG signal (bullish exhaustion):**

```
forward_return = close[t+h] - entry_price
# Positive if price rises
```

**Realized return (with trailing stop):**

```
Entry: close of confirmation bar
Exit:
  - Trailing stop triggers after 4 pips profit, then trails at 3 pips
  - Fixed stop-loss at 10 pips
  - Max holding period: 5 bars (timeout)
```

---

## Pre-Registration Commitment

This document was created **before running any statistical tests** on the exhaustion hypothesis components. All sub-hypotheses, acceptance criteria, and testing procedures are defined in advance to prevent p-hacking and hindsight bias.

**Signed:** [Researcher]  
**Date:** March 1, 2026
