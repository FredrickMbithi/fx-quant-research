"""
Backtest: Exhaustion MOMENTUM Strategy (Option A - Inverted Logic)

Tests the hypothesis that exhaustion bars indicate trend strength,
not reversal. This is the inverse of the mean reversion strategy.

Entry:
- LONG on bullish exhaustion (trade WITH upward momentum)
- SHORT on bearish exhaustion (trade WITH downward momentum)

Exit: Same as mean reversion (trailing stops, hard stops, max hold)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import pickle
from datetime import datetime

# Import components
from src.data.h1_loader import load_processed_data
from src.strategies.exhaustion_momentum_strategy import ExhaustionMomentumStrategy
from src.backtest.enhanced_backtest import EnhancedVectorizedBacktest
from src.backtest.engine import CostModel, PositionSizer
from src.backtest.exit_manager import TrailingStopManager, ExitConfig


def run_momentum_backtest(
    start_date: str = '2023-01-01',
    end_date: str = None,
    initial_capital: float = 100000.0,
    save_results: bool = True
):
    """
    Run backtest on momentum variant of exhaustion strategy.
    
    Args:
        start_date: Backtest start date
        end_date: Backtest end date (None = latest available)
        initial_capital: Starting capital
        save_results: Whether to save results to file
    """
    
    print("="*70)
    print("EXHAUSTION MOMENTUM STRATEGY BACKTEST (OPTION A)")
    print("Hypothesis: Exhaustion bars indicate trend strength (momentum)")
    print("="*70)
    print()
    
    # ========================================================================
    # Step 1: Load Data
    # ========================================================================
    print("Step 1: Loading H1 GBPUSD data...")
    df = load_processed_data()
    
    # Filter date range
    df_backtest = df[start_date:end_date] if end_date else df[start_date:]
    
    print(f"  Data range: {df_backtest.index[0]} to {df_backtest.index[-1]}")
    print(f"  Bars: {len(df_backtest):,}")
    print(f"  Duration: {(df_backtest.index[-1] - df_backtest.index[0]).days / 365.25:.1f} years")
    print()
    
    # ========================================================================
    # Step 2: Initialize Strategy
    # ========================================================================
    print("Step 2: Initializing Exhaustion MOMENTUM Strategy...")
    
    detector_params = {
        'pressure_threshold': 2,
        'range_expansion_factor': 0.8,
        'range_lookback': 10,
        'percentile_high': 0.65,
        'percentile_low': 0.35
    }
    
    strategy = ExhaustionMomentumStrategy(
        instrument='GBPUSD',
        detector_params=detector_params,
        use_confirmation=True
    )
    
    print("  Detector parameters:")
    for key, value in detector_params.items():
        print(f"    {key}: {value}")
    print()
    
    # ========================================================================
    # Step 3: Generate Signals
    # ========================================================================
    print("Step 3: Generating MOMENTUM signals...")
    signals = strategy.generate_signals_vectorized(df_backtest)
    
    # Signal statistics
    long_signals = (signals == 1.0).sum()
    short_signals = (signals == -1.0).sum()
    total_signals = (signals != 0).sum()
    signal_freq = total_signals / len(df_backtest) * 100
    
    print(f"  LONG signals:  {long_signals:,}")
    print(f"  SHORT signals: {short_signals:,}")
    print(f"  Total signals: {total_signals:,}")
    print(f"  Signal frequency: {signal_freq:.2f}%")
    print(f"  Long/Short ratio: {long_signals/(short_signals+1e-10):.2f}")
    print()
    
    # ========================================================================
    # Step 4: Configure Exit Manager
    # ========================================================================
    print("Step 4: Configuring exit management...")
    
    exit_config = ExitConfig(
        hard_stop_pips=10.0,
        profit_trigger_pips=4.0,
        trailing_distance_pips=3.0,
        max_hold_bars=5,
        pip_size=0.0001  # GBPUSD (4 decimal places)
    )
    
    exit_manager = TrailingStopManager(exit_config)
    
    print(f"  Hard stop: {exit_config.hard_stop_pips} pips")
    print(f"  Profit trigger: {exit_config.profit_trigger_pips} pips")
    print(f"  Trailing distance: {exit_config.trailing_distance_pips} pips")
    print(f"  Max hold: {exit_config.max_hold_bars} bars")
    print()
    
    # ========================================================================
    # Step 5: Configure Cost Model
    # ========================================================================
    print("Step 5: Configuring transaction costs...")
    
    # 2.5 pips = 0.00025 (0.025% slippage for GBPUSD ~1.27)
    cost_model = CostModel({
        'commission_per_share': 0.0,  # No commission (spread-based pricing)
        'slippage_pct': 0.00025,  # 2.5 pips slippage (1.0 spread + 1.5 slippage)
        'daily_borrow_fee': 0.0,  # No borrow fees for FX spot
    })
    
    print(f"  Transaction cost: 2.5 pips per trade (1.0 spread + 1.5 slippage)")
    print()
    
    # ========================================================================
    # Step 6: Configure Position Sizing
    # ========================================================================
    print("Step 6: Configuring position sizing...")
    
    position_sizer = PositionSizer({
        'strategy': 'threshold',
        'threshold': 0.5,
        'max_leverage': 1.0
    })
    
    print(f"  Strategy: threshold")
    print(f"  Signal threshold: 0.5")
    print(f"  Max leverage: 1.0")
    print()
    
    # ========================================================================
    # Step 7: Run Backtest
    # ========================================================================
    print("Step 7: Running backtest...")
    print()
    
    backtest = EnhancedVectorizedBacktest(
        prices=df_backtest,
        signal=signals,
        cost_model=cost_model,
        position_sizer=position_sizer,
        exit_manager=exit_manager,
        initial_capital=initial_capital,
        periods_per_year=252 * 24  # Hourly data
    )
    
    results = backtest.run()
    
    # ========================================================================
    # Step 8: Display Results
    # ========================================================================
    print("="*70)
    print("BACKTEST RESULTS - MOMENTUM STRATEGY")
    print("="*70)
    print()
    
    print("PERFORMANCE METRICS:")
    print(f"  Initial Capital:     ${results['initial_capital']:,.2f}")
    print(f"  Final Equity:        ${results['equity'][-1]:,.2f}")
    print(f"  Total Return:        {results['total_return']*100:,.2f}%")
    print(f"  Annualized Return:   {results['annualized_return']*100:,.2f}%")
    print()
    
    print("RISK-ADJUSTED METRICS:")
    print(f"  Sharpe Ratio:        {results['sharpe_ratio']:.2f}")
    print(f"  Sortino Ratio:       {results['sortino_ratio']:.2f}")
    print(f"  Calmar Ratio:        {results['calmar_ratio']:.2f}")
    print()
    
    print("RISK METRICS:")
    print(f"  Volatility (ann.):   {results['volatility']*100:.2f}%")
    print(f"  Max Drawdown:        {results['max_drawdown']*100:.2f}%")
    print(f"  Max DD Duration:     {results['max_drawdown_duration']:,} bars")
    print(f"  Downside Deviation:  {results['downside_deviation']*100:.2f}%")
    print()
    
    print("TRANSACTION METRICS:")
    print(f"  Total Costs:         ${results['total_costs']:.2f}")
    print(f"  Turnover:            {results['turnover']:.4f}")
    print()
    
    # ========================================================================
    # Step 9: Evaluate Success Criteria
    # ========================================================================
    print("="*70)
    print("SUCCESS CRITERIA EVALUATION")
    print("="*70)
    print()
    
    criteria = {
        'Sharpe Ratio': (results['sharpe_ratio'], 1.2, '≥'),
        'Max Drawdown': (abs(results['max_drawdown'])*100, 18.0, '≤'),
    }
    
    print(f"{'Criterion':<20} {'Actual':>12} {'Required':>12} {'Status':>10}")
    print("-"*70)
    
    passes = 0
    total_criteria = len(criteria)
    
    for criterion, (actual, required, comparator) in criteria.items():
        if comparator == '≥':
            status = '✓ PASS' if actual >= required else '✗ FAIL'
        else:  # ≤
            status = '✓ PASS' if actual <= required else '✗ FAIL'
        
        if '✓' in status:
            passes += 1
        
        if 'Ratio' in criterion or 'Return' in criterion:
            print(f"{criterion:<20} {actual:>12.2f} {required:>12.2f} {status:>10}")
        elif 'Drawdown' in criterion:
            print(f"{criterion:<20} {actual:>11.2f}% {required:>11.2f}% {status:>10}")
        else:
            print(f"{criterion:<20} {actual:>12.2f} {required:>12.2f} {status:>10}")
    
    print()
    print(f"PRELIMINARY: {passes}/{total_criteria} criteria passed")
    print("(Note: Full trade analysis needed for complete evaluation)")
    print()
    
    # ========================================================================
    # Step 10: Save Results
    # ========================================================================
    if save_results:
        print("="*70)
        print("SAVING RESULTS")
        print("="*70)
        print()
        
        # Prepare results package
        results_package = {
            'backtest_results': results,
            'strategy_name': 'ExhaustionMomentum',
            'instrument': 'GBPUSD',
            'timeframe': 'H1',
            'start_date': start_date,
            'end_date': df_backtest.index[-1].strftime('%Y-%m-%d'),
            'backtest_config': {
                'strategy': 'Exhaustion Momentum',
                'instrument': 'GBPUSD',
                'timeframe': 'H1',
                'start_date': start_date,
                'end_date': df_backtest.index[-1].strftime('%Y-%m-%d'),
                'detector_params': detector_params,
                'exit_params': {
                    'hard_stop_pips': exit_config.hard_stop_pips,
                    'profit_trigger_pips': exit_config.profit_trigger_pips,
                    'trailing_distance_pips': exit_config.trailing_distance_pips,
                    'max_hold_bars': exit_config.max_hold_bars
                },
                'signal_summary': {
                    'long_setups': int(long_signals),
                    'short_setups': int(short_signals),
                    'total_signals': int(total_signals),
                    'signal_frequency_pct': signal_freq,
                    'long_short_ratio': long_signals/(short_signals+1e-10),
                    'bullish_exhaustion_count': 0,  # Would need detector run
                    'bearish_exhaustion_count': 0
                }
            },
            'initial_capital': initial_capital,
            'sharpe_ratio': results['sharpe_ratio'],
            'sortino_ratio': results['sortino_ratio'],
            'calmar_ratio': results['calmar_ratio'],
            'total_return': results['total_return'],
            'annualized_return': results['annualized_return'],
            'volatility': results['volatility'],
            'max_drawdown': results['max_drawdown'],
            'max_drawdown_duration': results['max_drawdown_duration'],
            'downside_deviation': results['downside_deviation'],
            'total_costs': results['total_costs'],
            'turnover': results['turnover'],
            'n_bars': len(df_backtest),
            'equity': results['equity'],
            'returns': results['returns'],
            'positions': results.get('positions', signals.values),  # Use signals if positions not in results
            'signals': signals,
            'data': df_backtest
        }
        
        # Save to pickle
        output_dir = Path('reports/backtests')
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / 'exhaustion_momentum_backtest_results.pkl'
        
        with open(output_file, 'wb') as f:
            pickle.dump(results_package, f)
        
        print(f"✓ Results saved to: {output_file}")
        print()
    
    print("="*70)
    print("BACKTEST COMPLETE")
    print("="*70)
    
    return results


if __name__ == "__main__":
    results = run_momentum_backtest(
        start_date='2023-01-01',
        initial_capital=100000.0,
        save_results=True
    )
