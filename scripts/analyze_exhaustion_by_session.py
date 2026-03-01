#!/usr/bin/env python3
"""
Day 12: Session Breakdown Analyzer for Exhaustion Hypothesis
Tests Sub-H7: Does edge vary by trading session?
"""

import sys
sys.path.append('..')

import pandas as pd
import numpy as np
from scipy.stats import ttest_ind
from typing import Dict
import warnings
warnings.filterwarnings('ignore')

from src.features.exhaustion_features import ExhaustionFeatureBuilder
from src.features.sessions import SessionTagger


class SessionBreakdownAnalyzer:
    """
    Analyze exhaustion signal performance by trading session.
    
    Tests if London/NY overlap sessions show stronger edge than Asia/NY.
    """
    
    def __init__(self):
        """Initialize analyzer."""
        self.results = []
    
    def analyze_by_session(
        self,
        df: pd.DataFrame,
        signal: pd.Series,
        forward_returns: pd.Series
    ) -> pd.DataFrame:
        """
        Break down signal performance by session.
        
        Args:
            df: DataFrame with session labels
            signal: Binary signal series
            forward_returns: Forward returns to predict
            
        Returns:
            DataFrame with results per session
        """
        # Ensure we have session labels
        if 'session' not in df.columns:
            df['session'] = SessionTagger.tag_sessions(df)
        
        results_list = []
        
        # Test each session
        for session in ['ASIA', 'LONDON', 'NY']:
            session_data = df[df['session'] == session]
            session_signal = signal.loc[session_data.index]
            session_fwd_ret = forward_returns.loc[session_data.index]
            
            result = self._compute_session_metrics(
                session_signal,
                session_fwd_ret,
                session
            )
            results_list.append(result)
        
        # Also test London/NY overlap (12-16 UTC)
        overlap_mask = (df.index.hour >= 12) & (df.index.hour < 16)
        overlap_data = df[overlap_mask]
        overlap_signal = signal.loc[overlap_data.index]
        overlap_fwd_ret = forward_returns.loc[overlap_data.index]
        
        result_overlap = self._compute_session_metrics(
            overlap_signal,
            overlap_fwd_ret,
            'LONDON_NY_OVERLAP'
        )
        results_list.append(result_overlap)
        
        return pd.DataFrame(results_list)
    
    def _compute_session_metrics(
        self,
        signal: pd.Series,
        forward_returns: pd.Series,
        session_name: str
    ) -> Dict:
        """Compute metrics for a single session."""
        # Align
        df = pd.DataFrame({
            'signal': signal,
            'fwd_ret': forward_returns
        }).dropna()
        
        if len(df) == 0:
            return {
                'session': session_name,
                'n_signals': 0,
                'mean_bps': np.nan,
                'win_rate': np.nan,
                'p_value': np.nan
            }
        
        # Split signal vs baseline
        triggered = df[df['signal'] == 1]['fwd_ret']
        baseline = df[df['signal'] == 0]['fwd_ret']
        
        if len(triggered) < 5:
            return {
                'session': session_name,
                'n_signals': len(triggered),
                'mean_bps': np.nan,
                'win_rate': np.nan,
                'p_value': np.nan,
                'note': 'Insufficient signals'
            }
        
        # Compute metrics
        n_signals = len(triggered)
        mean_bps = triggered.mean() * 10000
        baseline_bps = baseline.mean() * 10000 if len(baseline) > 0 else 0
        win_rate = (triggered > 0).mean()
        
        # T-test
        if len(baseline) > 5:
            t_stat, p_value = ttest_ind(triggered, baseline)
        else:
            from scipy.stats import ttest_1samp
            t_stat, p_value = ttest_1samp(triggered, 0)
        
        return {
            'session': session_name,
            'n_signals': n_signals,
            'mean_bps': mean_bps,
            'baseline_bps': baseline_bps,
            'win_rate': win_rate,
            't_stat': t_stat,
            'p_value': p_value
        }
    
    def analyze_by_direction(
        self,
        df: pd.DataFrame,
        long_signal: pd.Series,
        short_signal: pd.Series,
        forward_returns: pd.Series
    ) -> pd.DataFrame:
        """
        Separate analysis for long vs short signals.
        
        Tests if exhaustion works better in one direction.
        """
        results_list = []
        
        # Long signals
        df_align = pd.DataFrame({
            'signal': long_signal,
            'fwd_ret': forward_returns
        }).dropna()
        
        triggered_long = df_align[df_align['signal'] == 1]['fwd_ret']
        
        if len(triggered_long) >= 5:
            results_list.append({
                'direction': 'LONG (Bearish Exhaustion)',
                'n_signals': len(triggered_long),
                'mean_bps': triggered_long.mean() * 10000,
                'win_rate': (triggered_long > 0).mean(),
                'std_bps': triggered_long.std() * 10000
            })
        
        # Short signals
        df_align = pd.DataFrame({
            'signal': short_signal,
            'fwd_ret': forward_returns
        }).dropna()
        
        triggered_short = df_align[df_align['signal'] == 1]['fwd_ret']
        
        if len(triggered_short) >= 5:
            results_list.append({
                'direction': 'SHORT (Bullish Exhaustion)',
                'n_signals': len(triggered_short),
                'mean_bps': triggered_short.mean() * 10000,
                'win_rate': (triggered_short > 0).mean(),
                'std_bps': triggered_short.std() * 10000
            })
        
        return pd.DataFrame(results_list)
    
    def print_breakdown_table(self, session_results: pd.DataFrame):
        """Pretty print session breakdown."""
        print("\n" + "="*80)
        print("SESSION BREAKDOWN ANALYSIS")
        print("="*80)
        print(f"{'Session':<20} | {'N':<6} | {'Mean bps':<10} | {'Win%':<8} | {'p-value':<8}")
        print("-"*80)
        
        for _, row in session_results.iterrows():
            if pd.isna(row['mean_bps']):
                print(f"{row['session']:<20} | {row['n_signals']:<6} | {'N/A':<10} | {'N/A':<8} | {'N/A':<8}")
            else:
                print(f"{row['session']:<20} | {row['n_signals']:<6} | "
                      f"{row['mean_bps']:>10.2f} | {row['win_rate']:>7.1%} | {row['p_value']:>8.4f}")
        
        print("="*80)
        
        # Determine best session
        valid_sessions = session_results[session_results['mean_bps'].notna()]
        if len(valid_sessions) > 0:
            best_session = valid_sessions.loc[valid_sessions['mean_bps'].idxmax()]
            print(f"\n✓ Best Session: {best_session['session']} "
                  f"({best_session['mean_bps']:.1f} bps, p={best_session['p_value']:.4f})")
            
            # Check Sub-H7 criterion
            london_or_overlap = session_results[
                session_results['session'].isin(['LONDON', 'LONDON_NY_OVERLAP'])
            ]
            
            if len(london_or_overlap) > 0:
                best_london = london_or_overlap['mean_bps'].max()
                significant = (london_or_overlap['p_value'] < 0.10).any()
                
                if best_london > 12 and significant:
                    print(f"✓ Sub-H7 PASS: London/overlap shows edge > 12 bps with p < 0.10")
                else:
                    print(f"⚠ Sub-H7 INCONCLUSIVE: London/overlap edge = {best_london:.1f} bps")


def main():
    """Run session breakdown analysis."""
    
    # Load data
    print("Loading GBP/USD H1 data...")
    
    try:
        df = pd.read_csv('../data/raw/GBPUSD60.csv',
                         names=['date', 'time', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['date'] + ' ' + df['time'])
        df = df.set_index('timestamp')
        df = df[['open', 'high', 'low', 'close', 'volume']]
        
        if df.index.tz is None:
            df.index = df.index.tz_localize('UTC')
        
        df = df.sort_index()
        df = df[~df.index.duplicated(keep='first')]
        
        print(f"Loaded {len(df)} bars from {df.index[0]} to {df.index[-1]}")
        
    except FileNotFoundError:
        print("ERROR: GBPUSD60.csv not found")
        return
    
    # Build features
    print("\nBuilding exhaustion features...")
    builder = ExhaustionFeatureBuilder()
    df = builder.build_all_features(df)
    
    # Full signal
    full_signal = (df['failure_to_continue_long'] | df['failure_to_continue_short']).astype(int)
    fwd_ret = df['fwd_ret_1h']
    
    # Session breakdown
    analyzer = SessionBreakdownAnalyzer()
    session_results = analyzer.analyze_by_session(df, full_signal, fwd_ret)
    analyzer.print_breakdown_table(session_results)
    
    # Direction breakdown
    print("\n" + "="*80)
    print("DIRECTIONAL BREAKDOWN (Long vs Short)")
    print("="*80)
    
    direction_results = analyzer.analyze_by_direction(
        df,
        df['failure_to_continue_long'],
        df['failure_to_continue_short'],
        fwd_ret
    )
    
    print(direction_results.to_string(index=False))
    
    # Save results
    output_path = '../reports/backtests/exhaustion_session_breakdown.csv'
    session_results.to_csv(output_path, index=False)
    print(f"\n\nResults saved to: {output_path}")


if __name__ == '__main__':
    main()
