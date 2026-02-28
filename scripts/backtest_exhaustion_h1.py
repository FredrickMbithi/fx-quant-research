"""
Complete Backtest for GBP/USD H1 Exhaustion Mean Reversion Strategy
Integrates all components: data loading, signal generation, exit management, backtesting
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
from datetime import datetime
import pickle

from src.data.h1_loader import load_processed_data
from src.features.exhaustion import ExhaustionDetector
from src.backtest.enhanced_backtest import EnhancedVectorizedBacktest
from src.backtest.engine import CostModel, PositionSizer
from src.backtest.exit_manager import TrailingStopManager, ExitConfig


def run_exhaustion_backtest(
    start_date: str = '2023-01-01',
    end_date: str = '2026-02-09',
    save_results: bool = True,
    verbose: bool = True
):
    """
    Run complete backtest of exhaustion mean reversion strategy.
    
    Args:
        start_date: Backtest start date (YYYY-MM-DD)
        end_date: Backtest end date (YYYY-MM-DD)
        save_results: If True, save results to pickle file
        verbose: If True, print detailed output
    
    Returns:
        Dict with backtest results
    """
    
    if verbose:
        print("="*70)
        print(" "*15 + "EXHAUSTION H1 BACKTEST")
        print("="*70)
    
    # ========================================================================
    # STEP 1: Load and prepare data
    # ========================================================================
    if verbose:
        print("\n[1/6] Loading data...")
    
    df = load_processed_data()
    
    # Filter to backtest period
    df_backtest = df[start_date:end_date].copy()
    
    if verbose:
        print(f"  Date range: {df_backtest.index[0]} to {df_backtest.index[-1]}")
        print(f"  Total bars: {len(df_backtest):,}")
        print(f"  Sessions: {df_backtest['session'].value_counts().to_dict()}")
    
    # ========================================================================
    # STEP 2: Generate signals
    # ========================================================================
    if verbose:
        print("\n[2/6] Generating signals...")
    
    # Initialize detector with default parameters
    detector = ExhaustionDetector(
        pressure_threshold=2,
        range_expansion_factor=0.8,
        range_lookback=10,
        percentile_high=0.65,
        percentile_low=0.35,
        percentile_window=10
    )
    
    # Generate signals
    df_signals = detector.generate_signals(df_backtest)
    
    # Get signal summary
    signal_summary = detector.get_signal_summary(df_signals)
    
    if verbose:
        print(f"  Bullish exhaustion bars: {signal_summary['bullish_exhaustion_count']}")
        print(f"  Bearish exhaustion bars: {signal_summary['bearish_exhaustion_count']}")
        print(f"  Long setups: {signal_summary['long_setups']}")
        print(f"  Short setups: {signal_summary['short_setups']}")
        print(f"  Total signals: {signal_summary['total_signals']}")
        print(f"  Signal frequency: {signal_summary['signal_frequency_pct']:.2f}%")
    
    # ========================================================================
    # STEP 3: Configure backtest components
    # ========================================================================
    if verbose:
        print("\n[3/6] Configuring backtest components...")
    
    # Transaction costs (FX-specific)
    cost_model = CostModel({
        'commission_per_share': 0.0,  # No commission (spread-based pricing)
        'slippage_pct': 0.00025,  # 2.5 pips slippage (1 pip spread + 1.5 pip slippage)
        'daily_borrow_fee': 0.0,  # No borrow fees for FX spot
    })
    
    if verbose:
        print(f"  Transaction cost: 2.5 pips per trade (1.0 spread + 1.5 slippage)")
    
    # Position sizing (simple threshold)
    position_sizer = PositionSizer({
        'strategy': 'threshold',
        'threshold_long': 0.5,  # Signal > 0.5 → long
        'threshold_short': -0.5,  # Signal < -0.5 → short
        'position_long': 1.0,  # 100% capital
        'position_short': -1.0,  # 100% capital short
    })
    
    if verbose:
        print(f"  Position sizing: 100% capital per signal")
    
    # Exit manager (trailing stop)
    exit_config = ExitConfig(
        hard_stop_pips=10.0,
        profit_trigger_pips=4.0,
        trailing_distance_pips=3.0,
        max_hold_bars=5,
        pip_size=0.0001  # GBPUSD pip size (4 decimal places)
    )
    
    exit_manager = TrailingStopManager(exit_config)
    
    if verbose:
        print(f"  Hard stop: {exit_config.hard_stop_pips} pips")
        print(f"  Profit trigger: {exit_config.profit_trigger_pips} pips → trail by {exit_config.trailing_distance_pips} pips")
        print(f"  Max hold: {exit_config.max_hold_bars} bars")
    
    # ========================================================================
    # STEP 4: Run backtest
    # ========================================================================
    if verbose:
        print("\n[4/6] Running backtest...")
    
    # Prepare OHLC DataFrame
    prices_df = df_signals[['open', 'high', 'low', 'close']].copy()
    
    # Signal array
    signal_array = df_signals['signal'].values
    
    # Initialize backtest
    backtest = EnhancedVectorizedBacktest(
        prices=prices_df,
        signal=signal_array,
        cost_model=cost_model,
        position_sizer=position_sizer,
        exit_manager=exit_manager,
        initial_capital=100000.0,
        periods_per_year=252 * 24  # Hourly data: 252 days * 24 hours
    )
    
    # Run
    results = backtest.run()
    
    if verbose:
        print(f"  Backtest complete!")
        if results['exit_stats']:
            print(f"  Exits: {results['exit_stats']['total_exits']} total")
            print(f"    Hard stops: {results['exit_stats']['hard_stop_exits']} ({results['exit_stats']['hard_stop_pct']:.1f}%)")
            print(f"    Trailing stops: {results['exit_stats']['trailing_stop_exits']} ({results['exit_stats']['trailing_stop_pct']:.1f}%)")
            print(f"    Max hold: {results['exit_stats']['max_hold_exits']} ({results['exit_stats']['max_hold_pct']:.1f}%)")
    
    # ========================================================================
    # STEP 5: Display results
    # ========================================================================
    if verbose:
        print("\n[5/6] Performance Summary:")
        print("-"*70)
        print(f"  Initial Capital:       ${results['initial_capital']:,.2f}")
        print(f"  Final Equity:          ${results['equity'][-1]:,.2f}")
        print(f"  Total Return:          {results['total_return']:.2%}")
        print(f"  Annualized Return:     {results['annualized_return']:.2%}")
        print(f"  CAGR:                  {results['cagr']:.2%}")
        print()
        print(f"  Sharpe Ratio:          {results['sharpe_ratio']:.2f}")
        print(f"  Sortino Ratio:         {results['sortino_ratio']:.2f}")
        print(f"  Calmar Ratio:          {results['calmar_ratio']:.2f}")
        print()
        print(f"  Volatility (ann.):     {results['volatility']:.2%}")
        print(f"  Max Drawdown:          {results['max_drawdown']:.2%}")
        print(f"  Max DD Duration:       {results['max_drawdown_duration']} bars")
        print()
        print(f"  Total Costs:           ${results['total_costs']:,.2f}")
        print(f"  Average Position:      {results['avg_position']:.2f}")
        print(f"  Turnover:              {results['turnover']:.4f}")
        print("-"*70)
    
    # ========================================================================
    # STEP 6: Save results
    # ========================================================================
    if save_results:
        if verbose:
            print("\n[6/6] Saving results...")
        
        output_dir = Path('reports/backtests')
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Add metadata to results
        results['backtest_config'] = {
            'strategy': 'Exhaustion Mean Reversion',
            'instrument': 'GBPUSD',
            'timeframe': 'H1',
            'start_date': start_date,
            'end_date': end_date,
            'detector_params': {
                'pressure_threshold': detector.pressure_threshold,
                'range_expansion_factor': detector.range_expansion_factor,
                'range_lookback': detector.range_lookback,
                'percentile_high': detector.percentile_high,
                'percentile_low': detector.percentile_low,
            },
            'exit_params': {
                'hard_stop_pips': exit_config.hard_stop_pips,
                'profit_trigger_pips': exit_config.profit_trigger_pips,
                'trailing_distance_pips': exit_config.trailing_distance_pips,
                'max_hold_bars': exit_config.max_hold_bars,
            },
            'signal_summary': signal_summary,
            'run_timestamp': datetime.now().isoformat(),
        }
        
        # Save to pickle
        output_file = output_dir / 'exhaustion_h1_backtest_results.pkl'
        with open(output_file, 'wb') as f:
            pickle.dump(results, f)
        
        if verbose:
            print(f"  Results saved to: {output_file}")
    
    if verbose:
        print("\n" + "="*70)
        print("Backtest complete!")
        print("="*70)
    
    return results


if __name__ == "__main__":
    # Run the backtest
    results = run_exhaustion_backtest(
        start_date='2023-01-01',
        end_date='2026-02-09',
        save_results=True,
        verbose=True
    )
    
    # Check success criteria (preliminary)
    print("\n" + "="*70)
    print("PRELIMINARY SUCCESS CRITERIA CHECK")
    print("="*70)
    
    criteria = {
        'Sharpe Ratio ≥ 1.2': results['sharpe_ratio'] >= 1.2,
        'Profit Factor ≥ 1.4': False,  # Need trade analysis
        'Win Rate ≥ 48%': False,  # Need trade analysis
        'Max DD ≤ 18%': results['max_drawdown'] >= -0.18,  # Note: DD is negative
        'Net Trade ≥ 2 pips': False,  # Need trade analysis
    }
    
    for criterion, passed in criteria.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {criterion:25s}: {status}")
    
    all_passed = all(criteria.values())
    
    print("\n" + "="*70)
    if all_passed:
        print("✓ Preliminary criteria met (full analysis needed)")
    else:
        print("✗ Some criteria not met (full analysis needed)")
    print("="*70)
