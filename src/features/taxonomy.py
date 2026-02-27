"""
Feature generation taxonomy for FX markets.
Each feature must include:
- Hypothesis (why it might predict returns)
- Stationarity check
- Lookback period justification
"""

from enum import Enum
from dataclasses import dataclass
from typing import Callable


class FeatureCategory(Enum):
    TREND = "trend"
    MEAN_REVERSION = "mean_reversion"
    VOLATILITY = "volatility"
    MICROSTRUCTURE = "microstructure"
    CALENDAR = "calendar"
    CROSS_ASSET = "cross_asset"


@dataclass
class FeatureSpec:
    """Standardized feature specification."""
    name: str
    category: FeatureCategory
    hypothesis: str  # Why this might predict returns
    computation: Callable
    lookback_period: int
    expected_stationarity: bool
    expected_correlation_sign: str  # 'positive', 'negative', 'none'
    
    def validate(self):
        """Ensure spec is complete."""
        assert self.hypothesis, "Must have hypothesis"
        assert self.lookback_period > 0, "Invalid lookback"
        assert self.expected_correlation_sign in ['positive', 'negative', 'none'], \
            "Correlation sign must be 'positive', 'negative', or 'none'"
        assert callable(self.computation), "Computation must be callable"
