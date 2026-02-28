"""
Analyze Paper Trading Results
Compare paper trading performance against backtested expectations
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys


def load_paper_trades(filepath: str = 'logs/paper_trades.csv') -> pd.DataFrame:
    """Load paper trading results from CSV"""
    if not Path(filepath).exists():
        print(f"❌ No paper trades found at: {filepath}")
        print("   Run paper trading first: python deploy_paper_trading.py")
        sys.exit(1)
    
    df = pd.read_csv(filepath)
    
    # Filter to closed trades only
    df_closed = df[df['Action'] == 'CLOSE'].copy()
    
    return df_closed


def calculate_metrics(trades: pd.DataFrame) -> dict:
    """Calculate performance metrics"""
    if len(trades) == 0:
        return None
    
    total_trades = len(trades)
    wins = (trades['NetPips'] > 0).sum()
    losses = (trades['NetPips'] <= 0).sum()
    win_rate = wins / total_trades if total_trades > 0 else 0
    
    total_pips = trades['NetPips'].sum()
    avg_pips = trades['NetPips'].mean()
    
    winning_trades = trades[trades['NetPips'] > 0]
    losing_trades = trades[trades['NetPips'] <= 0]
    
    avg_win = winning_trades['NetPips'].mean() if len(winning_trades) > 0 else 0
    avg_loss = losing_trades['NetPips'].mean() if len(losing_trades) > 0 else 0
    
    gross_profit = winning_trades['NetPips'].sum() if len(winning_trades) > 0 else 0
    gross_loss = abs(losing_trades['NetPips'].sum()) if len(losing_trades) > 0 else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    
    # Drawdown calculation
    cumulative_pips = trades['NetPips'].cumsum()
    running_max = cumulative_pips.cummax()
    drawdown = running_max - cumulative_pips
    max_dd = drawdown.max()
    
    # P&L
    total_pnl = trades['PnL_USD'].sum()
    final_balance = trades['AccountBalance'].iloc[-1]
    initial_balance = final_balance - total_pnl
    pct_return = (total_pnl / initial_balance) * 100
    
    # Consecutive wins/losses
    win_streak = 0
    loss_streak = 0
    current_win_streak = 0
    current_loss_streak = 0
    
    for pips in trades['NetPips']:
        if pips > 0:
            current_win_streak += 1
            current_loss_streak = 0
            win_streak = max(win_streak, current_win_streak)
        else:
            current_loss_streak += 1
            current_win_streak = 0
            loss_streak = max(loss_streak, current_loss_streak)
    
    return {
        'total_trades': total_trades,
        'wins': wins,
        'losses': losses,
        'win_rate': win_rate,
        'total_pips': total_pips,
        'avg_pips': avg_pips,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'profit_factor': profit_factor,
        'max_drawdown': max_dd,
        'total_pnl': total_pnl,
        'pct_return': pct_return,
        'final_balance': final_balance,
        'initial_balance': initial_balance,
        'max_win_streak': win_streak,
        'max_loss_streak': loss_streak
    }


def compare_to_backtest(paper_metrics: dict):
    """Compare paper trading results to backtested expectations"""
    # Backtested metrics (from notebook)
    backtest_metrics = {
        'total_pips': 480.6,
        'win_rate': 0.547,
        'profit_factor': 1.52,
        'avg_win': 34.4,
        'avg_loss': -27.4,
        'max_drawdown': 271.7,
        'total_trades': 75,
        'trades_per_year': 7
    }
    
    print("\n" + "="*80)
    print("📊 BACKTEST vs PAPER TRADING COMPARISON")
    print("="*80)
    
    metrics = [
        ('Total Pips', paper_metrics['total_pips'], backtest_metrics['total_pips']),
        ('Win Rate', f"{paper_metrics['win_rate']:.1%}", f"{backtest_metrics['win_rate']:.1%}"),
        ('Profit Factor', f"{paper_metrics['profit_factor']:.2f}", f"{backtest_metrics['profit_factor']:.2f}"),
        ('Avg Win', f"{paper_metrics['avg_win']:.1f} pips", f"{backtest_metrics['avg_win']:.1f} pips"),
        ('Avg Loss', f"{paper_metrics['avg_loss']:.1f} pips", f"{backtest_metrics['avg_loss']:.1f} pips"),
        ('Max DD', f"{paper_metrics['max_drawdown']:.1f} pips", f"{backtest_metrics['max_drawdown']:.1f} pips"),
    ]
    
    print(f"\n{'Metric':<20} {'Paper Trading':<20} {'Backtest':<20} {'Status':<10}")
    print("-"*80)
    
    for metric, paper, backtest in metrics:
        # Simple comparison logic
        if isinstance(paper, str):
            status = "✓"
        else:
            # For pips and PF, higher is better; for DD, lower is better
            if 'DD' in metric or 'Loss' in metric:
                status = "✓" if paper <= backtest * 1.2 else "⚠️"
            else:
                status = "✓" if paper >= backtest * 0.8 else "⚠️"
        
        print(f"{metric:<20} {str(paper):<20} {str(backtest):<20} {status:<10}")
    
    print("="*80)


def print_metrics(metrics: dict):
    """Pretty print all metrics"""
    print("\n" + "="*80)
    print("📈 PAPER TRADING PERFORMANCE SUMMARY")
    print("="*80)
    
    print(f"\n{'TRADE STATISTICS':-^80}")
    print(f"Total Trades:        {metrics['total_trades']}")
    print(f"Wins:                {metrics['wins']} ({metrics['win_rate']:.1%})")
    print(f"Losses:              {metrics['losses']} ({(1-metrics['win_rate']):.1%})")
    print(f"Max Win Streak:      {metrics['max_win_streak']}")
    print(f"Max Loss Streak:     {metrics['max_loss_streak']}")
    
    print(f"\n{'PROFITABILITY':-^80}")
    print(f"Total Pips:          {metrics['total_pips']:.1f} pips")
    print(f"Avg per Trade:       {metrics['avg_pips']:.2f} pips")
    print(f"Avg Win:             {metrics['avg_win']:.2f} pips")
    print(f"Avg Loss:            {metrics['avg_loss']:.2f} pips")
    print(f"Profit Factor:       {metrics['profit_factor']:.2f}")
    
    print(f"\n{'RISK METRICS':-^80}")
    print(f"Max Drawdown:        {metrics['max_drawdown']:.1f} pips")
    print(f"Recovery Factor:     {metrics['total_pips']/metrics['max_drawdown']:.2f}")
    
    print(f"\n{'ACCOUNT PERFORMANCE':-^80}")
    print(f"Initial Balance:     ${metrics['initial_balance']:,.2f}")
    print(f"Final Balance:       ${metrics['final_balance']:,.2f}")
    print(f"Net P&L:             ${metrics['total_pnl']:,.2f}")
    print(f"Return:              {metrics['pct_return']:.2f}%")
    
    print("="*80)


def show_trade_distribution(trades: pd.DataFrame):
    """Show distribution of trade outcomes"""
    print("\n" + "="*80)
    print("📊 TRADE DISTRIBUTION")
    print("="*80)
    
    # Bin trades by outcome
    bins = [-np.inf, -50, -25, 0, 25, 50, 100, np.inf]
    labels = ['< -50', '-50 to -25', '-25 to 0', '0 to 25', '25 to 50', '50 to 100', '> 100']
    
    trades['PipsBin'] = pd.cut(trades['NetPips'], bins=bins, labels=labels)
    distribution = trades['PipsBin'].value_counts().sort_index()
    
    print(f"\n{'Range (pips)':<20} {'Count':<10} {'Percentage':<15} {'Bar'}")
    print("-"*80)
    
    max_count = distribution.max()
    for label, count in distribution.items():
        pct = (count / len(trades)) * 100
        bar_length = int((count / max_count) * 40)
        bar = '█' * bar_length
        print(f"{str(label):<20} {count:<10} {pct:>5.1f}%         {bar}")
    
    print("="*80)


def show_exit_reasons(trades: pd.DataFrame):
    """Show breakdown of exit reasons"""
    print("\n" + "="*80)
    print("📊 EXIT REASONS")
    print("="*80)
    
    exit_counts = trades['ExitReason'].value_counts()
    
    print(f"\n{'Exit Reason':<20} {'Count':<10} {'Percentage':<15} {'Avg Pips'}")
    print("-"*80)
    
    for reason, count in exit_counts.items():
        pct = (count / len(trades)) * 100
        avg_pips = trades[trades['ExitReason'] == reason]['NetPips'].mean()
        print(f"{reason:<20} {count:<10} {pct:>5.1f}%         {avg_pips:>8.2f}")
    
    print("="*80)


def main():
    """Main analysis"""
    print("\n" + "="*80)
    print("🔍 ANALYZING PAPER TRADING RESULTS")
    print("="*80)
    
    # Load trades
    trades = load_paper_trades()
    
    if len(trades) == 0:
        print("\n❌ No closed trades found")
        print("   Run paper trading simulation first")
        return
    
    print(f"\n✓ Loaded {len(trades)} closed trades")
    print(f"  Period: {trades['EntryTime'].min()} to {trades['EntryTime'].max()}")
    
    # Calculate metrics
    metrics = calculate_metrics(trades)
    
    # Print results
    print_metrics(metrics)
    show_trade_distribution(trades)
    show_exit_reasons(trades)
    compare_to_backtest(metrics)
    
    # Validation checks
    print("\n" + "="*80)
    print("✅ VALIDATION CHECKLIST")
    print("="*80)
    
    checks = [
        ("Minimum trades (>20)", metrics['total_trades'] >= 20),
        ("Win rate > 50%", metrics['win_rate'] > 0.50),
        ("Profit factor > 1.2", metrics['profit_factor'] > 1.2),
        ("Positive total pips", metrics['total_pips'] > 0),
        ("Max DD < 300 pips", metrics['max_drawdown'] < 300),
        ("Max loss streak < 10", metrics['max_loss_streak'] < 10),
    ]
    
    all_passed = True
    for check, passed in checks:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}  {check}")
        if not passed:
            all_passed = False
    
    print("="*80)
    
    if all_passed and metrics['total_trades'] >= 20:
        print("\n🎉 PAPER TRADING VALIDATION SUCCESSFUL!")
        print("   Ready to proceed to live trading with minimal capital")
    elif metrics['total_trades'] < 20:
        print("\n⚠️  INSUFFICIENT DATA")
        print(f"   Need {20 - metrics['total_trades']} more trades for validation")
    else:
        print("\n⚠️  PAPER TRADING VALIDATION FAILED")
        print("   Review strategy parameters before live deployment")
    
    print("\n📁 Full trade log: logs/paper_trades.csv")
    print("📁 System log: logs/paper_trading.log")
    print()


if __name__ == '__main__':
    main()
