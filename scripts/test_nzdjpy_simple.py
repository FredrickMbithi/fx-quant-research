#!/usr/bin/env python3
import sys
sys.path.append('..')
import pandas as pd
import numpy as np
from src.features.exhaustion_features import ExhaustionFeatureBuilder

print("Loading NZD/JPY...")
df = pd.read_csv('../data/raw/NZDJPY60.csv',
                 names=['date', 'time', 'open', 'high', 'low', 'close', 'volume'])
df['timestamp'] = pd.to_datetime(df['date'] + ' ' + df['time'])
df = df.set_index('timestamp')
df = df[['open', 'high', 'low', 'close', 'volume']]
if df.index.tz is None:
    df.index = df.index.tz_localize('UTC')
df = df.sort_index()
df = df[~df.index.duplicated(keep='first')]

print(f"Loaded {len(df)} bars")
print(f"Date range: {df.index[0]} to {df.index[-1]}")

print("\nBuilding features...")
builder = ExhaustionFeatureBuilder()
df = builder.build_all_features(df)

print(f"Features built")
print(f"\nSignal counts:")
print(f"  exhaustion_long: {df['exhaustion_long'].sum()}")
print(f"  exhaustion_short: {df['exhaustion_short'].sum()}")
print(f"  full_long: {df['failure_to_continue_long'].sum()}")
print(f"  full_short: {df['failure_to_continue_short'].sum()}")

fwd_ret = df['fwd_ret_1h']
full_signal = (df['failure_to_continue_long'] | df['failure_to_continue_short']).astype(int)

df_test = pd.DataFrame({'signal': full_signal, 'fwd_ret': fwd_ret}).dropna()
triggered = df_test[df_test['signal'] == 1]['fwd_ret']

if len(triggered) > 0:
    mean_bps = triggered.mean() * 10000
    win_rate = (triggered > 0).mean()
    print(f"\nFull signal: N={len(triggered)}, Mean={mean_bps:.2f} bps, Win%={win_rate:.1%}")
else:
    print("\nNo signals generated")

print("\nDone!")
