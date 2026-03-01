"""
Analyze feature correlation and redundancy.

Purpose:
- Identify features that measure the same underlying signal
- Remove redundant features to avoid multicollinearity
- Keep the feature with higher IC when redundancy detected
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Set
import matplotlib.pyplot as plt

try:
    import seaborn as sns
    HAS_SEABORN = True
except ImportError:
    HAS_SEABORN = False


def compute_feature_correlation_matrix(features: Dict[str, pd.Series]) -> pd.DataFrame:
    """
    Compute pairwise correlation between features (not features vs returns).
    
    Args:
        features: Dict of {feature_name: feature_series}
    
    Returns:
        DataFrame with Spearman correlation matrix
    
    Note:
        Uses Spearman correlation to handle non-linear relationships.
    """
    df = pd.DataFrame(features)
    return df.corr(method='spearman')


def identify_redundant_features(
    feature_corr: pd.DataFrame,
    ic_scores: Dict[str, float],
    threshold: float = 0.7
) -> Dict[str, List[Tuple[str, float]]]:
    """
    Find features to drop due to redundancy.
    
    Logic:
    - If |corr(A, B)| > threshold
    - Drop the one with lower |IC|
    - Keep the stronger predictor
    
    Args:
        feature_corr: Feature correlation matrix
        ic_scores: Dict of {feature_name: IC value}
        threshold: Correlation threshold for redundancy (default 0.7)
    
    Returns:
        Dict with 'to_drop' (list of feature names) and 'pairs' (redundant pairs info)
    """
    to_drop = set()
    redundant_pairs = []
    
    feature_names = feature_corr.index.tolist()
    
    for i in range(len(feature_corr)):
        for j in range(i + 1, len(feature_corr)):
            feat_a = feature_names[i]
            feat_b = feature_names[j]
            
            corr_val = feature_corr.iloc[i, j]
            
            if abs(corr_val) > threshold:
                ic_a = abs(ic_scores.get(feat_a, 0))
                ic_b = abs(ic_scores.get(feat_b, 0))
                
                # Drop the one with lower IC
                if ic_a < ic_b:
                    to_drop.add(feat_a)
                    weaker, stronger = feat_a, feat_b
                    weaker_ic, stronger_ic = ic_a, ic_b
                else:
                    to_drop.add(feat_b)
                    weaker, stronger = feat_b, feat_a
                    weaker_ic, stronger_ic = ic_b, ic_a
                
                redundant_pairs.append({
                    'feature_1': feat_a,
                    'feature_2': feat_b,
                    'correlation': corr_val,
                    'ic_1': ic_scores.get(feat_a, 0),
                    'ic_2': ic_scores.get(feat_b, 0),
                    'drop': weaker,
                    'keep': stronger
                })
    
    return {
        'to_drop': list(to_drop),
        'pairs': redundant_pairs
    }


def plot_feature_correlation(
    feature_corr: pd.DataFrame, 
    save_path: str = None,
    figsize: Tuple[int, int] = (12, 10),
    title: str = 'Feature Correlation Matrix (Spearman)'
) -> None:
    """
    Create heatmap of feature correlations.
    
    Args:
        feature_corr: Correlation matrix DataFrame
        save_path: Path to save figure (optional)
        figsize: Figure size tuple
        title: Plot title
    """
    plt.figure(figsize=figsize)
    
    # Create mask for upper triangle (optional, for cleaner visualization)
    mask = np.triu(np.ones_like(feature_corr, dtype=bool), k=1)
    
    if HAS_SEABORN:
        sns.heatmap(
            feature_corr,
            annot=True,
            fmt='.2f',
            cmap='RdBu_r',
            center=0,
            vmin=-1,
            vmax=1,
            square=True,
            linewidths=0.5,
            cbar_kws={'label': 'Spearman Correlation'},
            mask=mask
        )
    else:
        # Fallback to matplotlib imshow
        masked_corr = feature_corr.copy()
        masked_corr[mask] = np.nan
        
        im = plt.imshow(masked_corr, cmap='RdBu_r', vmin=-1, vmax=1, aspect='auto')
        
        # Add colorbar
        cbar = plt.colorbar(im, label='Spearman Correlation')
        
        # Add annotations
        for i in range(len(feature_corr)):
            for j in range(len(feature_corr)):
                if not mask[i, j]:
                    text = plt.text(j, i, f'{feature_corr.iloc[i, j]:.2f}',
                                  ha="center", va="center", color="black", fontsize=8)
        
        # Set ticks and labels
        plt.xticks(range(len(feature_corr)), feature_corr.columns, rotation=45, ha='right')
        plt.yticks(range(len(feature_corr)), feature_corr.index, rotation=0)
    
    plt.title(title, fontsize=14, fontweight='bold', pad=20)
    plt.xlabel('')
    plt.ylabel('')
    if not HAS_SEABORN:
        plt.xticks(rotation=45, ha='right')
        plt.yticks(rotation=0)
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Figure saved to {save_path}")
    
    plt.show()


def analyze_feature_clusters(
    feature_corr: pd.DataFrame,
    threshold: float = 0.5
) -> Dict[str, List[str]]:
    """
    Identify clusters of correlated features.
    
    Args:
        feature_corr: Feature correlation matrix
        threshold: Minimum correlation to consider features related
    
    Returns:
        Dict of {cluster_id: [feature_names]}
    """
    from scipy.cluster.hierarchy import linkage, fcluster
    from scipy.spatial.distance import squareform
    
    # Convert correlation to distance
    distance = 1 - abs(feature_corr)
    
    # Hierarchical clustering
    condensed_dist = squareform(distance, checks=False)
    linkage_matrix = linkage(condensed_dist, method='average')
    
    # Form clusters
    cluster_labels = fcluster(linkage_matrix, t=1-threshold, criterion='distance')
    
    # Group features by cluster
    clusters = {}
    for idx, label in enumerate(cluster_labels):
        cluster_id = f"Cluster_{label}"
        if cluster_id not in clusters:
            clusters[cluster_id] = []
        clusters[cluster_id].append(feature_corr.index[idx])
    
    return clusters


def print_redundancy_report(
    redundancy_info: Dict,
    verbose: bool = True
) -> None:
    """
    Print formatted report of redundant features.
    
    Args:
        redundancy_info: Output from identify_redundant_features()
        verbose: Whether to print detailed pair information
    """
    print("=" * 80)
    print("FEATURE REDUNDANCY ANALYSIS")
    print("=" * 80)
    
    to_drop = redundancy_info['to_drop']
    pairs = redundancy_info['pairs']
    
    if not pairs:
        print("\n✓ No redundant features detected")
        print("  All features are sufficiently independent")
        return
    
    print(f"\n⚠ Found {len(pairs)} redundant pair(s)")
    print(f"→ Recommending to drop {len(to_drop)} feature(s): {', '.join(to_drop)}\n")
    
    if verbose and pairs:
        print("-" * 80)
        print("REDUNDANT PAIRS DETAIL:")
        print("-" * 80)
        
        for i, pair in enumerate(pairs, 1):
            print(f"\nPair {i}:")
            print(f"  {pair['feature_1']} (IC={pair['ic_1']:>7.4f}) ↔ "
                  f"{pair['feature_2']} (IC={pair['ic_2']:>7.4f})")
            print(f"  Correlation: {pair['correlation']:>6.3f}")
            print(f"  → DROP: {pair['drop']} (weaker IC)")
            print(f"  → KEEP: {pair['keep']} (stronger IC)")
    
    print("\n" + "=" * 80)


def create_feature_summary_table(
    ic_scores: Dict[str, float],
    feature_corr: pd.DataFrame,
    redundancy_info: Dict
) -> pd.DataFrame:
    """
    Create summary table with IC, max correlation, and status.
    
    Args:
        ic_scores: Feature IC values
        feature_corr: Feature correlation matrix
        redundancy_info: Redundancy analysis results
    
    Returns:
        DataFrame with feature summary
    """
    to_drop = set(redundancy_info['to_drop'])
    
    summary = []
    for feat in feature_corr.index:
        # Find max correlation with other features
        corr_values = feature_corr.loc[feat].drop(feat)
        max_corr = corr_values.abs().max()
        max_corr_with = corr_values.abs().idxmax()
        
        summary.append({
            'Feature': feat,
            'IC': ic_scores.get(feat, 0),
            'IC_abs': abs(ic_scores.get(feat, 0)),
            'Max_Corr': max_corr,
            'Max_Corr_With': max_corr_with,
            'Status': 'DROP' if feat in to_drop else 'KEEP'
        })
    
    df = pd.DataFrame(summary)
    df = df.sort_values('IC_abs', ascending=False)
    df = df.drop('IC_abs', axis=1)
    
    return df
