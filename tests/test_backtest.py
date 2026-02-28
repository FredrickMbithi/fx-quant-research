"""
Tests for backtest engine.

Tests cover:
- CostModel: Entry and holding costs
- PositionSizer: Threshold, linear, and volatility sizing
- VectorizedBacktest: Core backtesting logic
- PerformanceMetrics: All metrics calculations
- TradeAnalyzer: Trade extraction and statistics
- BacktestAnalyzer: Comprehensive analysis
"""

import pytest
import numpy as np
import pandas as pd
from src.backtest.engine import (
    CostModel,
    PositionSizer,
    VectorizedBacktest,
    PerformanceMetrics,
    TradeAnalyzer,
    BacktestAnalyzer,
)


class TestCostModel:
    """Test CostModel functionality."""
    
    def test_initialization(self):
        """Test CostModel initialization."""
        config = {
            'commission_per_share': 0.001,
            'slippage_pct': 0.0005,
            'daily_borrow_fee': 0.0001,
        }
        model = CostModel(config)
        
        assert model.commission_per_share == 0.001
        assert model.slippage_pct == 0.0005
        assert model.daily_borrow_fee == 0.0001
    
    def test_entry_cost_scalar(self):
        """Test entry cost calculation with scalar inputs."""
        model = CostModel({
            'commission_per_share': 0.001,
            'slippage_pct': 0.0005,
        })
        
        # Test with position change of 100 units at price 50
        cost = model.cost_entry(100, 50)
        expected = 100 * 0.001 + 100 * 0.0005 * 50  # commission + slippage
        assert np.isclose(cost, expected)
    
    def test_entry_cost_array(self):
        """Test entry cost calculation with array inputs."""
        model = CostModel({
            'commission_per_share': 0.001,
            'slippage_pct': 0.0005,
        })
        
        position_change = np.array([100, -50, 200])
        price = np.array([50, 51, 52])
        
        costs = model.cost_entry(position_change, price)
        
        # Check it returns array
        assert isinstance(costs, np.ndarray)
        assert len(costs) == 3
        
        # Check values
        expected_0 = 100 * 0.001 + 100 * 0.0005 * 50
        assert np.isclose(costs[0], expected_0)
    
    def test_holding_cost(self):
        """Test holding cost calculation."""
        model = CostModel({
            'daily_borrow_fee': 0.0005,
        })
        
        # Long position (should have no borrow cost)
        cost_long = model.cost_hold(1.0, period_days=1)
        assert cost_long == 0.0
        
        # Short position (should have borrow cost)
        cost_short = model.cost_hold(-1.0, period_days=1)
        assert cost_short == 0.0005
        
        # Multiple days
        cost_short_5d = model.cost_hold(-1.0, period_days=5)
        assert np.isclose(cost_short_5d, 0.0005 * 5)


class TestPositionSizer:
    """Test PositionSizer functionality."""
    
    def test_threshold_sizing(self):
        """Test threshold-based position sizing."""
        config = {
            'strategy': 'threshold',
            'threshold_long': 0.5,
            'threshold_short': -0.5,
            'position_long': 1.0,
            'position_short': -1.0,
        }
        sizer = PositionSizer(config)
        
        # Test long signal
        assert sizer.size(0.8) == 1.0
        
        # Test short signal
        assert sizer.size(-0.8) == -1.0
        
        # Test neutral signal
        assert sizer.size(0.0) == 0.0
        assert sizer.size(0.3) == 0.0
        assert sizer.size(-0.3) == 0.0
    
    def test_threshold_sizing_array(self):
        """Test threshold sizing with array input."""
        config = {
            'strategy': 'threshold',
            'threshold_long': 0.5,
            'threshold_short': -0.5,
            'position_long': 1.0,
            'position_short': -1.0,
        }
        sizer = PositionSizer(config)
        
        signals = np.array([0.8, -0.8, 0.0, 0.3, -0.3])
        positions = sizer.size(signals)
        
        expected = np.array([1.0, -1.0, 0.0, 0.0, 0.0])
        assert np.allclose(positions, expected)
    
    def test_linear_sizing(self):
        """Test linear position sizing."""
        config = {
            'strategy': 'linear',
            'scale_factor': 2.0,
        }
        sizer = PositionSizer(config)
        
        # Test various signals
        assert sizer.size(2.0) == 1.0  # Clipped to max
        assert sizer.size(-2.0) == -1.0  # Clipped to min
        assert sizer.size(1.0) == 0.5
        assert sizer.size(0.0) == 0.0
    
    def test_volatility_sizing(self):
        """Test volatility-adjusted position sizing."""
        config = {
            'strategy': 'volatility',
            'vol_window': 5,
            'target_volatility': 0.02,
        }
        sizer = PositionSizer(config)
        
        # Create sample returns data
        returns = np.array([0.01, -0.01, 0.02, -0.015, 0.005, 0.01, -0.01, 0.02, -0.01, 0.005])
        lookback_data = pd.DataFrame({'returns': returns})
        
        signal = np.ones(10)  # Constant long signal
        
        # This should scale position based on volatility
        positions = sizer.size(signal, lookback_data=lookback_data)
        
        # Check it returns array
        assert isinstance(positions, np.ndarray)
        assert len(positions) == 10
        
        # First few values will be NaN due to rolling window
        assert np.isnan(positions[0])
        
        # Check valid positions (after window) are within valid range
        valid_positions = positions[~np.isnan(positions)]
        assert np.all(valid_positions >= -1.0)
        assert np.all(valid_positions <= 1.0)
    
    def test_invalid_strategy(self):
        """Test that invalid strategy raises error."""
        config = {'strategy': 'invalid'}
        sizer = PositionSizer(config)
        
        with pytest.raises(ValueError, match="Unknown strategy"):
            sizer.size(1.0)


class TestPerformanceMetrics:
    """Test PerformanceMetrics calculations."""
    
    def test_total_return(self):
        """Test total return calculation."""
        equity = np.array([100, 110, 105, 115, 120])
        
        total_ret = PerformanceMetrics.total_return(equity)
        expected = (120 - 100) / 100
        
        assert np.isclose(total_ret, expected)
    
    def test_annualized_return(self):
        """Test annualized return calculation."""
        # Double in 252 days (1 year)
        equity = np.linspace(100, 200, 252)
        
        ann_ret = PerformanceMetrics.annualized_return(equity, periods_per_year=252)
        
        # Should be approximately 100% annual return
        assert np.isclose(ann_ret, 1.0, rtol=0.01)
    
    def test_volatility(self):
        """Test volatility calculation."""
        # Create returns with known std dev
        returns = np.random.randn(252) * 0.01  # 1% daily std dev
        
        vol = PerformanceMetrics.volatility(returns, periods_per_year=252)
        
        # Should be approximately 1% * sqrt(252) = ~15.9%
        assert 0.12 < vol < 0.20  # Rough check due to randomness
    
    def test_sharpe_ratio(self):
        """Test Sharpe ratio calculation."""
        # Create returns with positive mean
        np.random.seed(42)
        returns = np.random.randn(252) * 0.01 + 0.0005  # Positive drift
        
        sharpe = PerformanceMetrics.sharpe_ratio(returns, periods_per_year=252)
        
        # Should be positive
        assert sharpe > 0
    
    def test_sortino_ratio(self):
        """Test Sortino ratio calculation."""
        np.random.seed(42)
        returns = np.random.randn(252) * 0.01 + 0.0005
        
        sortino = PerformanceMetrics.sortino_ratio(returns, periods_per_year=252)
        
        # Should be positive and typically higher than Sharpe
        assert sortino > 0
    
    def test_max_drawdown(self):
        """Test maximum drawdown calculation."""
        # Create equity curve with known drawdown
        equity = np.array([100, 110, 120, 100, 90, 95, 105, 115])
        
        dd_metrics = PerformanceMetrics.drawdown_metrics(equity)
        
        # Max is from 120 to 90 = -25%
        expected_max_dd = (90 - 120) / 120
        
        assert np.isclose(dd_metrics['max_drawdown'], expected_max_dd, rtol=0.01)
        assert dd_metrics['max_drawdown_duration'] > 0
    
    def test_drawdown_series(self):
        """Test drawdown series calculation."""
        equity = np.array([100, 110, 105, 115, 120])
        
        dd_metrics = PerformanceMetrics.drawdown_metrics(equity)
        dd_series = dd_metrics['drawdown_series']
        
        # First point should have 0 drawdown (at peak)
        assert dd_series[0] == 0.0
        
        # Check shape
        assert len(dd_series) == len(equity)
    
    def test_turnover(self):
        """Test portfolio turnover calculation."""
        position = np.array([0, 1, 1, 0, -1, -1, 0])
        
        turnover = PerformanceMetrics.turnover(position)
        
        # Changes: 1, 0, 1, 1, 0, 1 -> avg = 4/6
        expected = (1 + 0 + 1 + 1 + 0 + 1) / 6
        
        assert np.isclose(turnover, expected)


class TestTradeAnalyzer:
    """Test TradeAnalyzer functionality."""
    
    def test_extract_trades_simple(self):
        """Test simple trade extraction."""
        position = np.array([0, 1, 1, 1, 0, -1, -1, 0])
        price = np.array([100, 101, 102, 103, 104, 105, 106, 107])
        equity = np.array([1000, 1001, 1002, 1003, 1004, 1003, 1002, 1001])
        
        trades_df = TradeAnalyzer.extract_trades(position, price, equity)
        
        # Should have 2 trades
        assert len(trades_df) == 2
        
        # First trade: long from bar 1 to 4
        assert trades_df.iloc[0]['entry_bar'] == 1
        assert trades_df.iloc[0]['exit_bar'] == 4
        assert trades_df.iloc[0]['position_size'] == 1
        
        # Second trade: short from bar 5 to 7
        assert trades_df.iloc[1]['entry_bar'] == 5
        assert trades_df.iloc[1]['exit_bar'] == 7
        assert trades_df.iloc[1]['position_size'] == -1
    
    def test_extract_trades_open_position(self):
        """Test trade extraction with open position at end."""
        position = np.array([0, 1, 1, 1, 1])
        price = np.array([100, 101, 102, 103, 104])
        equity = np.array([1000, 1001, 1002, 1003, 1004])
        
        trades_df = TradeAnalyzer.extract_trades(position, price, equity)
        
        # Should have 1 trade that's still open
        assert len(trades_df) == 1
        assert trades_df.iloc[0]['exit_bar'] == 4
    
    def test_trade_metrics(self):
        """Test trade metrics calculation."""
        # Create sample trades
        trades_data = {
            'pnl': [100, -50, 150, -30, 80],
            'duration': [5, 3, 7, 2, 4],
        }
        trades_df = pd.DataFrame(trades_data)
        
        metrics = TradeAnalyzer.calculate_trade_metrics(trades_df)
        
        assert metrics['total_trades'] == 5
        assert metrics['winning_trades'] == 3
        assert metrics['losing_trades'] == 2
        assert metrics['win_rate'] == 0.6
        
        # Profit factor
        total_wins = 100 + 150 + 80
        total_losses = 50 + 30
        expected_pf = total_wins / total_losses
        assert np.isclose(metrics['profit_factor'], expected_pf)


class TestVectorizedBacktest:
    """Test VectorizedBacktest core functionality."""
    
    def test_initialization(self):
        """Test backtest initialization."""
        price = np.array([100, 101, 102, 103, 104])
        signal = np.array([0, 1, 1, 0, -1])
        
        cost_model = CostModel({'commission_per_share': 0.001, 'slippage_pct': 0.0005})
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
            initial_capital=10000,
        )
        
        assert len(backtest.data) == 5
        assert backtest.initial_capital == 10000
    
    def test_signal_lag(self):
        """Test that signal is lagged by 1 bar."""
        price = np.array([100, 101, 102, 103, 104])
        signal = np.array([0, 1, 1, 0, -1])
        
        cost_model = CostModel({'commission_per_share': 0.0, 'slippage_pct': 0.0})
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
        )
        
        results = backtest.run()
        
        # Lagged signal should have 0 at first position
        assert results['lagged_signal'][0] == 0
        
        # Lagged signal should match original signal shifted by 1
        assert np.array_equal(results['lagged_signal'][1:], results['signal'][:-1])
    
    def test_run_basic(self):
        """Test basic backtest run."""
        np.random.seed(42)
        price = 100 + np.cumsum(np.random.randn(100) * 0.5)
        signal = np.sin(np.linspace(0, 4 * np.pi, 100))
        
        cost_model = CostModel({
            'commission_per_share': 0.001,
            'slippage_pct': 0.0005,
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
            initial_capital=100000,
        )
        
        results = backtest.run()
        
        # Check all expected keys are present
        assert 'equity' in results
        assert 'position' in results
        assert 'returns' in results
        assert 'sharpe_ratio' in results
        assert 'max_drawdown' in results
        assert 'total_return' in results
        
        # Check data shapes
        assert len(results['equity']) == 100
        assert len(results['position']) == 100
        assert len(results['returns']) == 99
    
    def test_positive_equity(self):
        """Test that equity stays reasonable."""
        price = np.linspace(100, 110, 50)  # Uptrend
        signal = np.ones(50)  # Always long
        
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
            initial_capital=100000,
        )
        
        results = backtest.run()
        
        # Equity should generally increase with uptrend
        assert results['equity'][-1] > results['equity'][0]
    
    def test_validation_errors(self):
        """Test that validation catches errors."""
        price = np.array([100, np.nan, 102])  # NaN in data
        signal = np.array([0, 1, 0])
        
        cost_model = CostModel({'commission_per_share': 0.001})
        position_sizer = PositionSizer({'strategy': 'threshold'})
        
        with pytest.raises(ValueError, match="NaN"):
            backtest = VectorizedBacktest(
                data=price,
                signal=signal,
                cost_model=cost_model,
                position_sizer=position_sizer,
            )
    
    def test_length_mismatch(self):
        """Test that length mismatch raises error."""
        price = np.array([100, 101, 102])
        signal = np.array([0, 1])  # Different length
        
        cost_model = CostModel({'commission_per_share': 0.001})
        position_sizer = PositionSizer({'strategy': 'threshold'})
        
        with pytest.raises(ValueError, match="length mismatch"):
            backtest = VectorizedBacktest(
                data=price,
                signal=signal,
                cost_model=cost_model,
                position_sizer=position_sizer,
            )


class TestBacktestAnalyzer:
    """Test BacktestAnalyzer functionality."""
    
    def test_initialization(self):
        """Test analyzer initialization."""
        results = {
            'equity': np.array([100, 110, 120]),
            'position': np.array([0, 1, 1]),
            'price': np.array([100, 101, 102]),
            'returns': np.array([0.01, 0.01]),
            'total_return': 0.2,
        }
        
        analyzer = BacktestAnalyzer(results)
        assert analyzer.results is not None
    
    def test_get_summary(self):
        """Test summary generation."""
        np.random.seed(42)
        price = 100 + np.cumsum(np.random.randn(100) * 0.5)
        signal = np.sin(np.linspace(0, 4 * np.pi, 100))
        
        cost_model = CostModel({'commission_per_share': 0.001, 'slippage_pct': 0.0005})
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
            initial_capital=100000,
        )
        
        results = backtest.run()
        analyzer = BacktestAnalyzer(results)
        
        summary = analyzer.get_summary(include_trades=True)
        
        # Check structure
        assert 'performance' in summary
        assert 'risk' in summary
        assert 'costs' in summary
        assert 'equity' in summary
        assert 'trades' in summary
    
    def test_validate(self):
        """Test validation."""
        np.random.seed(42)
        price = 100 + np.cumsum(np.random.randn(50) * 0.5)
        signal = np.random.randn(50)
        
        cost_model = CostModel({'commission_per_share': 0.001})
        position_sizer = PositionSizer({'strategy': 'linear', 'scale_factor': 2.0})
        
        backtest = VectorizedBacktest(
            data=price,
            signal=signal,
            cost_model=cost_model,
            position_sizer=position_sizer,
        )
        
        results = backtest.run()
        analyzer = BacktestAnalyzer(results)
        
        validations = analyzer.validate()
        
        # Should pass most validations
        assert validations['no_nan_equity']
        assert validations['positive_equity']
        assert validations['reasonable_costs']
    
    def test_rolling_metrics(self):
        """Test rolling metrics calculation."""
        np.random.seed(42)
        price = 100 + np.cumsum(np.random.randn(300) * 0.5)
        signal = np.random.randn(300)
        
        cost_model = CostModel({'commission_per_share': 0.001})
        position_sizer = PositionSizer({'strategy': 'linear', 'scale_factor': 2.0})
        
        backtest = VectorizedBacktest(
            data=price,
            signal=signal,
            cost_model=cost_model,
            position_sizer=position_sizer,
        )
        
        results = backtest.run()
        analyzer = BacktestAnalyzer(results)
        
        rolling = analyzer.get_rolling_metrics(window=50)
        
        # Check columns exist
        assert 'rolling_return' in rolling.columns
        assert 'rolling_volatility' in rolling.columns
        assert 'rolling_sharpe' in rolling.columns


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
