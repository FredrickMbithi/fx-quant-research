#!/usr/bin/env python3
"""
Day 12: Univariate Testing Framework for Exhaustion Hypothesis
Tests each sub-hypothesis independently with statistical rigor
"""

import sys
sys.path.append('..')

import pandas as pd
import numpy as np
from scipy import stats
from scipy.stats import ttest_ind, ttest_1samp
from statsmodels.stats.multitest import multipletests
from statsmodels.tsa.stattools import acf
from typing import Dict, List, Tuple
import warnings
warnings.filterwarnings('ignore')

from src.features.exhaustion_features import ExhaustionFeatureBuilder, generate_exhaustion_signal_series
from src.features.testing import test_feature, compute_information_coefficient
from src.data.loader import FXDataLoader


class UnivariateExhaustionTest:
    """
    Test individual exhaustion hypothesis components.
    
    Implements Day 12 testing framework with:
    - Binary signal testing (signal=1 vs signal=0)
    - Multiple testing correction (Benjamini-Hochberg)
    - Bootstrap confidence intervals
    - Distribution checks
    - Signal autocorrelation
    """
    
    def __init__(self, significance_level: float = 0.05):
        """
        Args:
            significance_level: Alpha level for hypothesis tests
        """
        self.alpha = significance_level
        self.results = {}
    
    def run_binary_signal_test(
        self,
        signal: pd.Series,
        forward_returns: pd.Series,
        signal_name: str
    ) -> Dict:
        """
        Test if binary signal (0/1) predicts forward returns.
        
        Args:
            signal: Binary series (1 = signal triggered, 0 = baseline)
            forward_returns: Forward returns to predict
            signal_name: Name for reporting
            
        Returns:
            Dict with test results
        """
        # Align and drop NaN
        df = pd.DataFrame({
            'signal': signal,
            'fwd_ret': forward_returns
        }).dropna()
        
        print(f"  Aligned {len(df)} observations", flush=True)
        
        if len(df) == 0:
            return self._empty_result(signal_name, "No data")
        
        # Split into signal vs baseline
        triggered = df[df['signal'] == 1]['fwd_ret']
        baseline = df[df['signal'] == 0]['fwd_ret']
        
        print(f"  Signals: {len(triggered)}, Baseline: {len(baseline)}", flush=True)
        
        if len(triggered) < 10:
            return self._empty_result(signal_name, f"Insufficient signals (N={len(triggered)})")
        
        # Compute statistics
        n_signals = len(triggered)
        n_baseline = len(baseline)
        mean_return_bps = triggered.mean() * 10000
        baseline_return_bps = baseline.mean() * 10000
        std_bps = triggered.std() * 10000
        
        # T-test: triggered vs baseline
        if len(baseline) > 10:
            t_stat, p_value = ttest_ind(triggered, baseline)
        else:
            # If no baseline, test against zero
            t_stat, p_value = ttest_1samp(triggered, 0)
        
        # Effect size (Cohen's d)
        pooled_std = np.sqrt(((len(triggered) - 1) * triggered.var() + 
                              (len(baseline) - 1) * baseline.var()) / 
                             (len(triggered) + len(baseline) - 2))
        cohens_d = (triggered.mean() - baseline.mean()) / pooled_std if pooled_std > 0 else 0
        
        # Win rate
        win_rate = (triggered > 0).mean()
        
        # Bootstrap 95% CI for mean return
        bootstrap_ci = self._bootstrap_ci(triggered.values)
        
        return {
            'signal_name': signal_name,
            'n_signals': n_signals,
            'n_baseline': n_baseline,
            'mean_bps': mean_return_bps,
            'baseline_bps': baseline_return_bps,
            'std_bps': std_bps,
            't_stat': t_stat,
            'p_value': p_value,
            'cohens_d': cohens_d,
            'win_rate': win_rate,
            'bootstrap_ci_lower': bootstrap_ci[0],
            'bootstrap_ci_upper': bootstrap_ci[1],
            'status': 'success'
        }
    
    def _bootstrap_ci(
        self,
        data: np.ndarray,
        n_bootstrap: int = 100,
        ci: float = 0.95
    ) -> Tuple[float, float]:
        """
        Compute bootstrap confidence interval for mean (simplified for speed).
        """
        if len(data) < 10:
            return (np.nan, np.nan)
        
        print(f"  Running bootstrap ({n_bootstrap} iterations on {len(data)} points)...", flush=True, end='')
        
        # Simple manual bootstrap (much faster than scipy.stats.bootstrap)
        rng = np.random.RandomState(42)
        bootstrap_means = []
        n = len(data)
        
        for _ in range(n_bootstrap):
            sample = rng.choice(data, size=n, replace=True)
            bootstrap_means.append(np.mean(sample))
        
        bootstrap_means = np.array(bootstrap_means)
        alpha = 1 - ci
        lower_percentile = (alpha / 2) * 100
        upper_percentile = (1 - alpha / 2) * 100
        
        lower = np.percentile(bootstrap_means, lower_percentile) * 10000
        upper = np.percentile(bootstrap_means, upper_percentile) * 10000
        
        print(" done", flush=True)
        
        return (lower, upper)
    
    def check_distribution(self, returns: pd.Series) -> Dict:
        """
        Test if return distribution is normal (for t-test validity).
        
        Returns:
            Dict with normality test results
        """
        # Shapiro-Wilk test (for small samples)
        if len(returns) < 5000:
            stat, p_value = stats.shapiro(returns.dropna())
            test_name = 'Shapiro-Wilk'
        else:
            # Jarque-Bera for larger samples
            stat, p_value = stats.jarque_bera(returns.dropna())
            test_name = 'Jarque-Bera'
        
        # Also compute skewness and kurtosis
        skew = returns.skew()
        kurt = returns.kurtosis()
        
        return {
            'test_name': test_name,
            'stat': stat,
            'p_value': p_value,
            'is_normal': p_value > 0.05,
            'skewness': skew,
            'kurtosis': kurt,
            'interpretation': 'Normal' if p_value > 0.05 else 'Non-normal (use bootstrap CI)'
        }
    
    def check_signal_autocorrelation(
        self,
        signal: pd.Series,
        max_lags: int = 10
    ) -> Dict:
        """
        Check if signals cluster in time (autocorrelation).
        
        High autocorrelation means signals are not independent samples.
        """
       # Manual lag-1 autocorrelation (much faster than statsmodels ACF)
        signal_clean = signal.fillna(0).values
        n = len(signal_clean)
        
        # Manually compute lag-1 correlation
        mean_val = signal_clean.mean()
        var_val = signal_clean.var()
        
        if var_val > 0:
            lag1_cov = np.mean((signal_clean[:-1] - mean_val) * (signal_clean[1:] - mean_val))
            acf_lag1 = lag1_cov / var_val
        else:
            acf_lag1 = 0.0
        
        return {
            'acf_lag1': acf_lag1,
            'acf_values': [1.0, acf_lag1],  # Simplified
            'clustered': acf_lag1 > 0.30,
            'interpretation': 'Signals clustered (reduce effective N)' if acf_lag1 > 0.30 else 'Signals independent'
        }
    
    def apply_multiple_testing_correction(
        self,
        p_values: List[float],
        method: str = 'fdr_bh'
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Apply Benjamini-Hochberg FDR correction.
        
        Args:
            p_values: List of p-values from multiple tests
            method: 'fdr_bh' (Benjamini-Hochberg) or 'bonferroni'
            
        Returns:
            (reject, corrected_p_values)
        """
        reject, p_corrected, _, _ = multipletests(
            p_values,
            alpha=self.alpha,
            method=method
        )
        
        return reject, p_corrected
    
    def _empty_result(self, signal_name: str, reason: str) -> Dict:
        """Return empty result dict for failed tests."""
        return {
            'signal_name': signal_name,
            'status': 'failed',
            'reason': reason,
            'n_signals': 0,
            'mean_bps': np.nan,
            't_stat': np.nan,
            'p_value': np.nan
        }
    
    def run_all_subhypotheses(
        self,
        df: pd.DataFrame,
        feature_builder: ExhaustionFeatureBuilder
    ) -> pd.DataFrame:
        """
        Run all 7 sub-hypotheses from decomposition document.
        
        Args:
            df: DataFrame with OHLC and exhaustion features
            feature_builder: ExhaustionFeatureBuilder instance
            
        Returns:
            Summary DataFrame with all test results
        """
        results_list = []
        
        # Use 1-hour forward return as primary target
        fwd_ret = df['fwd_ret_1h']
        
        print("="*80)
        print("EXHAUSTION HYPOTHESIS - UNIVARIATE TESTING")
        print("="*80)
        print(f"Data period: {df.index[0]} to {df.index[-1]}")
        print(f"Total bars: {len(df)}")
        print()
        
        # Sub-H1: Directional Pressure Alone
        print("\n[Sub-H1] Directional Pressure (±2) Predicts Next-Bar Direction", flush=True)
        print("-"*80, flush=True)
        signal_h1 = (df['dir_pressure_2'].abs() >= 2).astype(int)
        result_h1 = self.run_binary_signal_test(signal_h1, fwd_ret, 'Sub-H1: Directional Pressure')
        results_list.append(result_h1)
        self._print_result(result_h1)
        
        # Sub-H2: Range Expansion Alone
        print("\n[Sub-H2] Range Expansion Predicts Mean Reversion")
        print("-"*80)
        signal_h2 = df['range_expansion_10']
        result_h2 = self.run_binary_signal_test(signal_h2, fwd_ret, 'Sub-H2: Range Expansion')
        results_list.append(result_h2)
        self._print_result(result_h2)
        
        # Sub-H3: Close Extreme Alone
        print("\n[Sub-H3] Close Extreme Predicts Mean Reversion")
        print("-"*80)
        signal_h3 = df['close_extreme_35']
        result_h3 = self.run_binary_signal_test(signal_h3, fwd_ret, 'Sub-H3: Close Extreme')
        results_list.append(result_h3)
        self._print_result(result_h3)
        
        # Sub-H4: Combined Exhaustion (without confirmation)
        print("\n[Sub-H4] Combined Exhaustion (All 3 Features)")
        print("-"*80)
        signal_h4 = (df['exhaustion_long'] | df['exhaustion_short']).astype(int)
        result_h4 = self.run_binary_signal_test(signal_h4, fwd_ret, 'Sub-H4: Combined Exhaustion')
        results_list.append(result_h4)
        self._print_result(result_h4)
        
        # Sub-H5: With Failure-to-Continue Confirmation
        print("\n[Sub-H5] Exhaustion + Failure-to-Continue Confirmation")
        print("-"*80)
        signal_h5 = (df['failure_to_continue_long'] | df['failure_to_continue_short']).astype(int)
        result_h5 = self.run_binary_signal_test(signal_h5, fwd_ret, 'Sub-H5: Full Signal')
        results_list.append(result_h5)
        self._print_result(result_h5)
        
        # Check signal clustering for Sub-H5
        # clustering_h5 = self.check_signal_autocorrelation(signal_h5)
        # print(f"  Signal ACF[1]: {clustering_h5['acf_lag1']:.3f} - {clustering_h5['interpretation']}")
        
        # Sub-H6: Transaction Cost Hurdle (1.2 pips = 12 bps round trip)
        print("\n[Sub-H6] Edge After Transaction Costs (1.2 pips)")
        print("-"*80)
        net_return = fwd_ret * 10000 - 12  # Subtract 12 bps per trade
        signal_h6 = signal_h5  # Same signal as H5
        result_h6_temp = self.run_binary_signal_test(signal_h6, net_return / 10000, 'Sub-H6: After Costs')
        result_h6 = result_h6_temp.copy()
        result_h6['signal_name'] = 'Sub-H6: After Costs'
        results_list.append(result_h6)
        self._print_result(result_h6)
        
        # Sub-H7: Session filter tested in separate script
        print("\n[Sub-H7] Session Breakdown → See analyze_exhaustion_by_session.py")
        
        # Apply multiple testing correction
        print("\n" + "="*80)
        print("MULTIPLE TESTING CORRECTION (Benjamini-Hochberg FDR)")
        print("="*80)
        
        p_values = [r['p_value'] for r in results_list if r['status'] == 'success']
        if len(p_values) > 0:
            reject, p_corrected = self.apply_multiple_testing_correction(p_values)
            
            for i, result in enumerate([r for r in results_list if r['status'] == 'success']):
                result['p_value_corrected'] = p_corrected[i]
                result['significant_after_mtc'] = reject[i]
                print(f"{result['signal_name']}:")
                print(f"  Original p-value: {result['p_value']:.4f}")
                print(f"  Corrected p-value: {p_corrected[i]:.4f}")
                print(f"  Significant: {'YES' if reject[i] else 'NO'}")
        
        return pd.DataFrame(results_list)
    
    def _print_result(self, result: Dict):
        """Pretty print test result."""
        if result['status'] != 'success':
            print(f"  ⚠ {result['reason']}")
            return
        
        print(f"  N signals: {result['n_signals']}")
        print(f"  Mean return: {result['mean_bps']:.2f} bps")
        print(f"  Baseline: {result['baseline_bps']:.2f} bps")
        print(f"  Std: {result['std_bps']:.2f} bps")
        print(f"  t-stat: {result['t_stat']:.2f}")
        print(f"  p-value: {result['p_value']:.4f}")
        print(f"  Cohen's d: {result['cohens_d']:.3f}")
        print(f"  Win rate: {result['win_rate']:.1%}")
        print(f"  Bootstrap 95% CI: [{result['bootstrap_ci_lower']:.1f}, {result['bootstrap_ci_upper']:.1f}] bps")
    
    def evaluate_decision_gates(self, results_df: pd.DataFrame) -> Dict[str, bool]:
        """
        Evaluate Day 11 acceptance criteria.
        
        Returns:
            Dict of {criterion: pass/fail}
        """
        gates = {}
        
        # Gate 1: At least 2 of 3 individual features show bias (p < 0.10)
        individual = results_df[results_df['signal_name'].str.contains('Sub-H[1-3]')]
        individual_sig = (individual['p_value'] < 0.10).sum()
        gates['individual_features'] = individual_sig >= 2
        
        # Gate 2: Combined exhaustion mean > 10 bps, p < 0.05 (post-MTC)
        h4 = results_df[results_df['signal_name'] == 'Sub-H4: Combined Exhaustion']
        if len(h4) > 0:
            gates['combined_exhaustion'] = (
                h4['mean_bps'].values[0] > 10 and
                h4.get('p_value_corrected', h4['p_value']).values[0] < 0.05
            )
        else:
            gates['combined_exhaustion'] = False
        
        # Gate 3: N_signals > 300
        h5 = results_df[results_df['signal_name'] == 'Sub-H5: Full Signal']
        if len(h5) > 0:
            gates['sufficient_signals'] = h5['n_signals'].values[0] > 300
        else:
            gates['sufficient_signals'] = False
        
        # Gate 4: After-cost edge > 0 (Sub-H6)
        h6 = results_df[results_df['signal_name'] == 'Sub-H6: After Costs']
        if len(h6) > 0:
            gates['profitable_after_costs'] = h6['mean_bps'].values[0] > 0
        else:
            gates['profitable_after_costs'] = False
        
        return gates


def main():
    """Run univariate tests on GBP/USD H1 data."""
    
    # Load data
    print("Loading GBP/USD H1 data...")
    loader = FXDataLoader('../data/raw')
    
    try:
        # Try to load H1 data
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
        print("Please ensure H1 data exists at data/raw/GBPUSD60.csv")
        return
    
    # Build exhaustion features
    print("\nBuilding exhaustion features...")
    builder = ExhaustionFeatureBuilder()
    df = builder.build_all_features(df)
    
    # Run all hypothesis tests
    tester = UnivariateExhaustionTest(significance_level=0.05)
    results_df = tester.run_all_subhypotheses(df, builder)
    
    # Evaluate decision gates
    print("\n" + "="*80)
    print("DECISION GATES EVALUATION")
    print("="*80)
    
    gates = tester.evaluate_decision_gates(results_df)
    
    for gate_name, passed in gates.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status:8} | {gate_name}")
    
    all_passed = all(gates.values())
    
    print("\n" + "="*80)
    if all_passed:
        print("✅ ALL GATES PASSED - Proceed to Day 13 (Cross-Pair Validation)")
    else:
        print("❌ SOME GATES FAILED - Review hypothesis or revise Day 11")
    print("="*80)
    
    # Save results
    output_path = '../reports/backtests/exhaustion_univariate_results.csv'
    results_df.to_csv(output_path, index=False)
    print(f"\nResults saved to: {output_path}")


if __name__ == '__main__':
    main()
