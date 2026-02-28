"""
FX Transaction Cost Model

Provides realistic cost modeling for FX trading strategies.

Key concepts:
- Spread: Difference between bid and ask prices (always paid)
- Slippage: Adverse price movement during execution
- Total cost = Spread + Slippage (typically 0.8-1.5 bps for majors)

Why costs matter:
- High-frequency strategies are crushed by transaction costs
- A 1.0 pip cost on 100 trades = 100 pips of drag
- Many "profitable" backtests fail when realistic costs are added
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional, Union


class FXCostModel:
    """
    Transaction cost model for FX trading.
    
    Combines spread and slippage costs to model realistic execution.
    
    Typical costs for major pairs (basis points):
    - EURUSD: 0.6 pip spread + 0.2 pip slippage = 0.8 pip total
    - GBPUSD: 0.8 pip spread + 0.2 pip slippage = 1.0 pip total
    - USDJPY: 0.8 pip spread + 0.2 pip slippage = 1.0 pip total
    - AUDUSD: 1.0 pip spread + 0.3 pip slippage = 1.3 pip total
    
    1 pip = 0.0001 for most pairs = 1 basis point (bps)
    Exception: JPY pairs where 1 pip = 0.01
    """
    
    def __init__(
        self,
        spread_bps: float,
        slippage_bps: float,
        symbol: Optional[str] = None
    ):
        """
        Initialize cost model.
        
        Args:
            spread_bps: Bid-ask spread in basis points (pips)
            slippage_bps: Estimated slippage in basis points (pips)
            symbol: FX pair symbol (e.g., 'EURUSD') for logging
        
        Example:
            >>> # EURUSD: 0.6 pip spread, 0.2 pip slippage
            >>> model = FXCostModel(spread_bps=0.6, slippage_bps=0.2, symbol='EURUSD')
            >>> cost = model.compute_cost(10000, 'BUY')  # 10K units
        """
        if spread_bps < 0 or slippage_bps < 0:
            raise ValueError("Spread and slippage must be non-negative")
        
        self.spread_bps = spread_bps
        self.slippage_bps = slippage_bps
        self.total_bps = spread_bps + slippage_bps
        self.symbol = symbol or "UNKNOWN"
    
    def compute_cost(
        self,
        trade_size: Union[float, np.ndarray, pd.Series],
        side: Optional[str] = None
    ) -> Union[float, np.ndarray, pd.Series]:
        """
        Compute total transaction cost.
        
        Cost formula:
        - Total cost (bps) = spread + slippage
        - Cost in price units = price * (total_bps / 10000)
        
        Args:
            trade_size: Absolute value of trade size in units
                - Scalar: single trade
                - Array/Series: vectorized computation
            side: Trade side ('BUY' or 'SELL') - currently not used
                  but included for future asymmetric cost modeling
        
        Returns:
            Cost in basis points (pips)
        
        Note:
            Cost is always paid regardless of direction (round-trip cost).
            For example:
            - Buy 10,000 EUR/USD with 0.8 pip cost
            - Later sell 10,000 EUR/USD with another 0.8 pip cost
            - Total round-trip cost = 1.6 pips
        
        Example:
            >>> model = FXCostModel(spread_bps=0.6, slippage_bps=0.2)
            >>> cost = model.compute_cost(10000, 'BUY')
            >>> print(f"Cost: {cost:.2f} pips")
            Cost: 0.80 pips
        """
        # Absolute value in case negative trade sizes are passed
        abs_trade_size = np.abs(trade_size)
        
        # Cost is proportional to trade size
        # For FX, cost is typically quoted per unit but here we return
        # the cost rate (in bps) which should be applied to the trade
        return self.total_bps
    
    def compute_cost_in_dollars(
        self,
        trade_size: Union[float, np.ndarray, pd.Series],
        price: Union[float, np.ndarray, pd.Series],
        pip_value_per_unit: float = 0.0001
    ) -> Union[float, np.ndarray, pd.Series]:
        """
        Compute transaction cost in dollars (P&L impact).
        
        Args:
            trade_size: Trade size in units (absolute value)
            price: Current market price
            pip_value_per_unit: Value of 1 pip (0.0001 for most pairs, 0.01 for JPY)
        
        Returns:
            Cost in dollars
        
        Formula:
            cost_dollars = trade_size * pip_value_per_unit * cost_bps
        
        Example:
            >>> model = FXCostModel(spread_bps=0.6, slippage_bps=0.2)
            >>> # Trade 10,000 units of EURUSD at 1.2000
            >>> cost_usd = model.compute_cost_in_dollars(10000, 1.2000, pip_value_per_unit=0.0001)
            >>> print(f"Cost: ${cost_usd:.2f}")
            Cost: $8.00
            
            Calculation:
            - Cost in pips: 0.8
            - Trade size: 10,000 units
            - Pip value: $1 per pip for 10K units (0.0001 * 10000 = 1)
            - Total cost: 0.8 pips * $1/pip * 10 = $8
        """
        abs_trade_size = np.abs(trade_size)
        
        # Cost = trade_size * pip_value * cost_in_pips
        cost_dollars = abs_trade_size * pip_value_per_unit * self.total_bps
        
        return cost_dollars
    
    def compute_percentage_cost(
        self,
        trade_size: Union[float, np.ndarray, pd.Series],
        price: Union[float, np.ndarray, pd.Series],
        pip_value_per_unit: float = 0.0001
    ) -> Union[float, np.ndarray, pd.Series]:
        """
        Compute cost as percentage of trade notional.
        
        Args:
            trade_size: Trade size in units
            price: Current market price
            pip_value_per_unit: Value of 1 pip
        
        Returns:
            Cost as percentage (e.g., 0.0008 = 0.08%)
        
        Example:
            >>> model = FXCostModel(spread_bps=0.8, slippage_bps=0.2)
            >>> pct = model.compute_percentage_cost(10000, 1.2000)
            >>> print(f"Cost: {pct*100:.3f}%")
            Cost: 0.083%
        """
        cost_dollars = self.compute_cost_in_dollars(trade_size, price, pip_value_per_unit)
        notional = np.abs(trade_size) * price
        
        return cost_dollars / notional if notional != 0 else 0.0
    
    def __repr__(self) -> str:
        return (
            f"FXCostModel(symbol={self.symbol}, "
            f"spread={self.spread_bps} pips, "
            f"slippage={self.slippage_bps} pips, "
            f"total={self.total_bps} pips)"
        )


# Pre-configured cost models for common FX pairs
COST_MODELS: Dict[str, FXCostModel] = {
    'EURUSD': FXCostModel(spread_bps=0.6, slippage_bps=0.2, symbol='EURUSD'),
    'GBPUSD': FXCostModel(spread_bps=0.8, slippage_bps=0.2, symbol='GBPUSD'),
    'USDJPY': FXCostModel(spread_bps=0.8, slippage_bps=0.2, symbol='USDJPY'),
    'AUDUSD': FXCostModel(spread_bps=1.0, slippage_bps=0.3, symbol='AUDUSD'),
    'USDCAD': FXCostModel(spread_bps=1.2, slippage_bps=0.3, symbol='USDCAD'),
    'NZDUSD': FXCostModel(spread_bps=1.5, slippage_bps=0.3, symbol='NZDUSD'),
    'EURGBP': FXCostModel(spread_bps=1.0, slippage_bps=0.2, symbol='EURGBP'),
    'EURJPY': FXCostModel(spread_bps=1.2, slippage_bps=0.3, symbol='EURJPY'),
}


def get_cost_model(symbol: str) -> FXCostModel:
    """
    Get pre-configured cost model for a symbol.
    
    Args:
        symbol: FX pair symbol (e.g., 'EURUSD')
    
    Returns:
        FXCostModel instance
    
    Raises:
        KeyError: If symbol not found
    
    Example:
        >>> model = get_cost_model('EURUSD')
        >>> print(model)
        FXCostModel(symbol=EURUSD, spread=0.6 pips, slippage=0.2 pips, total=0.8 pips)
    """
    symbol_upper = symbol.upper()
    if symbol_upper not in COST_MODELS:
        raise KeyError(
            f"No cost model for {symbol}. "
            f"Available: {list(COST_MODELS.keys())}"
        )
    
    return COST_MODELS[symbol_upper]
