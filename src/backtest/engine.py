"""
Vectorized Backtest Engine

A high-performance backtesting engine that:
1. Applies 1-bar lag to signals (realistic execution timing)
2. Vectorizes core operations for speed
3. Models transaction costs and slippage
4. Generates equity curves with detailed transaction tracking

Architecture: See docs/backtest_spec.md
"""

import numpy as np
import pandas as pd
from typing import Dict, Tuple, Optional, Union


class CostModel:
    """
    Models transaction and holding costs.
    
    Supports:
    - Entry/exit costs (commission, slippage)
    - Holding costs (borrow fees, financing)
    - Per-bar cost accumulation
    """
    
    def __init__(self, config: Dict):
        """
        Initialize cost model.
        
        Args:
            config: Dict with keys:
                - commission_per_share: float (e.g., 0.001)
                - slippage_pct: float (e.g., 0.0005 for 0.05% slippage)
                - daily_borrow_fee: float (e.g., 0.0005 for 0.05% daily)
                - intraday_cost: bool (apply costs intrabar or interbar)
        """
        self.config = config
        self.commission_per_share = config.get('commission_per_share', 0.0)
        self.slippage_pct = config.get('slippage_pct', 0.0)
        self.daily_borrow_fee = config.get('daily_borrow_fee', 0.0)
        self.intraday_cost = config.get('intraday_cost', False)
    
    def cost_entry(self, position_change: Union[float, np.ndarray], 
                   price: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
        """
        Calculate entry/rebalancing costs.
        
        Args:
            position_change: Absolute position change (in units or %)
            price: Price at which trade executes
        
        Returns:
            Cost in dollars (positive value)
        """
        # Vectorized: works with scalars or arrays
        commission = np.abs(position_change) * self.commission_per_share
        slippage = np.abs(position_change) * self.slippage_pct * price
        return commission + slippage
    
    def cost_hold(self, position: Union[float, np.ndarray], 
                  period_days: float = 1.0) -> Union[float, np.ndarray]:
        """
        Calculate holding costs (borrow fees, financing).
        
        Args:
            position: Portfolio weight or notional position
            period_days: Holding period in days
        
        Returns:
            Cost in dollars (positive value)
        """
        # For shorts: apply borrow fee
        short_position = np.minimum(position, 0)  # Extract negative portion
        borrow_cost = np.abs(short_position) * self.daily_borrow_fee * period_days
        return borrow_cost


class PositionSizer:
    """
    Converts raw signals into portfolio positions.
    
    Interface allows different sizing strategies:
    - Threshold-based (signal crosses threshold -> fixed position)
    - Linear scaling (position proportional to signal)
    - Volatility-adjusted (risk parity)
    """
    
    def __init__(self, config: Dict):
        """
        Initialize position sizer.
        
        Args:
            config: Dict with strategy-specific parameters:
                - strategy: 'threshold' | 'linear' | 'volatility'
                - threshold_long: float
                - threshold_short: float
                - position_long: float (e.g., 1.0 for 100% long)
                - position_short: float (e.g., -1.0 for 100% short)
                - scale_factor: float (for linear strategy)
                - target_volatility: float (for vol-adjusted)
        """
        self.config = config
        self.strategy = config.get('strategy', 'threshold')
    
    def size(self, signal: Union[float, np.ndarray], 
             params: Optional[Dict] = None,
             lookback_data: Optional[pd.DataFrame] = None) -> Union[float, np.ndarray]:
        """
        Convert signal to position.
        
        Args:
            signal: Raw signal value(s)
            params: Optional runtime parameters (overrides config)
            lookback_data: DataFrame with 'returns' and 'price' for volatility calc
        
        Returns:
            Position in [-1, 1] (1 = 100% long, -1 = 100% short, 0 = flat)
        """
        if self.strategy == 'threshold':
            return self._size_threshold(signal)
        elif self.strategy == 'linear':
            return self._size_linear(signal)
        elif self.strategy == 'volatility':
            return self._size_volatility(signal, lookback_data)
        else:
            raise ValueError(f"Unknown strategy: {self.strategy}")
    
    def _size_threshold(self, signal: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
        """Threshold-based sizing: binary or ternary outcomes."""
        threshold_long = self.config.get('threshold_long', 0.5)
        threshold_short = self.config.get('threshold_short', -0.5)
        position_long = self.config.get('position_long', 1.0)
        position_short = self.config.get('position_short', -1.0)
        
        position = np.where(signal > threshold_long, position_long,
                           np.where(signal < threshold_short, position_short, 0.0))
        return position
    
    def _size_linear(self, signal: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
        """Linear scaling: position = clip(signal / scale_factor, -1, 1)."""
        scale_factor = self.config.get('scale_factor', 1.0)
        position = np.clip(signal / scale_factor, -1.0, 1.0)
        return position
    
    def _size_volatility(self, signal: Union[float, np.ndarray],
                        lookback_data: Optional[pd.DataFrame] = None) -> Union[float, np.ndarray]:
        """
        Volatility-adjusted sizing: risk parity.
        
        Scales position inversely to realized volatility to maintain constant risk exposure.
        
        Args:
            signal: Raw signal values
            lookback_data: DataFrame with 'returns' column for volatility calculation
        
        Returns:
            Position scaled by inverse volatility, clipped to [-1, 1]
        """
        if lookback_data is None:
            raise ValueError("Volatility sizing requires lookback_data with 'returns'")
        
        if 'returns' not in lookback_data.columns:
            raise ValueError("lookback_data must contain 'returns' column")
        
        # Calculate rolling volatility
        vol_window = self.config.get('vol_window', 20)
        vol = lookback_data['returns'].rolling(window=vol_window, min_periods=vol_window).std()
        
        # Target volatility (annualized)
        target_vol = self.config.get('target_volatility', 0.02)
        
        # Scale position: higher vol -> smaller position
        # Avoid division by zero
        vol_ratio = target_vol / (vol + 1e-8)
        
        # Apply signal direction with vol scaling
        position = signal * vol_ratio
        
        # Clip to valid range and convert to numpy array
        return np.clip(np.asarray(position), -1.0, 1.0)


class PerformanceMetrics:
    """
    Calculate comprehensive performance metrics for backtesting results.
    
    Includes:
    - Returns: Total, annualized, rolling
    - Risk: Volatility, downside deviation, beta
    - Risk-adjusted: Sharpe, Sortino, Calmar, Information ratio
    - Drawdown: Maximum, average, duration
    - Trading: Win rate, profit factor, trades per year
    """
    
    @staticmethod
    def calculate_all(equity: np.ndarray,
                     returns: np.ndarray,
                     position: np.ndarray,
                     costs: np.ndarray,
                     periods_per_year: int = 252) -> Dict:
        """
        Calculate all performance metrics.
        
        Args:
            equity: Equity curve (array)
            returns: Period returns (log returns)
            position: Position array (portfolio weights)
            costs: Transaction costs per period
            periods_per_year: Number of periods per year (252 for daily)
        
        Returns:
            Dict with all performance metrics
        """
        metrics = {}
        
        # Return metrics
        metrics['total_return'] = PerformanceMetrics.total_return(equity)
        metrics['annualized_return'] = PerformanceMetrics.annualized_return(equity, periods_per_year)
        metrics['cagr'] = PerformanceMetrics.cagr(equity, periods_per_year)
        
        # Risk metrics
        metrics['volatility'] = PerformanceMetrics.volatility(returns, periods_per_year)
        metrics['downside_deviation'] = PerformanceMetrics.downside_deviation(returns, periods_per_year)
        
        # Risk-adjusted metrics
        metrics['sharpe_ratio'] = PerformanceMetrics.sharpe_ratio(returns, periods_per_year)
        metrics['sortino_ratio'] = PerformanceMetrics.sortino_ratio(returns, periods_per_year)
        
        # Drawdown metrics
        dd_metrics = PerformanceMetrics.drawdown_metrics(equity)
        metrics['max_drawdown'] = dd_metrics['max_drawdown']
        metrics['max_drawdown_duration'] = dd_metrics['max_drawdown_duration']
        metrics['avg_drawdown'] = dd_metrics['avg_drawdown']
        metrics['drawdown_series'] = dd_metrics['drawdown_series']
        
        # Calmar ratio (return / max drawdown)
        if metrics['max_drawdown'] != 0:
            metrics['calmar_ratio'] = metrics['annualized_return'] / abs(metrics['max_drawdown'])
        else:
            metrics['calmar_ratio'] = 0.0
        
        # Trading metrics
        metrics['total_costs'] = np.sum(costs)
        metrics['avg_position'] = np.mean(np.abs(position))
        metrics['turnover'] = PerformanceMetrics.turnover(position)
        
        return metrics
    
    @staticmethod
    def total_return(equity: np.ndarray) -> float:
        """Calculate total return as percentage."""
        if len(equity) < 2 or equity[0] == 0:
            return 0.0
        return (equity[-1] - equity[0]) / equity[0]
    
    @staticmethod
    def annualized_return(equity: np.ndarray, periods_per_year: int = 252) -> float:
        """Calculate annualized return."""
        if len(equity) < 2 or equity[0] <= 0:
            return 0.0
        n_periods = len(equity) - 1
        years = n_periods / periods_per_year
        if years <= 0:
            return 0.0
        total_ret = equity[-1] / equity[0]
        return (total_ret ** (1.0 / years)) - 1.0
    
    @staticmethod
    def cagr(equity: np.ndarray, periods_per_year: int = 252) -> float:
        """Calculate compound annual growth rate (same as annualized return)."""
        return PerformanceMetrics.annualized_return(equity, periods_per_year)
    
    @staticmethod
    def volatility(returns: np.ndarray, periods_per_year: int = 252) -> float:
        """Calculate annualized volatility."""
        if len(returns) == 0:
            return 0.0
        return float(np.std(returns) * np.sqrt(periods_per_year))
    
    @staticmethod
    def downside_deviation(returns: np.ndarray, periods_per_year: int = 252,
                          threshold: float = 0.0) -> float:
        """
        Calculate downside deviation (volatility of negative returns).
        
        Args:
            returns: Period returns
            periods_per_year: Annualization factor
            threshold: Minimum acceptable return (default 0)
        
        Returns:
            Annualized downside deviation
        """
        if len(returns) == 0:
            return 0.0
        downside = returns[returns < threshold]
        if len(downside) == 0:
            return 0.0
        return float(np.std(downside) * np.sqrt(periods_per_year))
    
    @staticmethod
    def sharpe_ratio(returns: np.ndarray, periods_per_year: int = 252,
                    risk_free_rate: float = 0.0) -> float:
        """
        Calculate annualized Sharpe ratio.
        
        Args:
            returns: Period returns (log returns)
            periods_per_year: Annualization factor (252 for daily)
            risk_free_rate: Annual risk-free rate
        
        Returns:
            Sharpe ratio (annualized)
        """
        if len(returns) == 0:
            return 0.0
        
        excess_return = returns - risk_free_rate / periods_per_year
        sharpe = np.mean(excess_return) / (np.std(excess_return) + 1e-8) * np.sqrt(periods_per_year)
        return float(sharpe)
    
    @staticmethod
    def sortino_ratio(returns: np.ndarray, periods_per_year: int = 252,
                     risk_free_rate: float = 0.0) -> float:
        """
        Calculate Sortino ratio (Sharpe with downside deviation instead of volatility).
        
        Args:
            returns: Period returns
            periods_per_year: Annualization factor
            risk_free_rate: Annual risk-free rate
        
        Returns:
            Sortino ratio (annualized)
        """
        if len(returns) == 0:
            return 0.0
        
        excess_return = returns - risk_free_rate / periods_per_year
        downside_dev = PerformanceMetrics.downside_deviation(returns, periods_per_year)
        
        if downside_dev == 0:
            return 0.0
        
        sortino = np.mean(excess_return) * periods_per_year / downside_dev
        return float(sortino)
    
    @staticmethod
    def drawdown_metrics(equity: np.ndarray) -> Dict:
        """
        Calculate drawdown metrics.
        
        Args:
            equity: Equity curve
        
        Returns:
            Dict with:
            - max_drawdown: Maximum peak-to-trough decline (negative %)
            - max_drawdown_duration: Duration of longest drawdown (in bars)
            - avg_drawdown: Average drawdown across all periods
            - drawdown_series: Time series of drawdown percentages
        """
        if len(equity) < 2:
            return {
                'max_drawdown': 0.0,
                'max_drawdown_duration': 0,
                'avg_drawdown': 0.0,
                'drawdown_series': np.zeros_like(equity)
            }
        
        # Calculate running maximum
        running_max = np.maximum.accumulate(equity)
        
        # Drawdown as percentage from peak
        drawdown = (equity - running_max) / (running_max + 1e-8)
        
        # Maximum drawdown
        max_dd = float(np.min(drawdown))
        
        # Calculate drawdown durations
        in_drawdown = drawdown < 0
        duration = 0
        max_duration = 0
        
        for is_dd in in_drawdown:
            if is_dd:
                duration += 1
                max_duration = max(max_duration, duration)
            else:
                duration = 0
        
        # Average drawdown (only counting periods in drawdown)
        if np.any(in_drawdown):
            avg_dd = float(np.mean(drawdown[in_drawdown]))
        else:
            avg_dd = 0.0
        
        return {
            'max_drawdown': max_dd,
            'max_drawdown_duration': max_duration,
            'avg_drawdown': avg_dd,
            'drawdown_series': drawdown
        }
    
    @staticmethod
    def turnover(position: np.ndarray) -> float:
        """
        Calculate portfolio turnover (average absolute position change).
        
        Args:
            position: Position array
        
        Returns:
            Average absolute position change per period
        """
        if len(position) < 2:
            return 0.0
        position_changes = np.diff(position)
        return float(np.mean(np.abs(position_changes)))


class TradeAnalyzer:
    """
    Analyze individual trades from backtest results.
    
    Extracts trade-level information including:
    - Entry/exit times and prices
    - Trade PnL and returns
    - Win rate and profit factor
    - Average holding period
    """
    
    @staticmethod
    def extract_trades(position: np.ndarray,
                      price: np.ndarray,
                      equity: np.ndarray,
                      timestamps: Optional[np.ndarray] = None) -> pd.DataFrame:
        """
        Extract individual trades from position series.
        
        A trade is defined as a continuous period of non-zero position.
        Trade enters when position changes from 0 to non-zero.
        Trade exits when position returns to 0.
        
        Args:
            position: Position weights over time
            price: Price series
            equity: Equity curve
            timestamps: Optional timestamp array
        
        Returns:
            DataFrame with columns:
            - entry_bar: Entry bar index
            - exit_bar: Exit bar index
            - entry_price: Entry price
            - exit_price: Exit price
            - position_size: Position size (signed)
            - pnl: Trade PnL in dollars
            - pnl_pct: Trade return as percentage
            - duration: Trade duration in bars
            - entry_time: Entry timestamp (if provided)
            - exit_time: Exit timestamp (if provided)
        """
        trades = []
        n_bars = len(position)
        
        in_trade = False
        entry_bar = None
        entry_price_val = None
        entry_equity = None
        position_size = None
        
        for i in range(n_bars):
            # Check if entering a trade
            if not in_trade and position[i] != 0:
                in_trade = True
                entry_bar = i
                entry_price_val = price[i]
                entry_equity = equity[i]
                position_size = position[i]
            
            # Check if exiting a trade
            elif in_trade and position[i] == 0:
                exit_bar = i
                exit_price_val = price[i]
                exit_equity = equity[i]
                
                # Calculate trade metrics
                duration = exit_bar - entry_bar
                pnl = exit_equity - entry_equity
                pnl_pct = (exit_price_val - entry_price_val) / entry_price_val * position_size
                
                trade_dict = {
                    'entry_bar': entry_bar,
                    'exit_bar': exit_bar,
                    'entry_price': entry_price_val,
                    'exit_price': exit_price_val,
                    'position_size': position_size,
                    'pnl': pnl,
                    'pnl_pct': pnl_pct,
                    'duration': duration,
                }
                
                # Add timestamps if provided
                if timestamps is not None:
                    trade_dict['entry_time'] = timestamps[entry_bar]
                    trade_dict['exit_time'] = timestamps[exit_bar]
                
                trades.append(trade_dict)
                
                in_trade = False
                entry_bar = None
        
        # If still in trade at end, close it
        if in_trade:
            exit_bar = n_bars - 1
            exit_price_val = price[exit_bar]
            exit_equity = equity[exit_bar]
            
            duration = exit_bar - entry_bar
            pnl = exit_equity - entry_equity
            pnl_pct = (exit_price_val - entry_price_val) / entry_price_val * position_size
            
            trade_dict = {
                'entry_bar': entry_bar,
                'exit_bar': exit_bar,
                'entry_price': entry_price_val,
                'exit_price': exit_price_val,
                'position_size': position_size,
                'pnl': pnl,
                'pnl_pct': pnl_pct,
                'duration': duration,
            }
            
            if timestamps is not None:
                trade_dict['entry_time'] = timestamps[entry_bar]
                trade_dict['exit_time'] = timestamps[exit_bar]
            
            trades.append(trade_dict)
        
        return pd.DataFrame(trades)
    
    @staticmethod
    def calculate_trade_metrics(trades_df: pd.DataFrame) -> Dict:
        """
        Calculate aggregate trade statistics.
        
        Args:
            trades_df: DataFrame from extract_trades()
        
        Returns:
            Dict with:
            - total_trades: Total number of trades
            - winning_trades: Number of profitable trades
            - losing_trades: Number of losing trades
            - win_rate: Percentage of winning trades
            - avg_win: Average winning trade PnL
            - avg_loss: Average losing trade PnL
            - profit_factor: Ratio of total wins to total losses
            - avg_duration: Average trade duration
            - max_win: Largest winning trade
            - max_loss: Largest losing trade
            - expectancy: Average PnL per trade
        """
        if len(trades_df) == 0:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0,
                'profit_factor': 0.0,
                'avg_duration': 0.0,
                'max_win': 0.0,
                'max_loss': 0.0,
                'expectancy': 0.0,
            }
        
        total_trades = len(trades_df)
        winning_trades_df = trades_df[trades_df['pnl'] > 0]
        losing_trades_df = trades_df[trades_df['pnl'] < 0]
        
        winning_trades = len(winning_trades_df)
        losing_trades = len(losing_trades_df)
        
        win_rate = winning_trades / total_trades if total_trades > 0 else 0.0
        
        avg_win = winning_trades_df['pnl'].mean() if winning_trades > 0 else 0.0
        avg_loss = losing_trades_df['pnl'].mean() if losing_trades > 0 else 0.0
        
        total_wins = winning_trades_df['pnl'].sum() if winning_trades > 0 else 0.0
        total_losses = abs(losing_trades_df['pnl'].sum()) if losing_trades > 0 else 0.0
        
        profit_factor = total_wins / total_losses if total_losses > 0 else 0.0
        
        avg_duration = trades_df['duration'].mean()
        max_win = trades_df['pnl'].max() if total_trades > 0 else 0.0
        max_loss = trades_df['pnl'].min() if total_trades > 0 else 0.0
        expectancy = trades_df['pnl'].mean() if total_trades > 0 else 0.0
        
        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': float(win_rate),
            'avg_win': float(avg_win),
            'avg_loss': float(avg_loss),
            'profit_factor': float(profit_factor),
            'avg_duration': float(avg_duration),
            'max_win': float(max_win),
            'max_loss': float(max_loss),
            'expectancy': float(expectancy),
        }


class BacktestAnalyzer:
    """
    Comprehensive analysis of backtest results.
    
    Provides:
    - Summary statistics
    - Trade analysis
    - Risk analysis
    - Rolling metrics
    - Text reports
    """
    
    def __init__(self, results: Dict):
        """
        Initialize analyzer with backtest results.
        
        Args:
            results: Dict from VectorizedBacktest.run()
        """
        self.results = results
        self.trades_df = None
        self.trade_metrics = None
    
    def analyze_trades(self, timestamps: Optional[np.ndarray] = None) -> pd.DataFrame:
        """
        Extract and analyze individual trades.
        
        Args:
            timestamps: Optional timestamp array
        
        Returns:
            DataFrame of individual trades
        """
        self.trades_df = TradeAnalyzer.extract_trades(
            position=self.results['position'],
            price=self.results['price'],
            equity=self.results['equity'],
            timestamps=timestamps
        )
        
        self.trade_metrics = TradeAnalyzer.calculate_trade_metrics(self.trades_df)
        
        return self.trades_df
    
    def get_summary(self, include_trades: bool = True) -> Dict:
        """
        Get comprehensive summary of backtest results.
        
        Args:
            include_trades: Whether to include trade-level metrics
        
        Returns:
            Dict with summary statistics
        """
        summary = {
            'performance': {
                'total_return': self.results.get('total_return', 0.0),
                'annualized_return': self.results.get('annualized_return', 0.0),
                'cagr': self.results.get('cagr', 0.0),
                'sharpe_ratio': self.results.get('sharpe_ratio', 0.0),
                'sortino_ratio': self.results.get('sortino_ratio', 0.0),
                'calmar_ratio': self.results.get('calmar_ratio', 0.0),
            },
            'risk': {
                'volatility': self.results.get('volatility', 0.0),
                'max_drawdown': self.results.get('max_drawdown', 0.0),
                'max_drawdown_duration': self.results.get('max_drawdown_duration', 0),
                'avg_drawdown': self.results.get('avg_drawdown', 0.0),
                'downside_deviation': self.results.get('downside_deviation', 0.0),
            },
            'costs': {
                'total_costs': self.results.get('total_costs', 0.0),
                'avg_position': self.results.get('avg_position', 0.0),
                'turnover': self.results.get('turnover', 0.0),
            },
            'equity': {
                'initial_capital': self.results['equity'][0],
                'final_equity': self.results['equity'][-1],
                'peak_equity': np.max(self.results['equity']),
            }
        }
        
        if include_trades:
            if self.trade_metrics is None:
                self.analyze_trades()
            summary['trades'] = self.trade_metrics
        
        return summary
    
    def print_report(self, include_trades: bool = True):
        """
        Print a formatted text report of backtest results.
        
        Args:
            include_trades: Whether to include trade-level metrics
        """
        summary = self.get_summary(include_trades=include_trades)
        
        print("\n" + "=" * 70)
        print(" " * 20 + "BACKTEST RESULTS SUMMARY")
        print("=" * 70)
        
        print("\n📊 PERFORMANCE METRICS")
        print("-" * 70)
        perf = summary['performance']
        print(f"  Total Return:           {perf['total_return']:>12.2%}")
        print(f"  Annualized Return:      {perf['annualized_return']:>12.2%}")
        print(f"  CAGR:                   {perf['cagr']:>12.2%}")
        print(f"  Sharpe Ratio:           {perf['sharpe_ratio']:>12.2f}")
        print(f"  Sortino Ratio:          {perf['sortino_ratio']:>12.2f}")
        print(f"  Calmar Ratio:           {perf['calmar_ratio']:>12.2f}")
        
        print("\n⚠️  RISK METRICS")
        print("-" * 70)
        risk = summary['risk']
        print(f"  Volatility (ann.):      {risk['volatility']:>12.2%}")
        print(f"  Downside Deviation:     {risk['downside_deviation']:>12.2%}")
        print(f"  Max Drawdown:           {risk['max_drawdown']:>12.2%}")
        print(f"  Max DD Duration:        {risk['max_drawdown_duration']:>12} bars")
        print(f"  Avg Drawdown:           {risk['avg_drawdown']:>12.2%}")
        
        print("\n💰 EQUITY & COSTS")
        print("-" * 70)
        equity_info = summary['equity']
        costs = summary['costs']
        print(f"  Initial Capital:        ${equity_info['initial_capital']:>12,.2f}")
        print(f"  Final Equity:           ${equity_info['final_equity']:>12,.2f}")
        print(f"  Peak Equity:            ${equity_info['peak_equity']:>12,.2f}")
        print(f"  Total Costs:            ${costs['total_costs']:>12,.2f}")
        print(f"  Avg Position:           {costs['avg_position']:>12.2%}")
        print(f"  Turnover:               {costs['turnover']:>12.4f}")
        
        if include_trades and 'trades' in summary:
            print("\n📈 TRADE STATISTICS")
            print("-" * 70)
            trades = summary['trades']
            print(f"  Total Trades:           {trades['total_trades']:>12}")
            print(f"  Winning Trades:         {trades['winning_trades']:>12}")
            print(f"  Losing Trades:          {trades['losing_trades']:>12}")
            print(f"  Win Rate:               {trades['win_rate']:>12.2%}")
            print(f"  Profit Factor:          {trades['profit_factor']:>12.2f}")
            print(f"  Expectancy:             ${trades['expectancy']:>12,.2f}")
            print(f"  Avg Win:                ${trades['avg_win']:>12,.2f}")
            print(f"  Avg Loss:               ${trades['avg_loss']:>12,.2f}")
            print(f"  Max Win:                ${trades['max_win']:>12,.2f}")
            print(f"  Max Loss:               ${trades['max_loss']:>12,.2f}")
            print(f"  Avg Duration:           {trades['avg_duration']:>12.1f} bars")
        
        print("\n" + "=" * 70 + "\n")
    
    def get_rolling_metrics(self, window: int = 252) -> pd.DataFrame:
        """
        Calculate rolling performance metrics.
        
        Args:
            window: Rolling window size (default 252 for 1 year)
        
        Returns:
            DataFrame with rolling metrics
        """
        returns = self.results['returns']
        equity = self.results['equity']
        
        # Convert to pandas for rolling calculations
        returns_series = pd.Series(returns)
        
        rolling_metrics = pd.DataFrame({
            'rolling_return': returns_series.rolling(window).mean() * 252,
            'rolling_volatility': returns_series.rolling(window).std() * np.sqrt(252),
            'rolling_sharpe': (returns_series.rolling(window).mean() / 
                              (returns_series.rolling(window).std() + 1e-8) * np.sqrt(252)),
        })
        
        return rolling_metrics
    
    def validate(self) -> Dict[str, bool]:
        """
        Validate backtest results for common issues.
        
        Returns:
            Dict with validation flags
        """
        validations = {}
        
        # Check for NaN values
        validations['no_nan_equity'] = not np.any(np.isnan(self.results['equity']))
        validations['no_nan_returns'] = not np.any(np.isnan(self.results['returns']))
        
        # Check for reasonable values
        validations['positive_equity'] = np.all(self.results['equity'] > 0)
        validations['reasonable_costs'] = self.results.get('total_costs', 0) >= 0
        
        # Check for data integrity
        validations['position_in_range'] = np.all(
            (self.results['position'] >= -1.1) & (self.results['position'] <= 1.1)
        )
        
        # Check signal lag was applied
        if 'signal' in self.results and 'lagged_signal' in self.results:
            validations['signal_lag_applied'] = not np.array_equal(
                self.results['signal'], self.results['lagged_signal']
            )
        
        validations['all_passed'] = all(validations.values())
        
        return validations


class VectorizedBacktest:
    """
    High-performance backtesting engine using vectorized operations.
    
    Pipeline:
    1. Apply 1-bar lag to signal
    2. Size positions based on signal
    3. Calculate position changes
    4. Apply costs (commission, slippage, borrow fees)
    5. Generate equity curve via cumulative PnL
    6. Return results with transaction details
    """
    
    def __init__(self, data: Union[np.ndarray, pd.Series], 
                 signal: Union[np.ndarray, pd.Series],
                 cost_model: CostModel,
                 position_sizer: PositionSizer,
                 initial_capital: float = 100000.0,
                 trading_starts_at_bar: int = 2):
        """
        Initialize backtest.
        
        Args:
            data: Price data (close prices or OHLC prices)
            signal: Raw signal values (same length as data)
            cost_model: CostModel instance
            position_sizer: PositionSizer instance
            initial_capital: Starting equity
            trading_starts_at_bar: First bar to trade (0-indexed, default 2 for lag)
        
        Raises:
            ValueError: If data and signal have different lengths
        """
        self.data = np.asarray(data, dtype=np.float64)
        self.signal = np.asarray(signal, dtype=np.float64)
        self.cost_model = cost_model
        self.position_sizer = position_sizer
        self.initial_capital = initial_capital
        self.trading_starts_at_bar = trading_starts_at_bar
        
        if len(self.data) != len(self.signal):
            raise ValueError(f"Data ({len(self.data)}) and signal ({len(self.signal)}) length mismatch")
        
        self.n_bars = len(self.data)
        self._validate_inputs()
    
    def _validate_inputs(self):
        """Check for invalid inputs (NaN, infinite values, etc.)."""
        if np.any(np.isnan(self.data)):
            raise ValueError("Price data contains NaN values")
        if np.any(np.isinf(self.data)):
            raise ValueError("Price data contains infinite values")
        if self.initial_capital <= 0:
            raise ValueError("Initial capital must be positive")
    
    def run(self) -> Dict:
        """
        Execute backtest and return results.
        
        Returns:
            Dict with keys:
            - 'equity': numpy array of equity values
            - 'position': numpy array of position weights
            - 'price': input price data
            - 'signal': input signal data
            - 'lagged_signal': signal with 1-bar lag applied
            - 'returns': log returns
            - 'costs': transaction costs per bar
            - 'entry_prices': execution prices
            - Performance metrics:
                - 'total_return': total return as percentage
                - 'annualized_return': annualized return
                - 'cagr': compound annual growth rate
                - 'sharpe_ratio': annualized Sharpe ratio
                - 'sortino_ratio': annualized Sortino ratio
                - 'max_drawdown': maximum drawdown (negative %)
                - 'max_drawdown_duration': longest drawdown duration (bars)
                - 'calmar_ratio': return / max drawdown
                - 'volatility': annualized volatility
                - 'total_costs': sum of all transaction costs
                - 'turnover': average position change per bar
        """
        # Step 1: Apply 1-bar lag to signal
        lagged_signal = self._apply_lag()
        
        # Step 2: Size positions from lagged signal
        position = self._size_positions(lagged_signal)
        
        # Step 3: Calculate position changes and costs
        position_change = np.diff(position, prepend=0)
        costs = np.zeros(self.n_bars)
        
        # Entry costs
        costs[1:] = self.cost_model.cost_entry(position_change[1:], self.data[1:])
        
        # Holding costs (optional, placeholder)
        # costs += self.cost_model.cost_hold(position)
        
        # Step 4: Calculate PnL and equity curve
        entry_price = self._calculate_entry_prices(position_change)
        daily_pnl = self._calculate_daily_pnl(position, entry_price)
        
        equity = self._calculate_equity(daily_pnl, costs)
        returns = np.diff(np.log(equity)) if np.all(equity > 0) else np.zeros(self.n_bars - 1)
        
        # Step 5: Calculate comprehensive performance metrics
        metrics = PerformanceMetrics.calculate_all(
            equity=equity,
            returns=returns,
            position=position,
            costs=costs,
            periods_per_year=252
        )
        
        # Build results dictionary
        results = {
            'equity': equity,
            'position': position,
            'price': self.data,
            'signal': self.signal,
            'lagged_signal': lagged_signal,
            'returns': returns,
            'costs': costs,
            'entry_prices': entry_price,
        }
        
        # Add all metrics to results
        results.update(metrics)
        
        return results
    
    def _apply_lag(self) -> np.ndarray:
        """Apply 1-bar lag to signal (shift right, zero-pad start)."""
        lagged = np.roll(self.signal, 1)
        lagged[0] = 0.0  # First bar has no prior signal
        return lagged
    
    def _size_positions(self, lagged_signal: np.ndarray) -> np.ndarray:
        """Convert lagged signal to position weights."""
        position = self.position_sizer.size(lagged_signal)
        return np.asarray(position, dtype=np.float64)
    
    def _calculate_entry_prices(self, position_change: np.ndarray) -> np.ndarray:
        """
        Track entry prices as positions change.
        
        Logic:
        - If position increases (entry/pyramid): use current bar price
        - If position decreases (exit/reduce): use previous entry price
        - If flat: use last valid entry price
        """
        entry_price = np.zeros(self.n_bars)
        entry_price[0] = self.data[0]
        
        for i in range(1, self.n_bars):
            if position_change[i] > 0:  # Buying/increasing long
                entry_price[i] = self.data[i]
            elif position_change[i] < 0:  # Selling/reducing
                entry_price[i] = entry_price[i-1]  # Use previous entry price
            else:
                entry_price[i] = entry_price[i-1]
        
        return entry_price
    
    def _calculate_daily_pnl(self, position: np.ndarray, 
                             entry_price: np.ndarray) -> np.ndarray:
        """
        Calculate daily PnL as mark-to-market change.
        
        pnl[t] = position[t] * (price[t] - entry_price[t])
        """
        daily_pnl = position * (self.data - entry_price)
        return daily_pnl
    
    def _calculate_equity(self, daily_pnl: np.ndarray, 
                         costs: np.ndarray) -> np.ndarray:
        """
        Calculate equity curve via cumulative PnL minus costs.
        
        equity[t] = initial_capital + sum(daily_pnl[0:t]) - sum(costs[0:t])
        """
        cumulative_pnl = np.cumsum(daily_pnl)
        cumulative_costs = np.cumsum(costs)
        equity = self.initial_capital + cumulative_pnl - cumulative_costs
        return equity


# ============================================================================
# Example usage (for testing, not part of production code)
# ============================================================================

if __name__ == '__main__':
    """
    Minimal example to demonstrate API.
    
    Full example: see tests/test_backtest.py
    """
    
    # Synthetic data
    n_bars = 252
    np.random.seed(42)
    price = 100 + np.cumsum(np.random.randn(n_bars) * 0.5)
    signal = np.sin(np.linspace(0, 4 * np.pi, n_bars)) + np.random.randn(n_bars) * 0.2
    
    # Initialize models
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
    
    # Run backtest
    backtest = VectorizedBacktest(
        data=price,
        signal=signal,
        cost_model=cost_model,
        position_sizer=position_sizer,
        initial_capital=100000.0,
    )
    
    results = backtest.run()
    
    print("=" * 60)
    print("Backtest Results")
    print("=" * 60)
    print(f"Total Return:       {results['total_return']:.2%}")
    print(f"Annualized Return:  {results['annualized_return']:.2%}")
    print(f"Sharpe Ratio:       {results['sharpe_ratio']:.2f}")
    print(f"Sortino Ratio:      {results['sortino_ratio']:.2f}")
    print(f"Max Drawdown:       {results['max_drawdown']:.2%}")
    print(f"Calmar Ratio:       {results['calmar_ratio']:.2f}")
    print(f"Volatility (ann.):  {results['volatility']:.2%}")
    print(f"Total Costs:        ${results['total_costs']:,.2f}")
    print(f"Final Equity:       ${results['equity'][-1]:,.2f}")
    print("=" * 60)
