"""
Pure feature generation functions.
No prediction, no trading logic — just transformations.
"""

import numpy as np
import pandas as pd


def ma_spread(prices: pd.Series, fast: int, slow: int) -> pd.Series:
    """
    Moving average spread (fast - slow) / slow.
    
    Hypothesis: Positive spread indicates uptrend (momentum).
    Category: TREND
    """
    ma_fast = prices.rolling(fast).mean()
    ma_slow = prices.rolling(slow).mean()
    return (ma_fast - ma_slow) / ma_slow


def distance_from_ma(prices: pd.Series, period: int) -> pd.Series:
    """
    (Price - MA) / MA.
    
    Hypothesis: Large distance indicates overextension (mean reversion).
    Category: MEAN_REVERSION
    """
    ma = prices.rolling(period).mean()
    return (prices - ma) / ma


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
    """
    Average True Range (volatility measure).
    
    Hypothesis: Vol expansion precedes trend continuation.
    Category: VOLATILITY
    """
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """
    Relative Strength Index.
    
    Hypothesis: RSI < 30 indicates oversold (mean reversion).
    Category: MEAN_REVERSION
    """
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def return_vol_ratio(returns: pd.Series, vol_window: int) -> pd.Series:
    """
    Recent return / recent volatility (risk-adjusted momentum).
    
    Hypothesis: High ratio indicates strong trend with low noise.
    Category: TREND
    """
    vol = returns.rolling(vol_window).std()
    return returns.rolling(vol_window).mean() / vol


def close_position_in_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """
    (Close - Low) / (High - Low).
    
    Hypothesis: Close near high indicates buying pressure.
    Category: MICROSTRUCTURE
    """
    return (close - low) / (high - low + 1e-8)


def rate_of_change(prices: pd.Series, period: int) -> pd.Series:
    """
    Rate of change over period: (Price_t - Price_{t-period}) / Price_{t-period}.
    
    Hypothesis: Recent momentum persists in trending markets.
    Category: TREND
    """
    return prices.pct_change(periods=period)


def zscore_returns(returns: pd.Series, window: int) -> pd.Series:
    """
    Z-score of returns over rolling window.
    
    Hypothesis: Extreme z-scores indicate temporary overextension (mean reversion).
    Category: MEAN_REVERSION
    """
    mean = returns.rolling(window).mean()
    std = returns.rolling(window).std()
    return (returns - mean) / (std + 1e-8)


def parkinson_volatility(high: pd.Series, low: pd.Series, window: int) -> pd.Series:
    """
    Parkinson volatility estimator: sqrt(1/(4*ln(2)) * mean((ln(H/L))^2)).
    
    Hypothesis: More efficient volatility estimate than close-to-close.
    Category: VOLATILITY
    """
    hl_ratio = np.log(high / low)
    return np.sqrt((1 / (4 * np.log(2))) * (hl_ratio ** 2).rolling(window).mean())


def breakout_indicator(prices: pd.Series, lookback: int) -> pd.Series:
    """
    Binary indicator: 1 if price > max of last N bars, -1 if < min, 0 otherwise.
    
    Hypothesis: Breakouts indicate new trend formation.
    Category: TREND
    """
    rolling_max = prices.shift(1).rolling(lookback).max()
    rolling_min = prices.shift(1).rolling(lookback).min()
    
    result = pd.Series(0, index=prices.index, dtype=float)
    result[prices > rolling_max] = 1
    result[prices < rolling_min] = -1
    return result
