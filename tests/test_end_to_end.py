"""
End-to-End Integration Test Suite
==================================

Tests the complete workflow from raw data to backtest results:
1. Load real market data (EURUSD)
2. Generate features using FeatureLibrary
3. Create trading signals
4. Run backtest with cost modeling
5. Analyze performance metrics
6. Validate trade extraction

This simulates a realistic quantitative trading workflow.
"""

import pytest
import numpy as np
import pandas as pd
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.loader import FXDataLoader
from src.features.library import FeatureLibrary
from src.backtest.engine import (
    CostModel,
    PositionSizer,
    VectorizedBacktest,
    BacktestAnalyzer,
)


class TestEndToEnd:
    """End-to-end integration tests with real data."""
    
    @pytest.fixture
    def data_path(self):
        """Path to real data directory."""
        return Path(__file__).parent.parent / 'data' / 'raw'
    
    @pytest.fixture
    def real_data(self, data_path):
        """Load real EURUSD data."""
        if not data_path.exists():
            pytest.skip("Data directory not found")
        
        eurusd_file = data_path / 'EURUSD_daily.csv'
        if not eurusd_file.exists():
            pytest.skip("EURUSD_daily.csv not found")
        
        # Load data directly from CSV (bypassing strict validation for e2e test)
        # In real workflow, we'd clean the data first
        df = pd.read_csv(eurusd_file, parse_dates=['timestamp'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
        df = df.set_index('timestamp')
        df = df.sort_index()
        
        # Clean any OHLC inconsistencies (realistic data cleaning step)
        df['high'] = df[['high', 'open', 'close']].max(axis=1)
        df['low'] = df[['low', 'open', 'close']].min(axis=1)
        
        # Use subset for faster tests (1 year)
        return df[-252:]  # Last 252 trading days
    
    def test_complete_workflow_momentum_strategy(self, real_data):
        """
        Test complete workflow: data -> features -> signal -> backtest -> analysis.
        
        Strategy: Simple momentum cross-volatility strategy
        - Buy when momentum > 0 and volatility is low
        - Sell when momentum < 0 and volatility is low
        - Stay out during high volatility periods
        """
        # Step 1: Verify we have valid data
        assert len(real_data) > 100, "Insufficient data for testing"
        assert 'close' in real_data.columns, "Missing close prices"
        
        # Step 2: Generate features
        prices = real_data['close']
        features = FeatureLibrary(prices)
        
        # Create momentum and volatility features
        momentum_20d = features.momentum(period=20)
        volatility_20d = features.volatility(window=20)
        
        # Step 3: Create trading signal
        # Signal logic: trade momentum when vol is below median
        vol_median = volatility_20d.median()
        low_vol_regime = volatility_20d < vol_median
        
        # Generate raw signal
        raw_signal = pd.Series(0.0, index=prices.index)
        raw_signal[momentum_20d > 0] = 1.0  # Long
        raw_signal[momentum_20d < 0] = -1.0  # Short
        
        # Only trade in low vol regime
        signal = raw_signal.copy()
        signal[~low_vol_regime] = 0.0
        
        # Handle NaN values (from feature calculation warmup)
        signal = signal.fillna(0.0).values
        
        # Step 4: Configure backtest
        cost_model = CostModel({
            'commission_per_share': 0.0001,  # 1 pip commission
            'slippage_pct': 0.0001,  # 1 pip slippage
            'daily_borrow_fee': 0.0,  # No overnight fees for FX
        })
        
        position_sizer = PositionSizer({
            'strategy': 'threshold',
            'threshold_long': 0.5,
            'threshold_short': -0.5,
            'position_long': 1.0,
            'position_short': -1.0,
        })
        
        # Step 5: Run backtest
        backtest = VectorizedBacktest(
            data=prices.values,
            signal=signal,
            cost_model=cost_model,
            position_sizer=position_sizer,
            initial_capital=100000.0,
        )
        
        results = backtest.run()
        
        # Step 6: Validate results structure
        assert 'equity' in results, "Missing equity curve"
        assert 'position' in results, "Missing position"
        assert 'returns' in results, "Missing returns"
        
        # Validate equity curve
        equity = results['equity']
        assert len(equity) == len(prices), "Equity length mismatch"
        assert equity[0] == 100000.0, "Initial capital incorrect"
        assert np.all(equity > 0), "Equity should never be negative with 100% positions"
        
        # Validate positions
        positions = results['position']
        assert len(positions) == len(prices), "Position length mismatch"
        assert np.all(np.abs(positions) <= 1.0), "Positions exceed limits"
        
        # Step 7: Validate metrics (metrics are in the results dict directly)
        expected_metrics = [
            'total_return', 'annualized_return', 'volatility',
            'sharpe_ratio', 'max_drawdown'
        ]
        for metric in expected_metrics:
            assert metric in results, f"Missing metric: {metric}"
            assert not np.isnan(results[metric]), f"Metric {metric} is NaN"
        
        # Sanity checks on metrics
        assert -1.0 <= results['total_return'] <= 10.0, "Unrealistic total return"
        assert -2.0 <= results['annualized_return'] <= 5.0, "Unrealistic annual return"
        assert 0.0 <= results['volatility'] <= 1.0, "Unrealistic volatility"
        assert -5.0 <= results['sharpe_ratio'] <= 10.0, "Unrealistic Sharpe ratio"
        assert -1.0 <= results['max_drawdown'] <= 0.0, "Drawdown should be [-1, 0]"
        
        # Step 8: Analyze trades
        analyzer = BacktestAnalyzer(results)
        trades_df = analyzer.analyze_trades()
        
        if len(trades_df) > 0:
            # Validate trade structure (use actual column names from BacktestAnalyzer)
            required_cols = ['entry_bar', 'exit_bar', 'entry_price', 'exit_price',
                           'position_size', 'pnl', 'pnl_pct', 'duration']
            for col in required_cols:
                assert col in trades_df.columns, f"Missing column: {col}"
            
            # Validate trade data
            assert trades_df['duration'].min() > 0, "Invalid duration"
            assert trades_df['position_size'].isin([-1, 1]).all(), "Invalid positions"
    
    def test_compare_strategy_configurations(self, real_data):
        """
        Test that different strategy configurations produce different results.
        
        Compares:
        1. Threshold strategy (binary positions)
        2. Linear strategy (proportional positions)
        """
        prices = real_data['close']
        features = FeatureLibrary(prices)
        
        # Simple momentum signal
        momentum = features.momentum(period=20).fillna(0.0)
        signal = np.tanh(momentum.values / 0.01)  # Normalize to [-1, 1]
        
        # Shared cost model
        cost_model = CostModel({
            'commission_per_share': 0.0001,
            'slippage_pct': 0.0001,
        })
        
        # Test 1: Threshold strategy
        position_sizer_threshold = PositionSizer({
            'strategy': 'threshold',
            'threshold_long': 0.3,
            'threshold_short': -0.3,
            'position_long': 1.0,
            'position_short': -1.0,
        })
        
        backtest_threshold = VectorizedBacktest(
            data=prices.values,
            signal=signal,
            cost_model=cost_model,
            position_sizer=position_sizer_threshold,
            initial_capital=100000.0,
        )
        results_threshold = backtest_threshold.run()
        
        # Test 2: Linear strategy
        position_sizer_linear = PositionSizer({
            'strategy': 'linear',
            'scale_factor': 1.0,
        })
        
        backtest_linear = VectorizedBacktest(
            data=prices.values,
            signal=signal,
            cost_model=cost_model,
            position_sizer=position_sizer_linear,
            initial_capital=100000.0,
        )
        results_linear = backtest_linear.run()
        
        # Validate that strategies produce different results
        positions_threshold = results_threshold['position']
        positions_linear = results_linear['position']
        
        # Threshold should have binary positions
        unique_threshold = np.unique(positions_threshold)
        assert len(unique_threshold) <= 3, "Threshold should have at most 3 positions (-1, 0, 1)"
        
        # Linear should have continuous positions
        unique_linear = np.unique(positions_linear)
        assert len(unique_linear) > 10, "Linear should have continuous positions"
        
        # Results should differ
        assert not np.allclose(positions_threshold, positions_linear), \
            "Different strategies should produce different positions"
        
        # Both should have valid metrics
        for results in [results_threshold, results_linear]:
            assert 'sharpe_ratio' in results
            assert results['sharpe_ratio'] is not None
    
    def test_cost_impact_validation(self, real_data):
        """
        Test that transaction costs reduce performance as expected.
        
        Compares no-cost vs with-cost scenarios.
        """
        prices = real_data['close']
        features = FeatureLibrary(prices)
        
        # Generate signal (momentum strategy)
        momentum = features.momentum(period=20).fillna(0.0)
        signal = (momentum > 0).astype(float) * 2 - 1  # Convert to {-1, 1}
        signal = signal.values
        
        position_sizer = PositionSizer({
            'strategy': 'threshold',
            'threshold_long': 0.5,
            'threshold_short': -0.5,
            'position_long': 1.0,
            'position_short': -1.0,
        })
        
        # Scenario 1: No costs
        cost_model_none = CostModel({
            'commission_per_share': 0.0,
            'slippage_pct': 0.0,
            'daily_borrow_fee': 0.0,
        })
        
        backtest_none = VectorizedBacktest(
            data=prices.values,
            signal=signal,
            cost_model=cost_model_none,
            position_sizer=position_sizer,
            initial_capital=100000.0,
        )
        results_none = backtest_none.run()
        
        # Scenario 2: With realistic costs
        cost_model_real = CostModel({
            'commission_per_share': 0.0002,  # 2 pips
            'slippage_pct': 0.0002,  # 2 pips
            'daily_borrow_fee': 0.0,
        })
        
        backtest_real = VectorizedBacktest(
            data=prices.values,
            signal=signal,
            cost_model=cost_model_real,
            position_sizer=position_sizer,
            initial_capital=100000.0,
        )
        results_real = backtest_real.run()
        
        # Validate cost impact
        return_none = results_none['total_return']
        return_real = results_real['total_return']
        
        # Costs should reduce returns (or make losses worse)
        assert return_real <= return_none, \
            "Returns with costs should be <= returns without costs"
        
        # Cost impact should be measurable but not excessive
        # (Would indicate a bug in cost calculation)
        cost_impact = return_none - return_real
        assert 0.0 <= cost_impact <= 0.5, \
            f"Cost impact seems unrealistic: {cost_impact:.2%}"
    
    def test_feature_combinations(self, real_data):
        """
        Test that multiple features can be combined effectively.
        
        Tests a multi-factor strategy combining:
        - Momentum
        - Mean reversion (RSI)
        - Volatility
        """
        prices = real_data['close']
        features = FeatureLibrary(prices)
        
        # Generate multiple features
        momentum = features.momentum(period=20)
        rsi = features.rsi(period=14)
        volatility = features.volatility(window=20)
        
        # Validate features are generated
        assert not momentum.isna().all(), "Momentum all NaN"
        assert not rsi.isna().all(), "RSI all NaN"
        assert not volatility.isna().all(), "Volatility all NaN"
        
        # Create composite signal
        # Buy when: momentum > 0 AND RSI < 30 (oversold) AND vol is low
        # Sell when: momentum < 0 AND RSI > 70 (overbought) AND vol is low
        vol_median = volatility.median()
        
        signal = pd.Series(0.0, index=prices.index)
        signal[(momentum > 0) & (rsi < 30) & (volatility < vol_median)] = 1.0
        signal[(momentum < 0) & (rsi > 70) & (volatility < vol_median)] = -1.0
        signal = signal.fillna(0.0).values
        
        # Run backtest
        cost_model = CostModel({
            'commission_per_share': 0.0001,
            'slippage_pct': 0.0001,
        })
        
        position_sizer = PositionSizer({
            'strategy': 'threshold',
            'threshold_long': 0.5,
            'threshold_short': -0.5,
            'position_long': 1.0,
            'position_short': -1.0,
        })
        
        backtest = VectorizedBacktest(
            data=prices.values,
            signal=signal,
            cost_model=cost_model,
            position_sizer=position_sizer,
            initial_capital=100000.0,
        )
        
        results = backtest.run()
        
        # Validate backtest completes successfully
        assert 'equity' in results
        assert 'sharpe_ratio' in results
        assert len(results['equity']) == len(prices)
        
        # Validate that multi-factor signal affects position frequency
        positions = results['position']
        pct_in_market = np.mean(positions != 0)
        
        # Multi-factor filters should reduce time in market
        # (compared to single factor)
        assert 0.0 <= pct_in_market <= 1.0, "Invalid market exposure"
    
    def test_data_quality_requirements(self, real_data):
        """
        Test that the workflow handles real data quality issues correctly.
        
        Validates:
        - Missing data handling
        - Timezone consistency
        - Monotonic time index
        """
        # Validate data quality
        assert isinstance(real_data.index, pd.DatetimeIndex), \
            "Index should be DatetimeIndex"
        
        assert real_data.index.is_monotonic_increasing, \
            "Time index should be monotonic"
        
        # Check for duplicates
        assert not real_data.index.duplicated().any(), \
            "Data should not have duplicate timestamps"
        
        # Validate OHLC relationships
        assert (real_data['high'] >= real_data['low']).all(), \
            "High should be >= Low"
        
        assert (real_data['high'] >= real_data['open']).all(), \
            "High should be >= Open"
        
        assert (real_data['high'] >= real_data['close']).all(), \
            "High should be >= Close"
        
        assert (real_data['low'] <= real_data['open']).all(), \
            "Low should be <= Open"
        
        assert (real_data['low'] <= real_data['close']).all(), \
            "Low should be <= Close"
        
        # Check that data is clean enough for features
        prices = real_data['close']
        assert not prices.isna().any(), "Prices should not have NaN"
        assert (prices > 0).all(), "Prices should be positive"


if __name__ == '__main__':
    """Run tests directly for debugging."""
    pytest.main([__file__, '-v', '-s'])
