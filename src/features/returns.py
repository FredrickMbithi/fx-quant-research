"""
Return calculations and transformations.

This module provides fundamental return calculations for time-series analysis.
Key insight: Log returns are additive (suitable for portfolios, time-aggregation)
while arithmetic returns are not.
"""

import numpy as np
import pandas as pd
from typing import Tuple, Optional


def compute_log_returns(
    prices: pd.Series,
    dropna: bool = True
) -> pd.Series:
    """
    Compute log returns: r_t = ln(P_t / P_{t-1}).
    
    Log returns are preferred for time-series modeling because:
    - They are additive: r_total = r1 + r2 + ... (vs multiplicative for arithmetic)
    - They handle compounding naturally
    - They are approximately equal to arithmetic returns for small moves
    
    Args:
        prices: Series of prices (index should be datetime, values prices)
        dropna: Whether to drop NaN values (first row will always be NaN)
    
    Returns:
        Series of log returns, aligned with original prices index (or dropna'd)
    
    Example:
        >>> prices = pd.Series([100, 102, 101], index=pd.date_range('2024-01-01', periods=3))
        >>> returns = compute_log_returns(prices)
        >>> print(returns)  # [NaN, 0.0198, -0.0099]
    """
    if prices.empty or len(prices) < 2:
        raise ValueError("prices must contain at least 2 observations")
    
    # Log returns: ln(P_t / P_{t-1})
    log_returns = np.log(prices / prices.shift(1))
    
    return log_returns.dropna() if dropna else log_returns


def compute_rolling_volatility(
    returns: pd.Series,
    window: int = 20,
    min_periods: Optional[int] = None
) -> pd.Series:
    """
    Compute rolling volatility (standard deviation of returns).
    
    Volatility measures dispersion of returns and is essential for:
    - Risk normalization (Z-score computation)
    - Portfolio risk estimation
    - Signal sizing (position weights inversely proportional to volatility)
    
    Args:
        returns: Series of returns (typically log returns)
        window: Rolling window size (default 20 trading days ~1 month)
        min_periods: Minimum observations to compute volatility.
                    Defaults to window if None.
    
    Returns:
        Series of rolling volatility, same length as input
    
    Note:
        First (window - 1) values will be NaN if min_periods is not specified.
        Using min_periods < window gives earlier estimates but with higher bias.
    """
    if window < 2:
        raise ValueError("window must be >= 2")
    
    min_periods = min_periods or window
    return returns.rolling(window=window, min_periods=min_periods).std()


def compute_zscore(
    returns: pd.Series,
    window: int = 20,
    min_periods: Optional[int] = None
) -> pd.Series:
    """
    Compute rolling Z-score: (r_t - μ) / σ.
    
    Z-score interpretation:
    - Measures how many standard deviations the return is from the rolling mean
    - Z = 0: return equals rolling mean
    - Z = 2: return is 2 std devs above mean (extreme move in recent history)
    - Z = -2: return is 2 std devs below mean
    - Useful for mean-reversion strategies
    
    Args:
        returns: Series of returns
        window: Rolling window size
        min_periods: Minimum observations for valid calculation
    
    Returns:
        Series of Z-scores, same length as input
    
    Note:
        Z-scores will be NaN for the first (window - 1) observations.
        This is expected due to the lookback period requirement.
    
    Example:
        >>> returns = pd.Series([0.01, 0.02, -0.01, 0.015, 0.03])
        >>> z = compute_zscore(returns, window=3)
        # After first 2 NaN values, computes (r - mean_3) / std_3
    """
    if window < 2:
        raise ValueError("window must be >= 2")
    
    min_periods = min_periods or window
    
    mu = returns.rolling(window=window, min_periods=min_periods).mean()
    sigma = returns.rolling(window=window, min_periods=min_periods).std()
    
    # Avoid division by zero
    zscore = np.where(sigma != 0, (returns - mu) / sigma, np.nan)
    
    return pd.Series(zscore, index=returns.index)


def compute_arithmetic_returns(
    prices: pd.Series,
    dropna: bool = True
) -> pd.Series:
    """
    Compute arithmetic returns: r_t = (P_t - P_{t-1}) / P_{t-1}.
    
    Arithmetic returns represent simple percentage changes but are NOT additive
    over time. Useful for interpretation but less suitable for modeling.
    
    Args:
        prices: Series of prices
        dropna: Whether to drop NaN values
    
    Returns:
        Series of arithmetic returns
    
    Note:
        For small returns, arithmetic ≈ log returns: (P_t - P_{t-1}) / P_{t-1} ≈ ln(P_t / P_{t-1})
        This approximation breaks down for large moves (>5%).
    """
    if prices.empty or len(prices) < 2:
        raise ValueError("prices must contain at least 2 observations")
    
    arithmetic_returns = prices.pct_change()
    return arithmetic_returns.dropna() if dropna else arithmetic_returns


def compute_returns_comparison(
    prices: pd.Series,
    window: int = 1
) -> pd.DataFrame:
    """
    Compare log returns vs arithmetic returns over a given window.
    
    Shows how the two methods diverge, especially important for large moves.
    
    Args:
        prices: Series of prices
        window: Aggregation window (1 = single period, 5 = 5-period hold, etc)
    
    Returns:
        DataFrame with columns:
        - 'log_return': Log return over window
        - 'arithmetic_return': Arithmetic return over window
        - 'difference': Arithmetic - Log (shows where methods diverge)
    
    Example:
        >>> prices = pd.Series([100, 150, 120])
        >>> comp = compute_returns_comparison(prices, window=1)
        # Shows divergence of methods for the 50% move and -20% move
    """
    log_ret = np.log(prices / prices.shift(window))
    arith_ret = prices.pct_change(window)
    
    return pd.DataFrame({
        'log_return': log_ret,
        'arithmetic_return': arith_ret,
        'difference': arith_ret - log_ret
    })


def annualize_volatility(
    daily_volatility: float,
    periods_per_year: int = 252
) -> float:
    """
    Annualize daily/weekly volatility.
    
    Used for risk reporting and Sharpe ratio calculations.
    Assumes independent returns (weak assumption in practice).
    
    Args:
        daily_volatility: Volatility computed from daily returns
        periods_per_year: Trading periods per year (252 for daily, 52 for weekly)
    
    Returns:
        Annualized volatility
    
    Example:
        >>> daily_vol = 0.015  # 1.5% daily vol
        >>> annual_vol = annualize_volatility(daily_vol)
        >>> print(f"{annual_vol:.2%}")  # ~23.8% annualized
    """
    return daily_volatility * np.sqrt(periods_per_year)


def compute_return_quantiles(
    returns: pd.Series,
    window: int = 20,
    quantiles: Tuple[float, ...] = (0.05, 0.25, 0.5, 0.75, 0.95)
) -> pd.DataFrame:
    """
    Compute rolling quantiles of returns.
    
    Useful for understanding the distribution of returns over time
    and identifying regimes (e.g., high volatility periods).
    
    Args:
        returns: Series of returns
        window: Rolling window size
        quantiles: Tuple of quantiles to compute (0.0 to 1.0)
    
    Returns:
        DataFrame with one column per quantile
    """
    quantile_results = {}
    for q in quantiles:
        quantile_results[f'q_{q:.2f}'] = (
            returns.rolling(window=window)
            .quantile(q)
        )
    
    return pd.DataFrame(quantile_results)
