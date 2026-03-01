"""
Test features across multiple assets for generalization.

Purpose:
- Validate that features work across different currency pairs
- Detect features that only work on one asset (overfitting)
- Ensure IC sign consistency across pairs
"""

import pandas as pd
from typing import Dict, List, Callable
from src.features.testing import test_feature, FeatureTestResult


def test_feature_cross_pairs(
    feature_func: Callable,
    feature_name: str,
    pairs_data: Dict[str, pd.DataFrame],
    **feature_kwargs
) -> Dict[str, FeatureTestResult]:
    """
    Test same feature across multiple FX pairs.
    
    Args:
        feature_func: Function to generate feature (from generators.py)
        feature_name: Name for reporting
        pairs_data: Dict of {pair: DataFrame with OHLC}
        **feature_kwargs: Arguments to pass to feature_func
    
    Returns:
        Dictionary of {pair: FeatureTestResult}
    
    Example:
        >>> pairs_data = {
        ...     'EURUSD': eurusd_df,
        ...     'GBPUSD': gbpusd_df
        ... }
        >>> results = test_feature_cross_pairs(
        ...     distance_from_ma,
        ...     'Distance_MA_20',
        ...     pairs_data,
        ...     period=20
        ... )
    """
    results = {}
    
    for pair, df in pairs_data.items():
        print(f"Testing {feature_name} on {pair}...")
        
        prices = df['close']
        
        # Generate feature based on function signature
        # Handle different feature types (price-based, OHLC-based, etc.)
        try:
            if 'atr' in feature_name.lower():
                # ATR needs high, low, close
                feature = feature_func(df['high'], df['low'], df['close'], **feature_kwargs)
            elif 'close_position' in feature_name.lower():
                # Close position needs high, low, close
                feature = feature_func(df['high'], df['low'], df['close'])
            elif 'return' in feature_name.lower() or 'zscore' in feature_name.lower():
                # Return-based features need returns
                returns = prices.pct_change()
                feature = feature_func(returns, **feature_kwargs)
            else:
                # Standard price-based features
                feature = feature_func(prices, **feature_kwargs)
            
            result = test_feature(feature, prices, f"{feature_name}_{pair}")
            results[pair] = result
            
            print(f"  ✓ {pair}: IC={result.ic_mean:.4f}, t-stat={result.ic_tstat:.2f}")
            
        except Exception as e:
            print(f"  ✗ {pair}: Error - {str(e)}")
            continue
    
    return results


def summarize_cross_validation(results: Dict[str, FeatureTestResult]) -> pd.DataFrame:
    """
    Create summary table of cross-pair results.
    
    Args:
        results: Dict of {pair: FeatureTestResult}
    
    Returns:
        DataFrame with metrics for each pair
    """
    summary = []
    
    for pair, result in results.items():
        summary.append({
            'Pair': pair,
            'IC Mean': result.ic_mean,
            'IC t-stat': result.ic_tstat,
            'Hit Rate': result.hit_rate,
            'Monotonicity': result.monotonicity_score,
            'Stationary': result.is_stationary,
            'Significant': result.is_significant(),
            'Decay Half-Life': result.decay_half_life
        })
    
    df = pd.DataFrame(summary)
    
    # Sort by IC magnitude
    df = df.sort_values('IC Mean', key=abs, ascending=False)
    
    return df


def check_generalization(
    results: Dict[str, FeatureTestResult], 
    min_pairs: int = 3,
    min_ic: float = 0.03
) -> dict:
    """
    Check if feature generalizes across pairs.
    
    Criteria:
    1. Significant on at least min_pairs
    2. IC sign consistent across pairs (all positive or all negative)
    3. |IC| > min_ic threshold on majority
    
    Args:
        results: Dict of {pair: FeatureTestResult}
        min_pairs: Minimum number of pairs that must pass
        min_ic: Minimum absolute IC threshold
    
    Returns:
        dict with 'passes', 'reason', 'details'
    """
    if len(results) == 0:
        return {
            'passes': False,
            'reason': 'No results to analyze',
            'details': {}
        }
    
    ics = [r.ic_mean for r in results.values()]
    significant_count = sum(r.is_significant() for r in results.values())
    
    # Check IC magnitude
    strong_ic_count = sum(abs(ic) > min_ic for ic in ics)
    
    # Check sign consistency
    positive_count = sum(ic > 0 for ic in ics)
    negative_count = sum(ic < 0 for ic in ics)
    sign_consistent = (positive_count >= min_pairs) or (negative_count >= min_pairs)
    
    # Overall pass/fail
    passes = (significant_count >= min_pairs and 
              sign_consistent and 
              strong_ic_count >= min_pairs)
    
    # Calculate statistics
    mean_ic = sum(ics) / len(ics)
    std_ic = pd.Series(ics).std()
    
    details = {
        'total_pairs': len(results),
        'significant_pairs': significant_count,
        'strong_ic_pairs': strong_ic_count,
        'positive_ic_count': positive_count,
        'negative_ic_count': negative_count,
        'sign_consistent': sign_consistent,
        'mean_ic': mean_ic,
        'std_ic': std_ic,
        'min_ic_threshold': min_ic
    }
    
    # Generate reason
    if not passes:
        if significant_count < min_pairs:
            reason = f'Only {significant_count}/{len(results)} pairs significant (need {min_pairs})'
        elif not sign_consistent:
            reason = f'IC sign inconsistent: {positive_count} positive, {negative_count} negative'
        elif strong_ic_count < min_pairs:
            reason = f'Only {strong_ic_count}/{len(results)} pairs have |IC| > {min_ic}'
        else:
            reason = 'Unknown failure'
    else:
        reason = f'Generalizes: {significant_count}/{len(results)} pairs significant, sign consistent'
    
    return {
        'passes': passes,
        'reason': reason,
        'details': details
    }


def print_cross_validation_report(
    feature_name: str,
    results: Dict[str, FeatureTestResult],
    generalization: dict
) -> None:
    """
    Print formatted cross-validation report.
    
    Args:
        feature_name: Name of the feature
        results: Dict of {pair: FeatureTestResult}
        generalization: Output from check_generalization()
    """
    print("\n" + "="*80)
    print(f"CROSS-PAIR VALIDATION: {feature_name}")
    print("="*80)
    
    summary = summarize_cross_validation(results)
    print("\nPer-Pair Results:")
    print(summary.to_string(index=False))
    
    print("\n" + "="*80)
    print("GENERALIZATION CHECK")
    print("="*80)
    
    status = "✓ PASS" if generalization['passes'] else "✗ FAIL"
    print(f"Status: {status}")
    print(f"Reason: {generalization['reason']}")
    
    print("\nDetails:")
    details = generalization['details']
    print(f"  Total pairs tested:     {details['total_pairs']}")
    print(f"  Significant pairs:      {details['significant_pairs']}")
    print(f"  Strong IC pairs:        {details['strong_ic_pairs']}")
    print(f"  Sign consistent:        {details['sign_consistent']}")
    print(f"  Mean IC:                {details['mean_ic']:.4f}")
    print(f"  Std IC:                 {details['std_ic']:.4f}")
    print("="*80)


def compare_features_cross_pairs(
    feature_results: Dict[str, Dict[str, FeatureTestResult]]
) -> pd.DataFrame:
    """
    Compare multiple features across pairs.
    
    Args:
        feature_results: Dict of {feature_name: {pair: FeatureTestResult}}
    
    Returns:
        DataFrame with comparison metrics
    """
    comparison = []
    
    for feature_name, pair_results in feature_results.items():
        ics = [r.ic_mean for r in pair_results.values()]
        tstats = [r.ic_tstat for r in pair_results.values()]
        
        gen_check = check_generalization(pair_results)
        
        comparison.append({
            'Feature': feature_name,
            'Pairs Tested': len(pair_results),
            'Mean IC': sum(ics) / len(ics),
            'Std IC': pd.Series(ics).std(),
            'Min IC': min(ics),
            'Max IC': max(ics),
            'Mean t-stat': sum(tstats) / len(tstats),
            'Generalizes': gen_check['passes'],
            'Sign Consistent': gen_check['details']['sign_consistent']
        })
    
    df = pd.DataFrame(comparison)
    df = df.sort_values('Mean IC', key=abs, ascending=False)
    
    return df
