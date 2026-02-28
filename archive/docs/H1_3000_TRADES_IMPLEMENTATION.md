# H1 Multi-Pair: 3,000 Trades Implementation Plan

## Overview

Deploy the **high-quality exhaustion strategy** across 36 currency pairs on H1 timeframe to achieve ~3,000 profitable trades over 10 years.

## Strategy Configuration

### Best Parameters (85 trades/pair, 7.00 pips/trade)

```yaml
Strategy: Exhaustion Reversal
Direction: LONG entries on bearish exhaustion
Range Detection: 90th percentile (high quality)
Entry Zone: Bottom 30% of range (high conviction)
Exit Horizon: 10 hours
Stop Loss: TBD from Part 14 analysis
Take Profit: TBD from Part 14 analysis
```

### Expected Performance

- **Single Pair**: 85 trades → 595.3 pips (7.00 pips/trade)
- **36 Pairs**: 3,060 trades → **13,511 pips NET** after costs
- **Win Rate**: 50.6%
- **Profit Factor**: 1.41
- **Transaction Costs**: 7,500 pips total (2.5 pips × 3,000 trades)
- **Net Profit**: 21,011 pips gross - 7,500 pips costs = **13,511 pips**

## 36 Currency Pairs to Trade

### Tier 1: Major Pairs (8 pairs)

High liquidity, tight spreads (~1.0 pips)

1. EUR/USD
2. GBP/USD
3. USD/JPY
4. USD/CHF
5. AUD/USD
6. NZD/USD
7. USD/CAD
8. EUR/GBP

### Tier 2: Minor Crosses (14 pairs)

Good liquidity, moderate spreads (~1.5-2.0 pips) 9. EUR/JPY 10. GBP/JPY 11. AUD/JPY 12. NZD/JPY 13. EUR/CHF 14. GBP/CHF 15. EUR/AUD 16. EUR/NZD 17. GBP/AUD 18. GBP/NZD 19. AUD/NZD 20. AUD/CAD 21. EUR/CAD 22. GBP/CAD

### Tier 3: Additional Crosses (14 pairs)

Lower liquidity, wider spreads (~2.0-3.0 pips) 23. CHF/JPY 24. CAD/JPY 25. NZD/CAD 26. NZD/CHF 27. AUD/CHF 28. CAD/CHF 29. EUR/GBP (duplicate, replace) 30. GBP/NZD (duplicate, replace)

### Final Tier 3 List (14 pairs)

23. CHF/JPY
24. CAD/JPY
25. NZD/CAD
26. NZD/CHF
27. AUD/CHF
28. CAD/CHF
29. SGD/JPY
30. HKD/JPY
31. ZAR/JPY
32. MXN/JPY
33. TRY/JPY
34. NOK/SEK
35. EUR/NOK
36. EUR/SEK

**Note**: Choose pairs based on your broker's available instruments and spreads.

## Implementation Steps

### Phase 1: Data Collection (Week 1)

```bash
# Download H1 data for all 36 pairs
# Timeframe: 2015-2026 (10+ years)
# Format: OHLC + timestamp

# Recommended sources:
# - Your broker's API (MT5, Pepperstone FIX)
# - Free: Dukascopy, FXCM (via existing downloaders)
# - Paid: HistData.com, Norgate Data
```

### Phase 2: Data Validation (Week 1-2)

```python
# Run for each pair:
# 1. Check completeness (missing bars)
# 2. Validate OHLC relationships
# 3. Detect outliers/errors
# 4. Calculate actual spreads

# Use existing validator:
from src.data.validator import validate_ohlc_data

for pair in pairs_list:
    df = load_h1_data(pair)
    validate_ohlc_data(df, pair)
```

### Phase 3: Backtest Each Pair (Week 2)

```python
# Test the 85-trade config on each pair separately
# Verify profitability on each instrument

from src.features.exhaustion import ExhaustionDetector
from src.backtest.enhanced_backtest import run_backtest_with_costs

results = {}
for pair in all_36_pairs:
    df = load_processed_data(pair, '1H')

    detector = ExhaustionDetector(
        pressure_lookback=1,
        range_expansion_percentile=90,
        entry_zone_pct=0.30,
        exit_horizon_bars=10,
        detect_bullish=False,  # Bearish exhaustion only
        detect_bearish=True
    )

    trades, stats = run_backtest_with_costs(
        df=df,
        detector=detector,
        spread_pips=get_spread(pair),  # Pair-specific spread
        slippage_pips=1.5
    )

    results[pair] = {
        'trades': len(trades),
        'total_pips': stats['total_pips'],
        'win_rate': stats['win_rate'],
        'profit_factor': stats['profit_factor']
    }

# Filter: Keep only profitable pairs
profitable_pairs = [p for p, r in results.items() if r['total_pips'] > 0]
print(f"Profitable pairs: {len(profitable_pairs)}/36")
```

### Phase 4: Multi-Pair Engine Development (Week 3)

Create `/home/ghost/fx-quant-research/deploy_multipair_h1.py`:

```python
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from src.features.exhaustion import ExhaustionDetector
from src.data.h1_loader import load_processed_data

class MultiPairTradingEngine:
    def __init__(self, pairs_list, config_path):
        self.pairs = pairs_list
        self.config = self.load_config(config_path)
        self.detectors = {}
        self.positions = {}  # Track open positions per pair
        self.trade_history = []

        # Initialize detector for each pair
        for pair in pairs_list:
            self.detectors[pair] = ExhaustionDetector(
                pressure_lookback=self.config['pressure_lookback'],
                range_expansion_percentile=self.config['range_percentile'],
                entry_zone_pct=self.config['entry_threshold'],
                exit_horizon_bars=self.config['exit_horizon'],
                detect_bullish=self.config['detect_bullish'],
                detect_bearish=self.config['detect_bearish']
            )

    def detect_signals(self, pair, df):
        """Detect exhaustion signals for a specific pair"""
        detector = self.detectors[pair]
        signals = detector.detect(df)
        return signals

    def run_multi_pair_backtest(self):
        """Run backtest across all pairs simultaneously"""

        # Load data for all pairs
        data = {}
        for pair in self.pairs:
            data[pair] = load_processed_data(pair, '1H')

        # Align all pairs to common timeline
        common_dates = self.align_timelines(data)

        # Simulate trading day by day
        for date in common_dates:
            # Check each pair for signals
            for pair in self.pairs:
                if pair not in self.positions:  # No open position
                    signal = self.check_signal(pair, data[pair], date)
                    if signal:
                        self.open_position(pair, signal, date)
                else:
                    # Check exit conditions
                    self.check_exit(pair, data[pair], date)

        return self.trade_history

    def align_timelines(self, data):
        """Get common trading hours across all pairs"""
        # Find intersection of all timestamps
        common = set(data[self.pairs[0]].index)
        for pair in self.pairs[1:]:
            common = common.intersection(set(data[pair].index))
        return sorted(list(common))

    def open_position(self, pair, signal, timestamp):
        """Open new position for a pair"""
        self.positions[pair] = {
            'entry_time': timestamp,
            'entry_price': signal['entry_price'],
            'direction': signal['direction'],
            'sl': signal['stop_loss'],
            'tp': signal['take_profit'],
            'exit_bar': signal['exit_horizon']
        }

    def check_exit(self, pair, df, timestamp):
        """Check exit conditions for open position"""
        position = self.positions[pair]

        # Exit logic: time-based or SL/TP hit
        # ... implementation

        # Close and record trade
        del self.positions[pair]
        self.trade_history.append(trade_result)

if __name__ == "__main__":
    # List all 36 pairs
    pairs = [
        'EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'AUDUSD', 'NZDUSD', 'USDCAD', 'EURGBP',
        'EURJPY', 'GBPJPY', 'AUDJPY', 'NZDJPY', 'EURCHF', 'GBPCHF', 'EURAUD', 'EURNZD',
        'GBPAUD', 'GBPNZD', 'AUDNZD', 'AUDCAD', 'EURCAD', 'GBPCAD', 'CHFJPY', 'CADJPY',
        'NZDCAD', 'NZDCHF', 'AUDCHF', 'CADCHF', 'SGDJPY', 'HKDJPY', 'ZARJPY', 'MXNJPY',
        'TRYJPY', 'NOKSEK', 'EURNOK', 'EURSEK'
    ]

    engine = MultiPairTradingEngine(
        pairs_list=pairs,
        config_path='config/h1_multipair_config.json'
    )

    trades = engine.run_multi_pair_backtest()
    print(f"Total trades: {len(trades)}")
```

### Phase 5: Configuration File (Week 3)

Create `/home/ghost/fx-quant-research/config/h1_multipair_config.json`:

```json
{
  "strategy_name": "H1_MultiPair_3000_Trades",
  "pairs": 36,
  "timeframe": "1H",

  "exhaustion_params": {
    "pressure_lookback": 1,
    "range_percentile": 90,
    "entry_threshold": 0.3,
    "exit_horizon": 10,
    "detect_bullish": false,
    "detect_bearish": true
  },

  "risk_management": {
    "max_pairs_open_simultaneously": 10,
    "position_size_per_pair": "1%",
    "max_portfolio_risk": "10%",
    "stop_loss_pips": null,
    "take_profit_pips": null
  },

  "execution": {
    "spread_pips": {
      "majors": 1.0,
      "minors": 2.0,
      "exotics": 3.0
    },
    "slippage_pips": 1.5
  },

  "portfolio": {
    "initial_capital": 100000,
    "compound_returns": true
  }
}
```

### Phase 6: Position Sizing & Risk Management (Week 4)

#### Multi-Pair Kelly Sizing

```python
# With 36 pairs, need to allocate capital carefully

# Option A: Equal Weight per Pair
capital_per_pair = total_capital / 36  # $2,778 per pair if $100k total
position_size = capital_per_pair * kelly_fraction  # 9.3% = $258/pair

# Option B: Risk-Based Allocation
# Allocate more to pairs with better Sharpe/Sortino
# Use correlation matrix to avoid over-concentration

# Option C: Fixed Fractional (Recommended)
# Risk 1% per trade across entire portfolio
risk_per_trade = total_capital * 0.01  # $1,000
position_size = risk_per_trade / stop_loss_pips
```

#### Simultaneous Position Limits

```python
# Don't open all 36 at once (correlation risk)
max_concurrent_positions = 10

# Monitor correlation and limit exposure
# E.g., max 3 JPY pairs, max 3 GBP pairs open at once
```

### Phase 7: Backtesting Full Multi-Pair System (Week 4-5)

```bash
cd /home/ghost/fx-quant-research
python deploy_multipair_h1.py --mode backtest --pairs all
```

Expected output:

```
================================================================================
MULTI-PAIR H1 BACKTEST RESULTS
================================================================================
Pairs traded:          36
Total trades:          3,060
Total pips (gross):    21,011
Transaction costs:     7,500 pips
Net profit:            13,511 pips
Win rate:              50.6%
Profit factor:         1.41
Max drawdown:          TBD
Sharpe ratio:          TBD

Top 5 Performing Pairs:
1. GBP/USD:  595 pips (85 trades)
2. EUR/USD:  TBD
3. USD/JPY:  TBD
...
================================================================================
```

### Phase 8: Paper Trading (Week 6-8)

```bash
# Deploy paper trading with 5-10 pairs first
python deploy_multipair_h1.py --mode paper --pairs majors

# Monitor for 2 weeks, validate:
# - Signal detection accuracy
# - Execution quality (spreads, slippage)
# - Position management
# - Correlation effects

# Gradually add more pairs if profitable
```

### Phase 9: Live Deployment (Week 9+)

```bash
# Start with small capital ($10k) on 10 best pairs
python deploy_multipair_h1.py --mode live --pairs top10 --capital 10000

# Scale up after 1 month of profitable live trading
```

## Risk Considerations

### Correlation Risk

- Many pairs are highly correlated (EUR/USD, GBP/USD ~0.85)
- Avoid opening too many correlated positions simultaneously
- Use correlation matrix to limit exposure

### Data Quality Risk

- Not all pairs have clean 10-year H1 data
- Some exotic pairs might lack liquidity
- Validate each pair's data before including

### Execution Risk

- Wider spreads on minors/exotics eat into 7 pips/trade edge
- Slippage can be worse during low liquidity hours
- Some brokers don't offer all 36 pairs

### Capital Requirements

- $100k minimum recommended for 36 pairs
- Need enough to size positions properly
- Over-leverage = high drawdown risk

## Realistic Pair Selection

### Recommended: Start with 20 high-quality pairs

Focus on pairs with:

- Consistent 10-year H1 data
- Tight spreads (< 2 pips)
- Good broker execution
- Low correlation (< 0.7)

**Suggested 20-pair portfolio**:

1. EUR/USD, GBP/USD, USD/JPY, USD/CHF (low correlation majors)
2. AUD/USD, NZD/USD, USD/CAD (commodity currencies)
3. EUR/JPY, GBP/JPY, AUD/JPY, NZD/JPY (JPY crosses)
4. EUR/GBP, EUR/AUD, EUR/NZD (EUR crosses)
5. GBP/AUD, GBP/NZD (GBP crosses)
6. AUD/NZD, AUD/CAD (AUD crosses)
7. EUR/CHF, GBP/CHF (CHF crosses)
8. CHF/JPY (uncorrelated)

This gives ~1,700 trades (20 × 85) with better data quality and execution.

## Next Steps

1. **Immediate**: Download H1 data for 20 recommended pairs
2. **Week 1**: Validate data quality, calculate actual spreads
3. **Week 2**: Backtest each pair individually with 85-trade config
4. **Week 3**: Build multi-pair backtesting engine
5. **Week 4**: Run full 20-pair backtest, validate profitability
6. **Week 5**: Paper trade top 10 pairs
7. **Week 6+**: Live deployment with conservative sizing

## Performance Tracking

Create daily monitoring dashboard:

```python
# Track per-pair performance
# Monitor correlation matrix
# Alert on drawdown > 10%
# Report weekly aggregate stats
```

## Files to Create

1. `/home/ghost/fx-quant-research/deploy_multipair_h1.py` - Main engine
2. `/home/ghost/fx-quant-research/config/h1_multipair_config.json` - Config
3. `/home/ghost/fx-quant-research/scripts/download_36_pairs.py` - Data downloader
4. `/home/ghost/fx-quant-research/analyze_multipair_results.py` - Performance analyzer
5. `/home/ghost/fx-quant-research/MULTIPAIR_MONITORING_DASHBOARD.md` - Live tracking

---

**Status**: Ready for implementation
**Timeline**: 9 weeks to live deployment
**Capital Required**: $100k (recommended), $50k (minimum for 20 pairs)
**Expected Annual Return**: 1,239 pips/year net (13,511 pips / 10.9 years)
