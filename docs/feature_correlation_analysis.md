# Feature Correlation & Redundancy Analysis

## Overview

This module identifies redundant features that measure the same underlying signal, helping avoid multicollinearity in portfolio construction.

## Files Created

### 1. `src/features/correlation_analysis.py`

Core module with functions:

- **`compute_feature_correlation_matrix()`**: Calculate Spearman correlation between features
- **`identify_redundant_features()`**: Find features to drop based on correlation threshold
- **`plot_feature_correlation()`**: Create correlation heatmap visualization
- **`analyze_feature_clusters()`**: Group similar features using hierarchical clustering
- **`print_redundancy_report()`**: Print formatted analysis report
- **`create_feature_summary_table()`**: Generate summary DataFrame

### 2. `notebooks/06_feature_correlation.ipynb`

Comprehensive analysis notebook that:

1. Loads all 13 features from previous analysis
2. Computes feature correlation matrix
3. Visualizes correlations as heatmap
4. Identifies redundant pairs (|corr| > 0.7)
5. Applies selection rule: keep feature with higher |IC|
6. Performs sensitivity analysis across thresholds
7. Exports results to CSV files

### 3. `scripts/test_correlation_analysis.py`

Test script demonstrating module functionality with synthetic data.

## Key Concepts

### Redundancy Criteria

Two features are **redundant** if:
- |Spearman correlation| > 0.7 (default threshold)
- They measure similar market phenomena

**Selection Rule:**
- Keep the feature with higher |IC| (Information Coefficient)
- Drop the weaker predictor

### Why This Matters

**Problem:**
- RSI and Distance_MA might both measure overextension
- MA_Spread and ROC might both capture trend
- Using both adds no new information but inflates model confidence

**Solution:**
- Keep only one from each redundant pair
- Ensures feature diversity
- Reduces multicollinearity
- Improves model robustness

## Expected Redundancies

Based on 13 features tested in notebook 05:

### High Correlation Expected (> 0.7)

1. **Distance_MA_20 ↔ Distance_MA_50**
   - Both measure distance from moving average
   - Expected: Keep Distance_MA_20 (higher IC = -0.065)

2. **ROC_5 ↔ ROC_10**
   - Both measure momentum at similar scales
   - Expected: Keep ROC_10 (higher IC = -0.054)

3. **RSI_14 ↔ RSI_28**
   - Both measure overbought/oversold
   - Expected: Keep RSI_14 (higher IC = -0.054)

### Moderate Correlation (0.4 - 0.7)

4. **RSI_14 ↔ Distance_MA_20**
   - Both measure overextension
   - Expected: Keep both (independent enough)

5. **MA_Spread ↔ Distance_MA**
   - Both use moving averages
   - Expected: Keep both (measure different aspects)

### Low Correlation (< 0.3)

6. **Close_Position ↔ Others**
   - Unique intraday microstructure signal
   - Expected: Independent from all features

## Usage

### In Python Script

```python
from src.features.correlation_analysis import (
    compute_feature_correlation_matrix,
    identify_redundant_features,
    print_redundancy_report
)

# Your features dict
features = {
    'Distance_MA_20': distance_ma_series,
    'RSI_14': rsi_series,
    # ... more features
}

# Your IC scores from testing
ic_scores = {
    'Distance_MA_20': -0.065,
    'RSI_14': -0.054,
    # ... more ICs
}

# Compute correlations
corr_matrix = compute_feature_correlation_matrix(features)

# Find redundant features
redundancy = identify_redundant_features(corr_matrix, ic_scores, threshold=0.7)

# Print report
print_redundancy_report(redundancy)

# Features to use
final_features = [f for f in features.keys() if f not in redundancy['to_drop']]
```

### In Jupyter Notebook

See `notebooks/06_feature_correlation.ipynb` for complete workflow.

## Outputs

The notebook generates:

1. **reports/figures/feature_correlation_matrix.png**: Heatmap visualization
2. **reports/feature_correlation_matrix.csv**: Full correlation matrix
3. **reports/feature_redundancy_summary.csv**: Summary table with recommendations
4. **reports/final_feature_list.csv**: Final selected features

## Interpretation

### Correlation Matrix

- **Red (negative)**: Features move in opposite directions
- **Blue (positive)**: Features move together
- **White (zero)**: No correlation

### Redundancy Report

Example output:
```
⚠ Found 3 redundant pair(s)
→ Recommending to drop 3 feature(s): Distance_MA_50, ROC_5, RSI_28

Pair 1:
  Distance_MA_20 (IC=-0.0650) ↔ Distance_MA_50 (IC=-0.0520)
  Correlation: 0.912
  → DROP: Distance_MA_50 (weaker IC)
  → KEEP: Distance_MA_20 (stronger IC)
```

## Threshold Selection

| Threshold | Interpretation | Use Case |
|-----------|---------------|----------|
| 0.5 | Moderate correlation | Very strict, may drop useful features |
| 0.6 | Moderately high | Conservative approach |
| **0.7** | **High correlation** | **Standard (recommended)** |
| 0.8 | Very high | Liberal, keeps more features |
| 0.9 | Extreme | Only drops near-duplicates |

**Recommendation**: Use 0.7 as the standard cutoff for multicollinearity detection.

## Validation Steps

After running correlation analysis:

1. **Visual Check**: Examine heatmap for unexpected patterns
2. **Domain Knowledge**: Verify drops make sense (e.g., different MA periods are redundant)
3. **Cross-Pair Test**: Ensure correlation structure holds across assets
4. **Regime Test**: Check if correlations change in different market conditions

## Next Steps

After identifying non-redundant features:

1. Run cross-pair validation (Day 13 task)
2. Test feature stability across market regimes
3. Proceed to portfolio construction with final feature set
4. Build multi-strategy system using independent signals

## References

- Spearman correlation: Robust to non-linear relationships
- Multicollinearity threshold: Standard econometric practice (VIF > 5 ≈ corr > 0.7)
- Feature selection: Keep stronger predictor when redundancy detected
