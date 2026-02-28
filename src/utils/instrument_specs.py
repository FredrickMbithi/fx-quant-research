"""
Instrument specification helpers.

Provides pip/tick sizes and pip value calculation that respects quote currency.
Avoids hard-coded assumptions that only work for 4-decimal USD-quoted pairs.
"""

from dataclasses import dataclass
from typing import Dict
import logging

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class InstrumentSpec:
    symbol: str
    pip_size: float
    tick_size: float
    quote_currency: str


# Minimal built-in catalog. Extend or replace with live broker contract data.
INSTRUMENT_SPECS: Dict[str, InstrumentSpec] = {
    "GBPUSD": InstrumentSpec("GBPUSD", pip_size=0.0001, tick_size=0.00001, quote_currency="USD"),
    "EURUSD": InstrumentSpec("EURUSD", pip_size=0.0001, tick_size=0.00001, quote_currency="USD"),
    "AUDUSD": InstrumentSpec("AUDUSD", pip_size=0.0001, tick_size=0.00001, quote_currency="USD"),
    "NZDUSD": InstrumentSpec("NZDUSD", pip_size=0.0001, tick_size=0.00001, quote_currency="USD"),
    "USDJPY": InstrumentSpec("USDJPY", pip_size=0.01, tick_size=0.001, quote_currency="JPY"),
    "USDCAD": InstrumentSpec("USDCAD", pip_size=0.0001, tick_size=0.00001, quote_currency="CAD"),
    "XAUUSD": InstrumentSpec("XAUUSD", pip_size=0.1, tick_size=0.01, quote_currency="USD"),  # 1 pip = 0.1 USD
}


def get_instrument_spec(symbol: str) -> InstrumentSpec:
    """
    Return instrument specification. Falls back to a conservative default.
    """
    symbol_upper = symbol.upper()
    if symbol_upper in INSTRUMENT_SPECS:
        return INSTRUMENT_SPECS[symbol_upper]
    
    logger.warning(f"No instrument spec for {symbol_upper}; using default pip_size=0.0001, USD quote.")
    return InstrumentSpec(symbol_upper, pip_size=0.0001, tick_size=0.00001, quote_currency="USD")


def calculate_pip_value(units: float, price: float, symbol: str) -> float:
    """
    Compute pip value in USD given current price and instrument spec.
    
    Args:
        units: Position size in base currency units
        price: Current market price (quote per base)
        symbol: Instrument symbol
    
    Returns:
        Pip value in USD.
    
    Raises:
        ValueError for non-USD/JPY quote currencies (caller should provide conversion).
    """
    spec = get_instrument_spec(symbol)
    pip_value_quote = units * spec.pip_size
    
    if spec.quote_currency == "USD":
        return pip_value_quote
    if spec.quote_currency == "JPY":
        # Convert JPY quote to USD using USDJPY price (quote price already JPY per USD)
        if price <= 0:
            raise ValueError("Price must be positive to convert JPY pip value to USD")
        return pip_value_quote / price
    
    raise ValueError(
        f"Pip value conversion for quote currency {spec.quote_currency} not implemented. "
        "Provide conversion rate or extend INSTRUMENT_SPECS."
    )
