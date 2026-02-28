# Paper Trading Deployment - Complete Guide

## 🎯 Overview

Deploy the validated **Bearish Exhaustion Reversal** strategy (480.6 pips backtest) to paper trading environment.

**Current Status**: ✅ Backtest validated | 🟡 Ready for paper trading | ⏸️ Live deployment pending

---

## 📋 Pre-Flight Checklist

Before deploying, ensure notebook Parts 1-19 are complete:

- [x] **Part 1-9**: Hypothesis testing (rejected original, found profitable variant)
- [x] **Part 10**: Parameter optimization (1,296 combinations tested)
- [x] **Part 13**: Bearish-only strategy (480.6 pips validated)
- [x] **Part 14**: SL/TP optimization (⚠️ **UPDATE CONFIG WITH RESULTS**)
- [x] **Part 15**: Kelly position sizing (9.3% half-Kelly)
- [x] **Part 16**: Trade logging (75 trades reviewed)
- [x] **Part 17**: Walk-forward validation (2024-2026 OOS positive)
- [x] **Part 18**: Sensitivity analysis (parameter robustness confirmed)
- [x] **Part 19**: Advanced metrics (Sharpe, Sortino, Calmar calculated)

---

## 🚀 Quick Start (3 Steps)

### Step 1: Update Configuration with SL/TP

In your Jupyter notebook, check Part 14 results:

```python
# In notebook cell:
print(f"Best SL: {best_sltp['sl']} pips")
print(f"Best TP: {best_sltp['tp']} pips")
print(f"Total profit: {best_sltp['total_pips']:.1f} pips")
```

Then update the config:

```bash
python update_paper_config.py
# Enter SL and TP values when prompted
```

Or directly edit `config/paper_trading_config.json`:

```json
{
  "stop_loss_pips": 50, // ← Your value from Part 14
  "take_profit_pips": 100 // ← Your value from Part 14
}
```

### Step 2: Run Paper Trading

```bash
./deploy_paper.sh
```

Or manually:

```bash
python deploy_paper_trading.py
```

### Step 3: Analyze Results

```bash
python analyze_paper_results.py
```

---

## 📂 Files Created

| File                               | Purpose                     |
| ---------------------------------- | --------------------------- |
| `deploy_paper_trading.py`          | Main paper trading engine   |
| `config/paper_trading_config.json` | Strategy parameters         |
| `update_paper_config.py`           | Helper to update SL/TP      |
| `deploy_paper.sh`                  | One-click deployment script |
| `analyze_paper_results.py`         | Performance analysis        |
| `logs/paper_trades.csv`            | Trade history (generated)   |
| `logs/paper_trading.log`           | System logs (generated)     |

---

## ⚙️ Configuration Reference

### Validated Strategy Parameters

```json
{
  "pressure_threshold": 1, // Single large bar
  "range_expansion": 0.9, // 90th percentile range
  "percentile_high": 0.7, // Close in bottom 30%
  "exit_horizon_bars": 10, // 10-hour exit
  "trade_only_bearish": true // LONG only (validated)
}
```

### Risk Management

```json
{
  "initial_capital": 10000, // Starting capital
  "risk_per_trade_pct": 0.093, // 9.3% (Half Kelly)
  "max_concurrent_positions": 1, // One trade at a time
  "stop_loss_pips": null, // ← UPDATE from Part 14
  "take_profit_pips": null // ← UPDATE from Part 14
}
```

### Execution Costs

```json
{
  "spread_pips": 1.0, // GBP/USD typical spread
  "slippage_pips": 1.5, // Expected slippage
  "pips_to_points": 10000 // Price conversion
}
```

---

## 📊 Expected Performance

Based on 10.9-year backtest (2015-2026):

| Metric           | Target        |
| ---------------- | ------------- |
| Total Pips       | ~480 pips     |
| Win Rate         | ~55%          |
| Profit Factor    | ~1.5          |
| Trades/Year      | ~7            |
| Avg Win          | ~34 pips      |
| Avg Loss         | ~27 pips      |
| Max DD           | ~272 pips     |
| Return (on $10K) | ~$4,800 gross |

**Simulation Period**: Last 3 months of data  
**Expected Trades**: ~2-3 trades (depending on market conditions)  
**Validation Threshold**: Positive total pips after 20+ trades

---

## 📈 Monitoring & Analysis

### Real-Time Console Output

During execution, you'll see:

```
================================================================================
🚀 STARTING PAPER TRADING SIMULATION
================================================================================
✓ Loaded processed data: 65000 bars from 2015-04-02 to 2026-02-09

================================================================================
📈 NEW POSITION OPENED
   ID: 1
   Direction: LONG
   Entry: 1.25347 @ 2024-11-15 08:00:00+00:00
   Size: 0.15 lots
   Stop Loss: 1.24847
   Take Profit: 1.26347
   Exit Time: 2024-11-15 18:00:00+00:00
================================================================================

================================================================================
📊 POSITION CLOSED
   ID: 1
   Exit: 1.25547 @ 2024-11-15 18:00:00+00:00
   Reason: TIME_EXIT
   Gross: 20.00 pips | Net: 17.50 pips
   P&L: $175.00
   Account Balance: $10,175.00
   Return: 1.75%
================================================================================
```

### Trade Log (CSV)

`logs/paper_trades.csv` contains:

- Timestamp, TradeID, Action (OPEN/CLOSE)
- Entry/Exit prices and times
- Exit reason (TIME_EXIT, STOP_LOSS, TAKE_PROFIT)
- Gross pips, Net pips (after costs), P&L in USD
- Running account balance

### Performance Analysis

Run `python analyze_paper_results.py` to see:

- ✅ Trade statistics (wins, losses, streaks)
- ✅ Profitability metrics (total pips, profit factor)
- ✅ Risk metrics (max DD, recovery factor)
- ✅ Distribution of trade outcomes
- ✅ Exit reason breakdown
- ✅ Backtest vs paper trading comparison
- ✅ Validation checklist

---

## 🛡️ Risk Management

### Position Sizing

- **Method**: Half-Kelly Criterion (conservative)
- **Risk per trade**: 9.3% of current capital
- **Calculation**: Based on backtest win rate (54.7%) and avg win/loss
- **Max concurrent**: 1 position
- **Lot size**: Dynamic based on account balance and SL distance

### Stop Management

1. **Stop Loss**: Configured from Part 14 optimization
2. **Take Profit**: Configured from Part 14 optimization
3. **Time Exit**: 10 hours (fallback if SL/TP not hit)
4. **Max consecutive losses**: Monitor (exit strategy if > 7)

### Account Protection

- **Minimum balance**: $1,000 recommended
- **Max drawdown limit**: 30% of capital (manual override)
- **Trading hours**: All sessions (can configure LONDON/NY only)

---

## ✅ Validation Criteria

Before proceeding to live trading, paper trading must show:

| Criterion          | Threshold             | Rationale                |
| ------------------ | --------------------- | ------------------------ |
| Total trades       | ≥ 20                  | Statistical significance |
| Win rate           | > 50%                 | Maintain edge            |
| Profit factor      | > 1.2                 | Profitable after costs   |
| Total pips         | > 0                   | Positive expectancy      |
| Max drawdown       | < 300 pips            | Risk tolerance           |
| Max loss streak    | < 10                  | Psychological limit      |
| Return consistency | Positive across weeks | Avoid luck               |

**Timeline**: Run for 2-4 weeks or until 20+ trades

---

## 🔧 Troubleshooting

### Issue: "Processed data not found"

**Solution**: Generate processed data first:

```python
from src.data.h1_loader import H1DataLoader
loader = H1DataLoader()
df = loader.load_gbpusd_h1()
df_processed = loader.prepare_for_backtest(df, add_sessions=True, add_returns=True)
loader.save_processed(df_processed)
```

### Issue: "No trades detected"

**Possible causes**:

1. Simulation period too short (increase from 90 days)
2. No bearish exhaustion bars in period (normal - wait longer)
3. Max positions already open (check logs)

**Solution**: Run on longer period or full historical data:

```python
# In deploy_paper_trading.py main():
engine.run_simulation(df, start_date='2024-01-01')  # Full 2024-2026
```

### Issue: "Performance worse than backtest"

**Normal**: Small sample variance expected  
**Action**: Continue to 20+ trades before evaluating  
**If persistent**: Review SL/TP config, check for data quality issues

---

## 📍 Next Steps

### After Successful Paper Trading (20+ trades, positive)

1. **Review Results**

   ```bash
   python analyze_paper_results.py
   ```

   - Confirm all validation criteria met
   - Review trade distribution and exit reasons
   - Check max consecutive losses

2. **Update Live Configuration**

   ```bash
   cp config/paper_trading_config.json config/live_trading_config.json
   # Adjust initial_capital to actual live amount
   ```

3. **Start Live Trading**
   - Begin with **minimal capital** ($500-$1,000)
   - Use **conservative sizing** (5% per trade vs 9.3%)
   - Monitor for **1 month** before scaling
   - Compare live vs paper trading results

4. **Live Trading Checklist**
   - [ ] Broker account funded
   - [ ] API credentials configured
   - [ ] FIX connection tested (see `test_fix_logon.py`)
   - [ ] Monitoring system active
   - [ ] Stop-loss orders enabled
   - [ ] Emergency shutdown procedures documented

---

## 📞 Support & Documentation

### Related Files

- **Strategy Research**: `notebooks/04_exhaustion_reversal_hypothesis.ipynb`
- **Backtest Engine**: `src/backtest/engine.py`
- **Signal Detection**: `src/features/exhaustion.py`
- **Data Loading**: `src/data/h1_loader.py`
- **Live Trading**: `execute_gbpjpy_live.py` (example)

### Key Metrics Reference

Run in notebook to refresh memory:

```python
# Best parameters
print(best)
# Output: {'type': 'bearish', 'pressure': 1, 'range_expansion': 0.9, ...}

# Best SL/TP
print(best_sltp)

# Trade log
trade_log_df.describe()
```

### Questions?

1. Review `PAPER_TRADING_README.md` (summary)
2. Check `LIVE_TRADING_README.md` (next phase)
3. Consult `IMPLEMENTATION_STATUS.md` (overall progress)

---

## ⚠️ Important Reminders

1. **Paper trading is NOT live trading** - Expect differences due to:
   - Execution risk (slippage, requotes)
   - Market conditions variance
   - Psychological factors (fear/greed)

2. **Start SMALL in live** - Even after successful paper trading:
   - First month: $500-$1,000 capital
   - After 1 month positive: Scale to $2,000-$5,000
   - After 3 months positive: Full capital deployment

3. **Monitor CONTINUOUSLY** - First 2 weeks especially:
   - Check logs daily
   - Review each trade execution
   - Validate signal detection accuracy
   - Monitor costs (spread/slippage vs expected)

4. **Have EXIT PLAN** - Stop trading if:
   - 7+ consecutive losses
   - Drawdown > 30% of capital
   - Profit factor < 1.0 after 30 trades
   - Win rate < 45% after 50 trades

---

**Deployment Version**: 1.0  
**Last Updated**: 2026-02-24  
**Strategy**: Bearish Exhaustion Reversal (Validated)  
**Status**: 🟢 Ready for Paper Trading

**Next Milestone**: 20 successful paper trades → Live deployment with $500-$1K

---
