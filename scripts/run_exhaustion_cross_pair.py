#!/usr/bin/env python3
"""
Day 13: Cross-Pair Signal Validation
Tests if exhaustion signal is GBP/USD-specific or generic USD/FX noise
"""

import sys
sys.path.append('..')

import pandas as pd
import numpy as np
from scipy.stats import ttest_1samp
from typing import Dict, List
import warnings
warnings.filterwarnings('ignore')

from src.features.exhaustion_features import ExhaustionFeatureBuilder


class CrossPairValidator:
    """
    Test exhaustion signal across multiple currency pairs.
    
    Key question: Is this a GBP/USD microstructure signal or generic FX pattern?
    """
    
    def __init__(self):
        """Initialize validator."""
        self.results = {}
    
    def load_h1_pair(self, pair_name: str, data_path: str = '../data/raw') -> pd.DataFrame:
        """Load H1 data for a specific pair."""
        filename = f"{data_path}/{pair_name}60.csv"
        
        try:
            df = pd.read_csv(
                filename,
                names=['date', 'time', 'open', 'high', 'low', 'close', 'volume']
            )
            
            df['timestamp'] = pd.to_datetime(df['date'] + ' ' + df['time'])
            df = df.set_index('timestamp')
            df = df[['open', 'high', 'low', 'close', 'volume']]
            
            if df.index.tz is None:
                df.index = df.index.tz_localize('UTC')
            
            df = df.sort_index()
            df = df[~df.index.duplicated(keep='first')]
            
            return df
            
        except FileNotFoundError:
            print(f"WARNING: {pair_name} data not found at {filename}")
            return None
    
    def run_signal_detection(
        self,
        pair_name: str,
        df: pd.DataFrame,
        builder: ExhaustionFeatureBuilder
    ) -> Dict:
        """
        Run identical exhaustion detection on a pair.
        
        NO PARAMETER CHANGES - that would be curve fitting per pair.
        """
        print(f"\nTesting {pair_name}...")
        print("-"*60)
        
        # Build features with SAME parameters
        df_features = builder.build_all_features(df)
        
        # Generate signals
        full_signal = (
            df_features['failure_to_continue_long'] | 
            df_features['failure_to_continue_short']
        ).astype(int)
        
        fwd_ret = df_features['fwd_ret_1h']
        
        # Compute metrics
        df_align = pd.DataFrame({
            'signal': full_signal,
            'fwd_ret': fwd_ret
        }).dropna()
        
        if len(df_align) == 0:
            return {
                'pair': pair_name,
                'n_signals': 0,
                'mean_bps': np.nan,
                'p_value': np.nan,
                'status': 'no_data'
            }
        
        triggered = df_align[df_align['signal'] == 1]['fwd_ret']
        
        if len(triggered) < 10:
            return {
                'pair': pair_name,
                'n_signals': len(triggered),
                'mean_bps': np.nan,
                'p_value': np.nan,
                'status': 'insufficient_signals'
            }
        
        # Statistics
        n_signals = len(triggered)
        mean_bps = triggered.mean() * 10000
        std_bps = triggered.std() * 10000
        win_rate = (triggered > 0).mean()
        
        # T-test against zero
        t_stat, p_value = ttest_1samp(triggered, 0)
        
        print(f"  N signals: {n_signals}")
        print(f"  Mean return: {mean_bps:.2f} bps")
        print(f"  Win rate: {win_rate:.1%}")
        print(f"  p-value: {p_value:.4f}")
        
        # Store signal series for correlation analysis
        self.results[pair_name] = {
            'pair': pair_name,
            'n_signals': n_signals,
            'mean_bps': mean_bps,
            'std_bps': std_bps,
            'win_rate': win_rate,
            't_stat': t_stat,
            'p_value': p_value,
            'signal_series': full_signal,
            'timestamps': df_features.index,
            'status': 'success'
        }
        
        return self.results[pair_name]
    
    def compute_signal_correlation(
        self,
        base_pair: str = 'GBPUSD'
    ) -> pd.DataFrame:
        """
        Compute correlation between signal series across pairs.
        
        High correlation = signals fire at same time = contamination.
        """
        if base_pair not in self.results:
            print(f"ERROR: {base_pair} not in results")
            return pd.DataFrame()
        
        base_signal = self.results[base_pair]['signal_series']
        base_timestamps = self.results[base_pair]['timestamps']
        
        correlations = []
        
        for pair, data in self.results.items():
            if data['status'] != 'success':
                continue
            
            # Align timestamps (find common bars)
            common_idx = base_timestamps.intersection(data['timestamps'])
            
            if len(common_idx) < 100:
                correlations.append({
                    'pair': pair,
                    'signal_correlation': np.nan,
                    'common_bars': len(common_idx),
                    'note': 'Insufficient overlap'
                })
                continue
            
            # Get signals at common timestamps
            base_aligned = base_signal.loc[common_idx]
            pair_aligned = data['signal_series'].loc[common_idx]
            
            # Pearson correlation on binary series
            corr = base_aligned.corr(pair_aligned)
            
            correlations.append({
                'pair': pair,
                'signal_correlation': corr,
                'common_bars': len(common_idx)
            })
        
        return pd.DataFrame(correlations)
    
    def compute_signal_timing_overlap(
        self,
        base_pair: str = 'GBPUSD',
        other_pair: str = 'EURUSD',
        window: int = 1
    ) -> float:
        """
        % of base_pair signals that occur within ±window bars of other_pair signal.
        
        High overlap = signals cluster in time = likely same underlying driver.
        """
        if base_pair not in self.results or other_pair not in self.results:
            return np.nan
        
        base_signal = self.results[base_pair]['signal_series']
        other_signal = self.results[other_pair]['signal_series']
        
        # Find common timeline
        common_idx = base_signal.index.intersection(other_signal.index)
        
        if len(common_idx) < 100:
            return np.nan
        
        base_aligned = base_signal.loc[common_idx]
        other_aligned = other_signal.loc[common_idx]
        
        # Get base signal timestamps
        base_signal_times = base_aligned[base_aligned == 1].index
        
        if len(base_signal_times) == 0:
            return 0.0
        
        # Check how many occur near other_pair signals
        overlap_count = 0
        
        for t in base_signal_times:
            # Check ±window bars
            t_loc = common_idx.get_loc(t)
            start_loc = max(0, t_loc - window)
            end_loc = min(len(common_idx), t_loc + window + 1)
            
            window_idx = common_idx[start_loc:end_loc]
            
            # If other_pair has signal in this window
            if other_aligned.loc[window_idx].sum() > 0:
                overlap_count += 1
        
        overlap_pct = overlap_count / len(base_signal_times)
        
        return overlap_pct


def main():
    """Run cross-pair validation."""
    
    print("="*80)
    print("CROSS-PAIR EXHAUSTION SIGNAL VALIDATION")
    print("="*80)
    
    # Pairs to test (from Day 13 plan)
    pairs_test = {
        'baseline': ['GBPUSD'],
        'tier1_usd_contaminated': ['EURUSD', 'USDCHF'],
        'tier2_gbp_related': ['EURGBP', 'GBPJPY'],
        'tier3_independent': ['EURJPY', 'AUDJPY']
    }
    
    # Use same parameters as GBP/USD (no tuning per pair)
    builder = ExhaustionFeatureBuilder(
        pressure_threshold=2,
        range_expansion_factor=0.8,
        range_lookback=10,
        percentile_high=0.65,
        percentile_low=0.35
    )
    
    validator = CrossPairValidator()
    all_results = []
    
    # Test each tier
    for tier, pairs in pairs_test.items():
        print(f"\n{'='*80}")
        print(f"{tier.upper()}")
        print('='*80)
        
        for pair in pairs:
            df = validator.load_h1_pair(pair)
            
            if df is None:
                continue
            
            result = validator.run_signal_detection(pair, df, builder)
            all_results.append(result)
    
    # Build results table
    results_df = pd.DataFrame([r for r in all_results if r['status'] == 'success'])
    
    print("\n" + "="*80)
    print("CROSS-PAIR SUMMARY TABLE")
    print("="*80)
    print(f"{'Pair':<10} | {'N':<6} | {'Mean bps':<10} | {'Win%':<8} | {'p-value':<8}")
    print("-"*80)
    
    for _, row in results_df.iterrows():
        print(f"{row['pair']:<10} | {row['n_signals']:<6} | {row['mean_bps']:>10.2f} | "
              f"{row['win_rate']:>7.1%} | {row['p_value']:>8.4f}")
    
    # Compute signal correlations
    print("\n" + "="*80)
    print("SIGNAL TIMING CORRELATION WITH GBP/USD")
    print("="*80)
    
    corr_df = validator.compute_signal_correlation(base_pair='GBPUSD')
    
    if len(corr_df) > 0:
        print(f"{'Pair':<10} | {'Signal Corr':<12} | {'Common Bars':<12}")
        print("-"*80)
        
        for _, row in corr_df.iterrows():
            if pd.isna(row['signal_correlation']):
                print(f"{row['pair']:<10} | {'N/A':<12} | {row.get('common_bars', 0):<12}")
            else:
                print(f"{row['pair']:<10} | {row['signal_correlation']:>12.3f} | {row['common_bars']:<12}")
    
    # Signal timing overlap analysis
    print("\n" + "="*80)
    print("SIGNAL TIMING OVERLAP (% of GBP/USD signals occurring ±1 bar of other pair)")
    print("="*80)
    
    for pair in ['EURUSD', 'USDCHF', 'EURGBP', 'GBPJPY']:
        if pair in validator.results and validator.results[pair]['status'] == 'success':
            overlap = validator.compute_signal_timing_overlap('GBPUSD', pair, window=1)
            
            if not pd.isna(overlap):
                print(f"{pair:<10}: {overlap:>6.1%}", end='')
                
                if overlap > 0.40:
                    print("  ⚠ HIGH overlap - likely USD contamination")
                elif overlap < 0.15:
                    print("  ✓ LOW overlap - GBP-specific signal")
                else:
                    print("  ○ MODERATE overlap")
    
    # Decision gates
    print("\n" + "="*80)
    print("CROSS-PAIR VALIDATION DECISION GATES")
    print("="*80)
    
    gbpusd_result = results_df[results_df['pair'] == 'GBPUSD']
    eurusd_result = results_df[results_df['pair'] == 'EURUSD']
    eurgbp_result = results_df[results_df['pair'] == 'EURGBP']
    
    # Gate 1: EUR/USD contamination check
    if len(eurusd_result) > 0 and len(gbpusd_result) > 0:
        eurusd_edge = eurusd_result['mean_bps'].values[0]
        gbpusd_edge = gbpusd_result['mean_bps'].values[0]
        edge_diff = abs(eurusd_edge - gbpusd_edge)
        
        eurusd_corr = corr_df[corr_df['pair'] == 'EURUSD']['signal_correlation'].values
        
        if len(eurusd_corr) > 0 and eurusd_corr[0] > 0.65 and edge_diff < 3:
            print("⚠ FLAG: EUR/USD shows similar edge + high correlation → USD contamination present")
            print("   Action: Document, continue but note for position sizing")
        else:
            print("✓ PASS: EUR/USD contamination within acceptable limits")
    
    # Gate 2: EUR/GBP should NOT show edge (if it does, signal is not GBP-specific)
    if len(eurgbp_result) > 0:
        eurgbp_edge = eurgbp_result['mean_bps'].values[0]
        eurgbp_pval = eurgbp_result['p_value'].values[0]
        
        if eurgbp_edge > 8 and eurgbp_pval < 0.05:
            print("✗ FAIL: EUR/GBP shows significant edge → signal NOT GBP-specific")
            print("   Action: STOP and revise hypothesis")
        else:
            print(f"✓ PASS: EUR/GBP shows weak/no edge ({eurgbp_edge:.1f} bps) → signal is GBP-specific")
    
    # Gate 3: GBP/USD should outperform others
    if len(gbpusd_result) > 0 and len(results_df) > 1:
        gbpusd_edge = gbpusd_result['mean_bps'].values[0]
        other_edges = results_df[results_df['pair'] != 'GBPUSD']['mean_bps']
        
        if gbpusd_edge >= other_edges.mean():
            print(f"✓ PASS: GBP/USD edge ({gbpusd_edge:.1f} bps) >= average of other pairs")
        else:
            print(f"⚠ FLAG: GBP/USD edge lower than average → signal may not be pair-specific")
    
    # Save results
    output_path = '../reports/backtests/exhaustion_cross_pair_results.csv'
    results_df.to_csv(output_path, index=False)
    print(f"\n\nResults saved to: {output_path}")
    
    if len(corr_df) > 0:
        corr_output_path = '../reports/backtests/exhaustion_signal_correlations.csv'
        corr_df.to_csv(corr_output_path, index=False)
        print(f"Signal correlations saved to: {corr_output_path}")


if __name__ == '__main__':
    main()
