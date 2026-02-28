# FX Transaction Cost Assumptions

**Purpose**: Document realistic transaction costs for backtesting that "will kill bad strategies"

**Philosophy**: Use conservative (high) cost estimates to ensure only robust strategies pass testing.

---

## 1. Spread + Slippage Costs

### Cost Components

**Spread**: Bid-ask spread paid on every trade (unavoidable)
**Slippage**: Price movement during order execution (market impact + latency)
**Total Cost**: Paid twice per round-trip (entry + exit)

### Cost Schedule (per side, in pips)

| Pair   | Spread | Slippage | Total | Annual Volume | Liquidity |
| ------ | ------ | -------- | ----- | ------------- | --------- |
| EURUSD | 0.6    | 0.2      | 0.8   | $1.5T/day     | Highest   |
| GBPUSD | 0.8    | 0.2      | 1.0   | $700B/day     | High      |
| USDJPY | 0.8    | 0.2      | 1.0   | $900B/day     | High      |
| AUDUSD | 1.0    | 0.3      | 1.3   | $300B/day     | Medium    |
| USDCAD | 1.2    | 0.3      | 1.5   | $250B/day     | Medium    |
| NZDUSD | 1.5    | 0.3      | 1.8   | $100B/day     | Lower     |
| EURGBP | 0.9    | 0.3      | 1.2   | $200B/day     | Medium    |
| EURJPY | 1.2    | 0.3      | 1.5   | $150B/day     | Medium    |

### Data Sources

- **Spread**: Pepperstone cTrader historical tick data (95th percentile)
- **Slippage**: Empirical observation + 50% safety margin
  - Market orders: 0.2-0.3 pips typical
  - Limit orders: ~0 slippage but risk non-fill
  - News events: 1-5 pips (filtered out in backtest)

### Cost Impact Examples

**High-frequency (100 trades/year)**:

- EURUSD: 0.8 pips × 2 sides × 100 = 160 pips = 1.6% annual drag
- GBPUSD: 1.0 pips × 2 × 100 = 200 pips = 2.0% annual drag

**Medium-frequency (20 trades/year)**:

- EURUSD: 0.8 × 2 × 20 = 32 pips = 0.32% annual drag
- GBPUSD: 1.0 × 2 × 20 = 40 pips = 0.40% annual drag

**Why this kills bad strategies**:

- Any strategy with Sharpe < 1.0 likely fails after costs
- Win rate must exceed 55% just to break even at 100 trades/year
- Holding periods < 1 day face 5-10% annual cost drag

---

## 2. Swap/Rollover Costs

### What Are Swaps?

Overnight financing cost/credit for holding FX positions past 5pm EST.

**Formula**:

```
Swap = (Interest_Rate_Diff - Broker_Markup) × Position_Size × (Days_Held / 360)
```

### Current Interest Rate Environment (2024-2025)

| Currency | Central Bank Rate | Policy Stance |
| -------- | ----------------- | ------------- |
| USD      | 5.25%             | Restrictive   |
| EUR      | 4.00%             | Neutral       |
| GBP      | 5.00%             | Restrictive   |
| JPY      | -0.10%            | Accommodative |
| AUD      | 4.35%             | Restrictive   |
| CAD      | 4.75%             | Restrictive   |
| NZD      | 5.50%             | Restrictive   |

### Typical Swap Rates (pips per day, LONG positions)

| Pair   | Interest Diff | Broker Markup | Net Swap   | Direction             |
| ------ | ------------- | ------------- | ---------- | --------------------- |
| EURUSD | -1.25%        | -1.5%         | -0.18 pips | Pay (holding EUR)     |
| GBPUSD | -0.25%        | -1.5%         | -0.12 pips | Pay (holding GBP)     |
| USDJPY | +5.35%        | -1.5%         | +0.27 pips | Receive (holding USD) |
| AUDUSD | -0.90%        | -1.5%         | -0.16 pips | Pay (holding AUD)     |
| USDCAD | +0.50%        | -1.5%         | +0.07 pips | Receive (holding USD) |

**Notes**:

- Negative swap = cost (you pay)
- Positive swap = credit (you receive)
- SHORT positions have opposite sign
- Wednesday charges 3× swap (weekend rollover)

### Swap Data Source

**Preferred**: Download historical swap rates from MT5/cTrader

```bash
# Download from Pepperstone MT5
# File: data/swap_rates/pepperstone_swaps_2020_2025.csv
# Format: date,symbol,swap_long_pips,swap_short_pips
```

**Fallback**: Use interest rate differential approximation (see `swap_calculator.py`)

### Swap Impact Examples

**Holding EURUSD long for 30 days**:

- Swap: -0.18 pips/day × 30 days = -5.4 pips
- As % of 1.1000 entry: -0.05%
- Annualized drag: -0.60%

**Holding USDJPY long for 90 days**:

- Swap: +0.27 pips/day × 90 days = +24.3 pips
- As % of 150.00 entry: +0.16%
- Annualized credit: +0.65%

**Why this matters**:

- Carry trades can earn/cost 5-10 pips per week
- Multi-month swing trades accumulate significant swap
- Creates directional bias: profit from holding high-rate currencies

---

## 3. Cost Model Integration

### In Backtesting Engine

```python
from src.backtest.cost_model import get_cost_model
from src.backtest.swap_calculator import compute_swap_cost

# Get cost model for pair
cost_model = get_cost_model('EURUSD')

# Apply spread + slippage on entry
entry_cost_pips = cost_model.compute_cost()
# EURUSD: 0.8 pips

# Apply swap daily
daily_swap_pips = compute_swap_cost(
    symbol='EURUSD',
    position_size=10000,
    hold_days=1,
    swap_rate_pips_per_day=-0.18
)
# EURUSD: -0.18 pips/day

# Apply spread + slippage on exit
exit_cost_pips = cost_model.compute_cost()
# EURUSD: 0.8 pips

# Total cost for 30-day trade
total_cost = entry_cost_pips + exit_cost_pips + (daily_swap_pips * 30)
# 0.8 + 0.8 + (-0.18 × 30) = 1.6 - 5.4 = -3.8 pips net
```

### Cost Accounting in Performance Metrics

**Gross P&L**: Price movement only (unrealistic)
**Net P&L**: Price movement minus all costs (realistic)

```
Net P&L = Gross P&L - Entry Cost - Exit Cost - Swap Costs
```

**Example Trade**:

- Entry: 1.1000, Exit: 1.1050 (50 pips profit)
- Entry cost: 0.8 pips
- Hold: 10 days × -0.18 pips/day = -1.8 pips
- Exit cost: 0.8 pips
- **Gross P&L**: 50 pips
- **Net P&L**: 50 - 0.8 - 1.8 - 0.8 = 46.6 pips (7% cost drag)

---

## 4. Cost Validation Strategy

### Benchmarking Against Reality

1. **Compare to Live Trading**:
   - Run strategy on paper trading account
   - Measure actual spread/slippage from fill prices
   - Validate swap charges match broker statements

2. **Sensitivity Analysis**:
   - Test with costs ±50%
   - If performance degrades >30%, strategy is fragile
   - Robust strategies maintain Sharpe > 0.8 at 2× costs

3. **Cost Attribution**:
   - Track: Total Return, Spread Cost, Slippage Cost, Swap Cost
   - If costs > 30% of gross P&L, reduce trade frequency

### Red Flags

❌ **Strategy fails if**:

- Sharpe ratio drops below 1.0 with realistic costs
- Win rate < 55% and average hold < 2 days
- Gross P&L < 2× total costs
- More than 50 trades/year on pairs with >1.5 pip cost

✅ **Strategy passes if**:

- Sharpe ratio > 1.2 after all costs
- Profit factor > 1.5 (gross wins / gross losses)
- Average trade P&L > 5× round-trip cost
- Consistent across cost scenarios (±50%)

---

## 5. Future Enhancements

### Data Collection Tasks

- [ ] Download 5 years of Pepperstone swap rates (MT5)
- [ ] Collect intraday spread distributions (tick data)
- [ ] Measure slippage from live order executions
- [ ] Build weekend gap cost estimate

### Model Improvements

- [ ] Time-of-day spread variation (wider during Asian session)
- [ ] News event cost multiplier (ECB, NFP, FOMC)
- [ ] Market depth model (slippage increases with size)
- [ ] Broker-specific swap calculation (triple swap logic)

### Monitoring

- [ ] Monthly cost audit: compare backtest vs. live costs
- [ ] Swap rate update: re-download every quarter
- [ ] Spread monitoring: alert if live spreads > backtest assumption

---

## 6. References

**Data Sources**:

- Pepperstone cTrader: Live spreads and historical ticks
- Central bank websites: Policy rates
- BIS Triennial Survey: FX market volume statistics

**Cost Modeling Literature**:

- _Transaction Costs and Investment Style_ (Keim & Madhavan, 1998)
- _The Cost of Latency_ (Hasbrouck & Saar, 2013)
- _Execution Costs_ (Kissell & Glantz, 2003)

**FX Market Microstructure**:

- _The Microstructure of Foreign Exchange Markets_ (Lyons, 1995)
- _Exchange Rates and International Finance_ (Copeland, 2014)

---

**Last Updated**: 2025-02-25
**Next Review**: Quarterly (after swap rate updates)
