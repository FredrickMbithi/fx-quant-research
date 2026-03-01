#!/usr/bin/env python3
"""
Exhaustion Hypothesis Validation - NZD/JPY H1
Quick validation to test if signal works better on different pair
"""

import sys
sys.path.append('..')

import pandas as pd
import numpy as np
from scipy.stats import ttest_ind, ttest_1samp
from typing import Dict

from src.features.exhaustion_features import ExhaustionFeatureBuilder

def load_nzdjpy():
    """Load NZD/JPY H1 data."""
    df = pd.read_csv('../data/raw/NZDJPY60.csv',
                     names=['date', 'time', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['date'] + ' ' + df['time'])
    df = df.set_index('timestamp')
    df = df[['open', 'high', 'low', 'close', 'volume']]
    
    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC')
    
    df = df.sort_index()
    df = df[~df.index.duplicated(keep='first')]
    
    return df

def compute_signal_metrics(signal, fwd_ret, signal_name):
    """Compute basic metrics for a signal."""
    df = pd.DataFrame({'signal': signal, 'fwd_ret': fwd_ret}).dropna()
    
    if len(df) == 0:
        return None
    
    triggered = df[df['signal'] == 1]['fwd_ret']
    baseline = df[df['signal'] == 0]['fwd_ret']
    
    if len(triggered) < 5:
        return None
    
    mean_bps = triggered.mean() * 10000
    baseline_bps = baseline.mean() * 10000
    edge_bps = mean_bps - baseline_bps
    win_rate = (triggered > 0).mean()
    
    # T-test
    if len(baseline) > 5:
        t_stat, p_value = ttest_ind(triggered, baseline)
    else:
        t_stat, p_value = ttest_1samp(triggered, 0)
    
    return {
        'signal_name': signal_name,
        'n_signals': len(triggered),
        'mean_bps': mean_bps,
        'baseline_bps': baseline_bps,
        'edge_bps': edge_bps,
        'win_rate': win_rate,
        'std_bps': triggered.std() * 10000,
        'p_value': p_value,
        't_stat': t_stat
    }

def main():
    print("="*80)
    print("EXHAUSTION HYPOTHESIS VALIDATION - NZD/JPY H1")
    print("="*80)
    
    # Load data
    print("\nLoading NZD/JPY H1 data...")
    df = load_nzdjpy()
    print(f"Loaded {len(df)} bars from {df.index[0]} to {df.index[-1]}")
    
    # Build features
    print("\nBuilding exhaustion features...")
    builder = ExhaustionFeatureBuilder()
    df = builder.build_all_features(df)
    
    fwd_ret = df['fwd_ret_1h']
    
    # Test signals
    print("\n" + "="*80)
    print("SIGNAL PERFORMANCE")
    print("="*80)
    
    results = []
    
    # Individual features
    signals_to_test = [
        ('Dir Pressure >=2', (df['dir_pressure_2'].abs() >= 2).astype(int)),
        ('Range Expansion', df['range_expansion_10']),
        ('Close Extreme', df['close_extreme_35']),
        ('Combined Exhaustion', (df['exhaustion_long'] | df['exhaustion_short']).astype(int)),
        ('Full Signal', (df['failure_to_continue_long'] | df['failure_to_continue_short']).astype(int)),
        ('Long Only', df['failure_to_continue_long']),
        ('Short Only', df['failure_to_continue_short']),
    ]
    
    for name, signal in signals_to_test:
        result = compute_signal_metrics(signal, fwd_ret, name)
        if result:
            results.append(result)
    
    # Print results
    print(f"\n{'Signal':<25} | {'N':>6} | {'Mean':>8} | {'Edge':>8} | {'Win%':>6} | {'p-val':>8} | Status")
    print("-"*90)
    
    for r in results:
        status = "✓ SIG" if r['p_value'] < 0.05 else ("⚠ MARG" if r['p_value'] < 0.10 else "✗ NS")
        print(f"{r['signal_name']:<25} | {r['n_signals']:>6} | {r['mean_bps']:>7.2f} | "
              f"{r['edge_bps']:>7.2f} | {r['win_rate']:>5.1%} | {r['p_value']:>8.4f} | {status}")
    
    # Decision gates
    print("\n" + "="*80)
    print("DECISION GATE EVALUATION")
    print("="*80)
    
    full_signal = [r for r in results if r['signal_name'] == 'Full Signal'][0]
    
    gates = {
        'N signals > 50': full_signal['n_signals'] > 50,
        'Edge > 5 bps': full_signal['edge_bps'] > 5,
        'p-value < 0.10': full_signal['p_value'] < 0.10,
        'Edge after costs (12 bps)': full_signal['edge_bps'] > 12
    }
    
    for gate, passed in gates.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status:8} | {gate}")
    
    print("\n" + "="*80)
    if all(gates.values()):
        print("✅ ALL GATES PASSED - NZD/JPY shows exploitable edge")
    elif gates['Edge > 5 bps'] and gates['p-value < 0.10']:
        print("⚠️  BORDERLINE - Small but significant edge detected")
    else:
        print("❌ GATES FAILED - No exploitable edge on NZD/JPY")
    print("="*80)
    
    # Compare to GBP/USD
    print(f"\n📊 COMPARISON:")
    print(f"  NZD/JPY Full Signal: {full_signal['edge_bps']:.2f} bps (N={full_signal['n_signals']}, p={full_signal['p_value']:.4f})")
    print(f"  GBP/USD Full Signal:  0.06 bps (N=4583, p=0.8047)")
    print(f"  Improvement: {full_signal['edge_bps'] - 0.06:+.2f} bps")

if __name__ == '__main__':
    main()
