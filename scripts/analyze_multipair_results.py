#!/usr/bin/env python3
"""
Analyze Multi-Pair H1 Backtest Results

This script provides comprehensive analysis of multi-pair trading performance,
including per-pair breakdown, correlation analysis, and equity curve visualization.

Usage:
    python analyze_multipair_results.py reports/backtests/multipair_h1_trades_TIMESTAMP.csv
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import sys
from datetime import datetime


def load_results(trades_file: str) -> pd.DataFrame:
    """Load trades from CSV"""
    df = pd.read_csv(trades_file, parse_dates=['entry_time', 'exit_time'])
    return df


def print_summary_stats(trades_df: pd.DataFrame):
    """Print overall performance summary"""
    print("\n" + "="*80)
    print("OVERALL PERFORMANCE SUMMARY")
    print("="*80)
    
    total_trades = len(trades_df)
    wins = len(trades_df[trades_df['net_pips'] > 0])
    losses = len(trades_df[trades_df['net_pips'] < 0])
    breakeven = len(trades_df[trades_df['net_pips'] == 0])
    
    print(f"\n📊 TRADE STATISTICS:")
    print(f"   Total trades:      {total_trades:,}")
    print(f"   Winning:           {wins} ({wins/total_trades*100:.1f}%)")
    print(f"   Losing:            {losses} ({losses/total_trades*100:.1f}%)")
    print(f"   Breakeven:         {breakeven}")
    
    total_pips = trades_df['net_pips'].sum()
    avg_pips = trades_df['net_pips'].mean()
    
    print(f"\n💰 PIPS PERFORMANCE:")
    print(f"   Total pips:        {total_pips:+,.0f}")
    print(f"   Average per trade: {avg_pips:+.2f}")
    print(f"   Best trade:        {trades_df['net_pips'].max():+.2f} pips")
    print(f"   Worst trade:       {trades_df['net_pips'].min():+.2f} pips")
    
    if wins > 0:
        avg_win = trades_df[trades_df['net_pips'] > 0]['net_pips'].mean()
    else:
        avg_win = 0
    
    if losses > 0:
        avg_loss = trades_df[trades_df['net_pips'] < 0]['net_pips'].mean()
        winning_pips = trades_df[trades_df['net_pips'] > 0]['net_pips'].sum()
        losing_pips = abs(trades_df[trades_df['net_pips'] < 0]['net_pips'].sum())
        profit_factor = winning_pips / losing_pips if losing_pips > 0 else float('inf')
    else:
        avg_loss = 0
        profit_factor = float('inf')
    
    print(f"\n📈 TRADE QUALITY:")
    print(f"   Average win:       {avg_win:+.2f} pips")
    print(f"   Average loss:      {avg_loss:.2f} pips")
    print(f"   Win/Loss ratio:    {abs(avg_win/avg_loss):.2f}x" if avg_loss != 0 else "   Win/Loss ratio:    N/A")
    print(f"   Profit factor:     {profit_factor:.2f}")
    
    # Time analysis
    start = trades_df['entry_time'].min()
    end = trades_df['exit_time'].max()
    years = (end - start).days / 365.25
    
    print(f"\n⏱️  TIME ANALYSIS:")
    print(f"   Period:            {start.date()} to {end.date()}")
    print(f"   Duration:          {years:.1f} years")
    print(f"   Trades per year:   {total_trades/years:.0f}")
    print(f"   Pips per year:     {total_pips/years:+,.0f}")


def analyze_by_pair(trades_df: pd.DataFrame):
    """Analyze performance broken down by currency pair"""
    print("\n" + "="*80)
    print("PER-PAIR PERFORMANCE BREAKDOWN")
    print("="*80)
    
    pair_stats = trades_df.groupby('pair').agg({
        'net_pips': ['sum', 'mean', 'count'],
        'profit_usd': 'sum'
    }).round(2)
    
    pair_stats.columns = ['Total Pips', 'Avg Pips', 'Trades', 'Profit USD']
    pair_stats = pair_stats.sort_values('Total Pips', ascending=False)
    
    # Calculate win rate per pair
    win_rates = trades_df.groupby('pair').apply(
        lambda x: (x['net_pips'] > 0).sum() / len(x) * 100
    )
    pair_stats['Win Rate %'] = win_rates.round(1)
    
    print(f"\n🏆 TOP 10 PERFORMING PAIRS:")
    print(pair_stats.head(10).to_string())
    
    print(f"\n❌ BOTTOM 5 PERFORMING PAIRS:")
    print(pair_stats.tail(5).to_string())
    
    # Profitability summary
    profitable_pairs = len(pair_stats[pair_stats['Total Pips'] > 0])
    unprofitable_pairs = len(pair_stats[pair_stats['Total Pips'] <= 0])
    
    print(f"\n📊 PROFITABILITY:")
    print(f"   Profitable pairs:   {profitable_pairs}/{len(pair_stats)} ({profitable_pairs/len(pair_stats)*100:.1f}%)")
    print(f"   Unprofitable pairs: {unprofitable_pairs}/{len(pair_stats)}")
    
    return pair_stats


def analyze_exit_reasons(trades_df: pd.DataFrame):
    """Analyze performance by exit reason"""
    print("\n" + "="*80)
    print("EXIT REASON ANALYSIS")
    print("="*80)
    
    exit_stats = trades_df.groupby('exit_reason').agg({
        'net_pips': ['sum', 'mean', 'count']
    }).round(2)
    
    exit_stats.columns = ['Total Pips', 'Avg Pips', 'Count']
    
    print("\n" + exit_stats.to_string())
    
    # Calculate percentage
    total = len(trades_df)
    print(f"\n📊 EXIT DISTRIBUTION:")
    for reason in trades_df['exit_reason'].unique():
        count = len(trades_df[trades_df['exit_reason'] == reason])
        pct = count / total * 100
        avg_pips = trades_df[trades_df['exit_reason'] == reason]['net_pips'].mean()
        print(f"   {reason:12s}: {count:4d} trades ({pct:5.1f}%) | Avg: {avg_pips:+.2f} pips")


def plot_equity_curve(trades_df: pd.DataFrame, output_dir: Path):
    """Plot cumulative equity curve"""
    trades_df = trades_df.sort_values('exit_time')
    trades_df['cumulative_pips'] = trades_df['net_pips'].cumsum()
    trades_df['cumulative_usd'] = trades_df['profit_usd'].cumsum()
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
    
    # Pips equity curve
    ax1.plot(trades_df['exit_time'], trades_df['cumulative_pips'], linewidth=2)
    ax1.fill_between(trades_df['exit_time'], 0, trades_df['cumulative_pips'], alpha=0.3)
    ax1.axhline(y=0, color='black', linestyle='--', alpha=0.5)
    ax1.set_title('Cumulative Net Pips Over Time', fontsize=14, fontweight='bold')
    ax1.set_xlabel('Date')
    ax1.set_ylabel('Cumulative Pips')
    ax1.grid(True, alpha=0.3)
    
    # USD equity curve
    ax2.plot(trades_df['exit_time'], trades_df['cumulative_usd'], linewidth=2, color='green')
    ax2.fill_between(trades_df['exit_time'], 0, trades_df['cumulative_usd'], alpha=0.3, color='green')
    ax2.axhline(y=0, color='black', linestyle='--', alpha=0.5)
    ax2.set_title('Cumulative Profit USD Over Time', fontsize=14, fontweight='bold')
    ax2.set_xlabel('Date')
    ax2.set_ylabel('Cumulative Profit (USD)')
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    output_file = output_dir / 'multipair_equity_curve.png'
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"\n💾 Equity curve saved to: {output_file}")
    plt.close()


def plot_pair_performance(pair_stats: pd.DataFrame, output_dir: Path):
    """Plot performance by pair"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
    
    # Total pips by pair
    top_15 = pair_stats.sort_values('Total Pips', ascending=True).tail(15)
    top_15['Total Pips'].plot(kind='barh', ax=ax1, color='steelblue')
    ax1.set_title('Top 15 Pairs by Total Pips', fontsize=12, fontweight='bold')
    ax1.set_xlabel('Net Pips')
    ax1.axvline(x=0, color='black', linestyle='--', alpha=0.5)
    ax1.grid(True, alpha=0.3, axis='x')
    
    # Average pips per trade
    top_15_avg = pair_stats.sort_values('Avg Pips', ascending=True).tail(15)
    top_15_avg['Avg Pips'].plot(kind='barh', ax=ax2, color='coral')
    ax2.set_title('Top 15 Pairs by Avg Pips/Trade', fontsize=12, fontweight='bold')
    ax2.set_xlabel('Avg Pips per Trade')
    ax2.axvline(x=0, color='black', linestyle='--', alpha=0.5)
    ax2.grid(True, alpha=0.3, axis='x')
    
    plt.tight_layout()
    
    output_file = output_dir / 'multipair_performance_by_pair.png'
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"💾 Pair performance chart saved to: {output_file}")
    plt.close()


def plot_distributions(trades_df: pd.DataFrame, output_dir: Path):
    """Plot distribution of trade results"""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    # Pips distribution
    ax1 = axes[0, 0]
    trades_df['net_pips'].hist(bins=50, ax=ax1, edgecolor='black', alpha=0.7)
    ax1.axvline(x=0, color='red', linestyle='--', linewidth=2, label='Breakeven')
    ax1.axvline(x=trades_df['net_pips'].mean(), color='green', linestyle='--', linewidth=2, label='Mean')
    ax1.set_title('Distribution of Trade Results (Pips)', fontweight='bold')
    ax1.set_xlabel('Net Pips')
    ax1.set_ylabel('Frequency')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Win/Loss by pair
    ax2 = axes[0, 1]
    pair_winrate = trades_df.groupby('pair').apply(lambda x: (x['net_pips'] > 0).sum() / len(x) * 100)
    pair_winrate.hist(bins=20, ax=ax2, edgecolor='black', alpha=0.7, color='orange')
    ax2.axvline(x=50, color='red', linestyle='--', linewidth=2, label='50% Win Rate')
    ax2.set_title('Distribution of Win Rates by Pair', fontweight='bold')
    ax2.set_xlabel('Win Rate (%)')
    ax2.set_ylabel('Number of Pairs')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # Trades per pair
    ax3 = axes[1, 0]
    trades_per_pair = trades_df.groupby('pair').size()
    trades_per_pair.hist(bins=20, ax=ax3, edgecolor='black', alpha=0.7, color='purple')
    ax3.set_title('Distribution of Trades per Pair', fontweight='bold')
    ax3.set_xlabel('Number of Trades')
    ax3.set_ylabel('Number of Pairs')
    ax3.grid(True, alpha=0.3)
    
    # Monthly performance
    ax4 = axes[1, 1]
    trades_df['month'] = trades_df['exit_time'].dt.to_period('M')
    monthly_pips = trades_df.groupby('month')['net_pips'].sum()
    monthly_pips.plot(kind='bar', ax=ax4, color='teal', alpha=0.7)
    ax4.axhline(y=0, color='black', linestyle='--', alpha=0.5)
    ax4.set_title('Monthly Net Pips', fontweight='bold')
    ax4.set_xlabel('Month')
    ax4.set_ylabel('Net Pips')
    ax4.tick_params(axis='x', rotation=45, labelsize=8)
    ax4.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    
    output_file = output_dir / 'multipair_distributions.png'
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"💾 Distribution charts saved to: {output_file}")
    plt.close()


def main():
    """Main analysis routine"""
    if len(sys.argv) < 2:
        print("Usage: python analyze_multipair_results.py <trades_csv_file>")
        print("\nExample:")
        print("  python analyze_multipair_results.py reports/backtests/multipair_h1_trades_20260225_120000.csv")
        sys.exit(1)
    
    trades_file = sys.argv[1]
    
    if not Path(trades_file).exists():
        print(f"❌ Error: File not found: {trades_file}")
        sys.exit(1)
    
    print(f"\n📂 Loading trades from: {trades_file}")
    trades_df = load_results(trades_file)
    
    print(f"✅ Loaded {len(trades_df)} trades")
    
    # Create output directory for charts
    output_dir = Path('reports/backtests/analysis')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Run analyses
    print_summary_stats(trades_df)
    pair_stats = analyze_by_pair(trades_df)
    analyze_exit_reasons(trades_df)
    
    # Generate charts
    print("\n" + "="*80)
    print("GENERATING VISUALIZATIONS")
    print("="*80)
    
    plot_equity_curve(trades_df, output_dir)
    plot_pair_performance(pair_stats, output_dir)
    plot_distributions(trades_df, output_dir)
    
    print("\n" + "="*80)
    print("✅ ANALYSIS COMPLETE")
    print("="*80)
    print(f"\nAll charts saved to: {output_dir}/")
    print("\nGenerated files:")
    print("  - multipair_equity_curve.png")
    print("  - multipair_performance_by_pair.png")
    print("  - multipair_distributions.png")
    print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    main()
