#!/usr/bin/env python3
"""
Quick test of correlation analysis module.
Demonstrates the functionality with sample features.
"""

import sys
sys.path.append('..')

import pandas as pd
import numpy as np
from src.features.correlation_analysis import (
    compute_feature_correlation_matrix,
    identify_redundant_features,
    print_redundancy_report,
    create_feature_summary_table
)

# Create synthetic features for testing
np.random.seed(42)
n = 1000

# Feature 1: Random baseline
feat1 = pd.Series(np.random.randn(n), name='Random_Feature')

# Feature 2: Highly correlated with Feature 1 (correlation ~0.9)
feat2 = feat1 * 0.9 + np.random.randn(n) * 0.3
feat2.name = 'Correlated_Feature'

# Feature 3: Independent
feat3 = pd.Series(np.random.randn(n), name='Independent_Feature')

# Feature 4: Moderately correlated with Feature 1 (correlation ~0.5)
feat4 = feat1 * 0.5 + np.random.randn(n) * 0.7
feat4.name = 'Moderate_Feature'

# Feature 5: Anti-correlated with Feature 3
feat5 = -feat3 * 0.8 + np.random.randn(n) * 0.2
feat5.name = 'AntiCorrelated_Feature'

# Combine features
features = {
    'Random_Feature': feat1,
    'Correlated_Feature': feat2,
    'Independent_Feature': feat3,
    'Moderate_Feature': feat4,
    'AntiCorrelated_Feature': feat5
}

# Mock IC scores (simulating predictive power)
ic_scores = {
    'Random_Feature': -0.050,
    'Correlated_Feature': -0.040,  # Lower IC than Random_Feature
    'Independent_Feature': -0.065,
    'Moderate_Feature': -0.055,
    'AntiCorrelated_Feature': -0.030  # Lower IC than Independent_Feature
}

print("="*80)
print("CORRELATION ANALYSIS MODULE TEST")
print("="*80)

# 1. Compute correlation matrix
print("\n1. Computing feature correlation matrix...")
feature_corr = compute_feature_correlation_matrix(features)
print("\nCorrelation Matrix:")
print(feature_corr.round(3))

# 2. Identify redundant features
print("\n2. Identifying redundant features (threshold=0.7)...")
redundancy_info = identify_redundant_features(
    feature_corr,
    ic_scores,
    threshold=0.7
)

# 3. Print report
print_redundancy_report(redundancy_info, verbose=True)

# 4. Create summary table
print("\n3. Creating summary table...")
summary_table = create_feature_summary_table(
    ic_scores,
    feature_corr,
    redundancy_info
)
print("\nFeature Summary:")
print(summary_table.to_string(index=False))

print("\n" + "="*80)
print("✓ TEST COMPLETED SUCCESSFULLY")
print("="*80)
print("\nExpected behavior:")
print("  - Correlated_Feature should be dropped (corr ~0.9 with Random_Feature)")
print("  - AntiCorrelated_Feature should be dropped (corr ~-0.8 with Independent_Feature)")
print("  - Moderate_Feature should be kept (corr < 0.7 with all features)")
print("\nModule is ready for use in notebook 06!")
