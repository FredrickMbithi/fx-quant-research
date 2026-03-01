#!/usr/bin/env python3
import sys
sys.path.append('..')

import pandas as pd
import numpy as np
from src.features.exhaustion_features import ExhaustionFeatureBuilder
from src.data.loader import FXDataLoader

print("Loading data...")
loader = FXDataLoader('../data/raw')
df = loader.load_pair('GBP/USD', timeframe='H1')

print(f"Loaded {len(df)} bars")
print(f"Date range: {df.index[0]} to {df.index[-1]}")
print(f"Columns: {df.columns.tolist()}")

print("\nBuilding features...")
builder = ExhaustionFeatureBuilder()
df = builder.build_all_features(df)

print(f"Features built: {[col for col in df.columns if 'exhaustion' in col or 'failure' in col]}")
print(f"\nExhaustion long signals: {df['exhaustion_long'].sum()}")
print(f"Exhaustion short signals: {df['exhaustion_short'].sum()}")
print(f"Failure long signals: {df['failure_to_continue_long'].sum()}")
print(f"Failure short signals: {df['failure_to_continue_short'].sum()}")

print("\nDone!")
