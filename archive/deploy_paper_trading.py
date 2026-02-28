"""
Paper Trading Deployment - MA Deviation + Slope Filter Strategy
Walk-Forward Validated on GBP/USD H1 (2015-2026)

VALIDATED PARAMETERS (Part 25E):
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
  3. Slope filter: skip trades when MA slope is too steep (trending)
  4. LONG when z < -1.5 and slope filter passes
  5. SHORT when z > +1.5 and slope filter passes
  6. Exit after 20 bars (20 hours)
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import time
import json
import logging
from typing import Optional, Dict, List

# Import project modules
from src.strategies.ma_deviation_strategy import MADeviationStrategy
from src.data.h1_loader import H1DataLoader, load_processed_data

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/paper_trading.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class PaperTradingEngine:
    """Paper trading engine for MA deviation mean reversion strategy"""

    def __init__(self, config_path: str = 'config/paper_trading_config.json'):
        """Initialize paper trading engine"""
        self.config = self.load_config(config_path)
        self.positions = []
        self.closed_trades = []
        self.account_balance = self.config['initial_capital']
        self.starting_capital = self.config['initial_capital']

        # Initialize strategy with validated parameters
        strategy_params = self.config.get('strategy_params', {})
        self.strategy = MADeviationStrategy(
            name=self.config.get('strategy_name', 'MADeviation_SlopeFilter'),
            symbols=['GBPUSD'],
            config=strategy_params,
        )

        # Load historical data for lookback
        self.data_loader = H1DataLoader()
        self.price_data = None

        logger.info("Paper Trading Engine Initialized")
        logger.info(f"Initial Capital: ${self.account_balance:,.2f}")
        logger.info(f"Strategy: {self.config['strategy_name']}")
        logger.info(f"  MA Length:       {strategy_params.get('ma_length', 200)}")
        logger.info(f"  Z Threshold:     {strategy_params.get('z_threshold', 1.5)}")
        logger.info(f"  Exit Horizon:    {strategy_params.get('exit_horizon_bars', 20)}h")
        logger.info(f"  Slope Filter:    lookback={strategy_params.get('slope_lookback', 50)}, "
                     f"z<{strategy_params.get('slope_z_threshold', 0.5)}")

    def load_config(self, config_path: str) -> dict:
        """Load configuration from JSON file"""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"Config file not found. Using defaults.")
            return self.get_default_config()

    def get_default_config(self) -> dict:
        """Return default configuration"""
        return {
            'strategy_name': 'MA_Deviation_SlopeFilter_Paper',
            'initial_capital': 100000,
            'position_sizing_method': 'fixed_fraction',
            'risk_per_trade_pct': 0.02,
            'strategy_params': {
                'ma_length': 200,
                'z_threshold': 1.5,
                'exit_horizon_bars': 20,
                'slope_lookback': 50,
                'slope_z_threshold': 0.5,
                'slope_std_window': 500,
                'trade_both_directions': True,
                'max_bars': 600,
            },
            'max_concurrent_positions': 3,
            'trading_sessions': ['ALL'],
            'pips_to_points': 10000,
            'spread_pips': 1.0,
            'slippage_pips': 1.5,
            'lookback_bars': 600,
        }
    
    def load_historical_data(self, bars: int = 600):
        """Load recent historical data for analysis"""
        try:
            # Load processed data (includes all features)
            df = load_processed_data()

            # Get most recent bars (need 600 for MA200 + slope std)
            self.price_data = df.tail(bars).copy()

            logger.info(f"Loaded {len(self.price_data)} historical bars")
            logger.info(f"Data range: {self.price_data.index[0]} to {self.price_data.index[-1]}")

        except Exception as e:
            logger.error(f"Error loading historical data: {e}")
            raise

    def detect_signal(self, current_bar: pd.Series) -> Optional[str]:
        """
        Detect trading signal on current bar using MA deviation + slope filter.

        Returns:
            'LONG' for oversold mean reversion (z < -threshold)
            'SHORT' for overbought mean reversion (z > +threshold)
            None for no signal
        """
        if self.price_data is None or len(self.price_data) < self.config['lookback_bars']:
            return None

        # Append current bar to data
        temp_data = pd.concat(
            [self.price_data, pd.DataFrame([current_bar])],
            ignore_index=False,
        )

        close_vals = temp_data['close'].values
        sp = self.config.get('strategy_params', {})
        ma_len = sp.get('ma_length', 200)
        z_thresh = sp.get('z_threshold', 1.5)
        slope_lb = sp.get('slope_lookback', 50)
        slope_z_thresh = sp.get('slope_z_threshold', 0.5)
        slope_std_win = sp.get('slope_std_window', 500)

        n = len(close_vals)
        min_bars_needed = ma_len + slope_std_win + slope_lb
        if n < min_bars_needed:
            return None

        # 1. Compute SMA and Z-score
        ma = np.mean(close_vals[-ma_len:])
        std = np.std(close_vals[-ma_len:], ddof=1)
        if std < 1e-10:
            return None

        z = (close_vals[-1] - ma) / std

        # 2. Compute slope filter
        ma_prev_slice = close_vals[-(ma_len + slope_lb):-slope_lb]
        ma_prev = np.mean(ma_prev_slice)
        slope = (ma - ma_prev) / slope_lb
        abs_slope = abs(slope)

        # Rolling std of |slope| over slope_std_window
        slope_values = []
        for i in range(slope_std_win):
            offset = slope_std_win - 1 - i
            end_idx = n - offset
            start_idx = end_idx - ma_len
            prev_start = start_idx - slope_lb
            prev_end = end_idx - slope_lb

            if prev_start < 0:
                continue

            ma_i = np.mean(close_vals[start_idx:end_idx])
            ma_i_prev = np.mean(close_vals[prev_start:prev_end])
            s = (ma_i - ma_i_prev) / slope_lb
            slope_values.append(abs(s))

        if len(slope_values) < 50:
            return None

        slope_std = np.std(slope_values)
        if slope_std < 1e-15:
            return None

        slope_z = abs_slope / slope_std

        # 3. Apply filters
        if slope_z >= slope_z_thresh:
            logger.debug(
                f"Slope filter blocked: slope_z={slope_z:.2f} >= {slope_z_thresh}"
            )
            return None

        # 4. Generate signal
        if z < -z_thresh:
            logger.info(
                f"🔔 LONG SIGNAL: z={z:+.2f}, slope_z={slope_z:.2f}, "
                f"close={close_vals[-1]:.5f}, MA{ma_len}={ma:.5f}"
            )
            return 'LONG'

        if z > z_thresh and sp.get('trade_both_directions', True):
            logger.info(
                f"🔔 SHORT SIGNAL: z={z:+.2f}, slope_z={slope_z:.2f}, "
                f"close={close_vals[-1]:.5f}, MA{ma_len}={ma:.5f}"
            )
            return 'SHORT'

        return None
    
    def calculate_position_size(self) -> float:
        """Calculate position size based on fixed fraction risk"""
        risk_amount = self.account_balance * self.config['risk_per_trade_pct']

        # Approximate stop = exit_horizon expected adverse move
        # Use 50 pips as approximate risk per trade (from backtest avg loss)
        est_risk_pips = 50
        dollars_per_pip = 10  # For 1 mini lot

        position_size = risk_amount / (est_risk_pips * dollars_per_pip)

        return max(0.01, min(position_size, 1.0))  # 0.01 to 1.0 lots

    def open_position(self, signal: str, current_bar: pd.Series):
        """Open a new position"""
        if len(self.positions) >= self.config['max_concurrent_positions']:
            logger.warning("Max positions reached. Skipping trade.")
            return

        entry_price = current_bar['close']
        entry_time = current_bar.name

        # Calculate position size
        position_size = self.calculate_position_size()

        # Time-based exit (20 bars = 20 hours)
        exit_h = self.config.get('strategy_params', {}).get('exit_horizon_bars', 20)

        position = {
            'id': len(self.closed_trades) + len(self.positions) + 1,
            'direction': signal,
            'entry_price': entry_price,
            'entry_time': entry_time,
            'position_size': position_size,
            'stop_loss': None,
            'take_profit': None,
            'exit_bar': entry_time + timedelta(hours=exit_h),
            'bars_held': 0,
            'status': 'OPEN'
        }
        
        self.positions.append(position)

        logger.info("=" * 80)
        logger.info(f"📈 NEW POSITION OPENED")
        logger.info(f"   ID: {position['id']}")
        logger.info(f"   Direction: {signal}")
        logger.info(f"   Entry: {entry_price:.5f} @ {entry_time}")
        logger.info(f"   Size: {position_size:.2f} lots")
        logger.info(f"   Exit: Time-based after {exit_h}h @ {position['exit_bar']}")
        logger.info("=" * 80)
        
        # Save to trade log
        self.log_trade(position, 'OPEN')
    
    def check_positions(self, current_bar: pd.Series):
        """Check open positions for time-based exit"""
        current_time = current_bar.name
        current_price = current_bar['close']

        positions_to_close = []

        for position in self.positions:
            position['bars_held'] += 1

            # Time-based exit (primary exit mechanism)
            if current_time >= position['exit_bar']:
                positions_to_close.append(
                    (position, 'TIME_EXIT', current_price, current_time)
                )
        
        # Close positions
        for position, reason, exit_price, exit_time in positions_to_close:
            self.close_position(position, exit_price, exit_time, reason)
    
    def close_position(self, position: dict, exit_price: float, exit_time: pd.Timestamp, reason: str):
        """Close a position and calculate PnL"""
        # Calculate PnL in pips
        if position['direction'] == 'LONG':
            pips = (exit_price - position['entry_price']) * self.config['pips_to_points']
        else:
            pips = (position['entry_price'] - exit_price) * self.config['pips_to_points']
        
        # Subtract costs
        costs = self.config['spread_pips'] + self.config['slippage_pips']
        net_pips = pips - costs
        
        # Convert to dollars (simplified)
        dollars_per_pip = 10 * position['position_size']
        pnl_dollars = net_pips * dollars_per_pip
        
        # Update account balance
        self.account_balance += pnl_dollars
        
        # Update position
        position['exit_price'] = exit_price
        position['exit_time'] = exit_time
        position['exit_reason'] = reason
        position['pips'] = pips
        position['net_pips'] = net_pips
        position['pnl_dollars'] = pnl_dollars
        position['status'] = 'CLOSED'
        
        # Move to closed trades
        self.closed_trades.append(position)
        self.positions.remove(position)
        
        # Log closure
        logger.info("="*80)
        logger.info(f"📊 POSITION CLOSED")
        logger.info(f"   ID: {position['id']}")
        logger.info(f"   Direction: {position['direction']}")
        logger.info(f"   Entry: {position['entry_price']:.5f} @ {position['entry_time']}")
        logger.info(f"   Exit: {exit_price:.5f} @ {exit_time}")
        logger.info(f"   Reason: {reason}")
        logger.info(f"   Gross: {pips:.2f} pips | Net: {net_pips:.2f} pips")
        logger.info(f"   P&L: ${pnl_dollars:,.2f}")
        logger.info(f"   Account Balance: ${self.account_balance:,.2f}")
        logger.info(f"   Return: {((self.account_balance/self.starting_capital - 1) * 100):.2f}%")
        logger.info("="*80)
        
        # Save to trade log
        self.log_trade(position, 'CLOSE')
        
        # Show performance summary
        if len(self.closed_trades) % 5 == 0:
            self.print_performance_summary()
    
    def log_trade(self, position: dict, action: str):
        """Log trade to CSV"""
        log_file = Path('logs/paper_trades.csv')
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        if not log_file.exists():
            # Create header
            with open(log_file, 'w') as f:
                f.write('Timestamp,TradeID,Action,Direction,EntryPrice,ExitPrice,EntryTime,ExitTime,'
                       'ExitReason,GrossPips,NetPips,PnL_USD,AccountBalance,BarsHeld\n')
        
        with open(log_file, 'a') as f:
            f.write(f"{datetime.now()},{position['id']},{action},{position['direction']},"
                   f"{position['entry_price']:.5f},{position.get('exit_price', ''):.5f},"
                   f"{position['entry_time']},{position.get('exit_time', '')},"
                   f"{position.get('exit_reason', '')},{position.get('pips', ''):.2f},"
                   f"{position.get('net_pips', ''):.2f},{position.get('pnl_dollars', ''):.2f},"
                   f"{self.account_balance:.2f},{position['bars_held']}\n")
    
    def print_performance_summary(self):
        """Print current performance statistics"""
        if not self.closed_trades:
            return
        
        total_trades = len(self.closed_trades)
        wins = sum(1 for t in self.closed_trades if t['net_pips'] > 0)
        losses = total_trades - wins
        win_rate = wins / total_trades if total_trades > 0 else 0
        
        total_pips = sum(t['net_pips'] for t in self.closed_trades)
        total_pnl = sum(t['pnl_dollars'] for t in self.closed_trades)
        
        avg_win = np.mean([t['net_pips'] for t in self.closed_trades if t['net_pips'] > 0]) if wins > 0 else 0
        avg_loss = np.mean([t['net_pips'] for t in self.closed_trades if t['net_pips'] <= 0]) if losses > 0 else 0
        
        logger.info("\n" + "="*80)
        logger.info("📊 PERFORMANCE SUMMARY")
        logger.info("="*80)
        logger.info(f"Total Trades: {total_trades}")
        logger.info(f"Wins: {wins} ({win_rate:.1%}) | Losses: {losses}")
        logger.info(f"Total Pips: {total_pips:.1f}")
        logger.info(f"Total P&L: ${total_pnl:,.2f}")
        logger.info(f"Account Balance: ${self.account_balance:,.2f}")
        logger.info(f"Return: {((self.account_balance/self.starting_capital - 1) * 100):.2f}%")
        logger.info(f"Avg Win: {avg_win:.2f} pips | Avg Loss: {avg_loss:.2f} pips")
        logger.info("="*80 + "\n")
    
    def run_simulation(self, data: pd.DataFrame, start_date: Optional[str] = None):
        """
        Run paper trading simulation on historical data

        Args:
            data: OHLCV dataframe with DatetimeIndex
            start_date: Optional start date for simulation
        """
        logger.info("=" * 80)
        logger.info("🚀 STARTING PAPER TRADING SIMULATION")
        logger.info("=" * 80)
        logger.info(f"Strategy: MA Deviation + Slope Filter")
        sp = self.config.get('strategy_params', {})
        logger.info(f"Config:   MA{sp.get('ma_length',200)} Z>{sp.get('z_threshold',1.5)} "
                     f"Exit={sp.get('exit_horizon_bars',20)}h Slope<{sp.get('slope_z_threshold',0.5)}")

        if start_date:
            data = data[data.index >= pd.Timestamp(start_date, tz='UTC')]

        # Initialize with lookback data (need 600 bars for MA200 + slope std)
        lookback = self.config.get('lookback_bars', 600)
        lookback_data = data.iloc[:lookback]
        self.price_data = lookback_data.copy()

        # Simulate bar by bar
        for i in range(lookback, len(data)):
            current_bar = data.iloc[i]

            # Check existing positions first
            self.check_positions(current_bar)

            # Check for new signals
            signal = self.detect_signal(current_bar)
            if signal and len(self.positions) < self.config['max_concurrent_positions']:
                self.open_position(signal, current_bar)

            # Update price data (sliding window)
            self.price_data = data.iloc[max(0, i - lookback):i + 1].copy()
        
        # Close any remaining open positions at market
        for position in list(self.positions):
            last_bar = data.iloc[-1]
            self.close_position(position, last_bar['close'], last_bar.name, 'SIMULATION_END')
        
        # Final summary
        logger.info("\n" + "="*80)
        logger.info("✅ SIMULATION COMPLETE")
        logger.info("="*80)
        self.print_performance_summary()


def main():
    """Main execution"""
    # Create logs directory
    Path('logs').mkdir(exist_ok=True)

    # Initialize engine
    engine = PaperTradingEngine()

    # Load historical data
    df = load_processed_data()

    # Run simulation on recent data (last 6 months to get enough bars)
    simulation_start = (
        pd.Timestamp.now(tz='UTC') - pd.Timedelta(days=180)
    ).strftime('%Y-%m-%d')

    logger.info(f"Running simulation from {simulation_start}")
    logger.info(f"Strategy: MA Deviation + Slope Filter (Part 25E validated)")
    engine.run_simulation(df, start_date=simulation_start)

    logger.info("\n📁 Trade log saved to: logs/paper_trades.csv")
    logger.info("📁 Full log saved to: logs/paper_trading.log")


if __name__ == '__main__':
    main()
