"""
MA Deviation Mean Reversion Strategy with Slope Filter
Event-driven implementation for live/paper trading on Pepperstone via FIX API

VALIDATED PARAMETERS (Walk-Forward OOS on GBP/USD H1, 2015-2026):
  Config:        MA200, Z-score > 1.5, Slope(50) < 0.5, 20h exit
  Total trades:  3,806 (10.86 years) → ~350/year, ~0.96/day
  NET pips:      +28,233 (Retail_wide 2.5 pip costs)
  Profit factor: 1.35
  Recovery:      4.77
  OOS PF:        1.95
  OOS WR:        59.3%
  OOS MaxDD:     -2,111 pips

STRATEGY LOGIC:
  1. Compute 200-period SMA + rolling std on H1 close prices
  2. Z-score = (close - SMA200) / rolling_std(200)
  3. MA slope filter: |slope_z| < 0.5 (avoid trending markets)
     - slope = (SMA200[now] - SMA200[50 bars ago]) / 50
     - slope_z = |slope| / rolling_std(|slope|, 500)
  4. LONG when z < -1.5 and slope filter passes
  5. SHORT when z > +1.5 and slope filter passes
  6. Exit after 20 bars (20 hours)
"""

import numpy as np
import pandas as pd
from typing import Optional, Dict, Any
import logging
from datetime import datetime, timedelta

from src.strategies.base_strategy import BaseStrategy

logger = logging.getLogger(__name__)


class MADeviationStrategy(BaseStrategy):
    """
    H1 GBP/USD MA Deviation Mean Reversion Strategy with Slope Filter.

    Trades mean reversion when price deviates significantly from the 200-period
    SMA, but ONLY when the MA slope is flat (non-trending market).

    Walk-forward validated: OOS PF=1.95, WR=59.3% at 2.5 pip costs.
    """

    def __init__(
        self,
        name: str = "MADeviation_SlopeFilter",
        symbols: list = None,
        config: Dict[str, Any] = None
    ):
        """
        Initialize MA Deviation strategy.

        Args:
            name: Strategy name
            symbols: List of symbols to trade (default: ['GBPUSD'])
            config: Strategy configuration parameters
        """
        if symbols is None:
            symbols = ['GBPUSD']

        # Default configuration - validated parameters
        default_config = {
            'max_bars': 600,  # Need 200 for MA + 500 for slope std
            'ma_length': 200,
            'z_threshold': 1.5,
            'exit_horizon_bars': 20,
            'slope_lookback': 50,
            'slope_z_threshold': 0.5,
            'slope_std_window': 500,
            'trade_both_directions': True,
        }

        # Merge with user config
        if config:
            default_config.update(config)

        super().__init__(name, symbols, default_config)

        # Track open trade exit times {symbol: exit_timestamp}
        self.pending_exits = {symbol: [] for symbol in symbols}

        # Pre-computed indicator cache
        self._indicator_cache = {symbol: {} for symbol in symbols}

        logger.info(f"MA Deviation Strategy initialized")
        logger.info(f"  MA Length:       {self.config['ma_length']}")
        logger.info(f"  Z Threshold:     {self.config['z_threshold']}")
        logger.info(f"  Exit Horizon:    {self.config['exit_horizon_bars']}h")
        logger.info(f"  Slope Lookback:  {self.config['slope_lookback']}")
        logger.info(f"  Slope Z Thresh:  {self.config['slope_z_threshold']}")

    def calculate_signal(self, symbol: str) -> Optional[float]:
        """
        Calculate trading signal based on MA deviation + slope filter.

        Returns:
            +1.0 for LONG (price far below MA in non-trending market)
            -1.0 for SHORT (price far above MA in non-trending market)
            None for no signal
        """
        history = self.bar_history[symbol]
        closes = history['close']
        ma_len = self.config['ma_length']
        slope_lb = self.config['slope_lookback']
        slope_std_win = self.config['slope_std_window']

        # Need enough bars for MA + slope std calculation
        min_bars = ma_len + slope_std_win + slope_lb
        if len(closes) < min_bars:
            logger.debug(
                f"{symbol}: Need {min_bars} bars, have {len(closes)}"
            )
            return None

        # ---- Compute indicators ----
        close_arr = np.array(closes)
        n = len(close_arr)

        # 1. SMA and Z-score
        ma = np.mean(close_arr[-ma_len:])
        std = np.std(close_arr[-ma_len:], ddof=1)

        if std < 1e-10:
            return None

        current_close = close_arr[-1]
        z_score = (current_close - ma) / std

        # 2. Slope filter
        # MA at current bar
        ma_now = ma
        # MA at slope_lookback bars ago
        ma_prev_slice = close_arr[-(ma_len + slope_lb):-slope_lb]
        ma_prev = np.mean(ma_prev_slice)

        slope = (ma_now - ma_prev) / slope_lb
        abs_slope = abs(slope)

        # Compute rolling std of |slope| over slope_std_window
        # We need slope values for the last slope_std_window bars
        slope_values = []
        for i in range(slope_std_win):
            offset = slope_std_win - 1 - i
            end_idx = n - offset
            start_idx = end_idx - ma_len

            if start_idx < 0 or (end_idx - slope_lb - ma_len) < 0:
                continue

            ma_i = np.mean(close_arr[start_idx:end_idx])
            ma_i_prev = np.mean(
                close_arr[start_idx - slope_lb:end_idx - slope_lb]
            )
            s = (ma_i - ma_i_prev) / slope_lb
            slope_values.append(abs(s))

        if len(slope_values) < 50:
            return None

        slope_std = np.std(slope_values)
        if slope_std < 1e-15:
            return None

        slope_z = abs_slope / slope_std

        # ---- Apply filters and generate signal ----
        slope_passes = slope_z < self.config['slope_z_threshold']

        if not slope_passes:
            logger.debug(
                f"{symbol}: Slope filter blocked signal "
                f"(slope_z={slope_z:.2f} > {self.config['slope_z_threshold']})"
            )
            return None

        z_thresh = self.config['z_threshold']

        # LONG: price significantly below MA (oversold)
        if z_score < -z_thresh:
            logger.info(
                f"LONG signal: {symbol} z={z_score:+.2f} "
                f"(slope_z={slope_z:.2f}) close={current_close:.5f} "
                f"MA{self.config['ma_length']}={ma:.5f}"
            )
            return 1.0

        # SHORT: price significantly above MA (overbought)
        if z_score > z_thresh and self.config['trade_both_directions']:
            logger.info(
                f"SHORT signal: {symbol} z={z_score:+.2f} "
                f"(slope_z={slope_z:.2f}) close={current_close:.5f} "
                f"MA{self.config['ma_length']}={ma:.5f}"
            )
            return -1.0

        return None

    def should_exit(self, symbol: str, bars_held: int) -> bool:
        """
        Check if a position should be exited based on time.

        Args:
            symbol: Currency pair
            bars_held: Number of bars the position has been held

        Returns:
            True if position should be closed
        """
        return bars_held >= self.config['exit_horizon_bars']

    def _get_signal_metadata(self, symbol: str) -> Dict[str, Any]:
        """
        Get metadata for signal logging.

        Returns:
            dict with indicator values
        """
        metadata = super()._get_signal_metadata(symbol)

        closes = self.bar_history[symbol]['close']
        if len(closes) >= self.config['ma_length']:
            close_arr = np.array(closes)
            ma = np.mean(close_arr[-self.config['ma_length']:])
            std = np.std(close_arr[-self.config['ma_length']:], ddof=1)
            z = (close_arr[-1] - ma) / (std + 1e-10)

            metadata.update({
                'ma_value': round(ma, 5),
                'std_value': round(std, 5),
                'z_score': round(z, 3),
                'current_close': round(close_arr[-1], 5),
            })

        return metadata

    def get_strategy_info(self) -> Dict[str, Any]:
        """Return strategy configuration for logging."""
        return {
            'name': self.name,
            'type': 'MA_Deviation_MeanReversion',
            'ma_length': self.config['ma_length'],
            'z_threshold': self.config['z_threshold'],
            'exit_horizon': self.config['exit_horizon_bars'],
            'slope_lookback': self.config['slope_lookback'],
            'slope_z_threshold': self.config['slope_z_threshold'],
            'directions': 'BOTH' if self.config['trade_both_directions'] else 'LONG_ONLY',
            'backtest_results': {
                'total_trades': 3806,
                'net_pips': 28233,
                'profit_factor': 1.35,
                'oos_profit_factor': 1.95,
                'oos_win_rate': 0.593,
                'oos_max_drawdown_pips': -2111,
                'recovery_factor': 4.77,
                'cost_assumption_pips': 2.5,
            }
        }


if __name__ == "__main__":
    # Self-test
    from src.events.market_event import BarEvent

    print("=" * 60)
    print("TESTING MA DEVIATION STRATEGY (Event-Driven Mode)")
    print("=" * 60)

    strategy = MADeviationStrategy(symbols=['GBPUSD'])
    info = strategy.get_strategy_info()
    print(f"\nStrategy: {info['name']}")
    print(f"Type:     {info['type']}")
    print(f"Config:   MA{info['ma_length']} Z>{info['z_threshold']} "
          f"Exit={info['exit_horizon']}h Slope<{info['slope_z_threshold']}")
    print(f"\nBacktest: {info['backtest_results']['total_trades']} trades, "
          f"+{info['backtest_results']['net_pips']} pips")
    print(f"OOS PF:   {info['backtest_results']['oos_profit_factor']}")
    print(f"Needs {strategy.config['max_bars']} bars of history before first signal")
    print("\nStrategy test complete.")
