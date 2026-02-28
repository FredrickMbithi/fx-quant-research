"""
FX Swap/Rollover Cost Calculator

Computes overnight financing costs for holding FX positions.

Key concepts:
- Swap = Interest rate differential between currency pairs
- Charged/credited when holding position overnight (after 5pm EST)
- Broker adds markup (typically 0.5-2% annually)
- Must use historical swap rates, not current rates (to avoid lookahead bias)

Why swaps matter:
- Can be 5-10 pips per week for carry trades
- Multi-month positions accumulate significant costs
- Creates bias: profitable to hold high-interest currencies long
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional, Union
from pathlib import Path


def compute_swap_cost(
    symbol: str,
    position_size: float,
    hold_days: int,
    interest_rate_diff: Optional[float] = None,
    broker_markup: float = 0.015,  # 1.5% annualized
    swap_rate_pips_per_day: Optional[float] = None
) -> float:
    """
    Compute swap/rollover cost for holding an FX position.
    
    There are two methods to compute swap:
    
    Method 1: From interest rate differential (theoretical)
    -------------------------------------------------------
    Swap = (interest_rate_diff - broker_markup) * position_size * (hold_days / 360)
    
    Where:
    - interest_rate_diff: Annual interest rate differential (e.g., 0.03 = 3%)
    - broker_markup: Broker's annual markup (e.g., 0.015 = 1.5%)
    - 360: Day count convention for FX (not 365)
    
    Method 2: From historical swap rates (recommended)
    ---------------------------------------------------
    Swap = swap_rate_pips_per_day * hold_days
    
    Where swap_rate_pips_per_day comes from broker's historical data.
    
    Args:
        symbol: FX pair (e.g., 'EURUSD')
        position_size: Position size in units (positive = long, negative = short)
        hold_days: Number of days position is held
        interest_rate_diff: Annual interest rate differential (Method 1)
        broker_markup: Annual broker markup (default: 1.5%)
        swap_rate_pips_per_day: Historical swap rate in pips/day (Method 2)
    
    Returns:
        Swap cost in pips (positive = cost, negative = credit)
    
    Note:
        - For backtesting, use Method 2 with historical swap rates
        - Method 1 is approximate and doesn't account for:
          * Weekend/triple swap days (Wednesday charges 3 days)
          * Holiday adjustments
          * Broker-specific swap calculations
    
    Example (Method 1 - Interest Rate Differential):
        >>> # Long EURUSD: EUR rate 0%, USD rate 5%, bank markup 1.5%
        >>> # Holding USD liability, so paying 5% - 1.5% = 3.5% annually
        >>> swap = compute_swap_cost(
        ...     symbol='EURUSD',
        ...     position_size=10000,  # Long 10K units
        ...     hold_days=30,
        ...     interest_rate_diff=-0.05,  # Negative: paying USD interest
        ...     broker_markup=0.015
        ... )
        >>> print(f"Swap cost: {swap:.2f} pips")
        Swap cost: -5.42 pips (paying)
    
    Example (Method 2 - Historical Swap Rate):
        >>> # Use broker's historical swap rate
        >>> swap = compute_swap_cost(
        ...     symbol='EURUSD',
        ...     position_size=10000,
        ...     hold_days=30,
        ...     swap_rate_pips_per_day=-0.18  # From broker data
        ... )
        >>> print(f"Swap cost: {swap:.2f} pips")
        Swap cost: -5.40 pips
    """
    if hold_days < 0:
        raise ValueError("hold_days must be non-negative")
    
    if hold_days == 0:
        return 0.0
    
    # Method 2: Use actual swap rate (preferred if available)
    if swap_rate_pips_per_day is not None:
        # Direct calculation from historical swap rates
        swap_pips = swap_rate_pips_per_day * hold_days
        
        # Adjust for position direction
        # Swap rates are typically quoted for long positions
        # For short positions, swap has opposite sign
        if position_size < 0:
            swap_pips = -swap_pips
        
        return swap_pips
    
    # Method 1: Calculate from interest rate differential
    if interest_rate_diff is None:
        raise ValueError(
            "Must provide either swap_rate_pips_per_day or interest_rate_diff"
        )
    
    # Net interest rate after broker markup
    net_interest_rate = interest_rate_diff - broker_markup
    
    # Annualized swap as fraction of position
    # Using 360-day convention (FX standard)
    daily_swap_fraction = net_interest_rate / 360.0
    
    # Total swap cost as fraction of position value
    total_swap_fraction = daily_swap_fraction * hold_days
    
    # Convert to pips (assuming 0.0001 = 1 pip for most pairs)
    # For simplicity, this returns percentage terms
    # Caller should convert to actual P&L based on position size
    swap_cost_pips = total_swap_fraction * 10000  # Convert to pips
    
    # Swap is paid/received based on position direction
    if position_size > 0:
        # Long position: pay if USD rates higher (negative interest_rate_diff)
        return swap_cost_pips
    else:
        # Short position: receive if USD rates higher
        return -swap_cost_pips


def load_historical_swap_rates(
    swap_data_path: Union[str, Path],
    symbol: str
) -> pd.DataFrame:
    """
    Load historical swap rates from file.
    
    Expected format (CSV):
    date,symbol,swap_long_pips,swap_short_pips
    2024-01-01,EURUSD,-0.15,0.10
    2024-01-02,EURUSD,-0.16,0.11
    
    Args:
        swap_data_path: Path to CSV file with swap rates
        symbol: FX pair symbol to filter
    
    Returns:
        DataFrame with columns [date, swap_long_pips, swap_short_pips]
        indexed by date
    
    Example:
        >>> swap_rates = load_historical_swap_rates('data/swap_rates/swaps.csv', 'EURUSD')
        >>> # Get swap rate for a specific date
        >>> swap_long = swap_rates.loc['2024-01-15', 'swap_long_pips']
    """
    swap_data_path = Path(swap_data_path)
    
    if not swap_data_path.exists():
        raise FileNotFoundError(f"Swap data file not found: {swap_data_path}")
    
    # Load swap data
    df = pd.read_csv(swap_data_path, parse_dates=['date'])
    
    # Filter for specific symbol
    df = df[df['symbol'] == symbol.upper()].copy()
    
    if df.empty:
        raise ValueError(f"No swap data found for symbol: {symbol}")
    
    # Set date as index
    df.set_index('date', inplace=True)
    
    # Sort by date
    df.sort_index(inplace=True)
    
    return df[['swap_long_pips', 'swap_short_pips']]


def compute_swap_series(
    positions: pd.Series,
    swap_rates: pd.DataFrame,
    symbol: str
) -> pd.Series:
    """
    Compute swap costs for a series of positions over time.
    
    Args:
        positions: Series of position sizes (index = dates)
                  Positive = long, Negative = short
        swap_rates: DataFrame from load_historical_swap_rates()
                    with columns [swap_long_pips, swap_short_pips]
        symbol: FX pair symbol (for logging/validation)
    
    Returns:
        Series of daily swap costs in pips (index = dates)
    
    Note:
        - Only charges swap when position is held overnight
        - Uses historical swap rate for each specific date
        - Accounts for long/short direction automatically
    
    Example:
        >>> positions = pd.Series([10000, 10000, -5000, 0], 
        ...                       index=pd.date_range('2024-01-01', periods=4))
        >>> swap_rates = load_historical_swap_rates('swaps.csv', 'EURUSD')
        >>> swap_costs = compute_swap_series(positions, swap_rates, 'EURUSD')
        >>> print(f"Total swap cost: {swap_costs.sum():.2f} pips")
    """
    # Align swap rates with position dates
    aligned_swaps = swap_rates.reindex(positions.index, method='ffill')
    
    # Determine swap rate based on position direction
    swap_daily = pd.Series(index=positions.index, dtype=float)
    
    for date in positions.index:
        position = positions.loc[date]
        
        if position == 0:
            # No position, no swap
            swap_daily.loc[date] = 0.0
        elif position > 0:
            # Long position
            swap_daily.loc[date] = aligned_swaps.loc[date, 'swap_long_pips']
        else:
            # Short position
            swap_daily.loc[date] = aligned_swaps.loc[date, 'swap_short_pips']
    
    return swap_daily


# Historical interest rate differentials (approximate, for reference)
# Should be replaced with actual historical data for backtesting
HISTORICAL_RATE_DIFFS: Dict[str, float] = {
    'EURUSD': -0.025,  # EUR 0%, USD 2.5% (approximate 2024)
    'GBPUSD': -0.020,  # GBP 0.5%, USD 2.5%
    'USDJPY': 0.045,   # USD 2.5%, JPY -2.0%
    'AUDUSD': 0.015,   # AUD 4.0%, USD 2.5%
}


def get_approx_swap_rate(symbol: str, broker_markup: float = 0.015) -> float:
    """
    Get approximate swap rate for a symbol.
    
    WARNING: This uses static approximations. For accurate backtesting,
    use load_historical_swap_rates() with actual broker data.
    
    Args:
        symbol: FX pair symbol
        broker_markup: Annual broker markup (default: 1.5%)
    
    Returns:
        Approximate daily swap rate in pips for LONG position
    
    Example:
        >>> swap_rate = get_approx_swap_rate('EURUSD')
        >>> print(f"Approx daily swap: {swap_rate:.3f} pips/day")
    """
    symbol_upper = symbol.upper()
    
    if symbol_upper not in HISTORICAL_RATE_DIFFS:
        raise KeyError(
            f"No approximate swap data for {symbol}. "
            f"Available: {list(HISTORICAL_RATE_DIFFS.keys())}"
        )
    
    rate_diff = HISTORICAL_RATE_DIFFS[symbol_upper]
    
    # Net rate after broker markup
    net_rate = rate_diff - broker_markup
    
    # Convert to daily pips using 360-day convention
    # Assume 1 pip = 0.0001 for most pairs
    daily_swap_pips = (net_rate / 360.0) * 10000
    
    return daily_swap_pips
