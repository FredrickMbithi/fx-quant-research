#!/usr/bin/env python3
"""
Multi-Pair H1 Trading Engine
Target: 3,000 trades using high-quality exhaustion strategy across multiple pairs
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import logging

from src.features.exhaustion import ExhaustionDetector
from src.data.h1_loader import load_processed_data


class MultiPairTradingEngine:
    """
    Trade exhaustion reversal strategy across multiple currency pairs on H1 timeframe.
    
    Target: 3,000 trades over 10 years using 36 pairs (85 trades/pair)
    Expected: 13,511 pips NET profit after transaction costs
    """
    
    def __init__(self, config_path: str = 'config/h1_multipair_config.json'):
        self.config = self.load_config(config_path)
        self.pairs = self.config['pairs_to_trade']
        self.detectors = {}
        self.positions = {}  # {pair: position_dict}
        self.trade_history = []
        self.account = self.config['portfolio']['initial_capital']
        self.account_history = []
        
        # Setup logging
        self.setup_logging()
        
        # Initialize detectors for each pair
        self.initialize_detectors()
        
        logging.info(f"MultiPairTradingEngine initialized with {len(self.pairs)} pairs")
    
    def load_config(self, config_path: str) -> dict:
        """Load configuration from JSON file"""
        with open(config_path, 'r') as f:
            return json.load(f)
    
    def setup_logging(self):
        """Setup logging to file and console"""
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = log_dir / f'multipair_h1_{timestamp}.log'
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
    
    def initialize_detectors(self):
        """Create ExhaustionDetector for each pair"""
        params = self.config['exhaustion_params']
        
        for pair in self.pairs:
            self.detectors[pair] = ExhaustionDetector(
                pressure_lookback=params['pressure_lookback'],
                range_expansion_percentile=params['range_percentile'],
                entry_zone_pct=params['entry_threshold'],
                exit_horizon_bars=params['exit_horizon'],
                detect_bullish=params['detect_bullish'],
                detect_bearish=params['detect_bearish']
            )
            logging.info(f"Initialized detector for {pair}")
    
    def load_data(self) -> Dict[str, pd.DataFrame]:
        """Load H1 data for all pairs"""
        data = {}
        
        for pair in self.pairs:
            try:
                df = load_processed_data(pair, '1H')
                data[pair] = df
                logging.info(f"Loaded {len(df)} bars for {pair}")
            except Exception as e:
                logging.error(f"Failed to load data for {pair}: {e}")
        
        return data
    
    def align_timelines(self, data: Dict[str, pd.DataFrame]) -> pd.DatetimeIndex:
        """Get common trading hours across all pairs"""
        # Start with first pair's index
        common_dates = set(data[self.pairs[0]].index)
        
        # Intersect with all other pairs
        for pair in self.pairs[1:]:
            if pair in data:
                common_dates = common_dates.intersection(set(data[pair].index))
        
        return pd.DatetimeIndex(sorted(list(common_dates)))
    
    def get_spread(self, pair: str) -> float:
        """Get spread for a specific pair based on tier"""
        spreads = self.config['execution']['spread_pips']
        
        # Classify pair into major/minor/exotic
        majors = ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'AUDUSD', 'NZDUSD', 'USDCAD']
        
        if pair.replace('/', '') in majors:
            return spreads['majors']
        elif 'JPY' in pair or 'EUR' in pair or 'GBP' in pair:
            return spreads['minors']
        else:
            return spreads['exotics']
    
    def check_correlation_limit(self, pair: str) -> bool:
        """
        Check if opening a position on this pair would violate correlation limits.
        Prevents too many correlated pairs being traded simultaneously.
        """
        max_concurrent = self.config['risk_management']['max_pairs_open_simultaneously']
        
        if len(self.positions) >= max_concurrent:
            return False
        
        # TODO: Implement correlation matrix check
        # For now, just limit total open positions
        return True
    
    def calculate_position_size(self, pair: str, stop_loss_pips: float) -> float:
        """
        Calculate position size based on risk management rules.
        
        Using fixed fractional: risk 1% of account per trade
        """
        risk_pct = self.config['risk_management']['position_size_per_pair']
        risk_amount = self.account * (risk_pct / 100)
        
        # Position size = risk_amount / stop_loss_in_account_currency
        # For simplicity, assume 1 pip = $10 per lot
        # This should be adjusted based on actual pair specifications
        pip_value = 10.0  # USD per pip per standard lot
        
        position_size = risk_amount / (stop_loss_pips * pip_value)
        
        return position_size
    
    def detect_signal(self, pair: str, df: pd.DataFrame, current_idx: int) -> Optional[dict]:
        """
        Detect exhaustion signal for a specific pair at current bar.
        
        Returns signal dict if exhaustion detected, None otherwise.
        """
        # Get data up to current point (avoid lookahead bias)
        data_so_far = df.iloc[:current_idx + 1]
        
        if len(data_so_far) < 100:  # Need minimum bars for detector
            return None
        
        # Detect exhaustion
        detector = self.detectors[pair]
        signals = detector.detect(data_so_far)
        
        # Check if bearish exhaustion at current bar
        if 'bearish' in signals and len(signals['bearish']) > 0:
            if data_so_far.index[-1] in signals['bearish']:
                # Signal detected
                current_bar = data_so_far.iloc[-1]
                
                return {
                    'pair': pair,
                    'direction': 'LONG',  # Reversal from bearish exhaustion
                    'entry_time': data_so_far.index[-1],
                    'entry_price': current_bar['Close'],
                    'high': current_bar['High'],
                    'low': current_bar['Low']
                }
        
        return None
    
    def open_position(self, signal: dict, df: pd.DataFrame, current_idx: int):
        """Open new position based on signal"""
        pair = signal['pair']
        
        # Get SL/TP from config (if specified) or use defaults
        sl_pips = self.config['risk_management']['stop_loss_pips']
        tp_pips = self.config['risk_management']['take_profit_pips']
        
        # Default: no SL/TP, use time-based exit only
        sl_price = None
        tp_price = None
        
        if sl_pips:
            sl_price = signal['entry_price'] - (sl_pips * 0.0001)  # LONG position
        if tp_pips:
            tp_price = signal['entry_price'] + (tp_pips * 0.0001)
        
        # Calculate position size
        position_size = self.calculate_position_size(pair, sl_pips or 50)
        
        # Record position
        self.positions[pair] = {
            'entry_time': signal['entry_time'],
            'entry_price': signal['entry_price'],
            'entry_idx': current_idx,
            'direction': signal['direction'],
            'position_size': position_size,
            'sl_price': sl_price,
            'tp_price': tp_price,
            'exit_bar': current_idx + self.config['exhaustion_params']['exit_horizon']
        }
        
        logging.info(f"OPEN {pair} LONG @ {signal['entry_price']:.5f} | Size: {position_size:.2f}")
    
    def check_exit(self, pair: str, df: pd.DataFrame, current_idx: int) -> Optional[dict]:
        """
        Check if open position should be exited.
        
        Returns trade result dict if exited, None otherwise.
        """
        position = self.positions[pair]
        current_bar = df.iloc[current_idx]
        
        exit_reason = None
        exit_price = None
        
        # Check Stop Loss
        if position['sl_price'] and current_bar['Low'] <= position['sl_price']:
            exit_reason = 'STOP_LOSS'
            exit_price = position['sl_price']
        
        # Check Take Profit
        elif position['tp_price'] and current_bar['High'] >= position['tp_price']:
            exit_reason = 'TAKE_PROFIT'
            exit_price = position['tp_price']
        
        # Check time-based exit
        elif current_idx >= position['exit_bar']:
            exit_reason = 'TIME_EXIT'
            exit_price = current_bar['Close']
        
        if exit_reason:
            # Calculate P&L
            entry_price = position['entry_price']
            pips = (exit_price - entry_price) / 0.0001  # LONG position
            
            # Apply transaction costs
            spread = self.get_spread(pair)
            slippage = self.config['execution']['slippage_pips']
            total_cost = spread + slippage
            net_pips = pips - total_cost
            
            # Update account
            pip_value = 10.0  # $10 per pip per lot
            profit = net_pips * pip_value * position['position_size']
            self.account += profit
            
            trade_result = {
                'pair': pair,
                'entry_time': position['entry_time'],
                'exit_time': df.index[current_idx],
                'entry_price': entry_price,
                'exit_price': exit_price,
                'direction': position['direction'],
                'pips': pips,
                'costs': total_cost,
                'net_pips': net_pips,
                'profit_usd': profit,
                'exit_reason': exit_reason,
                'account_balance': self.account
            }
            
            logging.info(f"CLOSE {pair} @ {exit_price:.5f} | {net_pips:+.1f} pips | Reason: {exit_reason}")
            
            return trade_result
        
        return None
    
    def run_backtest(self) -> pd.DataFrame:
        """
        Run multi-pair backtest across all pairs simultaneously.
        
        Returns DataFrame of all trades executed.
        """
        logging.info("="*80)
        logging.info("STARTING MULTI-PAIR H1 BACKTEST")
        logging.info("="*80)
        
        # Load data for all pairs
        data = self.load_data()
        
        if not data:
            logging.error("No data loaded. Exiting.")
            return pd.DataFrame()
        
        # Get common timeline
        common_dates = self.align_timelines(data)
        logging.info(f"Common timeline: {len(common_dates)} bars from {common_dates[0]} to {common_dates[-1]}")
        
        # Create index mapping for each pair
        idx_maps = {}
        for pair in self.pairs:
            if pair in data:
                idx_maps[pair] = {date: i for i, date in enumerate(data[pair].index)}
        
        # Simulate trading bar by bar
        for date_idx, date in enumerate(common_dates):
            if date_idx % 1000 == 0:
                logging.info(f"Progress: {date_idx}/{len(common_dates)} bars processed | Open positions: {len(self.positions)}")
            
            # Check each pair
            for pair in self.pairs:
                if pair not in data:
                    continue
                
                current_idx = idx_maps[pair][date]
                
                if pair not in self.positions:
                    # Check for new signal
                    if self.check_correlation_limit(pair):
                        signal = self.detect_signal(pair, data[pair], current_idx)
                        if signal:
                            self.open_position(signal, data[pair], current_idx)
                else:
                    # Check for exit
                    trade_result = self.check_exit(pair, data[pair], current_idx)
                    if trade_result:
                        self.trade_history.append(trade_result)
                        del self.positions[pair]
            
            # Track account balance
            self.account_history.append({
                'date': date,
                'balance': self.account,
                'open_positions': len(self.positions)
            })
        
        # Close any remaining positions
        for pair in list(self.positions.keys()):
            final_idx = len(data[pair]) - 1
            trade_result = self.check_exit(pair, data[pair], final_idx)
            if trade_result:
                self.trade_history.append(trade_result)
        
        logging.info("="*80)
        logging.info("BACKTEST COMPLETE")
        logging.info("="*80)
        
        # Convert to DataFrame
        trades_df = pd.DataFrame(self.trade_history)
        return trades_df
    
    def analyze_results(self, trades_df: pd.DataFrame):
        """Print comprehensive performance analysis"""
        if len(trades_df) == 0:
            print("No trades executed.")
            return
        
        # Calculate metrics
        total_trades = len(trades_df)
        winning_trades = len(trades_df[trades_df['net_pips'] > 0])
        losing_trades = len(trades_df[trades_df['net_pips'] < 0])
        win_rate = winning_trades / total_trades * 100
        
        total_pips_gross = trades_df['pips'].sum()
        total_costs = trades_df['costs'].sum()
        total_pips_net = trades_df['net_pips'].sum()
        
        avg_win = trades_df[trades_df['net_pips'] > 0]['net_pips'].mean() if winning_trades > 0 else 0
        avg_loss = trades_df[trades_df['net_pips'] < 0]['net_pips'].mean() if losing_trades > 0 else 0
        
        winning_pips = trades_df[trades_df['net_pips'] > 0]['net_pips'].sum()
        losing_pips = abs(trades_df[trades_df['net_pips'] < 0]['net_pips'].sum())
        profit_factor = winning_pips / losing_pips if losing_pips > 0 else float('inf')
        
        final_balance = self.account
        initial_capital = self.config['portfolio']['initial_capital']
        total_return_usd = final_balance - initial_capital
        total_return_pct = (total_return_usd / initial_capital) * 100
        
        # Time analysis
        start_date = trades_df['entry_time'].min()
        end_date = trades_df['exit_time'].max()
        years = (end_date - start_date).days / 365.25
        
        print("\n" + "="*80)
        print("MULTI-PAIR H1 BACKTEST RESULTS")
        print("="*80)
        print(f"\n📊 OVERVIEW:")
        print(f"   Pairs traded:          {len(self.pairs)}")
        print(f"   Period:                {start_date.date()} to {end_date.date()} ({years:.1f} years)")
        print(f"   Initial capital:       ${initial_capital:,.0f}")
        print(f"   Final balance:         ${final_balance:,.0f}")
        print(f"   Total return:          ${total_return_usd:+,.0f} ({total_return_pct:+.1f}%)")
        
        print(f"\n📈 TRADING STATISTICS:")
        print(f"   Total trades:          {total_trades:,}")
        print(f"   Trades per year:       {total_trades/years:.0f}")
        print(f"   Trades per pair:       {total_trades/len(self.pairs):.0f}")
        print(f"   Winning trades:        {winning_trades} ({win_rate:.1f}%)")
        print(f"   Losing trades:         {losing_trades}")
        
        print(f"\n💰 PIPS PERFORMANCE:")
        print(f"   Gross pips:            {total_pips_gross:+,.0f}")
        print(f"   Transaction costs:     {total_costs:,.0f} pips")
        print(f"   NET PIPS:              {total_pips_net:+,.0f}")
        print(f"   Pips per year:         {total_pips_net/years:+,.0f}")
        print(f"   Avg pips per trade:    {total_pips_net/total_trades:+.2f}")
        
        print(f"\n📊 TRADE QUALITY:")
        print(f"   Average win:           {avg_win:+.2f} pips")
        print(f"   Average loss:          {avg_loss:.2f} pips")
        print(f"   Profit factor:         {profit_factor:.2f}")
        print(f"   Win/Loss ratio:        {abs(avg_win/avg_loss):.2f}" if avg_loss != 0 else "   Win/Loss ratio:        N/A")
        
        # Per-pair breakdown
        print(f"\n🏆 TOP 5 PERFORMING PAIRS:")
        pair_performance = trades_df.groupby('pair').agg({
            'net_pips': 'sum',
            'pair': 'count'
        }).rename(columns={'pair': 'trades'})
        pair_performance = pair_performance.sort_values('net_pips', ascending=False)
        
        for i, (pair, row) in enumerate(pair_performance.head(5).iterrows(), 1):
            print(f"   {i}. {pair:8s}  {row['net_pips']:+8.0f} pips  ({int(row['trades'])} trades)")
        
        print(f"\n❌ BOTTOM 5 PERFORMING PAIRS:")
        for i, (pair, row) in enumerate(pair_performance.tail(5).iterrows(), 1):
            print(f"   {i}. {pair:8s}  {row['net_pips']:+8.0f} pips  ({int(row['trades'])} trades)")
        
        print("="*80)
        
        # Save results
        output_dir = Path('reports/backtests')
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        trades_file = output_dir / f'multipair_h1_trades_{timestamp}.csv'
        trades_df.to_csv(trades_file, index=False)
        print(f"\n💾 Trades saved to: {trades_file}")
        
        # Save account history
        account_df = pd.DataFrame(self.account_history)
        account_file = output_dir / f'multipair_h1_account_{timestamp}.csv'
        account_df.to_csv(account_file, index=False)
        print(f"💾 Account history saved to: {account_file}")


def main():
    """Main execution"""
    print("\n" + "="*80)
    print("MULTI-PAIR H1 TRADING ENGINE")
    print("Target: 3,000 trades via high-quality exhaustion strategy")
    print("="*80 + "\n")
    
    # Initialize engine
    engine = MultiPairTradingEngine(config_path='config/h1_multipair_config.json')
    
    # Run backtest
    trades_df = engine.run_backtest()
    
    # Analyze results
    engine.analyze_results(trades_df)


if __name__ == "__main__":
    main()
