"""
Framework for testing feature predictive power.
"""

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from dataclasses import dataclass


@dataclass
class FeatureTestResult:
    """Results of univariate feature test."""
    feature_name: str
    ic_mean: float
    ic_std: float
    ic_tstat: float
    hit_rate: float
    monotonicity_score: float
    is_stationary: bool
    decay_half_life: int  # bars until IC drops by 50%
    
    def is_significant(self, threshold: float = 0.05) -> bool:
        """Check if IC is statistically significant."""
        return abs(self.ic_mean) > threshold and abs(self.ic_tstat) > 2.0


def diagnose_overlapping_bias(
    feature: pd.Series,
    forward_returns: pd.Series,
    window: int = 252
) -> dict:
    """
    Compare t-stat from overlapping vs non-overlapping windows.
    
    This diagnostic shows how much overlapping windows inflate t-statistics.
    
    Returns:
        dict with:
            - overlapping_tstat: WRONG t-stat (inflated)
            - non_overlapping_tstat: CORRECT t-stat
            - n_overlapping: number of overlapping samples (misleading)
            - n_independent: number of independent samples (correct)
            - inflation_factor: how much the overlap inflated the t-stat
    """
    # Overlapping IC (WRONG for t-stat)
    overlap_ics = rolling_ic(feature, forward_returns, window)
    overlap_mean = overlap_ics.mean()
    overlap_std = overlap_ics.std()
    n_overlap = len(overlap_ics.dropna())
    
    if overlap_std > 0:
        overlap_tstat = overlap_mean / (overlap_std / np.sqrt(n_overlap))
    else:
        overlap_tstat = 0.0
    
    # Non-overlapping IC (CORRECT for t-stat)
    non_overlap_ics = non_overlapping_ic(feature, forward_returns, window)
    non_overlap_mean = non_overlap_ics.mean()
    non_overlap_std = non_overlap_ics.std()
    n_independent = len(non_overlap_ics.dropna())
    
    if non_overlap_std > 0 and n_independent > 1:
        non_overlap_tstat = non_overlap_mean / (non_overlap_std / np.sqrt(n_independent))
    else:
        non_overlap_tstat = 0.0
    
    # Calculate inflation factor
    if non_overlap_tstat != 0:
        inflation = abs(overlap_tstat) / abs(non_overlap_tstat)
    else:
        inflation = np.nan
    
    return {
        'overlapping_tstat': overlap_tstat,
        'non_overlapping_tstat': non_overlap_tstat,
        'n_overlapping': n_overlap,
        'n_independent': n_independent,
        'inflation_factor': inflation,
        'ic_mean_overlap': overlap_mean,
        'ic_mean_non_overlap': non_overlap_mean
    }


def compute_information_coefficient(
    feature: pd.Series, 
    forward_returns: pd.Series,
    method: str = 'spearman'
) -> float:
    """
    Correlation between feature and forward return.
    
    Args:
        feature: Feature values
        forward_returns: Returns at T+1, T+2, etc.
        method: 'spearman' (rank-based, more robust) or 'pearson'
    
    Returns:
        IC value
    """
    # Drop NaN pairs
    valid = ~(feature.isna() | forward_returns.isna())
    
    if valid.sum() < 20:
        return np.nan
    
    if method == 'spearman':
        ic, _ = spearmanr(feature[valid], forward_returns[valid])
    else:
        ic = feature[valid].corr(forward_returns[valid])
    
    return ic


def rolling_ic(
    feature: pd.Series,
    forward_returns: pd.Series,
    window: int = 252  # 1 year for daily data
) -> pd.Series:
    """
    Compute rolling Information Coefficient.
    
    Purpose: Check if feature predictive power is stable over time.
    
    WARNING: These are overlapping windows. Do NOT use len(rolling_ic) 
    as N for t-stat calculation - windows are not independent.
    """
    def calc_ic(feat_window, ret_window):
        if len(feat_window) < 20:
            return np.nan
        return compute_information_coefficient(feat_window, ret_window)
    
    return pd.Series([
        calc_ic(feature.iloc[i:i+window], forward_returns.iloc[i:i+window])
        for i in range(len(feature) - window + 1)
    ], index=feature.index[window-1:])


def non_overlapping_ic(
    feature: pd.Series,
    forward_returns: pd.Series,
    window: int = 252
) -> pd.Series:
    """
    Compute IC on non-overlapping windows for proper statistical inference.
    
    Purpose: Get independent samples for valid t-stat calculation.
    
    Returns:
        Series of IC values from non-overlapping periods.
        Length will be approximately N_total / window.
    """
    def calc_ic(feat_window, ret_window):
        if len(feat_window) < 20:
            return np.nan
        return compute_information_coefficient(feat_window, ret_window)
    
    n_windows = len(feature) // window
    
    if n_windows < 2:
        # Not enough data for even 2 windows
        return pd.Series([compute_information_coefficient(feature, forward_returns)])
    
    ics = []
    window_centers = []
    
    for i in range(n_windows):
        start_idx = i * window
        end_idx = min((i + 1) * window, len(feature))
        
        feat_window = feature.iloc[start_idx:end_idx]
        ret_window = forward_returns.iloc[start_idx:end_idx]
        
        ic = calc_ic(feat_window, ret_window)
        ics.append(ic)
        window_centers.append(feature.index[start_idx + window // 2])
    
    return pd.Series(ics, index=window_centers)


def compute_hit_rate(
    feature: pd.Series,
    forward_returns: pd.Series
) -> float:
    """
    % of times feature correctly predicts direction.
    
    Logic:
    - If feature > 0, predict positive return
    - If feature < 0, predict negative return
    """
    predictions = np.sign(feature)
    actuals = np.sign(forward_returns)
    
    valid = ~(predictions.isna() | actuals.isna())
    
    if valid.sum() == 0:
        return np.nan
    
    correct = (predictions[valid] == actuals[valid]).sum()
    
    return correct / valid.sum()


def test_monotonicity(
    feature: pd.Series,
    forward_returns: pd.Series,
    n_bins: int = 10
) -> float:
    """
    Test if feature has monotonic relationship with returns.
    
    Method:
    1. Bin feature into deciles
    2. Compute mean return per decile
    3. Check if mean return increases monotonically
    
    Returns:
        Score from 0 (random) to 1 (perfect monotonic)
    """
    df = pd.DataFrame({
        'feature': feature,
        'forward_ret': forward_returns
    }).dropna()
    
    if len(df) < n_bins:
        return np.nan
    
    try:
        df['bin'] = pd.qcut(df['feature'], n_bins, labels=False, duplicates='drop')
    except ValueError:
        # Handle case where there are not enough unique values
        return np.nan
    
    bin_means = df.groupby('bin')['forward_ret'].mean()
    
    if len(bin_means) < 2:
        return np.nan
    
    # Count monotonic increases
    diffs = bin_means.diff().dropna()
    monotonic_count = (diffs > 0).sum()
    
    return monotonic_count / len(diffs)


def ic_decay_curve(
    feature: pd.Series,
    prices: pd.Series,
    max_horizon: int = 20
) -> pd.Series:
    """
    Compute IC at different forward horizons.
    
    Purpose: Understand how long feature stays predictive.
    """
    ics = []
    
    for h in range(1, max_horizon + 1):
        forward_ret = prices.pct_change(h).shift(-h)
        ic = compute_information_coefficient(feature, forward_ret)
        ics.append(ic)
    
    return pd.Series(ics, index=range(1, max_horizon + 1))


def test_feature(
    feature: pd.Series,
    prices: pd.Series,
    feature_name: str
) -> FeatureTestResult:
    """
    Comprehensive feature test.
    
    Returns:
        FeatureTestResult with all metrics
        
    IMPORTANT: T-stat is computed using NON-OVERLAPPING IC samples to avoid
    inflating statistical significance from autocorrelated rolling windows.
    """
    from statsmodels.tsa.stattools import adfuller
    
    # Forward returns (1-day ahead)
    forward_ret = prices.pct_change().shift(-1)
    
    # IC metrics - use NON-OVERLAPPING windows for proper t-stat
    # This gives independent samples for valid statistical inference
    non_overlap_ics = non_overlapping_ic(feature, forward_ret, window=252)
    ic_mean = non_overlap_ics.mean()
    ic_std = non_overlap_ics.std()
    
    # Proper t-stat using independent samples
    n_independent = len(non_overlap_ics.dropna())
    
    if pd.isna(ic_std) or ic_std == 0 or n_independent < 2:
        ic_tstat = 0.0
    else:
        # Standard t-stat: mean / standard_error
        # where standard_error = std / sqrt(N)
        ic_tstat = ic_mean / (ic_std / np.sqrt(n_independent))
    
    # Hit rate
    hit_rate = compute_hit_rate(feature, forward_ret)
    
    # Monotonicity
    monotonicity = test_monotonicity(feature, forward_ret)
    
    # Stationarity
    feature_clean = feature.dropna()
    if len(feature_clean) < 20:
        is_stationary = False
    else:
        try:
            adf_stat, adf_pval, *_ = adfuller(feature_clean)
            is_stationary = adf_pval < 0.05
        except:
            is_stationary = False
    
    # IC decay
    decay_curve = ic_decay_curve(feature, prices, max_horizon=20)
    try:
        if ic_mean != 0:
            half_ic = abs(ic_mean) / 2
            below_half = decay_curve.abs() < half_ic
            if below_half.any():
                half_life = below_half.idxmax()
            else:
                half_life = 20
        else:
            half_life = 20
    except:
        half_life = 20
    
    return FeatureTestResult(
        feature_name=feature_name,
        ic_mean=ic_mean if not pd.isna(ic_mean) else 0.0,
        ic_std=ic_std if not pd.isna(ic_std) else 0.0,
        ic_tstat=ic_tstat if not pd.isna(ic_tstat) else 0.0,
        hit_rate=hit_rate if not pd.isna(hit_rate) else 0.5,
        monotonicity_score=monotonicity if not pd.isna(monotonicity) else 0.5,
        is_stationary=is_stationary,
        decay_half_life=int(half_life)
    )
