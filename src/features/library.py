"""
Standardized feature library for quantitative trading.

This module provides a unified interface to generate technical and statistical
features suitable for signal generation and machine learning models.

All features are designed to work with daily/weekly price data.
"""

import numpy as np
import pandas as pd
from typing import Optional, Dict, List
from .returns import compute_log_returns, compute_rolling_volatility, compute_zscore


class FeatureLibrary:
    """
    Standardized feature generation for trading signals.
    
    Features are organized into categories:
    - Momentum: Return-based features
    - Volatility: Dispersion-based features
    - Mean-reversion: Z-score and RSI-based
    - Trend: Moving average based
    
    Design principles:
    1. All features return NaN for insufficient data (no look-ahead bias)
    2. Features are normalized where applicable (Z-score, RSI bounded [0,100])
    3. Default parameters tuned for daily data and medium-term trading
    """
    
    def __init__(self, prices: pd.Series):
        """
        Initialize feature library with price series.
        
        Args:
            prices: Series of prices indexed by datetime
        """
        if prices.empty:
            raise ValueError("prices cannot be empty")
        if not isinstance(prices.index, pd.DatetimeIndex):
            raise ValueError("prices must have DatetimeIndex")
        
        self.prices = prices
        self.returns = compute_log_returns(prices, dropna=False)
    
    # ========== MOMENTUM FEATURES ==========
    
    def momentum(self, period: int = 20) -> pd.Series:
        """
        Return over a period: r_t(period) = ln(P_t / P_{t-period}).
        
        Interpretation:
        - Positive: asset appreciated over the period
        - Magnitude indicates strength of move
        - Common periods: 20 (1 month), 60 (3 months), 252 (1 year)
        
        Args:
            period: Look-back period in days
        
        Returns:
            Series of momentum values
        
        Note:
            First 'period' values will be NaN.
        """
        return np.log(self.prices / self.prices.shift(period))
    
    def momentum_zscore(self, period: int = 20, window: int = 60) -> pd.Series:
        """
        Z-score of momentum relative to its rolling mean.
        
        Useful for identifying momentum extremes (potential reversals).
        
        Args:
            period: Momentum look-back period
            window: Rolling window for Z-score calculation
        
        Returns:
            Series of Z-scores
        
        Example:
            If momentum_zscore = 2.0, the current momentum is 2 std devs
            above its recent average (potentially over-extended).
        """
        mom = self.momentum(period)
        return compute_zscore(mom, window=window)
    
    # ========== VOLATILITY FEATURES ==========
    
    def volatility(self, window: int = 20) -> pd.Series:
        """
        Rolling volatility (standard deviation of returns).
        
        Interpretation:
        - Measures dispersion of recent returns
        - High vol: market uncertainty, large recent swings
        - Low vol: stable price action, mean-reversion regime
        
        Common use:
        - Risk normalization (divide signals by volatility)
        - Regime identification
        - Position sizing (position_size ∝ 1/volatility)
        
        Args:
            window: Rolling window in days (default 20 ~1 month)
        
        Returns:
            Series of volatility values
        """
        return compute_rolling_volatility(self.returns, window=window)
    
    def volatility_regime(self, window: int = 20, threshold_percentile: float = 50) -> pd.Series:
        """
        Classify volatility as high/low based on rolling percentile.
        
        Args:
            window: Rolling window
            threshold_percentile: Percentile of historical volatility (0-100)
        
        Returns:
            Series of 1 (high vol) / 0 (low vol) / NaN
        """
        vol = self.volatility(window)
        threshold = vol.rolling(window=window * 2).quantile(threshold_percentile / 100)
        return (vol > threshold).astype(float)
    
    # ========== MEAN-REVERSION FEATURES ==========
    
    def zscore(self, window: int = 20) -> pd.Series:
        """
        Z-score of returns relative to rolling mean.
        
        Interpretation:
        - Z > 1.5: Unusually high return (potential reversal signal)
        - Z < -1.5: Unusually low return (potential recovery signal)
        - Useful for mean-reversion strategies
        
        Args:
            window: Rolling window in days
        
        Returns:
            Series of Z-scores
        """
        return compute_zscore(self.returns, window=window)
    
    def rsi(self, period: int = 14, use_sma: bool = False) -> pd.Series:
        """
        Relative Strength Index (RSI): measures momentum via up/down moves.
        
        Formula:
            RS = avg_gain / avg_loss (over period)
            RSI = 100 - (100 / (1 + RS))
        
        Interpretation:
        - RSI > 70: Overbought (potential sell signal in mean-reversion)
        - RSI < 30: Oversold (potential buy signal)
        - RSI = 50: Neutral
        - Useful for identifying extremes in price action
        
        Args:
            period: Look-back period (default 14, standard in technical analysis)
            use_sma: If False (default), use EMA smoothing (Wilder's method)
                     If True, use simple moving average
        
        Returns:
            Series of RSI values (0-100)
        
        Note:
            Traditional RSI uses Wilder's smoothing (EMA with alpha=1/period).
            First (period * 2) values will be NaN due to initialization.
        """
        # Compute gains and losses
        delta = self.prices.diff()
        gains = delta.clip(lower=0)
        losses = -delta.clip(upper=0)
        
        if use_sma:
            # Simple moving average
            avg_gain = gains.rolling(window=period).mean()
            avg_loss = losses.rolling(window=period).mean()
        else:
            # Wilder's smoothing (EMA with alpha = 1/period)
            alpha = 1 / period
            avg_gain = gains.ewm(alpha=alpha, adjust=False).mean()
            avg_loss = losses.ewm(alpha=alpha, adjust=False).mean()
        
        # Avoid division by zero
        rs = np.where(avg_loss != 0, avg_gain / avg_loss, np.nan)
        rsi = 100 - (100 / (1 + rs))
        
        return pd.Series(rsi, index=self.prices.index)
    
    # ========== TREND FEATURES ==========
    
    def moving_average_ratio(self, short_window: int = 20, long_window: int = 60) -> pd.Series:
        """
        Ratio of short-term to long-term moving average.
        
        Interpretation:
        - Ratio > 1: Price above long-term average (uptrend)
        - Ratio < 1: Price below long-term average (downtrend)
        - Closer to 1: Convergence (less pronounced trend)
        
        Args:
            short_window: Short-term MA period
            long_window: Long-term MA period
        
        Returns:
            Series of ratios
        """
        sma_short = self.prices.rolling(window=short_window).mean()
        sma_long = self.prices.rolling(window=long_window).mean()
        
        return sma_short / sma_long
    
    def trend_strength(self, window: int = 20) -> pd.Series:
        """
        Trend strength: ratio of return to volatility.
        
        Interpretation:
        - High value: Strong directional move relative to noise
        - Low value: Choppy price action
        - Useful for filter: only trade when trend_strength > threshold
        
        Args:
            window: Rolling window
        
        Returns:
            Series of trend strength values
        """
        ret = self.momentum(period=window)
        vol = self.volatility(window=window)
        
        return ret / vol
    
    def ema(self, window: int = 20) -> pd.Series:
        """
        Exponential moving average.
        
        Places more weight on recent prices than SMA.
        
        Args:
            window: EMA period
        
        Returns:
            Series of EMA values
        """
        return self.prices.ewm(span=window, adjust=False).mean()
    
    # ========== VOLATILITY CLUSTERING ==========
    
    def garman_klass_volatility(self, window: int = 20) -> pd.Series:
        """
        Garman-Klass volatility estimator (uses high/low prices).
        
        More efficient volatility estimate when intraday OHLC data available.
        For daily close data only, falls back to close-based calculation.
        
        Args:
            window: Rolling window
        
        Returns:
            Series of volatility estimates
        
        Note:
            Requires OHLC data as DataFrame with 'High', 'Low', 'Open', 'Close' columns.
            Currently implemented for close-only; extend if you have OHLC data.
        """
        # Simplified version for close-only data
        # Full GK formula: 0.5*ln(H/L)^2 - (2*ln2-1)*ln(C/O)^2
        return self.volatility(window=window)
    
    def parkinson_volatility(self, high: Optional[pd.Series] = None,
                            low: Optional[pd.Series] = None,
                            window: int = 20) -> pd.Series:
        """
        Parkinson volatility (requires high/low prices).
        
        More efficient than close-only estimates; useful if you have OHLC data.
        
        Args:
            high: Series of high prices
            low: Series of low prices
            window: Rolling window
        
        Returns:
            Series of volatility estimates
        
        Note:
            If high/low not provided, falls back to close-only volatility.
        """
        if high is None or low is None:
            return self.volatility(window=window)
        
        # Parkinson: sqrt( ln(H/L)^2 / (4*ln2) )
        hl_range = np.log(high / low)
        parkinson_vol = np.sqrt((hl_range ** 2) / (4 * np.log(2)))
        
        return parkinson_vol.rolling(window=window).mean()
    
    # ========== BATCH FEATURE GENERATION ==========
    
    def generate_all_features(self, window: int = 20, period: int = 20) -> pd.DataFrame:
        """
        Generate comprehensive feature set at once.
        
        Returns:
            DataFrame with all features as columns
        
        Common usage for machine learning pipelines.
        """
        features = pd.DataFrame(index=self.prices.index)
        
        # Momentum features
        features['momentum_20d'] = self.momentum(period=20)
        features['momentum_60d'] = self.momentum(period=60)
        features['momentum_zscore'] = self.momentum_zscore(period=20, window=60)
        
        # Volatility features
        features['volatility'] = self.volatility(window=window)
        features['vol_regime'] = self.volatility_regime(window=window)
        
        # Mean reversion features
        features['zscore'] = self.zscore(window=window)
        features['rsi_14'] = self.rsi(period=14)
        
        # Trend features
        features['ma_ratio'] = self.moving_average_ratio(short_window=20, long_window=60)
        features['trend_strength'] = self.trend_strength(window=window)
        features['ema_20'] = self.ema(window=20)
        
        return features
    
    def feature_report(self) -> Dict[str, pd.Series]:
        """
        Generate all features and return as dictionary for analysis.
        
        Returns:
            Dictionary mapping feature name to Series
        """
        features_df = self.generate_all_features()
        return {col: features_df[col] for col in features_df.columns}
