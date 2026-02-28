"""
Trade-Level Analysis for Backtest Results
Extract and analyze individual trade performance
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
import pickle


def analyze_trades(results_file: str = 'reports/backtests/exhaustion_h1_backtest_results.pkl'):
    """
    Analyze individual trades from backtest results.
    
    Args:
        results_file: Path to pickled backtest results
    
    Returns:
        Dict with trade-level statistics
    """
    # Load results
    print("Loading backtest results...")
    with open(results_file, 'rb') as f:
        results = pickle.load(f)
    
    # Extract trade information
    print("\nExtracting trades...")
    
    position = results['position']
    prices = results['price']
    equity = results['equity']
    exit_info = results['exit_info']
    
    # Find trades (entry when position != 0 from 0, exit when position returns to 0)
    trades = []
    in_trade = False
    entry_idx = None
    entry_price = None
    entry_equity = None
    position_direction = None
    
    for i in range(len(position)):
        # Entry
        if not in_trade and position[i] != 0:
            in_trade = True
            entry_idx = i
            entry_price = prices[i]
            entry_equity = equity[i]
            position_direction = np.sign(position[i])
        
        # Exit
        elif in_trade and position[i] == 0:
            exit_idx = i
            exit_price = prices[i]
            exit_equity = equity[i]
            
            # Calculate P&L
            trade_pnl = exit_equity - entry_equity
            
            # Calculate P&L in pips
            if position_direction > 0:  # LONG
                pnl_pips = (exit_price - entry_price) / 0.0001
            else:  # SHORT
                pnl_pips = (entry_price - exit_price) / 0.0001
            
            # Duration
            duration = exit_idx - entry_idx
            
            # Exit reason (from exit_info)
            exit_reason = exit_info.iloc[exit_idx]['exit_reason'] if exit_info is not None else 'unknown'
            
            trades.append({
                'entry_idx': entry_idx,
                'exit_idx': exit_idx,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'direction': 'LONG' if position_direction > 0 else 'SHORT',
                'pnl_usd': trade_pnl,
                'pnl_pips': pnl_pips,
                'duration_bars': duration,
                'exit_reason': exit_reason,
                'winning': trade_pnl > 0,
            })
            
            in_trade = False
    
    # Convert to DataFrame
    trades_df = pd.DataFrame(trades)
    
    print(f"Total trades extracted: {len(trades_df)}")
    
    # Calculate statistics
    if len(trades_df) == 0:
        print("No trades found!")
        return None
    
    winning_trades = trades_df[trades_df['winning']]
    losing_trades = trades_df[~trades_df['winning']]
    
    long_trades = trades_df[trades_df['direction'] == 'LONG']
    short_trades = trades_df[trades_df['direction'] == 'SHORT']
    
    stats = {
        # Overall
        'total_trades': len(trades_df),
        'winning_trades': len(winning_trades),
        'losing_trades': len(losing_trades),
        'win_rate': len(winning_trades) / len(trades_df) * 100,
        
        # P&L in USD
        'total_pnl_usd': trades_df['pnl_usd'].sum(),
        'avg_pnl_usd': trades_df['pnl_usd'].mean(),
        'median_pnl_usd': trades_df['pnl_usd'].median(),
        'avg_win_usd': winning_trades['pnl_usd'].mean() if len(winning_trades) > 0 else 0,
        'avg_loss_usd': losing_trades['pnl_usd'].mean() if len(losing_trades) > 0 else 0,
        'max_win_usd': trades_df['pnl_usd'].max(),
        'max_loss_usd': trades_df['pnl_usd'].min(),
        
        # P&L in pips
        'avg_pnl_pips': trades_df['pnl_pips'].mean(),
        'median_pnl_pips': trades_df['pnl_pips'].median(),
        'avg_win_pips': winning_trades['pnl_pips'].mean() if len(winning_trades) > 0 else 0,
        'avg_loss_pips': losing_trades['pnl_pips'].mean() if len(losing_trades) > 0 else 0,
        'max_win_pips': trades_df['pnl_pips'].max(),
        'max_loss_pips': trades_df['pnl_pips'].min(),
        
        # Profit factor
        'gross_profit': winning_trades['pnl_usd'].sum() if len(winning_trades) > 0 else 0,
        'gross_loss': abs(losing_trades['pnl_usd'].sum()) if len(losing_trades) > 0 else 0,
        'profit_factor': (winning_trades['pnl_usd'].sum() / abs(losing_trades['pnl_usd'].sum()) 
                         if len(losing_trades) > 0 and losing_trades['pnl_usd'].sum() != 0 else 0),
        
        # Duration
        'avg_duration_bars': trades_df['duration_bars'].mean(),
        'median_duration_bars': trades_df['duration_bars'].median(),
        
        # Direction analysis
        'long_trades': len(long_trades),
        'short_trades': len(short_trades),
        'long_win_rate': (long_trades['winning'].sum() / len(long_trades) * 100) if len(long_trades) > 0 else 0,
        'short_win_rate': (short_trades['winning'].sum() / len(short_trades) * 100) if len(short_trades) > 0 else 0,
        
        # Exit reason analysis
        'exit_by_hard_stop': (trades_df['exit_reason'] == 'hard_stop').sum(),
        'exit_by_trailing': (trades_df['exit_reason'] == 'trailing_stop').sum(),
        'exit_by_max_hold': (trades_df['exit_reason'] == 'max_hold').sum(),
    }
    
    return stats, trades_df


def print_trade_analysis(stats: dict):
    """Print formatted trade analysis."""
    print("\n" + "="*70)
    print(" "*20 + "TRADE-LEVEL ANALYSIS")
    print("="*70)
    
    print(f"\nOverall Statistics:")
    print(f"  Total Trades:          {stats['total_trades']}")
    print(f"  Winning Trades:        {stats['winning_trades']} ({stats['win_rate']:.1f}%)")
    print(f"  Losing Trades:         {stats['losing_trades']} ({100-stats['win_rate']:.1f}%)")
    
    print(f"\nProfit & Loss (USD):")
    print(f"  Gross Profit:          ${stats['gross_profit']:,.2f}")
    print(f"  Gross Loss:            ${stats['gross_loss']:,.2f}")
    print(f"  Net P&L:               ${stats['total_pnl_usd']:,.2f}")
    print(f"  Profit Factor:         {stats['profit_factor']:.2f}")
    print(f"  Average Trade:         ${stats['avg_pnl_usd']:.2f}")
    print(f"  Median Trade:          ${stats['median_pnl_usd']:.2f}")
    print(f"  Average Winner:        ${stats['avg_win_usd']:.2f}")
    print(f"  Average Loser:         ${stats['avg_loss_usd']:.2f}")
    print(f"  Max Winner:            ${stats['max_win_usd']:.2f}")
    print(f"  Max Loser:             ${stats['max_loss_usd']:.2f}")
    
    print(f"\nProfit & Loss (Pips):")
    print(f"  Average Trade:         {stats['avg_pnl_pips']:.2f} pips")
    print(f"  Median Trade:          {stats['median_pnl_pips']:.2f} pips")
    print(f"  Average Winner:        {stats['avg_win_pips']:.2f} pips")
    print(f"  Average Loser:         {stats['avg_loss_pips']:.2f} pips")
    print(f"  Max Winner:            {stats['max_win_pips']:.2f} pips")
    print(f"  Max Loser:             {stats['max_loss_pips']:.2f} pips")
    
    print(f"\nTrade Duration:")
    print(f"  Average:               {stats['avg_duration_bars']:.1f} bars")
    print(f"  Median:                {stats['median_duration_bars']:.0f} bars")
    
    print(f"\nDirection Analysis:")
    print(f"  Long Trades:           {stats['long_trades']} (win rate: {stats['long_win_rate']:.1f}%)")
    print(f"  Short Trades:          {stats['short_trades']} (win rate: {stats['short_win_rate']:.1f}%)")
    
    print(f"\nExit Reasons:")
    print(f"  Hard Stop:             {stats['exit_by_hard_stop']}")
    print(f"  Trailing Stop:         {stats['exit_by_trailing']}")
    print(f"  Max Hold:              {stats['exit_by_max_hold']}")
    
    print("\n" + "="*70)
    
    # Success criteria check
    print("\nSUCCESS CRITERIA EVALUATION:")
    print("-"*70)
    
    criteria_results = {
        'Sharpe Ratio ≥ 1.2': ('N/A', 'Need full backtest result'),
        'Profit Factor ≥ 1.4': (stats['profit_factor'], stats['profit_factor'] >= 1.4),
        'Win Rate ≥ 48%': (f"{stats['win_rate']:.1f}%", stats['win_rate'] >= 48.0),
        'Max DD ≤ 18%': ('N/A', 'Need full backtest result'),
        'Net Trade ≥ 2 pips': (f"{stats['avg_pnl_pips']:.2f}", stats['avg_pnl_pips'] >= 2.0),
    }
    
    for criterion, (value, passed) in criteria_results.items():
        if isinstance(passed, bool):
            status = "✓ PASS" if passed else "✗ FAIL"
            print(f"  {criterion:25s}: {status:10s} (actual: {value})")
        else:
            print(f"  {criterion:25s}: {value}")
    
    print("="*70)


if __name__ == "__main__":
    # Analyze trades
    stats, trades_df = analyze_trades()
    
    if stats:
        # Print analysis
        print_trade_analysis(stats)
        
        # Show sample trades
        print("\nSample Trades (first 10):")
        print(trades_df[['direction', 'pnl_pips', 'pnl_usd', 'duration_bars', 'exit_reason']].head(10))
        
        print("\nBest 5 Trades:")
        print(trades_df.nlargest(5, 'pnl_pips')[['direction', 'pnl_pips', 'pnl_usd', 'duration_bars', 'exit_reason']])
        
        print("\nWorst 5 Trades:")
        print(trades_df.nsmallest(5, 'pnl_pips')[['direction', 'pnl_pips', 'pnl_usd', 'duration_bars', 'exit_reason']])
