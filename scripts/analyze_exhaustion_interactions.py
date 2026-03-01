#!/usr/bin/env python3
"""
Day 13: Feature Interaction and Correlation Analysis
Tests which feature combinations drive the exhaustion edge
"""

import sys
sys.path.append('..')

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import seaborn as sns
import matplotlib.pyplot as plt
from scipy.stats import spearmanr, ttest_1samp
from statsmodels.stats.outliers_influence import variance_inflation_factor
from typing import Dict
import warnings
warnings.filterwarnings('ignore')

from src.features.exhaustion_features import ExhaustionFeatureBuilder


class InteractionAnalyzer:
    """
    Analyze feature interactions and correlations.
    
    Key questions:
    1. Do features work independently or only in combination?
    2. Are features measuring the same thing (redundant)?
    3. Which combinations drive the edge?
    """
    
    def __init__(self):
        """Initialize analyzer."""
        pass
    
    def build_interaction_grid(
        self,
        df: pd.DataFrame,
        forward_returns: pd.Series
    ) -> pd.DataFrame:
        """
        Build 2×2×2 interaction grid for 3 binary features.
        
        Tests all 8 combinations of:
        - Directional pressure (dp)
        - Range expansion (rng)
        - Close extreme (cls)
        
        Returns:
            DataFrame with edge for each combination
        """
        print("="*80)
        print("2×2×2 FEATURE INTERACTION GRID")
        print("="*80)
        
        # Create binary flags
        df_work = df.copy()
        df_work['dp_high'] = (df_work['dir_pressure_2'].abs() >= 2).astype(int)
        df_work['rng_expand'] = df_work['range_expansion_10'].astype(int)
        df_work['cls_extreme'] = df_work['close_extreme_35'].astype(int)
        df_work['fwd_ret'] = forward_returns
        
        results = []
        
        # Generate all 8 combinations
        for dp in [0, 1]:
            for rng in [0, 1]:
                for cls in [0, 1]:
                    mask = (
                        (df_work['dp_high'] == dp) &
                        (df_work['rng_expand'] == rng) &
                        (df_work['cls_extreme'] == cls)
                    )
                    
                    subset = df_work[mask]['fwd_ret'].dropna()
                    
                    if len(subset) < 20:
                        results.append({
                            'dir_pressure': dp,
                            'range_expand': rng,
                            'close_extreme': cls,
                            'n': len(subset),
                            'mean_bps': np.nan,
                            'p_value': np.nan,
                            'win_rate': np.nan,
                            'note': 'Insufficient data'
                        })
                        continue
                    
                    mean_bps = subset.mean() * 10000
                    win_rate = (subset > 0).mean()
                    
                    # T-test against zero
                    t_stat, p_value = ttest_1samp(subset, 0)
                    
                    results.append({
                        'dir_pressure': dp,
                        'range_expand': rng,
                        'close_extreme': cls,
                        'n': len(subset),
                        'mean_bps': mean_bps,
                        'std_bps': subset.std() * 10000,
                        't_stat': t_stat,
                        'p_value': p_value,
                        'win_rate': win_rate
                    })
        
        results_df = pd.DataFrame(results)
        
        # Print table
        print(f"\n{'DP':<4} | {'RNG':<4} | {'CLS':<4} | {'N':<6} | {'Mean bps':<10} | {'Win%':<8} | {'p-val':<8} | Interpretation")
        print("-"*100)
        
        for _, row in results_df.iterrows():
            if pd.isna(row['mean_bps']):
                interp = row.get('note', 'N/A')
            else:
                # Interpretation
                if row['dir_pressure'] == 1 and row['range_expand'] == 1 and row['close_extreme'] == 1:
                    interp = "⭐ FULL SIGNAL (hypothesis)"
                elif (row['dir_pressure'] + row['range_expand'] + row['close_extreme']) == 0:
                    interp = "Baseline (no features)"
                elif (row['dir_pressure'] + row['range_expand'] + row['close_extreme']) == 1:
                    interp = "Single feature only"
                else:
                    interp = "Partial combination"
            
            print(f"{row['dir_pressure']:<4} | {row['range_expand']:<4} | {row['close_extreme']:<4} | "
                  f"{row['n']:<6} | {row['mean_bps']:>10.2f} | {row['win_rate']:>7.1%} | "
                  f"{row['p_value']:>8.4f} | {interp}")
        
        print("="*80)
        
        # Analysis: Do features interact or work independently?
        print("\n" + "="*80)
        print("INTERACTION ANALYSIS")
        print("="*80)
        
        # Get key combinations
        full_signal = results_df[
            (results_df['dir_pressure'] == 1) &
            (results_df['range_expand'] == 1) &
            (results_df['close_extreme'] == 1)
        ]
        
        dp_only = results_df[
            (results_df['dir_pressure'] == 1) &
            (results_df['range_expand'] == 0) &
            (results_df['close_extreme'] == 0)
        ]
        
        rng_only = results_df[
            (results_df['dir_pressure'] == 0) &
            (results_df['range_expand'] == 1) &
            (results_df['close_extreme'] == 0)
        ]
        
        cls_only = results_df[
            (results_df['dir_pressure'] == 0) &
            (results_df['range_expand'] == 0) &
            (results_df['close_extreme'] == 1)
        ]
        
        baseline = results_df[
            (results_df['dir_pressure'] == 0) &
            (results_df['range_expand'] == 0) &
            (results_df['close_extreme'] == 0)
        ]
        
        if len(full_signal) > 0:
            full_edge = full_signal['mean_bps'].values[0]
            print(f"Full signal (1,1,1): {full_edge:.2f} bps")
            
            # Check if individual features perform similarly
            if len(dp_only) > 0:
                dp_edge = dp_only['mean_bps'].values[0]
                print(f"DP alone (1,0,0):    {dp_edge:.2f} bps")
                
                if not pd.isna(dp_edge) and abs(dp_edge - full_edge) < 3:
                    print("  ⚠ WARNING: DP alone gives same edge → other features redundant!")
            
            if len(rng_only) > 0:
                rng_edge = rng_only['mean_bps'].values[0]
                print(f"RNG alone (0,1,0):   {rng_edge:.2f} bps")
                
                if not pd.isna(rng_edge) and abs(rng_edge - full_edge) < 3:
                    print("  ⚠ WARNING: Range alone gives same edge → simplify hypothesis!")
            
            if len(cls_only) > 0:
                cls_edge = cls_only['mean_bps'].values[0]
                print(f"CLS alone (0,0,1):   {cls_edge:.2f} bps")
                
                if not pd.isna(cls_edge) and abs(cls_edge - full_edge) < 3:
                    print("  ⚠ WARNING: Close extreme alone gives same edge!")
            
            if len(baseline) > 0:
                baseline_edge = baseline['mean_bps'].values[0]
                print(f"Baseline (0,0,0):    {baseline_edge:.2f} bps")
            
            print("\n✓ If full signal >> individual features: TRUE INTERACTION (features combine)")
            print("✗ If one feature ≈ full signal: DOMINANT FEATURE (others add little value)")
        
        return results_df
    
    def compute_feature_correlation_matrix(
        self,
        df: pd.DataFrame,
        feature_cols: list
    ) -> pd.DataFrame:
        """
        Matrix 1: Feature-to-Feature correlation (redundancy check).
        """
        print("\n" + "="*80)
        print("MATRIX 1: FEATURE-FEATURE CORRELATION (Input Redundancy)")
        print("="*80)
        
        # Extract features
        df_features = df[feature_cols].dropna()
        
        if len(df_features) == 0:
            print("ERROR: No valid feature data")
            return pd.DataFrame()
        
        # Spearman correlation (rank-based, robust for binary features)
        corr_matrix = df_features.corr(method='spearman')
        
        print("\nCorrelation Matrix:")
        print(corr_matrix.round(3))
        
        # Find high correlations
        print("\nHigh Correlations (|r| > 0.70):")
        
        high_corr_found = False
        for i in range(len(corr_matrix)):
            for j in range(i+1, len(corr_matrix)):
                corr_val = corr_matrix.iloc[i, j]
                
                if abs(corr_val) > 0.70:
                    feat_a = corr_matrix.index[i]
                    feat_b = corr_matrix.index[j]
                    print(f"  {feat_a} ↔ {feat_b}: {corr_val:.3f}")
                    high_corr_found = True
        
        if not high_corr_found:
            print("  ✓ No high correlations found (features are independent)")
        
        # Plot heatmap
        plt.figure(figsize=(10, 8))
        sns.heatmap(
            corr_matrix,
            annot=True,
            fmt='.2f',
            cmap='RdBu_r',
            center=0,
            vmin=-1,
            vmax=1,
            square=True
        )
        plt.title('Feature-Feature Correlation Matrix', fontsize=14, fontweight='bold')
        plt.tight_layout()
        
        plot_path = '../reports/figures/exhaustion_feature_correlation.png'
        plt.savefig(plot_path, dpi=300, bbox_inches='tight')
        print(f"\n✓ Heatmap saved to: {plot_path}")
        plt.close()
        
        return corr_matrix
    
    def compute_feature_return_correlation(
        self,
        df: pd.DataFrame,
        feature_cols: list,
        return_cols: list
    ) -> pd.DataFrame:
        """
        Matrix 2: Feature-to-Return correlation (predictive power map).
        """
        print("\n" + "="*80)
        print("MATRIX 2: FEATURE-RETURN CORRELATION (Predictive Power by Horizon)")
        print("="*80)
        
        # Build combined dataframe
        all_cols = feature_cols + return_cols
        df_combined = df[all_cols].dropna()
        
        if len(df_combined) == 0:
            print("ERROR: No valid data")
            return pd.DataFrame()
        
        # Compute full correlation matrix
        full_corr = df_combined.corr(method='spearman')
        
        # Extract feature-to-return portion
        predictive_matrix = full_corr.loc[feature_cols, return_cols]
        
        print("\nFeature → Forward Return Correlations:")
        print(predictive_matrix.round(3))
        
        # Check for decay pattern (microstructure signature)
        print("\nIC Decay Pattern (should decay with horizon for microstructure signal):")
        
        for feat in feature_cols:
            ics = predictive_matrix.loc[feat].values
            
            if len(ics) >= 3:
                decay = abs(ics[0]) > abs(ics[-1])
                print(f"  {feat}: {ics[0]:.3f} → {ics[-1]:.3f} ", end='')
                
                if decay:
                    print("✓ Decays (microstructure)")
                else:
                    print("⚠ No decay (macro/trend?)")
        
        # Plot heatmap
        plt.figure(figsize=(12, 6))
        sns.heatmap(
            predictive_matrix.T,  # Transpose for better readability
            annot=True,
            fmt='.3f',
            cmap='RdBu_r',
            center=0,
            vmin=-0.5,
            vmax=0.5
        )
        plt.title('Feature → Forward Return Predictive Power', fontsize=14, fontweight='bold')
        plt.xlabel('Features', fontsize=12)
        plt.ylabel('Forward Horizons', fontsize=12)
        plt.tight_layout()
        
        plot_path = '../reports/figures/exhaustion_feature_return_correlation.png'
        plt.savefig(plot_path, dpi=300, bbox_inches='tight')
        print(f"\n✓ Heatmap saved to: {plot_path}")
        plt.close()
        
        return predictive_matrix
    
    def run_vif_test(
        self,
        df: pd.DataFrame,
        feature_cols: list
    ) -> pd.DataFrame:
        """
        Variance Inflation Factor test for multicollinearity.
        """
        print("\n" + "="*80)
        print("VARIANCE INFLATION FACTOR (VIF) TEST")
        print("="*80)
        
        # Prepare data
        X = df[feature_cols].dropna()
        
        if len(X) == 0:
            print("ERROR: No valid data")
            return pd.DataFrame()
        
        # Compute VIF for each feature
        vif_data = []
        
        for i, col in enumerate(X.columns):
            try:
                vif = variance_inflation_factor(X.values, i)
                vif_data.append({
                    'feature': col,
                    'VIF': vif
                })
            except Exception as e:
                print(f"  WARNING: Could not compute VIF for {col}: {e}")
                vif_data.append({
                    'feature': col,
                    'VIF': np.nan
                })
        
        vif_df = pd.DataFrame(vif_data)
        
        print("\nVIF Results:")
        print(f"{'Feature':<25} | {'VIF':<10} | Interpretation")
        print("-"*60)
        
        for _, row in vif_df.iterrows():
            vif_val = row['VIF']
            
            if pd.isna(vif_val):
                interp = "N/A"
            elif vif_val < 5:
                interp = "✓ Acceptable"
            elif vif_val < 10:
                interp = "⚠ Moderate multicollinearity"
            else:
                interp = "✗ High multicollinearity (consider dropping)"
            
            print(f"{row['feature']:<25} | {vif_val:>10.2f} | {interp}")
        
        print("\nGuidelines:")
        print("  VIF < 5:  No multicollinearity")
        print("  VIF 5-10: Moderate (document)")
        print("  VIF > 10: High (drop or combine features)")
        
        return vif_df


def main():
    """Run interaction and correlation analysis."""
    
    print("="*80)
    print("EXHAUSTION FEATURE INTERACTION & CORRELATION ANALYSIS")
    print("="*80)
    
    # Load data
    print("\nLoading GBP/USD H1 data...")
    
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
    
    # Run interaction grid
    analyzer = InteractionAnalyzer()
    
    interaction_df = analyzer.build_interaction_grid(
        df,
        df['fwd_ret_1h']
    )
    
    # Feature correlation matrix
    feature_cols = [
        'dir_pressure_2',
        'range_expansion_10',
        'close_extreme_35',
        'session_london',
        'body_ratio',
        'upper_wick_ratio',
        'lower_wick_ratio'
    ]
    
    corr_matrix = analyzer.compute_feature_correlation_matrix(df, feature_cols)
    
    # Feature-return correlation
    return_cols = ['fwd_ret_1h', 'fwd_ret_2h', 'fwd_ret_3h', 'fwd_ret_4h', 'fwd_ret_5h']
    
    predictive_matrix = analyzer.compute_feature_return_correlation(
        df,
        feature_cols,
        return_cols
    )
    
    # VIF test
    vif_df = analyzer.run_vif_test(df, feature_cols)
    
    # Save results
    print("\n" + "="*80)
    print("SAVING RESULTS")
    print("="*80)
    
    interaction_df.to_csv('../reports/backtests/exhaustion_interaction_grid.csv', index=False)
    print("✓ Interaction grid: reports/backtests/exhaustion_interaction_grid.csv")
    
    if len(corr_matrix) > 0:
        corr_matrix.to_csv('../reports/backtests/exhaustion_feature_correlation.csv')
        print("✓ Feature correlation: reports/backtests/exhaustion_feature_correlation.csv")
    
    if len(predictive_matrix) > 0:
        predictive_matrix.to_csv('../reports/backtests/exhaustion_feature_return_correlation.csv')
        print("✓ Feature-return correlation: reports/backtests/exhaustion_feature_return_correlation.csv")
    
    if len(vif_df) > 0:
        vif_df.to_csv('../reports/backtests/exhaustion_vif_test.csv', index=False)
        print("✓ VIF test: reports/backtests/exhaustion_vif_test.csv")
    
    print("\n" + "="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)


if __name__ == '__main__':
    main()
