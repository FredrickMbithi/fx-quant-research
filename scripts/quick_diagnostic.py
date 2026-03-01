#!/usr/bin/env python3
"""Quick diagnostic for exhaustion features"""
import sys
sys.path.append('..')

import pandas as pd
import numpy as np
from src.features.exhaustion_features import ExhaustionFeatureBuilder
from src.data.loader import FXDataLoader

print("1. Loading data...")
df = pd.read_csv('../data/raw/GBPUSD60.csv', 
                 names=['date', 'time', 'open', 'high', 'low', 'close', 'volume'])
df['timestamp'] = pd.to_datetime(df['date'] + ' ' + df['time'])
df = df.set_index('timestamp')
df = df[['open', 'high', 'low', 'close', 'volume']]

if df.index.tz is None:
    df.index = df.index.tz_localize('UTC')

df = df.sort_index()
df = df[~df.index.duplicated(keep='first')]
print(f"   Loaded {len(df)} bars\n")

print("2. Building features...")
builder = ExhaustionFeatureBuilder()
df = builder.build_all_features(df)
print(f"   Features built\n")

# Compute forward returns
print("3. Computing forward returns...")
df['fwd_ret_1h'] = df['close'].pct_change().shift(-1)
print(f"   Forward returns computed\n")

# Check signals
print("4. Signal Counts:")
print(f"   dir_pressure >=2: {(df['dir_pressure_2'].abs() >= 2).sum()}")
print(f"   range_expansion_10: {df['range_expansion_10'].sum()}")
print(f"   close_extreme_35: {df['close_extreme_35'].sum()}")
print(f"   exhaustion_long: {df['exhaustion_long'].sum()}")
print(f"   exhaustion_short: {df['exhaustion_short'].sum()}")
print(f"   failure_to_continue_long: {df['failure_to_continue_long'].sum()}")
print(f"   failure_to_continue_short: {df['failure_to_continue_short'].sum()}\n")

# Quick mean return test (no bootstrap)
print("5. Mean Returns (bps):")
fwd_ret = df['fwd_ret_1h']

for signal_name, signal_col in [
    ('dir_pressure', (df['dir_pressure_2'].abs() >= 2)),
    ('range_expansion', df['range_expansion_10']),
    ('close_extreme', df['close_extreme_35']),
    ('exhaustion_long', df['exhaustion_long']),
    ('exhaustion_short', df['exhaustion_short']),
    ('full_signal', df['failure_to_continue_long'] | df['failure_to_continue_short'])
]:
    triggered = fwd_ret[signal_col == 1]
    baseline = fwd_ret[signal_col == 0]
    
    if len(triggered) > 0:
        mean_ret_bps = triggered.mean() * 10000
        baseline_bps = baseline.mean() * 10000
        edge_bps = mean_ret_bps - baseline_bps
        print(f"   {signal_name:20s}: N={len(triggered):5d}, Mean={mean_ret_bps:6.2f}, Baseline={baseline_bps:6.2f}, Edge={edge_bps:6.2f}")
    else:
        print(f"   {signal_name:20s}: No signals")

print("\nDone!")
