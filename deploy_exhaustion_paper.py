"""
Paper Trading Deployment - Exhaustion + Failure Pattern
NZDJPY (PASS - 4.25 pips/trade) & GBPUSD (MARGINAL - 1.31 pips/trade)

Hypothesis: Two-bar mean reversion after exhaustion + failure-to-continue
- Exhaustion bar: Pressure ±2, range >0.8×median, extreme close (top/bottom 35%)
- Failure bar: Opposite direction, no new high/low
- Exit: 10 pip stop, trailing (4 pip trigger, 3 pip trail), 5 bar max hold
"""

import sys
import argparse
from pathlib import Path
import logging
import json
import pandas as pd
import numpy as np
from datetime import datetime
from scipy import stats

# Add project root
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.strategies.exhaustion_strategy import ExhaustionStrategy
from src.events.market_event import BarEvent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/paper_exhaustion.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class ExhaustionPaperTrader:
    """Paper trading engine for exhaustion+failure pattern"""
    
    def __init__(self, config_path: str):
        """Initialize paper trader"""
        self.config = self.load_config(config_path)
        self.symbol = self.config['symbol']
        self.positions = []
        self.closed_trades = []
        self.account_balance = self.config['initial_capital']
        self.starting_capital = self.config['initial_capital']
        self.peak_equity = self.config['initial_capital']
        self.consecutive_losses = 0
        
        # Initialize strategy
        self.strategy = ExhaustionStrategy(
            name=self.config['strategy_name'],
            symbols=[self.symbol],
            config=self.config['strategy_params']
        )
        
        # Exit parameters
        self.exit_params = self.config['exit_params']
        
        # Monitoring params
        self.monitoring = self.config.get('monitoring', {})
        
        # Load data
        self.data = None
       
        logger.info("="*70)
        logger.info(f"PAPER TRADING: {self.config['strategy_name']}")
        logger.info("="*70)
        logger.info(f"Symbol: {self.symbol}")
        logger.info(f"Initial Capital: ${self.account_balance:,.2f}")
        logger.info(f"Pattern: Exhaustion + Failure-to-Continue (2-bar)")
        logger.info(f"Exit: {self.exit_params['stop_loss_pips']}pip SL, "
                   f"{self.exit_params['profit_trigger_pips']}pip trigger, "
                   f"{self.exit_params['trailing_distance_pips']}pip trail, "
                   f"{self.exit_params['max_hold_bars']}bar max")
        logger.info("="*70)
    
    def load_config(self, config_path: str) -> dict:
        """Load configuration"""
        with open(config_path, 'r') as f:
            return json.load(f)
    
    def load_data(self, start_date: str = None, end_date: str = None):
        """Load historical H1 data"""
        logger.info(f"Loading {self.symbol} H1 data...")
        
        # Map pair name to file
        file_map = {
            'GBPUSD': 'GBPUSD60.csv',
            'EURUSD': 'EURUSD60.csv',
            'USDJPY': 'USDJPY60.csv',
            'USDCAD': 'USDCAD60.csv',
            'NZDUSD': 'NZDUSD60.csv',
            'USDCHF': 'USDCHF60.csv',
            'NZDJPY': 'NZDJPY60.csv',
            'AUDNZD': 'AUDNZD60.csv'
        }
        
        file_path = Path('data/raw') / file_map[self.symbol]
        df = pd.read_csv(file_path, names=['date', 'time', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['date'] + ' ' + df['time'])
        df = df.set_index('timestamp')
        df = df[['open', 'high', 'low', 'close', 'volume']]
        
        # Ensure UTC
        if df.index.tz is None:
            df.index = df.index.tz_localize('UTC')
        
        df = df.sort_index()
        df = df[~df.index.duplicated(keep='first')]
        
        # Filter date range if specified
        if start_date:
            df = df[df.index >= pd.to_datetime(start_date)]
        if end_date:
            df = df[df.index <= pd.to_datetime(end_date)]
        
        self.data = df
        logger.info(f"Loaded {len(df)} bars from {df.index[0]} to {df.index[-1]}")
    
    def simulate_trade_exit(self, entry_idx: int, direction: int, entry_price: float) -> dict:
        """
        Simulate trade exit using configured exit logic.
        
        Returns dict with exit info: exit_price, exit_reason, bars_held, pnl_pips
        """
        pip_value = 0.01 if 'JPY' in self.symbol else 0.0001
        max_profit = 0
        
        for bar_offset in range(1, self.exit_params['max_hold_bars'] + 1):
            if entry_idx + bar_offset >= len(self.data):
                break
            
            bar = self.data.iloc[entry_idx + bar_offset]
            high = bar['high']
            low = bar['low']
            close = bar['close']
            
            # Calculate profit/loss in pips
            if direction == 1:  # LONG
                profit_pips = (high - entry_price) / pip_value
                loss_pips = (entry_price - low) / pip_value
            else:  # SHORT
                profit_pips = (entry_price - low) / pip_value
                loss_pips = (high - entry_price) / pip_value
            
            max_profit = max(max_profit, profit_pips)
            
            # Check stop loss
            if loss_pips >= self.exit_params['stop_loss_pips']:
                exit_price = entry_price - (self.exit_params['stop_loss_pips'] * pip_value * direction)
                return {
                    'exit_price': exit_price,
                    'exit_reason': 'SL',
                    'bars_held': bar_offset,
                    'pnl_pips': -self.exit_params['stop_loss_pips']
                }
            
            # Check trailing stop
            if max_profit >= self.exit_params['profit_trigger_pips']:
                trailing_level = max_profit - self.exit_params['trailing_distance_pips']
                current_profit = (close - entry_price) / pip_value * direction
                
                if current_profit <= trailing_level:
                    exit_price = entry_price + (trailing_level * pip_value * direction)
                    return {
                        'exit_price': exit_price,
                        'exit_reason': 'TRAIL',
                        'bars_held': bar_offset,
                        'pnl_pips': trailing_level
                    }
            
            # Check max hold
            if bar_offset == self.exit_params['max_hold_bars']:
                pnl_pips = (close - entry_price) / pip_value * direction
                return {
                    'exit_price': close,
                    'exit_reason': 'TIME',
                    'bars_held': bar_offset,
                    'pnl_pips': pnl_pips
                }
        
        # End of data
        final_price = self.data.iloc[-1]['close']
        pnl_pips = (final_price - entry_price) / pip_value * direction
        return {
            'exit_price': final_price,
            'exit_reason': 'EOD',
            'bars_held': len(self.data) - entry_idx - 1,
            'pnl_pips': pnl_pips
        }
    
    def check_halt_conditions(self) -> tuple:
        """Check if trading should be halted. Returns (should_halt, reason)"""
        # Check drawdown
        current_drawdown = ((self.peak_equity - self.account_balance) / self.peak_equity) * 100
        max_dd = self.monitoring.get('halt_on_drawdown_pct', 10)
        if current_drawdown >= max_dd:
            return True, f"Max drawdown {current_drawdown:.1f}% >= {max_dd}%"
        
        # Check consecutive losses
        max_consec = self.monitoring.get('halt_on_consecutive_losses', 10)
        if self.consecutive_losses >= max_consec:
            return True, f"Consecutive losses {self.consecutive_losses} >= {max_consec}"
        
        return False, None
    
    def run_simulation(self):
        """Run paper trading simulation on historical data"""
        logger.info("\n🚀 STARTING PAPER TRADING SIMULATION\n")
        
        # Process each bar
        for i in range(self.config['lookback_bars'], len(self.data)):
            bar = self.data.iloc[i]
            
            # Create bar event
            bar_event = BarEvent(
                symbol=self.symbol,
                timeframe='H1',
                timestamp=bar.name,
                open_price=bar['open'],
                high=bar['high'],
                low=bar['low'],
                close=bar['close'],
                volume=bar['volume']
            )
            
            # Process bar with strategy
            signal = self.strategy.on_bar(bar_event)
            
            if signal:
                # Check halt conditions before trading
                should_halt, halt_reason = self.check_halt_conditions()
                if should_halt:
                    logger.warning(f"🛑 TRADING HALTED: {halt_reason}")
                    break
                
                # Signal generated!
                direction = 1 if signal.signal_strength > 0 else -1
                entry_price = bar['close']
                
                # Simulate exit
                exit_info = self.simulate_trade_exit(i, direction, entry_price)
                
                # Apply costs
                cost_pips = self.config['spread_pips'] + self.config['slippage_pips']
                net_pnl_pips = exit_info['pnl_pips'] - cost_pips
                
                # Record trade
                trade = {
                    'entry_time': bar.name,
                    'exit_time': self.data.index[min(i + exit_info['bars_held'], len(self.data) - 1)],
                    'symbol': self.symbol,
                    'direction': 'LONG' if direction == 1 else 'SHORT',
                    'entry_price': entry_price,
                    'exit_price': exit_info['exit_price'],
                    'exit_reason': exit_info['exit_reason'],
                    'bars_held': exit_info['bars_held'],
                    'gross_pnl_pips': exit_info['pnl_pips'],
                    'cost_pips': cost_pips,
                    'net_pnl_pips': net_pnl_pips
                }
                
                self.closed_trades.append(trade)
                
                # Update balance
                self.account_balance += net_pnl_pips
                
                # Update peak equity
                if self.account_balance > self.peak_equity:
                    self.peak_equity = self.account_balance
                
                # Track consecutive losses
                if net_pnl_pips < 0:
                    self.consecutive_losses += 1
                else:
                    self.consecutive_losses = 0
                
                # Log trade
                if len(self.closed_trades) % self.config['performance_report_frequency'] == 0:
                    self.print_performance_summary()
        
        # Final summary
        self.print_final_summary()
        
        # Save trades
        if self.config['save_trades_to_csv']:
            self.save_trades()
    
    def print_performance_summary(self):
        """Print current performance"""
        if not self.closed_trades:
            return
        
        df = pd.DataFrame(self.closed_trades)
        total_pnl = df['net_pnl_pips'].sum()
        win_rate = (df['net_pnl_pips'] > 0).sum() / len(df)
        avg_pnl = df['net_pnl_pips'].mean()
        
        print(f"\n📊 Trades: {len(df)} | Total PnL: {total_pnl:.0f} pips | "
              f"Avg: {avg_pnl:.2f} pips | Win%: {win_rate*100:.1f}%")
    
    def print_final_summary(self):
        """Print final paper trading summary"""
        if not self.closed_trades:
            logger.warning("No trades executed")
            return
        
        df = pd.DataFrame(self.closed_trades)
        
        logger.info("\n" + "="*70)
        logger.info("PAPER TRADING RESULTS")
        logger.info("="*70)
        
        # Overall stats
        total_trades = len(df)
        gross_pnl = df['gross_pnl_pips'].sum()
        costs = df['cost_pips'].sum()
        net_pnl = df['net_pnl_pips'].sum()
        avg_pnl = df['net_pnl_pips'].mean()
        
        wins = (df['net_pnl_pips'] > 0).sum()
        losses = (df['net_pnl_pips'] < 0).sum()
        win_rate = wins / total_trades if total_trades > 0 else 0
        
        gross_wins = df[df['net_pnl_pips'] > 0]['net_pnl_pips'].sum()
        gross_losses = abs(df[df['net_pnl_pips'] < 0]['net_pnl_pips'].sum())
        pf = gross_wins / gross_losses if gross_losses > 0 else np.inf
        
        # Calculate max drawdown
        cumulative = df['net_pnl_pips'].cumsum()
        running_max = cumulative.cummax()
        drawdown = running_max - cumulative
        max_dd = drawdown.max()
        
        logger.info(f"\nTotal Trades:      {total_trades}")
        logger.info(f"LONG trades:       {(df['direction'] == 'LONG').sum()}")
        logger.info(f"SHORT trades:      {(df['direction'] == 'SHORT').sum()}")
        logger.info(f"\nGross PnL:         {gross_pnl:.0f} pips")
        logger.info(f"Total Costs:       {costs:.0f} pips")
        logger.info(f"NET PnL:           {net_pnl:.0f} pips")
        logger.info(f"Avg PnL/trade:     {avg_pnl:.2f} pips")
        logger.info(f"\nWins:              {wins}")
        logger.info(f"Losses:            {losses}")
        logger.info(f"Win Rate:          {win_rate*100:.1f}%")
        logger.info(f"Profit Factor:     {pf:.2f}")
        logger.info(f"Max Drawdown:      {max_dd:.0f} pips")
        
        # Statistical significance
        t_stat, p_value = stats.ttest_1samp(df['net_pnl_pips'], 0)
        logger.info(f"\nStatistical Test (t-test vs 0):")
        logger.info(f"  t-statistic:     {t_stat:.3f}")
        logger.info(f"  p-value:         {p_value:.4f}")
        logger.info(f"  Significant:     {'Yes' if p_value < 0.05 else 'No'} (p < 0.05)")
        
        # Exit breakdown
        logger.info(f"\nExit Breakdown:")
        for reason in df['exit_reason'].unique():
            count = (df['exit_reason'] == reason).sum()
            pct = count / total_trades * 100
            logger.info(f"  {reason:8s}: {count:4d} ({pct:.1f}%)")
        
        logger.info(f"\nAvg Bars Held:     {df['bars_held'].mean():.1f}")
        
        # Validation check
        logger.info("\n" + "="*70)
        logger.info("VALIDATION CHECK")
        logger.info("="*70)
        
        # Compare to backtest expectations
        if self.symbol == 'NZDJPY':
            expected_avg = 4.25
            expected_wr = 0.633
            expected_pf = 2.34
        elif self.symbol == 'GBPUSD':
            expected_avg = 1.31
            expected_wr = 0.501
            expected_pf = 1.23
        else:
            expected_avg = expected_wr = expected_pf = None
        
        if expected_avg:
            logger.info(f"\nExpected avg PnL:  {expected_avg:.2f} pips/trade")
            logger.info(f"Actual avg PnL:    {avg_pnl:.2f} pips/trade")
            logger.info(f"Difference:        {avg_pnl - expected_avg:+.2f} pips")
            
            logger.info(f"\nExpected Win Rate: {expected_wr*100:.1f}%")
            logger.info(f"Actual Win Rate:   {win_rate*100:.1f}%")
            logger.info(f"Difference:        {(win_rate - expected_wr)*100:+.1f}%")
            
            logger.info(f"\nExpected PF:       {expected_pf:.2f}")
            logger.info(f"Actual PF:         {pf:.2f}")
            
            # Decision
            avg_close = abs(avg_pnl - expected_avg) < 1.0
            wr_close = abs(win_rate - expected_wr) < 0.10
            
            if avg_close and wr_close:
                logger.info("\n✅ PAPER TRADING VALIDATES BACKTEST - Proceed to next phase")
            else:
                logger.info("\n⚠️  PAPER TRADING DEVIATES - Investigate differences")
        
        # Check monitoring thresholds
        logger.info("\n" + "="*70)
        logger.info("MONITORING ALERTS")
        logger.info("="*70)
        
        alerts = []
        
        # Check win rate threshold
        min_wr = self.monitoring.get('min_win_rate_threshold', 0)
        if min_wr > 0 and win_rate < min_wr:
            alerts.append(f"⚠️  Win rate {win_rate*100:.1f}% below threshold {min_wr*100:.1f}%")
        
        # Check avg PnL threshold
        min_avg = self.monitoring.get('min_avg_pnl_threshold', 0)
        if min_avg > 0 and avg_pnl < min_avg:
            alerts.append(f"⚠️  Avg PnL {avg_pnl:.2f} pips below threshold {min_avg:.2f} pips")
        
        # Check review checkpoint
        review_at = self.monitoring.get('review_after_trades', 0)
        if review_at > 0 and total_trades >= review_at:
            alerts.append(f"📋 Review checkpoint reached: {total_trades} trades (target: {review_at})")
        
        if alerts:
            for alert in alerts:
                logger.info(alert)
        else:
            logger.info("✅ All monitoring thresholds passed")
        
        logger.info("="*70)
    
    def save_trades(self):
        """Save trades to CSV"""
        if not self.closed_trades:
            return
        
        df = pd.DataFrame(self.closed_trades)
        output_path = self.config['trades_csv_path']
        
        # Ensure state directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        df.to_csv(output_path, index=False)
        logger.info(f"\n💾 Trades saved to: {output_path}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Paper trade exhaustion+failure pattern')
    parser.add_argument('--symbol', type=str, required=True, choices=['NZDJPY', 'GBPUSD'],
                       help='Symbol to trade')
    parser.add_argument('--start', type=str, default=None,
                       help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, default=None,
                       help='End date (YYYY-MM-DD)')
    
    args = parser.parse_args()
    
    # Load config
    if args.symbol == 'NZDJPY':
        config_path = 'config/paper_exhaustion_nzdjpy.json'
    elif args.symbol == 'GBPUSD':
        config_path = 'config/paper_exhaustion_gbpusd.json'
    
    # Run paper trading
    trader = ExhaustionPaperTrader(config_path)
    trader.load_data(start_date=args.start, end_date=args.end)
    trader.run_simulation()


if __name__ == '__main__':
    main()
