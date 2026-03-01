# Days 11-13: Exhaustion Hypothesis Validation Framework

**Implementation Date:** March 1, 2026  
**Status:** Ready for execution

---

## Overview

This framework implements statistical validation of the exhaustion reversal hypothesis following the rigorous Day 11-13 protocol:

- **Day 11**: Feature taxonomy and hypothesis decomposition (pre-registration)
- **Day 12**: Univariate testing with multiple testing correction
- **Day 13**: Cross-pair validation and interaction analysis

---

## File Structure

```
experiments/
  ├── exhaustion_feature_registry.csv           # Feature taxonomy
  └── exhaustion_hypothesis_decomposition.md    # 7 sub-hypotheses with acceptance criteria

src/features/
  └── exhaustion_features.py                    # Lookahead-clean feature builder

scripts/
  ├── test_exhaustion_univariate.py            # Day 12: Test each sub-hypothesis
  ├── analyze_exhaustion_by_session.py         # Day 12: Session breakdown (Sub-H7)
  ├── run_exhaustion_cross_pair.py             # Day 13: Cross-pair contamination detection
  └── analyze_exhaustion_interactions.py       # Day 13: 2×2×2 grid + correlation matrices
```

---

## Execution Sequence

### Step 1: Review Pre-Registered Hypotheses (Day 11)

**No code execution required** — documentation phase.

Read the hypothesis decomposition document to understand what we're testing:

```bash
cat experiments/exhaustion_hypothesis_decomposition.md
```

**Key artifacts:**

- 7 sub-hypotheses (H1-H7) defined before seeing any results
- Acceptance criteria established (prevents p-hacking)
- Feature registry with lookahead audit status

---

### Step 2: Run Univariate Tests (Day 12)

Test each hypothesis component independently:

```bash
cd scripts/
python test_exhaustion_univariate.py
```

**What this does:**

- Tests Sub-H1 through Sub-H6 on GBP/USD H1 data
- Applies Benjamini-Hochberg multiple testing correction
- Checks signal autocorrelation (clustering)
- Evaluates decision gates (proceed/revise/stop)

**Output:**

- `reports/backtests/exhaustion_univariate_results.csv`
- Console shows each test result with p-values, effect sizes, bootstrap CIs

**Expected runtime:** ~30 seconds

**Decision point:** If critical gates fail, STOP and revise Day 11 features.

---

### Step 3: Session Breakdown Analysis (Day 12 - Sub-H7)

Test if edge varies by trading session:

```bash
python analyze_exhaustion_by_session.py
```

**What this does:**

- Breaks down signal performance by ASIA/LONDON/NY/OVERLAP
- Tests if London/NY overlap shows superior edge
- Analyzes long vs short signals separately

**Output:**

- `reports/backtests/exhaustion_session_breakdown.csv`
- Console table showing edge per session

**Expected result:** London/overlap should outperform (hypothesis prediction)

**Expected runtime:** ~20 seconds

---

### Step 4: Cross-Pair Validation (Day 13)

Test if signal is GBP/USD-specific or generic USD noise:

```bash
python run_exhaustion_cross_pair.py
```

**What this does:**

- Runs identical signal detection on EUR/USD, USD/CHF, EUR/GBP, GBP/JPY, EUR/JPY, AUD/JPY
- Computes signal timing correlation with GBP/USD
- Detects USD contamination (if EUR/USD shows same edge + high correlation)

**Output:**

- `reports/backtests/exhaustion_cross_pair_results.csv`
- `reports/backtests/exhaustion_signal_correlations.csv`
- Console shows edge per pair and signal overlap percentages

**Critical check:**

- ✓ PASS: EUR/GBP shows weak/no edge → signal is GBP-specific
- ✗ FAIL: EUR/GBP shows >8 bps edge (p<0.05) → signal NOT pair-specific

**Expected runtime:** ~2 minutes (tests 6+ pairs)

**Note:** Some pairs may not have H1 data available — script handles gracefully

---

### Step 5: Interaction Analysis (Day 13)

Test which feature combinations drive the edge:

```bash
python analyze_exhaustion_interactions.py
```

**What this does:**

- Builds 2×2×2 interaction grid (8 combinations of 3 features)
- Computes feature-feature correlation matrix (redundancy check)
- Computes feature-return correlation at horizons 1-5h (predictive decay)
- Runs VIF test for multicollinearity

**Output:**

- `reports/backtests/exhaustion_interaction_grid.csv`
- `reports/backtests/exhaustion_feature_correlation.csv`
- `reports/backtests/exhaustion_feature_return_correlation.csv`
- `reports/backtests/exhaustion_vif_test.csv`
- `reports/figures/exhaustion_feature_correlation.png` (heatmap)
- `reports/figures/exhaustion_feature_return_correlation.png` (heatmap)

**Critical check:**

- ✓ Full signal (1,1,1) >> individual features → TRUE INTERACTION
- ✗ One feature alone ≈ full signal → DOMINANT FEATURE (simplify hypothesis)

**Expected runtime:** ~30 seconds

---

## Acceptance Criteria Summary

After running all scripts, evaluate:

### PASS Criteria (proceed to Day 14+ backtest):

1. ✓ **Individual features**: ≥2 of 3 show directional bias (p < 0.10)
2. ✓ **Combined signal**: Mean return > 10 bps (p < 0.05 post-MTC)
3. ✓ **Sample size**: N_signals > 300
4. ✓ **Session filter**: London OR overlap significant (p < 0.10)
5. ✓ **Independence**: Signal ACF[1] < 0.30
6. ✓ **Cross-pair**: EUR/GBP shows weak edge (< 8 bps or p > 0.05)
7. ✓ **Multicollinearity**: VIF < 8 for all features

### FLAG Criteria (document but continue):

- ⚠ EUR/USD shows similar edge + signal correlation > 0.65 → USD contamination
- ⚠ One feature drives all edge in 2×2×2 grid → simplify hypothesis

### FAIL Criteria (STOP and revise):

- ✗ All features IC < 0.03 or p > 0.10
- ✗ Combined signal < 5 bps
- ✗ N_signals < 200
- ✗ EUR/GBP edge > 8 bps (p < 0.05) → signal not pair-specific
- ✗ VIF > 10 for all features → redundant features

---

## Data Requirements

**Required:**

- `data/raw/GBPUSD60.csv` (H1 GBP/USD data)

**Optional (for cross-pair validation):**

- `data/raw/EURUSD60.csv`
- `data/raw/USDCHF60.csv`
- `data/raw/EURGBP60.csv`
- `data/raw/GBPJPY60.csv`
- `data/raw/EURJPY60.csv`
- `data/raw/AUDJPY60.csv`

**Format:** CSV with columns: `date,time,open,high,low,close,volume`

Cross-pair script handles missing pairs gracefully.

---

## Troubleshooting

### Error: "GBPUSD60.csv not found"

**Fix:**

```bash
# Verify file exists
ls -lh data/raw/GBPUSD60.csv

# Check format (should have 7 columns)
head -3 data/raw/GBPUSD60.csv
```

### Error: "No module named 'src.features.exhaustion'"

**Fix:**

```bash
# Verify PYTHONPATH or run from project root
export PYTHONPATH="${PYTHONPATH}:/home/ghost/fx-quant-research"
cd /home/ghost/fx-quant-research/scripts
python test_exhaustion_univariate.py
```

### Warning: "Insufficient signals"

**Cause:** Not enough data or hypothesis too restrictive

**Fix:** Check data period covers 2+ years of H1 bars (minimum ~10,000 bars)

---

## Next Steps After Days 11-13

### If ALL GATES PASS:

✅ **Day 14**: Walk-forward parameter optimization  
✅ **Day 15**: Walk-forward out-of-sample validation  
✅ **Day 16**: Full backtest with realistic execution model

### If FLAGGED (USD contamination):

⚠ **Action**: Document contamination, adjust position sizing to avoid simultaneous GBP/USD + EUR/USD exposure

### If CRITICAL FAILURE:

❌ **Action**: Return to Day 11, revise feature definitions or hypothesis logic

---

## Technical Notes

### Lookahead Prevention

All features use `.shift(1)` for rolling calculations:

```python
# CORRECT (lookahead-clean)
rolling_med = df['range'].shift(1).rolling(10).median()

# WRONG (includes current bar)
rolling_med = df['range'].rolling(10).median()
```

Validated in `exhaustion_features.py` via `validate_lookahead()` method.

### Multiple Testing Correction

Uses Benjamini-Hochberg FDR (False Discovery Rate) instead of Bonferroni:

- Less conservative, appropriate for exploratory research
- Controls expected proportion of false discoveries
- Applied in `test_exhaustion_univariate.py`

### Statistical Power

With typical parameters:

- Required edge: 10 bps
- Expected std: ~15 bps
- Minimum N for 80% power: ~350 signals

Decision gate requires N > 300 to ensure adequate statistical power.

---

## References

**Methodology:**

- Evidence-Based Technical Analysis — David Aronson
- Advances in Financial Machine Learning — Marcos López de Prado (Chapter 5)

**Statistical Frameworks:**

- Benjamini-Hochberg FDR: Benjamini & Hochberg (1995)
- Bootstrap CI: Efron & Tibshirani (1994)
- VIF test: Belsley, Kuh & Welsch (1980)

---

**Prepared by:** fx-quant-research  
**Last updated:** March 1, 2026
