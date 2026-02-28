"""
Multi-Pair H1 Hypothesis Test: Exhaustion + Failure-to-Continue Pattern

Tests the two-bar mean reversion pattern across all available H1 FX pairs:
1. Exhaustion bar: Directional pressure ±2, range expansion, extreme close
2. Failure bar: Opposite direction, no new high/low

Exit Strategy:
- Stop Loss: 10 pips fixed
- Trailing Stop: Activates after +4 pips profit, trails at 3 pips distance
- Max Hold: 5 bars (5 hours)

Expected: Mean reversion opposite to exhaustion direction
"""

import sys
import os
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# Set project root
project_root = Path(__file__).parent
os.chdir(project_root)
sys.path.insert(0, str(project_root))

import numpy as np
import pandas as pd
from scipy import stats
from datetime import datetime
from typing import Dict, Tuple, List

# Import cost model
from src.backtest.cost_model import get_cost_model, FXCostModel

print("="*80)
print(" " * 20 + "EXHAUSTION + FAILURE PATTERN TEST")
print(" " * 25 + "Multi-Pair H1 Analysis")
print("="*80)
print(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
print("="*80)


class ExhaustionFailureDetector:
    """
    Detect two-bar exhaustion + failure-to-continue pattern.
    
    Pattern:
    1. Exhaustion Bar (N): Directional pressure ±2, range expansion, extreme close
    2. Failure Bar (N+1): Moves opposite direction, fails to make new extremes
    
    Entry: Close of failure bar
    Direction: Opposite to exhaustion
    """
    
    def __init__(self):
        pass
    
    def detect_signals(self, df: pd.DataFrame, pair: str) -> pd.DataFrame:
        """
        Detect all exhaustion + failure signals in the data.
        
        Returns DataFrame with columns:
        - signal_idx: Index where signal occurs (Bar N+1 close)
        - direction: 'LONG' or 'SHORT'
        - entry_price: Close price at signal_idx
        - exhaustion_idx: Index of exhaustion bar (Bar N)
        """
        # Calculate components (vectorized)
        df = df.copy().reset_index(drop=False)
        df['bar_direction'] = np.sign(df['close'] - df['open'])
        df['bar_range'] = df['high'] - df['low']
        
        # Rolling 2-bar direction sum
        df['pressure'] = df['bar_direction'].rolling(2, min_periods=2).sum()
        
        # Range expansion: current range > 0.8 × median(10 bars)
        df['median_range'] = df['bar_range'].shift(1).rolling(10, min_periods=10).median()
        df['range_expanded'] = df['bar_range'] > (0.8 * df['median_range'])
        
        # Close percentile within bar
        df['close_pct_in_bar'] = (df['close'] - df['low']) / (df['bar_range'] + 1e-10)
        
        # Shift columns to get next bar
        df['next_bar_direction'] = df['bar_direction'].shift(-1)
        df['next_high'] = df['high'].shift(-1)
        df['next_low'] = df['low'].shift(-1)
        df['next_close'] = df['close'].shift(-1)
        
        # Vectorized detection for BULLISH exhaustion (SHORT setup)
        bullish_exhaustion = (
            (df['pressure'] == 2) &
            (df['range_expanded']) &
            (df['close_pct_in_bar'] >= 0.65)
        )
        
        bullish_failure = (
            (df['next_bar_direction'] < 0) &  # Next bar bearish
            (df['next_high'] <= df['high'])    # No new high
        )
        
        short_signals = bullish_exhaustion & bullish_failure
        
        # Vectorized detection for BEARISH exhaustion (LONG setup)
        bearish_exhaustion = (
            (df['pressure'] == -2) &
            (df['range_expanded']) &
            (df['close_pct_in_bar'] <= 0.35)
        )
        
        bearish_failure = (
            (df['next_bar_direction'] > 0) &  # Next bar bullish
            (df['next_low'] >= df['low'])      # No new low
        )
        
        long_signals = bearish_exhaustion & bearish_failure
        
        # Collect results
        signals = []
        
        # SHORT signals (from bullish exhaustion + failure)
        short_indices = df[short_signals].index.tolist()
        for i in short_indices:
            if i + 1 < len(df):
                signals.append({
                    'signal_idx': i + 1,
                    'direction': 'SHORT',
                    'entry_price': df.loc[i + 1, 'close'],
                    'exhaustion_idx': i,
                    'exhaustion_high': df.loc[i, 'high'],
                    'timestamp': df.loc[i + 1, 'timestamp']
                })
        
        # LONG signals (from bearish exhaustion + failure)
        long_indices = df[long_signals].index.tolist()
        for i in long_indices:
            if i + 1 < len(df):
                signals.append({
                    'signal_idx': i + 1,
                    'direction': 'LONG',
                    'entry_price': df.loc[i + 1, 'close'],
                    'exhaustion_idx': i,
                    'exhaustion_low': df.loc[i, 'low'],
                    'timestamp': df.loc[i + 1, 'timestamp']
                })
        
        return pd.DataFrame(signals)


def load_h1_pair(pair_name: str) -> pd.DataFrame:
    """Load H1 data for a specific pair."""
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
    
    if pair_name not in file_map:
        raise ValueError(f"Unknown pair: {pair_name}")
    
    file_path = Path('data/raw') / file_map[pair_name]
    
    if not file_path.exists():
        raise FileNotFoundError(f"Data file not found: {file_path}")
    
    # Read CSV
    df = pd.read_csv(
        file_path,
        names=['date', 'time', 'open', 'high', 'low', 'close', 'volume']
    )
    
    # Combine date and time
    df['timestamp'] = pd.to_datetime(df['date'] + ' ' + df['time'])
    df = df.set_index('timestamp')
    df = df[['open', 'high', 'low', 'close', 'volume']]
    
    # Ensure UTC timezone
    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC')
    
    df = df.sort_index()
    
    # Remove duplicates
    df = df[~df.index.duplicated(keep='first')]
    
    return df


def calculate_forward_returns_with_exits(
    df: pd.DataFrame,
    signals: pd.DataFrame,
    pair: str
) -> pd.DataFrame:
    """
    Calculate forward returns with realistic exit logic:
    - Stop Loss: 10 pips fixed
    - Trailing Stop: Activates after +4 pips, trails at 3 pips
    - Max Hold: 5 bars
    
    Returns signal DataFrame with realized PnL.
    """
    results = signals.copy()
    
    # Calculate pip multiplier (0.0001 for 4-decimal pairs, 0.01 for JPY)
    pip_value = 0.01 if 'JPY' in pair else 0.0001
    
    returns = []
    exit_reasons = []
    
    for idx, signal in signals.iterrows():
        signal_idx = signal['signal_idx']
        entry_price = signal['entry_price']
        direction = 1 if signal['direction'] == 'LONG' else -1
        
        # Initialize exit tracking
        max_profit = 0
        exit_price = None
        exit_reason = None
        
        # Simulate bar-by-bar
        for bar_offset in range(1, 6):  # Max 5 bars
            if signal_idx + bar_offset >= len(df):
                break
            
            current_bar = df.iloc[signal_idx + bar_offset]
            high = current_bar['high']
            low = current_bar['low']
            close = current_bar['close']
            
            # Calculate profit in pips at this bar
            if direction == 1:  # LONG
                profit_pips = (high - entry_price) / pip_value
                loss_pips = (entry_price - low) / pip_value
            else:  # SHORT
                profit_pips = (entry_price - low) / pip_value
                loss_pips = (high - entry_price) / pip_value
            
            # Update max profit
            max_profit = max(max_profit, profit_pips)
            
            # Check Stop Loss (-10 pips)
            if loss_pips >= 10:
                if direction == 1:
                    exit_price = entry_price - 10 * pip_value
                else:
                    exit_price = entry_price + 10 * pip_value
                exit_reason = 'SL'
                break
            
            # Check Trailing Stop (activates after +4 pips, trails at 3 pips)
            if max_profit >= 4:
                trailing_stop_level = max_profit - 3
                current_profit = (close - entry_price) / pip_value * direction
                
                if current_profit <= trailing_stop_level:
                    if direction == 1:
                        exit_price = entry_price + trailing_stop_level * pip_value
                    else:
                        exit_price = entry_price - trailing_stop_level * pip_value
                    exit_reason = 'TRAIL'
                    break
            
            # Check if this is max hold
            if bar_offset == 5:
                exit_price = close
                exit_reason = 'TIME'
                break
        
        # Calculate return
        if exit_price is None:
            # End of data reached
            exit_price = entry_price
            exit_reason = 'EOD'
        
        pnl_pips = (exit_price - entry_price) / pip_value * direction
        returns.append(pnl_pips)
        exit_reasons.append(exit_reason)
    
    results['pnl_pips'] = returns
    results['exit_reason'] = exit_reasons
    
    return results


def calculate_pair_metrics(pair: str, results: dict, cost_model) -> dict:
    """Calculate comprehensive metrics for a pair."""
    signals = results['signals']
    
    # Get realized PnL
    returns_gross = signals['pnl_pips'].values
    
    # Apply transaction costs (round-trip)
    # Each trade: entry cost + exit cost
    cost_per_trade = cost_model.total_bps * 2  # Round trip
    returns_net = returns_gross - cost_per_trade
    
    # Calculate statistics
    metrics = {
        'pair': pair,
        'signal_count': len(signals),
        'long_count': (signals['direction'] == 'LONG').sum(),
        'short_count': (signals['direction'] == 'SHORT').sum(),
        
        # Gross metrics
        'gross_pnl_mean': returns_gross.mean(),
        'gross_pnl_median': np.median(returns_gross),
        'gross_pnl_std': returns_gross.std(),
        'gross_pnl_total': returns_gross.sum(),
        
        # Net metrics (after costs)
        'net_pnl_mean': returns_net.mean(),
        'net_pnl_median': np.median(returns_net),
        'net_pnl_std': returns_net.std(),
        'net_pnl_total': returns_net.sum(),
        
        # Win rate and profit factor
        'win_rate': (returns_net > 0).sum() / len(returns_net) if len(returns_net) > 0 else 0,
        'wins': (returns_net > 0).sum(),
        'losses': (returns_net < 0).sum(),
        
        # Profit factor
        'gross_wins': returns_net[returns_net > 0].sum() if (returns_net > 0).any() else 0,
        'gross_losses': abs(returns_net[returns_net < 0].sum()) if (returns_net < 0).any() else 1,
        
        # Statistical tests
        't_statistic': stats.ttest_1samp(returns_net, 0)[0] if len(returns_net) > 1 else 0,
        'p_value': stats.ttest_1samp(returns_net, 0)[1] if len(returns_net) > 1 else 1.0,
        
        # Cost info
        'cost_per_trade': cost_per_trade,
        'total_costs': cost_per_trade * len(returns_net),
        
        # Returns distribution
        'returns_gross': returns_gross,
        'returns_net': returns_net
    }
    
    # Profit factor
    if metrics['gross_losses'] > 0:
        metrics['profit_factor'] = metrics['gross_wins'] / metrics['gross_losses']
    else:
        metrics['profit_factor'] = np.inf if metrics['gross_wins'] > 0 else 0
    
    # Categorization
    is_significant = metrics['p_value'] < 0.05 and metrics['net_pnl_mean'] > 0
    is_viable = metrics['net_pnl_mean'] >= 2.0  # At least 2 pips net edge
    
    if is_significant and is_viable:
        metrics['status'] = 'PASS'
    elif is_significant or is_viable:
        metrics['status'] = 'MARGINAL'
    else:
        metrics['status'] = 'FAIL'
    
    return metrics


def generate_html_dashboard(pair_metrics: dict, output_path: str):
    """Generate comprehensive interactive HTML dashboard using Plotly."""
    
    # Create metrics DataFrame for easier manipulation
    metrics_df = pd.DataFrame([m for m in pair_metrics.values()])
    metrics_df = metrics_df.sort_values('net_pnl_total', ascending=False)
    
    # Calculate summary stats
    total_pairs = len(metrics_df)
    pass_count = (metrics_df['status'] == 'PASS').sum()
    marginal_count = (metrics_df['status'] == 'MARGINAL').sum()
    fail_count = (metrics_df['status'] == 'FAIL').sum()
    profitable_count = (metrics_df['net_pnl_total'] > 0).sum()
    
    # Decision logic
    pass_pct = pass_count / total_pairs * 100
    if pass_pct >= 70:
        final_decision = '✅ PROCEED'
        decision_color = 'green'
        decision_text = f'Strategy validated on {pass_count}/{total_pairs} pairs ({pass_pct:.0f}%). Deploy across all validated pairs.'
    elif pass_pct >= 40:
        final_decision = '⚠️ SELECTIVE'
        decision_color = 'orange'
        decision_text = f'Strategy works on {pass_count}/{total_pairs} pairs ({pass_pct:.0f}%). Deploy only on PASS pairs.'
    else:
        final_decision = '❌ REJECT'
        decision_color = 'red'
        decision_text = f'Strategy validated on only {pass_count}/{total_pairs} pairs ({pass_pct:.0f}%). Likely overfit or random.'
    
    # Start HTML
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Exhaustion+Failure H1 Multi-Pair Test</title>
    <script src="https://cdn.plot.ly/plotly-2.18.0.min.js"></script>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 0 20px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #34495e;
            margin-top: 30px;
            border-left: 4px solid #3498db;
            padding-left: 15px;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
        }}
        .summary-box {{
            background-color: {decision_color if decision_color != 'orange' else '#ff9800'};
            color: white;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
            font-size: 18px;
            font-weight: bold;
            text-align: center;
        }}
        .metric {{
            display: inline-block;
            margin: 10px 20px;
        }}
        .metric-label {{
            font-size: 14px;
            color: rgba(255,255,255,0.8);
        }}
        .metric-value {{
            font-size: 28px;
            font-weight: bold;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th {{
            background-color: #3498db;
            color: white;
            padding: 12px;
            text-align: left;
        }}
        td {{
            padding: 10px;
            border-bottom: 1px solid #ddd;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
        .status-PASS {{
            color: green;
            font-weight: bold;
        }}
        .status-MARGINAL {{
            color: orange;
            font-weight: bold;
        }}
        .status-FAIL {{
            color: red;
            font-weight: bold;
        }}
        .chart-container {{
            margin: 30px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔬 Exhaustion + Failure-to-Continue Pattern</h1>
            <h2>Multi-Pair H1 Hypothesis Test</h2>
            <p><strong>Test Date:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
            <p><strong>Pairs Tested:</strong> {total_pairs} | <strong>Timeframe:</strong> H1 (Hourly)</p>
        </div>
        
        <div class="summary-box">
            <div style="font-size: 32px; margin-bottom: 10px;">{final_decision}</div>
            <div style="font-size: 16px; font-weight: normal;">{decision_text}</div>
        </div>
        
        <h2>📊 Executive Summary</h2>
        <div style="background-color: #ecf0f1; padding: 20px; border-radius: 8px;">
            <div class="metric">
                <div class="metric-label">Total Pairs</div>
                <div class="metric-value" style="color: #3498db;">{total_pairs}</div>
            </div>
            <div class="metric">
                <div class="metric-label">✅ PASS</div>
                <div class="metric-value" style="color: green;">{pass_count}</div>
            </div>
            <div class="metric">
                <div class="metric-label">⚠️ MARGINAL</div>
                <div class="metric-value" style="color: orange;">{marginal_count}</div>
            </div>
            <div class="metric">
                <div class="metric-label">❌ FAIL</div>
                <div class="metric-value" style="color: red;">{fail_count}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Profitable</div>
                <div class="metric-value" style="color: #27ae60;">{profitable_count}/{total_pairs}</div>
            </div>
        </div>
        
        <h2>📈 Cross-Pair Comparison Table</h2>
        <table id="metricsTable">
            <thead>
                <tr>
                    <th>Pair</th>
                    <th>Signals</th>
                    <th>Net PnL (pips)</th>
                    <th>Avg/Trade</th>
                    <th>Win %</th>
                    <th>Profit Factor</th>
                    <th>p-value</th>
                    <th>Significant</th>
                    <th>Viable</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
    """
    
    # Add table rows
    for _, row in metrics_df.iterrows():
        significant = '✅' if row['p_value'] < 0.05 and row['net_pnl_mean'] > 0 else '❌'
        viable = '✅' if row['net_pnl_mean'] >= 2.0 else '❌'
        
        html += f"""
                <tr>
                    <td><strong>{row['pair']}</strong></td>
                    <td>{row['signal_count']}</td>
                    <td style="color: {'green' if row['net_pnl_total'] > 0 else 'red'}; font-weight: bold;">
                        {row['net_pnl_total']:.0f}
                    </td>
                    <td>{row['net_pnl_mean']:.2f}</td>
                    <td>{row['win_rate']*100:.1f}%</td>
                    <td>{row['profit_factor']:.2f}</td>
                    <td>{row['p_value']:.4f}</td>
                    <td>{significant}</td>
                    <td>{viable}</td>
                    <td class="status-{row['status']}">{row['status']}</td>
                </tr>
        """
    
    html += """
            </tbody>
        </table>
        
        <h2>🎯 Decision Matrix</h2>
        <div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 20px; margin: 20px 0;">
            <h3>Recommendation</h3>
            <p><strong style="font-size: 20px;">{}</strong></p>
            <p>{}</p>
            
            <h4>Validated Pairs (PASS):</h4>
            <ul>
    """.format(final_decision, decision_text)
    
    # List validated pairs
    pass_pairs = metrics_df[metrics_df['status'] == 'PASS']['pair'].tolist()
    if pass_pairs:
        for pair in pass_pairs:
            html += f"<li><strong>{pair}</strong></li>"
    else:
        html += "<li><em>None</em></li>"
    
    html += """
            </ul>
            
            <h4>Implementation Notes:</h4>
            <ul>
                <li>Deploy only on pairs with PASS status</li>
                <li>Use fixed 10-pip stop loss + trailing stop (activate at +4 pips, trail at 3 pips)</li>
                <li>Maximum hold period: 5 hours</li>
                <li>Transaction costs already accounted for in metrics</li>
                <li>Monitor performance continuously and halt if edge deteriorates</li>
            </ul>
        </div>
    </div>
</body>
</html>
    """
    
    # Write to file
    os.makedirs('dashboards', exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"\n✅ Dashboard saved to: {output_path}")
    return output_path


def main():
    """Main execution function."""
    
    # Load all available pairs
    pairs_to_test = ['GBPUSD', 'EURUSD', 'USDJPY', 'USDCAD', 'NZDUSD', 'USDCHF', 'NZDJPY', 'AUDNZD']
    data_dict = {}
    
    print("\n" + "="*80)
    print("LOADING H1 DATA FOR ALL PAIRS")
    print("="*80)
    
    for pair in pairs_to_test:
        try:
            df = load_h1_pair(pair)
            data_dict[pair] = df
            print(f"✅ {pair:8s} | {len(df):,} bars | {df.index[0].date()} to {df.index[-1].date()}")
        except Exception as e:
            print(f"❌ {pair:8s} | Error: {e}")
    
    print(f"\n✅ Successfully loaded {len(data_dict)}/{len(pairs_to_test)} pairs")
    
    # Detect patterns
    print("\n" + "="*80)
    print("DETECTING EXHAUSTION + FAILURE PATTERNS")
    print("="*80)
    
    detector = ExhaustionFailureDetector()
    all_results = {}
    
    for pair in data_dict.keys():
        print(f"\n{pair}:")
        df = data_dict[pair]
        
        # Detect signals
        signals = detector.detect_signals(df, pair)
        
        if len(signals) == 0:
            print(f"  ⚠️  No signals found")
            all_results[pair] = None
            continue
        
        print(f"  ✅ Found {len(signals)} signals")
        print(f"     LONG:  {(signals['direction'] == 'LONG').sum()}")
        print(f"     SHORT: {(signals['direction'] == 'SHORT').sum()}")
        
        # Calculate forward returns with exit logic
        signals_with_returns = calculate_forward_returns_with_exits(df, signals, pair)
        
        # Store results
        all_results[pair] = {
            'df': df,
            'signals': signals_with_returns,
            'signal_count': len(signals)
        }
    
    print(f"\n{'='*80}")
    print(f"✅ Pattern detection complete for {len([r for r in all_results.values() if r is not None])} pairs")
    print(f"{'='*80}")
    
    # Calculate metrics with transaction costs
    print("\n" + "="*80)
    print("CALCULATING METRICS WITH TRANSACTION COSTS")
    print("="*80)
    
    pair_metrics = {}
    
    for pair, results in all_results.items():
        if results is None:
            continue
        
        # Get cost model for this pair
        try:
            cost_model = get_cost_model(pair)
        except KeyError:
            # Use default for pairs not in COST_MODELS
            cost_model = FXCostModel(spread_bps=1.3, slippage_bps=0.5, symbol=pair)
        
        metrics = calculate_pair_metrics(pair, results, cost_model)
        pair_metrics[pair] = metrics
        
        print(f"\n{pair}:")
        print(f"  Signals:       {metrics['signal_count']}")
        print(f"  Net PnL:       {metrics['net_pnl_mean']:.2f} pips/trade (total: {metrics['net_pnl_total']:.0f} pips)")
        print(f"  Win Rate:      {metrics['win_rate']*100:.1f}%")
        print(f"  Profit Factor: {metrics['profit_factor']:.2f}")
        print(f"  p-value:       {metrics['p_value']:.4f}")
        print(f"  Status:        {metrics['status']}")
    
    print(f"\n{'='*80}")
    print("✅ Metrics calculation complete")
    print(f"{'='*80}")
    
    # Generate HTML dashboard
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    dashboard_path = f'dashboards/exhaustion_failure_h1_multipair_{timestamp}.html'
    
    generate_html_dashboard(pair_metrics, dashboard_path)
    
    # Print final summary
    print("\n" + "="*100)
    print(" " * 40 + "FINAL SUMMARY")
    print("="*100)
    
    metrics_df = pd.DataFrame([m for m in pair_metrics.values()])
    metrics_df = metrics_df.sort_values('net_pnl_total', ascending=False)
    
    # Print table
    print(f"\n{'Pair':<10} | {'Signals':>8} | {'Net PnL':>10} | {'Win%':>6} | {'PF':>6} | {'p-value':>8} | {'Sig':>4} | {'Viable':>7} | {'Status':>10}")
    print("-" * 100)
    
    for _, row in metrics_df.iterrows():
        significant = '✅' if row['p_value'] < 0.05 and row['net_pnl_mean'] > 0 else '❌'
        viable = '✅' if row['net_pnl_mean'] >= 2.0 else '❌'
        
        print(f"{row['pair']:<10} | {row['signal_count']:>8} | {row['net_pnl_total']:>10.0f} | {row['win_rate']*100:>5.1f}% | {row['profit_factor']:>6.2f} | {row['p_value']:>8.4f} | {significant:>4} | {viable:>7} | {row['status']:>10}")
    
    # Summary stats
    print("\n" + "="*100)
    print("SUMMARY STATISTICS:")
    print("="*100)
    
    total_pairs = len(metrics_df)
    pass_count = (metrics_df['status'] == 'PASS').sum()
    marginal_count = (metrics_df['status'] == 'MARGINAL').sum()
    fail_count = (metrics_df['status'] == 'FAIL').sum()
    profitable_count = (metrics_df['net_pnl_total'] > 0).sum()
    
    print(f"\nTotal pairs tested:        {total_pairs}")
    print(f"Pairs with PASS status:    {pass_count} ({pass_count/total_pairs*100:.1f}%)")
    print(f"Pairs with MARGINAL:       {marginal_count} ({marginal_count/total_pairs*100:.1f}%)")
    print(f"Pairs with FAIL status:    {fail_count} ({fail_count/total_pairs*100:.1f}%)")
    print(f"Profitable pairs:          {profitable_count} ({profitable_count/total_pairs*100:.1f}%)")
    
    # Best and worst
    best_pair = metrics_df.iloc[0]
    worst_pair = metrics_df.iloc[-1]
    
    print(f"\n{'='*100}")
    print("BEST PERFORMING PAIR:")
    print(f"{'='*100}")
    print(f"Pair:          {best_pair['pair']}")
    print(f"Signals:       {best_pair['signal_count']}")
    print(f"Net PnL:       {best_pair['net_pnl_total']:.0f} pips total ({best_pair['net_pnl_mean']:.2f} pips/trade)")
    print(f"Win Rate:      {best_pair['win_rate']*100:.1f}%")
    print(f"Profit Factor: {best_pair['profit_factor']:.2f}")
    print(f"p-value:       {best_pair['p_value']:.4f}")
    print(f"Status:        {best_pair['status']}")
    
    print(f"\n{'='*100}")
    print("WORST PERFORMING PAIR:")
    print(f"{'='*100}")
    print(f"Pair:          {worst_pair['pair']}")
    print(f"Signals:       {worst_pair['signal_count']}")
    print(f"Net PnL:       {worst_pair['net_pnl_total']:.0f} pips total ({worst_pair['net_pnl_mean']:.2f} pips/trade)")
    print(f"Win Rate:      {worst_pair['win_rate']*100:.1f}%")
    print(f"Profit Factor: {worst_pair['profit_factor']:.2f}")
    print(f"p-value:       {worst_pair['p_value']:.4f}")
    print(f"Status:        {worst_pair['status']}")
    
    # Final decision
    print(f"\n{'='*100}")
    print("FINAL RECOMMENDATION:")
    print(f"{'='*100}")
    
    pass_pct = pass_count / total_pairs * 100
    if pass_pct >= 70:
        decision = '✅ PROCEED - Deploy across all validated pairs'
        recommendation = f'Strategy validated on {pass_count}/{total_pairs} pairs ({pass_pct:.0f}%). Strong evidence of robust edge.'
    elif pass_pct >= 40:
        decision = '⚠️  SELECTIVE - Deploy only on PASS pairs'
        recommendation = f'Strategy works on {pass_count}/{total_pairs} pairs ({pass_pct:.0f}%). Use selective deployment.'
    else:
        decision = '❌ REJECT - Do not deploy'
        recommendation = f'Strategy validated on only {pass_count}/{total_pairs} pairs ({pass_pct:.0f}%). Likely overfit or random.'
    
    print(f"\n{decision}")
    print(f"\n{recommendation}")
    
    print(f"\nValidated pairs (PASS status):")
    pass_pairs = metrics_df[metrics_df['status'] == 'PASS']['pair'].tolist()
    if pass_pairs:
        for pair in pass_pairs:
            print(f"  • {pair}")
    else:
        print("  None")
    
    print(f"\n{'='*100}")
    print(f"📊 Dashboard saved to: {dashboard_path}")
    print(f"{'='*100}\n")


if __name__ == '__main__':
    main()
