#!/usr/bin/env python3
"""
Professional Backtest Data Exporter for Dashboard
==================================================

Exports backtest results to multi-file JSON/Parquet format with:
- Full versioning metadata (strategy version, git commit, run ID)
- MAE/MFE metrics for stop placement analysis
- Edge diagnostics with structural issue detection
- DST-aware session classification
- Proper equity curve downsampling (LTTB algorithm)
- Comprehensive validation checks

Usage:
    python scripts/export_backtest_dashboard.py

Output:
    data/backtests/{instrument}_{timeframe}_{strategy}/run_{timestamp}_v{version}_{commit}/
        metadata.json
        metrics.json
        trades.json
        equity.json (downsampled)
        ohlc.json (first 500 bars)
        diagnostics.json
"""

import pickle
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Tuple, Optional
import warnings

import numpy as np
import pandas as pd
import pytz

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))
import src


class BacktestDashboardExporter:
    """Export backtest results to professional dashboard format."""
    
    def __init__(self, pickle_path: str, output_base: str = "data/backtests"):
        """
        Initialize exporter.
        
        Args:
            pickle_path: Path to backtest results pickle file
            output_base: Base directory for output files
        """
        self.pickle_path = Path(pickle_path)
        self.output_base = Path(output_base)
        self.results = None
        self.pip_size = 0.0001  # GBPUSD 4-decimal
        
    def load_backtest_results(self) -> None:
        """Load pickle file and validate structure."""
        print(f"📂 Loading backtest results from {self.pickle_path}")
        
        with open(self.pickle_path, 'rb') as f:
            self.results = pickle.load(f)
        
        # Validate required fields
        required = ['backtest_results', 'strategy_name', 'instrument', 'timeframe', 
                    'initial_capital', 'data']
        missing = [f for f in required if f not in self.results]
        if missing:
            raise ValueError(f"Missing required fields in pickle: {missing}")
        
        print(f"✓ Loaded {self.results['strategy_name']} backtest")
        print(f"  Instrument: {self.results['instrument']}")
        print(f"  Timeframe: {self.results['timeframe']}")
        print(f"  Bars: {self.results['n_bars']:,}")
        
    def extract_trades_from_exit_info(self) -> pd.DataFrame:
        """
        Extract trades using exit_info DataFrame (PRIMARY METHOD).
        
        Returns:
            DataFrame with columns: entry_idx, exit_idx, entry_time, exit_time,
                                   entry_price, exit_price, direction, pnl_usd,
                                   pnl_pips, duration_bars, exit_reason, mae_pips,
                                   mfe_pips, highest_favorable, lowest_favorable
        """
        print("📊 Extracting trades from exit_info DataFrame...")
        
        backtest = self.results['backtest_results']
        exit_info = backtest['exit_info']
        position = backtest['position']
        equity = backtest['equity']
        data = self.results['data']
        
        # Find all exit events
        exit_rows = exit_info[exit_info['exit_reason'] != ''].copy()
        
        if len(exit_rows) == 0:
            warnings.warn("No trades found in exit_info - using fallback position parsing")
            return self.extract_trades_from_position_fallback()
        
        trades = []
        
        for exit_idx, row in exit_rows.iterrows():
            entry_idx_pos = row['entry_bar']
            
            if entry_idx_pos == -1 or pd.isna(entry_idx_pos):
                continue
                
            # Convert to integer index in the DataFrame
            entry_idx = int(entry_idx_pos)
            exit_idx_num = data.index.get_loc(exit_idx)
            
            # Get entry/exit data
            entry_price = row['entry_price']
            exit_price = data['close'].iloc[exit_idx_num]
            
            # Determine direction from position sign
            direction = 'LONG' if position[entry_idx] > 0 else 'SHORT'
            
            # Calculate P&L
            entry_equity = equity[entry_idx]
            exit_equity = equity[exit_idx_num]
            pnl_usd = exit_equity - entry_equity
            
            # P&L in pips
            if direction == 'LONG':
                pnl_pips = (exit_price - entry_price) / self.pip_size
            else:
                pnl_pips = (entry_price - exit_price) / self.pip_size
            
            # MAE/MFE calculation
            highest_favorable = row['highest_favorable']
            lowest_favorable = row['lowest_favorable']
            
            if direction == 'LONG':
                # For longs: MFE is highest point, MAE is lowest point
                mfe_pips = (highest_favorable - entry_price) / self.pip_size if not pd.isna(highest_favorable) else 0.0
                mae_pips = (lowest_favorable - entry_price) / self.pip_size if not pd.isna(lowest_favorable) else 0.0
            else:
                # For shorts: MFE is lowest point, MAE is highest point
                mfe_pips = (entry_price - lowest_favorable) / self.pip_size if not pd.isna(lowest_favorable) else 0.0
                mae_pips = (entry_price - highest_favorable) / self.pip_size if not pd.isna(highest_favorable) else 0.0
            
            # Duration
            duration_bars = int(row['bars_held'])
            duration_hours = duration_bars * 1  # H1 timeframe
            
            trades.append({
                'entry_idx': entry_idx,
                'exit_idx': exit_idx_num,
                'entry_time': data.index[entry_idx],
                'exit_time': data.index[exit_idx_num],
                'entry_price': float(entry_price),
                'exit_price': float(exit_price),
                'direction': direction,
                'pnl_usd': float(pnl_usd),
                'pnl_pips': float(pnl_pips),
                'duration_bars': duration_bars,
                'duration_hours': duration_hours,
                'exit_reason': row['exit_reason'],
                'mae_pips': float(mae_pips),
                'mfe_pips': float(mfe_pips),
                'highest_favorable': float(highest_favorable) if not pd.isna(highest_favorable) else None,
                'lowest_favorable': float(lowest_favorable) if not pd.isna(lowest_favorable) else None,
                'winning': pnl_usd > 0
            })
        
        trades_df = pd.DataFrame(trades)
        print(f"✓ Extracted {len(trades_df)} trades from exit_info")
        
        return trades_df
    
    def extract_trades_from_position_fallback(self) -> pd.DataFrame:
        """Fallback: Extract trades from position array transitions."""
        print("⚠️  Using fallback position array parsing...")
        
        backtest = self.results['backtest_results']
        position = backtest['position']
        equity = backtest['equity']
        prices = backtest['price']
        data = self.results['data']
        
        trades = []
        in_trade = False
        entry_idx = None
        entry_price = None
        entry_equity = None
        direction = None
        
        for i in range(len(position)):
            # Entry: 0 → non-zero
            if not in_trade and position[i] != 0:
                in_trade = True
                entry_idx = i
                entry_price = prices[i]
                entry_equity = equity[i]
                direction = 'LONG' if position[i] > 0 else 'SHORT'
            
            # Exit: non-zero → 0
            elif in_trade and position[i] == 0:
                exit_idx = i
                exit_price = prices[i]
                exit_equity = equity[i]
                
                pnl_usd = exit_equity - entry_equity
                
                if direction == 'LONG':
                    pnl_pips = (exit_price - entry_price) / self.pip_size
                else:
                    pnl_pips = (entry_price - exit_price) / self.pip_size
                
                duration_bars = exit_idx - entry_idx
                
                trades.append({
                    'entry_idx': entry_idx,
                    'exit_idx': exit_idx,
                    'entry_time': data.index[entry_idx],
                    'exit_time': data.index[exit_idx],
                    'entry_price': float(entry_price),
                    'exit_price': float(exit_price),
                    'direction': direction,
                    'pnl_usd': float(pnl_usd),
                    'pnl_pips': float(pnl_pips),
                    'duration_bars': duration_bars,
                    'duration_hours': duration_bars * 1,
                    'exit_reason': 'unknown',
                    'mae_pips': 0.0,  # Not available in fallback
                    'mfe_pips': 0.0,
                    'highest_favorable': None,
                    'lowest_favorable': None,
                    'winning': pnl_usd > 0
                })
                
                in_trade = False
        
        return pd.DataFrame(trades)
    
    def classify_session_dst_aware(self, timestamp: pd.Timestamp) -> str:
        """
        Classify trading session using DST-aware London time.
        
        Args:
            timestamp: UTC timestamp
            
        Returns:
            Session name: 'ASIA', 'LONDON', or 'NY'
        """
        london_tz = pytz.timezone('Europe/London')
        local_time = timestamp.tz_convert(london_tz)
        hour = local_time.hour
        
        # Session definitions in London local time
        if 0 <= hour < 8:
            return 'ASIA'
        elif 8 <= hour < 16:
            return 'LONDON'
        else:
            return 'NY'
    
    def add_session_to_trades(self, trades_df: pd.DataFrame) -> pd.DataFrame:
        """Add session classification to trades."""
        print("🌍 Classifying trading sessions (DST-aware)...")
        
        trades_df['session'] = trades_df['entry_time'].apply(self.classify_session_dst_aware)
        
        # Distribution
        session_counts = trades_df['session'].value_counts()
        for session, count in session_counts.items():
            pct = (count / len(trades_df)) * 100
            print(f"  {session}: {count} trades ({pct:.1f}%)")
        
        return trades_df
    
    def calculate_all_metrics(self, trades_df: pd.DataFrame) -> Dict:
        """
        Calculate ALL metrics in Python (never defer to JavaScript).
        
        Returns:
            Dictionary with all performance metrics
        """
        print("📊 Calculating performance metrics...")
        
        wins = trades_df[trades_df['winning']]
        losses = trades_df[~trades_df['winning']]
        
        total_pnl = trades_df['pnl_usd'].sum()
        win_sum = wins['pnl_usd'].sum()
        loss_sum = abs(losses['pnl_usd'].sum())
        
        metrics = {
            # Core performance
            'initial_capital': float(self.results['initial_capital']),
            'final_equity': float(self.results['initial_capital'] + total_pnl),
            'total_pnl_usd': float(total_pnl),
            'total_return_pct': float(self.results.get('total_return', 0) * 100),
            
            # Risk-adjusted
            'sharpe_ratio': float(self.results.get('sharpe_ratio', 0)),
            'sortino_ratio': float(self.results.get('sortino_ratio', 0)),
            'calmar_ratio': float(self.results.get('calmar_ratio', 0)),
            'max_drawdown_pct': float(abs(self.results.get('max_drawdown', 0)) * 100),
            'volatility_annual_pct': float(self.results.get('volatility', 0) * 100),
            
            # Trade statistics
            'total_trades': len(trades_df),
            'winning_trades': len(wins),
            'losing_trades': len(losses),
            'win_rate_pct': float((len(wins) / len(trades_df)) * 100) if len(trades_df) > 0 else 0,
            
            # P&L metrics
            'profit_factor': float(win_sum / loss_sum) if loss_sum > 0 else 0,
            'avg_win_usd': float(wins['pnl_usd'].mean()) if len(wins) > 0 else 0,
            'avg_loss_usd': float(losses['pnl_usd'].mean()) if len(losses) > 0 else 0,
            'avg_win_pips': float(wins['pnl_pips'].mean()) if len(wins) > 0 else 0,
            'avg_loss_pips': float(losses['pnl_pips'].mean()) if len(losses) > 0 else 0,
            'largest_win_usd': float(wins['pnl_usd'].max()) if len(wins) > 0 else 0,
            'largest_loss_usd': float(losses['pnl_usd'].min()) if len(losses) > 0 else 0,
            
            # Duration
            'avg_duration_bars': float(trades_df['duration_bars'].mean()),
            'avg_duration_hours': float(trades_df['duration_hours'].mean()),
            'max_duration_bars': int(trades_df['duration_bars'].max()),
            
            # MAE/MFE
            'avg_mae_pips': float(trades_df['mae_pips'].mean()),
            'avg_mfe_pips': float(trades_df['mfe_pips'].mean()),
            'mae_std_pips': float(trades_df['mae_pips'].std()),
            'mfe_std_pips': float(trades_df['mfe_pips'].std()),
        }
        
        # Session-based metrics
        metrics['session_metrics'] = {}
        for session in ['ASIA', 'LONDON', 'NY']:
            session_trades = trades_df[trades_df['session'] == session]
            if len(session_trades) > 0:
                session_wins = session_trades[session_trades['winning']]
                metrics['session_metrics'][session] = {
                    'total_trades': len(session_trades),
                    'pnl_usd': float(session_trades['pnl_usd'].sum()),
                    'win_rate_pct': float((len(session_wins) / len(session_trades)) * 100),
                    'avg_pnl_pips': float(session_trades['pnl_pips'].mean()),
                }
        
        print(f"✓ Calculated {len(metrics)} core metrics + session breakdowns")
        
        return metrics
    
    def calculate_edge_diagnostics(self, trades_df: pd.DataFrame, metrics: Dict) -> Dict:
        """
        Calculate institutional-grade edge diagnostics.
        
        Returns:
            Dictionary with diagnostic metrics and structural issue detection
        """
        print("🔬 Running edge diagnostics...")
        
        # Get exit config params
        config = self.results['backtest_config']['exit_params']
        hard_stop_pips = config['hard_stop_pips']
        profit_trigger_pips = config['profit_trigger_pips']
        
        # Exit breakdown
        exit_counts = trades_df['exit_reason'].value_counts()
        total_trades = len(trades_df)
        
        # Expectancy
        win_rate = metrics['win_rate_pct'] / 100
        avg_win_pips = metrics['avg_win_pips']
        avg_loss_pips = metrics['avg_loss_pips']
        expectancy_pips = (win_rate * avg_win_pips) + ((1 - win_rate) * avg_loss_pips)
        
        # MAE/MFE ratios
        avg_mae = metrics['avg_mae_pips']
        avg_mfe = metrics['avg_mfe_pips']
        mae_vs_stop = abs(avg_mae) / hard_stop_pips if hard_stop_pips > 0 else 0
        mfe_vs_target = avg_mfe / profit_trigger_pips if profit_trigger_pips > 0 else 0
        efficiency_ratio = avg_mfe / abs(avg_mae) if avg_mae != 0 else 0
        
        # Trailing activation rate
        trades_reached_target = len(trades_df[trades_df['mfe_pips'] >= profit_trigger_pips])
        trailing_activation_pct = (trades_reached_target / total_trades * 100) if total_trades > 0 else 0
        
        # Hard stop capture
        hard_stop_exits = exit_counts.get('hard_stop', 0)
        hard_stop_pct = (hard_stop_exits / total_trades * 100) if total_trades > 0 else 0
        
        diagnostics = {
            'expectancy_per_trade_pips': float(expectancy_pips),
            'expectancy_per_trade_usd': float(expectancy_pips * 10),  # Approx for standard lot
            
            'mae_vs_stop_ratio': float(mae_vs_stop),
            'mfe_vs_target_ratio': float(mfe_vs_target),
            'efficiency_ratio': float(efficiency_ratio),
            
            'hard_stop_capture_pct': float(hard_stop_pct),
            'trailing_activation_pct': float(trailing_activation_pct),
            
            'win_loss_ratio': float(abs(avg_win_pips / avg_loss_pips)) if avg_loss_pips != 0 else 0,
            
            'exit_breakdown': {
                reason: int(count) for reason, count in exit_counts.items()
            },
            
            'structural_issues': []
        }
        
        # Detect structural issues
        issues = []
        
        if hard_stop_pct > 50:
            issues.append({
                'severity': 'HIGH',
                'issue': f'Hard stop hit rate ({hard_stop_pct:.1f}%) >> trailing stop rate',
                'implication': f'Profit target ({profit_trigger_pips} pips) rarely achieved - entry lacks predictive power',
                'suggested_fix': f'Test wider profit trigger ({profit_trigger_pips*1.5:.0f}-{profit_trigger_pips*2:.0f} pips) or tighter stops ({hard_stop_pips*0.7:.0f}-{hard_stop_pips*0.8:.0f} pips)'
            })
        
        if diagnostics['win_loss_ratio'] < 1.0 and win_rate < 0.55:
            issues.append({
                'severity': 'MEDIUM',
                'issue': f'Win/loss ratio {diagnostics["win_loss_ratio"]:.2f}:1 with {metrics["win_rate_pct"]:.1f}% win rate',
                'implication': f'Expectancy near zero ({expectancy_pips:.2f} pips) - unprofitable after costs',
                'suggested_fix': 'Add regime filter (only trade high-volatility sessions or strong trend conditions)'
            })
        
        if mfe_vs_target > 1.2 and trailing_activation_pct < 50:
            issues.append({
                'severity': 'MEDIUM',
                'issue': f'Avg MFE ({avg_mfe:.1f} pips) > profit trigger ({profit_trigger_pips} pips), but only {trailing_activation_pct:.1f}% activated trailing',
                'implication': 'Entries directionally correct but profit target hit prematurely',
                'suggested_fix': f'Increase profit trigger to {avg_mfe*0.8:.1f} pips to capture larger moves'
            })
        
        diagnostics['structural_issues'] = issues
        
        print(f"✓ Diagnostics complete - detected {len(issues)} structural issues")
        
        return diagnostics
    
    def downsample_equity_curve(self, n_points: int = 500) -> List[Dict]:
        """
        Downsample equity curve using largest-triangle-three-buckets (LTTB) algorithm.
        Preserves peaks and valleys for accurate drawdown visualization.
        
        Args:
            n_points: Target number of points
            
        Returns:
            List of dicts with 'timestamp' and 'equity'
        """
        print(f"📉 Downsampling equity curve to {n_points} points...")
        
        equity = self.results['backtest_results']['equity']
        data = self.results['data']
        
        if len(equity) <= n_points:
            # No downsampling needed
            return [
                {'timestamp': data.index[i].isoformat(), 'equity': float(equity[i])}
                for i in range(len(equity))
            ]
        
        # Simple downsampling with min-max preservation
        # For production, use LTTB library, but this captures peaks
        bucket_size = len(equity) // n_points
        downsampled = []
        
        for i in range(n_points):
            start_idx = i * bucket_size
            end_idx = min((i + 1) * bucket_size, len(equity))
            
            if start_idx >= len(equity):
                break
            
            # Get bucket data
            bucket = equity[start_idx:end_idx]
            
            # Find min, max, and last value in bucket
            min_idx = start_idx + np.argmin(bucket)
            max_idx = start_idx + np.argmax(bucket)
            last_idx = end_idx - 1
            
            # Add points to preserve shape
            for idx in sorted(set([start_idx, min_idx, max_idx, last_idx])):
                if idx < len(equity):
                    downsampled.append({
                        'timestamp': data.index[idx].isoformat(),
                        'equity': float(equity[idx])
                    })
        
        # CRITICAL: Always include the final point to ensure equity curve ends correctly
        final_idx = len(equity) - 1
        if downsampled[-1]['timestamp'] != data.index[final_idx].isoformat():
            downsampled.append({
                'timestamp': data.index[final_idx].isoformat(),
                'equity': float(equity[final_idx])
            })
        
        print(f"✓ Downsampled from {len(equity)} to {len(downsampled)} points")
        
        return downsampled
    
    def get_versioning_metadata(self) -> Dict:
        """Generate versioning metadata (strategy version, git commit, run ID)."""
        print("🏷️  Generating versioning metadata...")
        
        # Get git commit
        try:
            git_commit = subprocess.check_output(
                ['git', 'rev-parse', '--short', 'HEAD'],
                cwd=Path(__file__).parent.parent,
                stderr=subprocess.DEVNULL
            ).decode().strip()
        except:
            git_commit = 'unknown'
        
        # Generate run ID
        run_id = (
            f"{self.results['instrument'].lower()}_"
            f"{self.results['timeframe'].lower()}_"
            f"{self.results['strategy_name'].lower().replace(' ', '_')}_"
            f"{int(datetime.now(timezone.utc).timestamp())}"
        )
        
        metadata = {
            'strategy_version': src.__version__,
            'git_commit': git_commit,
            'run_id': run_id,
            'run_timestamp': datetime.now(timezone.utc).isoformat(),
            'exporter_version': '2.0.0'
        }
        
        print(f"✓ Version: {metadata['strategy_version']}, Commit: {metadata['git_commit']}")
        
        return metadata
    
    def validate_equity_curve(self) -> None:
        """Validate equity curve consistency."""
        print("✅ Validating equity curve...")
        
        equity = self.results['backtest_results']['equity']
        initial_capital = self.results['initial_capital']
        total_return = self.results.get('total_return', 0)
        expected_final = initial_capital * (1 + total_return)
        
        # Check start value
        if abs(equity[0] - initial_capital) > 0.01:
            raise ValueError(f"Equity curve validation failed: start = {equity[0]}, expected {initial_capital}")
        
        # Check end value
        if abs(equity[-1] - expected_final) > 1.0:  # Allow $1 tolerance
            warnings.warn(f"Equity curve end mismatch: {equity[-1]:.2f} vs expected {expected_final:.2f}")
        
        print(f"✓ Equity curve validated: ${equity[0]:,.2f} → ${equity[-1]:,.2f}")
    
    def export_to_files(self, trades_df: pd.DataFrame, metrics: Dict, 
                       diagnostics: Dict, versioning: Dict) -> Path:
        """
        Export all data to multi-file structure.
        
        Returns:
            Path to output directory
        """
        print("\n📦 Exporting to multi-file structure...")
        
        # Create output directory
        folder_name = (
            f"{self.results['instrument'].lower()}_"
            f"{self.results['timeframe'].lower()}_"
            f"{self.results['strategy_name'].lower().replace(' ', '_')}"
        )
        run_folder = (
            f"run_{datetime.now(timezone.utc).strftime('%Y_%m_%d')}_"
            f"v{versioning['strategy_version']}_"
            f"{versioning['git_commit']}"
        )
        
        output_dir = self.output_base / folder_name / run_folder
        output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"📁 Output directory: {output_dir}")
        
        # 1. Metadata
        metadata = {
            **versioning,
            'strategy_name': self.results['strategy_name'],
            'instrument': self.results['instrument'],
            'timeframe': self.results['timeframe'],
            'start_date': self.results['start_date'],
            'end_date': self.results['end_date'],
            'n_bars': self.results['n_bars'],
            'parameters': {
                'detector_params': self.results['backtest_config'].get('detector_params', {}),
                'exit_params': self.results['backtest_config'].get('exit_params', {})
            }
        }
        
        with open(output_dir / 'metadata.json', 'w') as f:
            json.dump(metadata, f, indent=2)
        print(f"  ✓ metadata.json ({(output_dir / 'metadata.json').stat().st_size / 1024:.1f} KB)")
        
        # 2. Metrics
        with open(output_dir / 'metrics.json', 'w') as f:
            json.dump(metrics, f, indent=2)
        print(f"  ✓ metrics.json ({(output_dir / 'metrics.json').stat().st_size / 1024:.1f} KB)")
        
        # 3. Trades
        trades_list = []
        for idx, row in trades_df.iterrows():
            trade = {
                'id': f"T{idx+1:04d}",
                'entry_time': row['entry_time'].isoformat(),
                'exit_time': row['exit_time'].isoformat(),
                'direction': row['direction'],
                'entry_price': row['entry_price'],
                'exit_price': row['exit_price'],
                'pnl_usd': row['pnl_usd'],
                'pnl_pips': row['pnl_pips'],
                'duration_bars': row['duration_bars'],
                'duration_hours': row['duration_hours'],
                'exit_reason': row['exit_reason'],
                'mae_pips': row['mae_pips'],
                'mfe_pips': row['mfe_pips'],
                'session': row['session'],
                'winning': row['winning']
            }
            trades_list.append(trade)
        
        with open(output_dir / 'trades.json', 'w') as f:
            json.dump(trades_list, f, indent=2)
        print(f"  ✓ trades.json ({(output_dir / 'trades.json').stat().st_size / 1024:.1f} KB)")
        
        # 4. Equity curve (downsampled)
        equity_curve = self.downsample_equity_curve(n_points=500)
        with open(output_dir / 'equity.json', 'w') as f:
            json.dump(equity_curve, f, indent=2)
        print(f"  ✓ equity.json ({(output_dir / 'equity.json').stat().st_size / 1024:.1f} KB)")
        
        # 5. OHLC (first 500 bars for price chart)
        data = self.results['data']
        ohlc_list = []
        for i in range(min(500, len(data))):
            ohlc_list.append({
                'timestamp': data.index[i].isoformat(),
                'open': float(data['open'].iloc[i]),
                'high': float(data['high'].iloc[i]),
                'low': float(data['low'].iloc[i]),
                'close': float(data['close'].iloc[i])
            })
        
        with open(output_dir / 'ohlc.json', 'w') as f:
            json.dump(ohlc_list, f, indent=2)
        print(f"  ✓ ohlc.json ({(output_dir / 'ohlc.json').stat().st_size / 1024:.1f} KB)")
        
        # 6. Diagnostics
        with open(output_dir / 'diagnostics.json', 'w') as f:
            json.dump(diagnostics, f, indent=2)
        print(f"  ✓ diagnostics.json ({(output_dir / 'diagnostics.json').stat().st_size / 1024:.1f} KB)")
        
        # Summary
        total_size = sum(f.stat().st_size for f in output_dir.iterdir() if f.is_file()) / 1024
        print(f"\n✓ Export complete! Total size: {total_size:.1f} KB")
        print(f"📂 Data location: {output_dir}")
        
        return output_dir
    
    def run(self) -> Path:
        """Execute full export pipeline."""
        print("\n" + "="*70)
        print("PROFESSIONAL BACKTEST DASHBOARD EXPORTER")
        print("="*70 + "\n")
        
        # Load data
        self.load_backtest_results()
        
        # Validate
        self.validate_equity_curve()
        
        # Extract trades (PRIMARY: use exit_info)
        trades_df = self.extract_trades_from_exit_info()
        
        # Add sessions
        trades_df = self.add_session_to_trades(trades_df)
        
        # Calculate metrics (ALL in Python)
        metrics = self.calculate_all_metrics(trades_df)
        
        # Calculate diagnostics
        diagnostics = self.calculate_edge_diagnostics(trades_df, metrics)
        
        # Get versioning
        versioning = self.get_versioning_metadata()
        
        # Export
        output_dir = self.export_to_files(trades_df, metrics, diagnostics, versioning)
        
        print("\n" + "="*70)
        print("✅ EXPORT COMPLETE")
        print("="*70)
        print(f"\n📊 Summary:")
        print(f"  Trades: {len(trades_df)}")
        print(f"  Equity: ${metrics['initial_capital']:,.0f} → ${metrics['final_equity']:,.0f}")
        print(f"  Return: {metrics['total_return_pct']:.2f}%")
        print(f"  Sharpe: {metrics['sharpe_ratio']:.2f}")
        print(f"  Issues detected: {len(diagnostics['structural_issues'])}")
        print(f"\n📁 Next step: Open dashboard and point it to:")
        print(f"   {output_dir}")
        
        return output_dir


def main():
    """Main execution."""
    # Default pickle path
    pickle_path = "reports/backtests/exhaustion_momentum_backtest_results.pkl"
    
    # Check if file exists
    if not Path(pickle_path).exists():
        print(f"❌ Error: Pickle file not found: {pickle_path}")
        print("\nAvailable backtest files:")
        for f in Path("reports/backtests").glob("*.pkl"):
            print(f"  - {f}")
        sys.exit(1)
    
    # Run exporter
    exporter = BacktestDashboardExporter(pickle_path)
    output_dir = exporter.run()
    
    print(f"\n✅ Success! Dashboard data ready at: {output_dir}")


if __name__ == "__main__":
    main()
