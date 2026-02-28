"""
Strategy Framework for Live Trading

Event-driven strategy execution for real-time trading.
"""

from .base_strategy import BaseStrategy
from .strategies import ThresholdStrategy, MomentumStrategy
from .ma_deviation_strategy import MADeviationStrategy

__all__ = [
    'BaseStrategy',
    'ThresholdStrategy',
    'MomentumStrategy',
    'MADeviationStrategy',
]
