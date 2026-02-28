"""
Enhanced Vectorized Backtest with Exit Manager Support
Extends the base VectorizedBacktest to work with OHLC data and trailing stops
"""

import numpy as np
import pandas as pd
from typing import Dict, Union, Optional
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.backtest.engine import CostModel, PositionSizer, PerformanceMetrics
from src.backtest.exit_manager import TrailingStopManager, ExitConfig


class EnhancedVectorizedBacktest:
    """
    Enhanced backtesting engine with OHLC support and exit management.
    
    Improvements over base VectorizedBacktest:
    - Accepts OHLC DataFrame instead of just close prices
    - Supports TrailingStopManager for complex exit logic
    - Maintains backward compatibility with price-only mode
    
    Pipeline:
    1. Apply 1-bar lag to signal
    2. Size positions based on signal
    3. Apply exit logic (if exit_manager provided)
    4. Calculate position changes and costs
    5. Generate equity curve via cumulative PnL
    6. Return results with transaction details
    """
    
    def __init__(
        self,
        prices: Union[pd.DataFrame, np.ndarray, pd.Series],
        signal: Union[np.ndarray, pd.Series],
        cost_model: CostModel,
        position_sizer: PositionSizer,
        exit_manager: Optional[TrailingStopManager] = None,
        initial_capital: float = 100000.0,
        periods_per_year: int = 252
    ):
        """
        Initialize enhanced backtest.
        
        Args:
            prices: OHLC DataFrame with columns ['open', 'high', 'low', 'close']
                    OR single price array (for backward compatibility)
            signal: Raw signal values (same length as prices)
            cost_model: CostModel instance for transaction costs
            position_sizer: PositionSizer instance for position sizing
            exit_manager: Optional TrailingStopManager for complex exits
            initial_capital: Starting equity
            periods_per_year: Number of periods per year (252 for daily, 252*24/4 for 4H)
        """
        # Handle both DataFrame and array inputs
        if isinstance(prices, pd.DataFrame):
            # OHLC mode
            required_cols = ['open', 'high', 'low', 'close']
            if not all(col in prices.columns for col in required_cols):
                raise ValueError(f"DataFrame must have columns: {required_cols}")
            
            self.prices_df = prices[required_cols].copy()
            self.close_prices = prices['close'].values
            self.ohlc_mode = True
        else:
            # Single price mode (backward compatible)
            self.close_prices = np.asarray(prices, dtype=np.float64)
            self.prices_df = None
            self.ohlc_mode = False
        
        self.signal = np.asarray(signal, dtype=np.float64)
        self.cost_model = cost_model
        self.position_sizer = position_sizer
        self.exit_manager = exit_manager
        self.initial_capital = initial_capital
        self.periods_per_year = periods_per_year
        
        self.n_bars = len(self.close_prices)
        
        # Validation
        if len(self.signal) != self.n_bars:
            raise ValueError(
                f"Signal length ({len(self.signal)}) != prices length ({self.n_bars})"
            )
        
        self._validate_inputs()
    
    def _validate_inputs(self):
        """Check for invalid inputs."""
        if np.any(np.isnan(self.close_prices)):
            raise ValueError("Price data contains NaN values")
        if np.any(np.isinf(self.close_prices)):
            raise ValueError("Price data contains infinite values")
        if self.initial_capital <= 0:
            raise ValueError("Initial capital must be positive")
        
        # Validate exit manager compatibility
        if self.exit_manager is not None and not self.ohlc_mode:
            raise ValueError(
                "Exit manager requires OHLC DataFrame (not single price array)"
            )
    
    def run(self) -> Dict:
        """
        Execute backtest and return results.
        
        Returns:
            Dict with backtest results including:
            - Price/signal/position arrays
            - Equity curve
            - Performance metrics
            - Trade-level statistics
            - Exit information (if exit_manager used)
        """
        # Step 1: Apply 1-bar lag to signal (realistic execution delay)
        lagged_signal = self._apply_lag()
        
        # Step 2: Size positions from lagged signal
        position_initial = self._size_positions(lagged_signal)
        
        # Step 3: Apply exit logic (if exit manager provided)
        if self.exit_manager is not None:
            position, exit_info_df = self.exit_manager.apply_exits(
                prices=self.prices_df,
                signals=lagged_signal,
                positions=position_initial
            )
            exit_stats = self.exit_manager.get_exit_statistics(exit_info_df)
        else:
            position = position_initial
            exit_info_df = None
            exit_stats = None
        
        # Step 4: Calculate costs
        position_change = np.diff(position, prepend=0)
        costs = np.zeros(self.n_bars)
        costs[1:] = self.cost_model.cost_entry(
            position_change[1:],
            self.close_prices[1:]
        )
        
        # Step 5: Calculate P&L and equity curve
        # For simplicity, use close-to-close P&L
        # (more sophisticated: could use entry_price tracking)
        price_returns = np.diff(self.close_prices, prepend=0)
        price_returns[0] = 0  # No return on first bar
        
        # P&L = position * price_change * initial_capital
        # (position is in fractional units, e.g., 1.0 = 100% of capital)
        strategy_returns = position[:-1] * price_returns[1:]
        strategy_returns = np.insert(strategy_returns, 0, 0)  # Pad first bar
        
        # Calculate equity
        cumulative_returns = np.cumsum(strategy_returns)
        cumulative_costs = np.cumsum(costs)
        
        equity = self.initial_capital + (cumulative_returns * self.initial_capital) - cumulative_costs
        
        # Ensure equity never goes negative (bankruptcy check)
        if np.any(equity <= 0):
            print("⚠️  Warning: Equity went negative (bankruptcy). Results may be invalid.")
        
        # Calculate log returns for metrics
        returns = np.diff(np.log(equity + 1)) if np.all(equity > 0) else np.zeros(self.n_bars - 1)
        
        # Step 6: Calculate performance metrics
        metrics = PerformanceMetrics.calculate_all(
            equity=equity,
            returns=returns,
            position=position,
            costs=costs,
            periods_per_year=self.periods_per_year
        )
        
        # Build results dictionary
        results = {
            # Arrays
            'equity': equity,
            'position': position,
            'position_initial': position_initial,  # Before exits
            'price': self.close_prices,
            'signal': self.signal,
            'lagged_signal': lagged_signal,
            'returns': returns,
            'costs': costs,
            'strategy_returns': strategy_returns,
            
            # Exit info (if applicable)
            'exit_info': exit_info_df,
            'exit_stats': exit_stats,
            
            # Metadata
            'initial_capital': self.initial_capital,
            'periods_per_year': self.periods_per_year,
            'n_bars': self.n_bars,
        }
        
        # Add performance metrics
        results.update(metrics)
        
        return results
    
    def _apply_lag(self) -> np.ndarray:
        """
        Apply 1-bar lag to signal (realistic execution delay).
        
        Signal at time t is executed at time t+1.
        """
        lagged = np.roll(self.signal, 1)
        lagged[0] = 0.0  # No signal on first bar
        return lagged
    
    def _size_positions(self, lagged_signal: np.ndarray) -> np.ndarray:
        """Convert lagged signal to position weights."""
        position = self.position_sizer.size(lagged_signal)
        return np.asarray(position, dtype=np.float64)


if __name__ == "__main__":
    # Test the enhanced backtest with exit manager
    print("="*60)
    print("TESTING ENHANCED VECTORIZED BACKTEST")
    print("="*60)
    
    # Create synthetic OHLC data
    n_bars = 100
    dates = pd.date_range('2024-01-01', periods=n_bars, freq='D')
    
    np.random.seed(42)
    close_prices = 100 + np.cumsum(np.random.randn(n_bars) * 1.5)
    
    prices_df = pd.DataFrame({
        'open': close_prices + np.random.randn(n_bars) * 0.5,
        'high': close_prices + np.abs(np.random.randn(n_bars)) * 1.0,
        'low': close_prices - np.abs(np.random.randn(n_bars)) * 1.0,
        'close': close_prices,
    }, index=dates)
    
    # Create signal (simple sine wave)
    signal = np.sin(np.linspace(0, 4*np.pi, n_bars))
    
    # Initialize components
    cost_model = CostModel({
        'commission_per_share': 0.001,
        'slippage_pct': 0.0005,
    })
    
    position_sizer = PositionSizer({
        'strategy': 'threshold',
        'threshold_long': 0.3,
        'threshold_short': -0.3,
        'position_long': 1.0,
        'position_short': -1.0,
    })
    
    exit_config = ExitConfig(
        hard_stop_pips=100.0,  # 100 pips for stocks (scaled)
        profit_trigger_pips=40.0,
        trailing_distance_pips=30.0,
        max_hold_bars=10,
        pip_size=0.01  # 1 cent for stocks
    )
    
    exit_manager = TrailingStopManager(exit_config)
    
    # Run backtest WITHOUT exit manager
    print("\n1. Backtest without exit manager:")
    backtest_basic = EnhancedVectorizedBacktest(
        prices=prices_df,
        signal=signal,
        cost_model=cost_model,
        position_sizer=position_sizer,
        exit_manager=None,
        initial_capital=100000.0,
        periods_per_year=252
    )
    
    results_basic = backtest_basic.run()
    
    print(f"   Total Return: {results_basic['total_return']:.2%}")
    print(f"   Sharpe Ratio: {results_basic['sharpe_ratio']:.2f}")
    print(f"   Max Drawdown: {results_basic['max_drawdown']:.2%}")
    
    # Run backtest WITH exit manager
    print("\n2. Backtest with exit manager:")
    backtest_exits = EnhancedVectorizedBacktest(
        prices=prices_df,
        signal=signal,
        cost_model=cost_model,
        position_sizer=position_sizer,
        exit_manager=exit_manager,
        initial_capital=100000.0,
        periods_per_year=252
    )
    
    results_exits = backtest_exits.run()
    
    print(f"   Total Return: {results_exits['total_return']:.2%}")
    print(f"   Sharpe Ratio: {results_exits['sharpe_ratio']:.2f}")
    print(f"   Max Drawdown: {results_exits['max_drawdown']:.2%}")
    
    if results_exits['exit_stats']:
        print(f"\n   Exit Statistics:")
        for key, value in results_exits['exit_stats'].items():
            if isinstance(value, float):
                print(f"     {key}: {value:.2f}")
            else:
                print(f"     {key}: {value}")
    
    print("\n" + "="*60)
    print("Test complete!")
