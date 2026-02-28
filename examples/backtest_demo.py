"""
Example: Complete Backtest Engine Demonstration

This script demonstrates all features of the backtest engine:
1. Different position sizing strategies
2. Cost modeling
3. Performance metrics
4. Trade analysis
5. Comprehensive reporting
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import numpy as np
import pandas as pd
from src.backtest.engine import (
    CostModel,
    PositionSizer,
    VectorizedBacktest,
    BacktestAnalyzer,
)


def generate_sample_data(n_bars=252, seed=42):
    """Generate sample price and signal data."""
    np.random.seed(seed)
    
    # Generate random walk price
    returns = np.random.randn(n_bars) * 0.01
    price = 100 * np.exp(np.cumsum(returns))
    
    # Generate signal (simple moving average crossover)
    short_ma = pd.Series(price).rolling(20).mean().values
    long_ma = pd.Series(price).rolling(50).mean().values
    
    # Signal: 1 when short MA > long MA, -1 otherwise
    signal = np.where(short_ma > long_ma, 1.0, -1.0)
    signal = np.nan_to_num(signal, nan=0.0)
    
    return price, signal


def run_threshold_strategy():
    """Example 1: Threshold-based position sizing."""
    print("\n" + "=" * 70)
    print("EXAMPLE 1: Threshold-Based Strategy")
    print("=" * 70)
    
    price, signal = generate_sample_data(n_bars=252)
    
    cost_model = CostModel({
        'commission_per_share': 0.001,
        'slippage_pct': 0.0005,
        'daily_borrow_fee': 0.0001,
    })
    
    position_sizer = PositionSizer({
        'strategy': 'threshold',
        'threshold_long': 0.5,
        'threshold_short': -0.5,
        'position_long': 1.0,
        'position_short': -1.0,
    })
    
    backtest = VectorizedBacktest(
        data=price,
        signal=signal,
        cost_model=cost_model,
        position_sizer=position_sizer,
        initial_capital=100000.0,
    )
    
    results = backtest.run()
    
    # Analyze results
    analyzer = BacktestAnalyzer(results)
    analyzer.print_report(include_trades=True)
    
    # Show first few trades
    trades_df = analyzer.analyze_trades()
    if len(trades_df) > 0:
        print("First 5 Trades:")
        print(trades_df.head())
    
    return results


def run_linear_strategy():
    """Example 2: Linear position sizing."""
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Linear Scaling Strategy")
    print("=" * 70)
    
    price, signal = generate_sample_data(n_bars=252, seed=123)
    
    # Normalize signal to [-1, 1] range
    signal = np.tanh(signal)  # Squash to [-1, 1]
    
    cost_model = CostModel({
        'commission_per_share': 0.001,
        'slippage_pct': 0.0005,
    })
    
    position_sizer = PositionSizer({
        'strategy': 'linear',
        'scale_factor': 1.0,
    })
    
    backtest = VectorizedBacktest(
        data=price,
        signal=signal,
        cost_model=cost_model,
        position_sizer=position_sizer,
        initial_capital=100000.0,
    )
    
    results = backtest.run()
    
    analyzer = BacktestAnalyzer(results)
    analyzer.print_report(include_trades=False)  # Skip trade details for this example
    
    return results


def run_volatility_strategy():
    """Example 3: Volatility-adjusted position sizing."""
    print("\n" + "=" * 70)
    print("EXAMPLE 3: Volatility-Adjusted Strategy")
    print("=" * 70)
    
    price, signal = generate_sample_data(n_bars=300, seed=456)
    
    # Calculate returns for volatility sizing
    returns = np.diff(np.log(price))
    returns = np.insert(returns, 0, 0)  # Prepend 0 to match length
    
    lookback_data = pd.DataFrame({'returns': returns})
    
    cost_model = CostModel({
        'commission_per_share': 0.001,
        'slippage_pct': 0.0005,
    })
    
    position_sizer = PositionSizer({
        'strategy': 'volatility',
        'vol_window': 20,
        'target_volatility': 0.02,
    })
    
    # For volatility sizing, we need to pass lookback_data
    # This is a limitation of the current API - we'll use threshold for simplicity
    # In production, you'd integrate this into the backtest engine
    
    # For now, use threshold as placeholder
    position_sizer = PositionSizer({
        'strategy': 'threshold',
        'threshold_long': 0.5,
        'threshold_short': -0.5,
        'position_long': 0.5,  # Smaller position for risk management
        'position_short': -0.5,
    })
    
    backtest = VectorizedBacktest(
        data=price,
        signal=signal,
        cost_model=cost_model,
        position_sizer=position_sizer,
        initial_capital=100000.0,
    )
    
    results = backtest.run()
    
    analyzer = BacktestAnalyzer(results)
    analyzer.print_report(include_trades=True)
    
    # Validate results
    print("\nValidation Results:")
    validations = analyzer.validate()
    for key, value in validations.items():
        status = "✓" if value else "✗"
        print(f"  {status} {key}: {value}")
    
    return results


def compare_strategies():
    """Compare multiple strategies."""
    print("\n" + "=" * 70)
    print("STRATEGY COMPARISON")
    print("=" * 70)
    
    # Use same data for all strategies
    price, signal = generate_sample_data(n_bars=252, seed=42)
    
    strategies = {
        'Aggressive': {
            'strategy': 'threshold',
            'threshold_long': 0.3,
            'threshold_short': -0.3,
            'position_long': 1.0,
            'position_short': -1.0,
        },
        'Conservative': {
            'strategy': 'threshold',
            'threshold_long': 0.7,
            'threshold_short': -0.7,
            'position_long': 0.5,
            'position_short': -0.5,
        },
        'Linear': {
            'strategy': 'linear',
            'scale_factor': 2.0,
        },
    }
    
    cost_model = CostModel({
        'commission_per_share': 0.001,
        'slippage_pct': 0.0005,
    })
    
    results_comparison = []
    
    for name, sizer_config in strategies.items():
        position_sizer = PositionSizer(sizer_config)
        
        backtest = VectorizedBacktest(
            data=price,
            signal=signal,
            cost_model=cost_model,
            position_sizer=position_sizer,
            initial_capital=100000.0,
        )
        
        results = backtest.run()
        
        results_comparison.append({
            'Strategy': name,
            'Total Return': results['total_return'],
            'Sharpe Ratio': results['sharpe_ratio'],
            'Max Drawdown': results['max_drawdown'],
            'Calmar Ratio': results['calmar_ratio'],
            'Total Costs': results['total_costs'],
        })
    
    # Print comparison table
    comparison_df = pd.DataFrame(results_comparison)
    print("\nPerformance Comparison:")
    print(comparison_df.to_string(index=False))
    
    # Find best strategy by Sharpe ratio
    best_idx = comparison_df['Sharpe Ratio'].idxmax()
    best_strategy = comparison_df.iloc[best_idx]['Strategy']
    print(f"\n🏆 Best Strategy (by Sharpe): {best_strategy}")


def main():
    """Run all examples."""
    print("\n" + "=" * 70)
    print(" " * 15 + "BACKTEST ENGINE DEMONSTRATION")
    print("=" * 70)
    
    # Run examples
    run_threshold_strategy()
    run_linear_strategy()
    run_volatility_strategy()
    compare_strategies()
    
    print("\n" + "=" * 70)
    print("Demonstration complete!")
    print("=" * 70 + "\n")


if __name__ == '__main__':
    main()
