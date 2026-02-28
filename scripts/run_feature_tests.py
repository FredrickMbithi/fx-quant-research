"""
Run univariate feature tests on EURUSD and update results document.
"""

import sys
sys.path.append('.')

import pandas as pd
import numpy as np
from src.features.generators import (
    ma_spread, distance_from_ma, atr, rsi, 
    return_vol_ratio, close_position_in_range,
    rate_of_change, zscore_returns, breakout_indicator
)
from src.features.testing import test_feature

# Load data
print("Loading EURUSD data...")
data_path = 'data/raw/EURUSD_daily.csv'
eurusd = pd.read_csv(data_path)
eurusd['timestamp'] = pd.to_datetime(eurusd['timestamp'])
eurusd = eurusd.set_index('timestamp')
eurusd = eurusd.sort_index()
eurusd.columns = eurusd.columns.str.lower()

prices = eurusd['close']
high = eurusd['high']
low = eurusd['low']
returns = prices.pct_change()

print(f"Data loaded: {len(prices)} bars from {eurusd.index[0]} to {eurusd.index[-1]}")

# Generate features
print("\nGenerating features...")
features = {
    'MA_Spread_50_200': ma_spread(prices, 50, 200),
    'Distance_MA_20': distance_from_ma(prices, 20),
    'ATR_14': atr(high, low, prices, 14),
    'RSI_14': rsi(prices, 14),
    'Return_Vol_Ratio_20': return_vol_ratio(returns, 20),
    'Close_Position': close_position_in_range(high, low, prices),
    'ROC_10': rate_of_change(prices, 10),
    'ZScore_Returns_20': zscore_returns(returns, 20),
    'Breakout_20': breakout_indicator(prices, 20)
}

print(f"Generated {len(features)} features\n")

# Test each feature
print("Testing Features...")
print("=" * 80)
results = {}

for name, feature in features.items():
    print(f"\nTesting: {name}")
    result = test_feature(feature, prices, name)
    results[name] = result
    
    print(f"  IC Mean:         {result.ic_mean:>8.4f}")
    print(f"  IC t-stat:       {result.ic_tstat:>8.2f}")
    print(f"  Hit Rate:        {result.hit_rate:>8.2%}")
    print(f"  Monotonicity:    {result.monotonicity_score:>8.2f}")
    print(f"  Stationary:      {str(result.is_stationary):>8}")
    print(f"  Decay Half-Life: {result.decay_half_life:>8} bars")
    print(f"  Significant:     {str(result.is_significant()):>8}")

print("\n" + "=" * 80)

# Create summary
summary = pd.DataFrame([
    {
        'Feature': r.feature_name,
        'IC Mean': r.ic_mean,
        'IC t-stat': r.ic_tstat,
        'Hit Rate': r.hit_rate,
        'Monotonicity': r.monotonicity_score,
        'Stationary': r.is_stationary,
        'Half-Life': r.decay_half_life,
        'Significant': r.is_significant()
    }
    for r in results.values()
])

summary['abs_ic'] = summary['IC Mean'].abs()
summary = summary.sort_values('abs_ic', ascending=False).drop('abs_ic', axis=1)

print("\n\nFEATURE TEST SUMMARY")
print("=" * 80)
print(summary.to_string(index=False))

# Count significant features
significant = [name for name, r in results.items() if r.is_significant()]
print(f"\n\nSIGNIFICANT FEATURES: {len(significant)}")
for name in significant:
    r = results[name]
    print(f"  ✓ {name}: IC={r.ic_mean:.4f}, t-stat={r.ic_tstat:.2f}")

# Save summary
summary.to_csv('reports/feature_test_results_eurusd.csv', index=False)
print(f"\n\nResults saved to: reports/feature_test_results_eurusd.csv")
