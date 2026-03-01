#!/usr/bin/env python3
"""
Feature Correlation Analysis - Standalone Script
Generates correlation analysis results for all features.
"""

import sys
sys.path.append('..')

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt

# Try to import seaborn, use basic matplotlib if not available
try:
    import seaborn as sns
    HAS_SEABORN = True
except ImportError:
    HAS_SEABORN = False
    print("Note: seaborn not available, using basic matplotlib")

from src.features.generators import (
    ma_spread,
    distance_from_ma,
    atr,
    rsi,
    rate_of_change,
    breakout_indicator,
    return_vol_ratio,
    close_position_in_range,
    zscore_returns
)

from src.features.correlation_analysis import (
    compute_feature_correlation_matrix,
    identify_redundant_features,
    plot_feature_correlation,
    analyze_feature_clusters,
    print_redundancy_report,
    create_feature_summary_table
)

print("="*80)
print("FEATURE CORRELATION ANALYSIS")
print("="*80)

# 1. Load Data
print("\n[1/8] Loading EURUSD data...")
df = pd.read_csv('../data/raw/EURUSD_daily.csv')
df['timestamp'] = pd.to_datetime(df['timestamp'])
df = df.set_index('timestamp').sort_index()
df.columns = df.columns.str.lower()
print(f"✓ Data loaded: {len(df)} bars ({df.index[0].date()} to {df.index[-1].date()})")

# 2. Generate Features
print("\n[2/8] Generating features...")
prices = df['close']
high = df['high']
low = df['low']
returns = prices.pct_change()

features = {}
features['MA_Spread_50_200'] = ma_spread(prices, 50, 200)
features['Distance_MA_20'] = distance_from_ma(prices, 20)
features['Distance_MA_50'] = distance_from_ma(prices, 50)
features['ROC_5'] = rate_of_change(prices, 5)
features['ROC_10'] = rate_of_change(prices, 10)
features['ROC_20'] = rate_of_change(prices, 20)
features['RSI_14'] = rsi(prices, 14)
features['RSI_28'] = rsi(prices, 28)
features['ATR_14'] = atr(high, low, prices, 14)
features['Return_Vol_Ratio'] = return_vol_ratio(returns, 20)
features['Close_Position'] = close_position_in_range(high, low, prices)
features['Breakout_20'] = breakout_indicator(prices, 20)
features['ZScore_Returns'] = zscore_returns(returns, 20)

print(f"✓ Generated {len(features)} features")

# 3. Compute Correlation Matrix
print("\n[3/8] Computing feature correlation matrix...")
feature_corr = compute_feature_correlation_matrix(features)
print("✓ Correlation matrix computed")
print("\nCorrelation Matrix (first 5x5):")
print(feature_corr.iloc[:5, :5].round(3))

# 4. Find High Correlation Pairs
print("\n[4/8] Identifying highly correlated pairs (|corr| > 0.7)...")
high_corr_pairs = []
for i in range(len(feature_corr)):
    for j in range(i + 1, len(feature_corr)):
        corr_val = feature_corr.iloc[i, j]
        if abs(corr_val) > 0.7:
            high_corr_pairs.append({
                'Feature_1': feature_corr.index[i],
                'Feature_2': feature_corr.columns[j],
                'Correlation': corr_val
            })

if high_corr_pairs:
    high_corr_df = pd.DataFrame(high_corr_pairs)
    high_corr_df = high_corr_df.sort_values('Correlation', key=abs, ascending=False)
    print(f"\n✓ Found {len(high_corr_pairs)} highly correlated pairs:")
    print(high_corr_df.to_string(index=False))
else:
    print("\n✓ No highly correlated pairs found")

# 5. Load IC Scores
print("\n[5/8] Loading IC scores from previous analysis...")
ic_scores = {
    'Close_Position': -0.7530,
    'Distance_MA_20': -0.0650,
    'Distance_MA_50': -0.0520,
    'MA_Spread_50_200': -0.0570,
    'ROC_5': -0.0430,
    'ROC_10': -0.0540,
    'ROC_20': -0.0380,
    'RSI_14': -0.0540,
    'RSI_28': -0.0450,
    'ATR_14': -0.0120,
    'Return_Vol_Ratio': -0.0210,
    'Breakout_20': -0.0320,
    'ZScore_Returns': -0.0080
}
print("✓ IC scores loaded")

# 6. Identify Redundant Features
print("\n[6/8] Identifying redundant features (threshold=0.7)...")
redundancy_info = identify_redundant_features(
    feature_corr,
    ic_scores,
    threshold=0.7
)
print_redundancy_report(redundancy_info, verbose=True)

# 7. Create Summary Table
print("\n[7/8] Creating summary table...")
summary_table = create_feature_summary_table(
    ic_scores,
    feature_corr,
    redundancy_info
)
print("\nFeature Summary Table:")
print(summary_table.to_string(index=False))

# 8. Generate Visualization
print("\n[8/8] Generating correlation heatmap...")
plot_feature_correlation(
    feature_corr,
    save_path='../reports/figures/feature_correlation_matrix.png',
    figsize=(14, 12)
)
plt.close('all')
print("✓ Heatmap saved to reports/figures/feature_correlation_matrix.png")

# Export Results
print("\n" + "="*80)
print("EXPORTING RESULTS")
print("="*80)

feature_corr.to_csv('../reports/feature_correlation_matrix.csv')
print("✓ ../reports/feature_correlation_matrix.csv")

summary_table.to_csv('../reports/feature_redundancy_summary.csv', index=False)
print("✓ ../reports/feature_redundancy_summary.csv")

features_to_keep = [f for f in ic_scores.keys() if f not in redundancy_info['to_drop']]
final_features = pd.DataFrame({
    'Feature': features_to_keep,
    'IC': [ic_scores[f] for f in features_to_keep]
})
final_features = final_features.sort_values('IC', key=abs, ascending=False)
final_features.to_csv('../reports/final_feature_list.csv', index=False)
print("✓ ../reports/final_feature_list.csv")

# Final Summary
print("\n" + "="*80)
print("FINAL SUMMARY")
print("="*80)
print(f"Total features analyzed: {len(ic_scores)}")
print(f"Features to drop: {len(redundancy_info['to_drop'])}")
print(f"Features to keep: {len(features_to_keep)}")
print(f"\nReduction: {100*len(redundancy_info['to_drop'])/len(ic_scores):.1f}%")

if features_to_keep:
    print(f"\n✓ FINAL FEATURE LIST ({len(features_to_keep)} features):")
    for feat in final_features['Feature'].values:
        ic = ic_scores[feat]
        max_corr = feature_corr.loc[feat].drop(feat).abs().max()
        print(f"  {feat:25s} IC={ic:>7.4f}  Max_Corr={max_corr:.3f}")

print("\n" + "="*80)
print("✓ ANALYSIS COMPLETE")
print("="*80)
