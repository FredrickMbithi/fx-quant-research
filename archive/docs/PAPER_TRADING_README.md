# Paper Trading Deployment - Exhaustion Reversal Strategy

## 📊 Strategy Summary

**Validated Performance (10.9 years backtest):**

- Total PnL: **480.6 pips**
- Win Rate: **54.7%**
- Profit Factor: **1.52**
- Max Drawdown: **271.7 pips**
- Trades: **75** (7 per year)
- Average PnL per trade: **6.4 pips** (after costs)

**Strategy Configuration:**

- **Type**: Bearish exhaustion reversal (LONG only)
- **Entry**: Large down-bar (90th percentile range), close in bottom 30%
- **Exit**: 10 hours after entry (time-based)
- **Direction**: Counter-trend mean reversion
- **Position Sizing**: Half-Kelly (9.3% of capital)

## 🚀 Quick Start

###1. Update Configuration

Edit `config/paper_trading_config.json` with optimal SL/TP from Part 14:

```json
{
  "stop_loss_pips": 50, // UPDATE from notebook Part 14 results
  "take_profit_pips": 100 // UPDATE from notebook Part 14 results
}
```

### 2. Run Paper Trading Simulation

```bash
# Activate environment
source venv/bin/activate

# Run on historical data (last 3 months)
python deploy_paper_trading.py
```

### 3. Monitor Results

- **Trade Log**: `logs/paper_trades.csv` (all trades with entry/exit/P&L)
- **System Log**: `logs/paper_trading.log` (detailed execution log)
- **Console**: Real-time trade notifications

## 📁 Files Structure

```
fx-quant-research/
├── deploy_paper_trading.py          # Main paper trading engine
├── config/
│   └── paper_trading_config.json    # Strategy parameters
├── logs/
│   ├── paper_trades.csv             # Trade history (CSV)
│   └── paper_trading.log            # System logs
├── src/
│   ├── features/exhaustion.py       # Signal detection
│   └── data/h1_loader.py            # Data loading
└── PAPER_TRADING_README.md          # This file
```

## ⚙️ Configuration Parameters

### Strategy Parameters (Validated)

```json
{
  "pressure_threshold": 1, // Single large bar
  "range_expansion": 0.9, // 90th percentile range
  "percentile_high": 0.7, // Close in bottom 30%
  "exit_horizon_bars": 10, // 10-hour exit
  "trade_only_bearish": true // LONG only
}
```

### Risk Management (Update from Notebook)

```json
{
  "initial_capital": 10000,
  "risk_per_trade_pct": 0.093, // Half-Kelly: 9.3%
  "stop_loss_pips": null, // ← UPDATE THIS
  "take_profit_pips": null, // ← UPDATE THIS
  "max_concurrent_positions": 1
}
```

### Costs (Broker-specific)

```json
{
  "spread_pips": 1.0, // GBP/USD typical spread
  "slippage_pips": 1.5 // Expected slippage
}
```

## 📈 Expected Performance

Based on backtested results:

| Metric          | Value         |
| --------------- | ------------- |
| Annual Return   | ~44 pips/year |
| Trades per Year | ~7            |
| Win Rate        | 54.7%         |
| Avg Win         | 34.4 pips     |
| Avg Loss        | -27.4 pips    |
| Profit Factor   | 1.52          |
| Max Drawdown    | 271.7 pips    |
| Sharpe Ratio    | See Part 19   |
| Sortino Ratio   | See Part 19   |

## 🔍 Validation Checklist

Before live deployment, confirm:

- [ ] **Part 14** - SL/TP optimization complete (config updated)
- [ ] **Part 15** - Position sizing validated (Kelly = 18.6%, Half = 9.3%)
- [ ] **Part 16** - Trade log reviewed (75 historical trades)
- [ ] **Part 17** - Walk-forward passed (2024-2026 out-of-sample positive)
- [ ] **Part 18** - Sensitivity analysis acceptable (< 20% parameter sensitivity)
- [ ] **Part 19** - Sharpe > 0.5, Profit Factor > 1.2
- [ ] **Paper trading** - 2 weeks simulated → positive results

## 🎯 Running Modes

### 1. Historical Simulation (Current)

```python
# Run on last 3 months of historical data
python deploy_paper_trading.py
```

### 2. Live Paper Trading (Next Step)

For live operation, you'll need:

- Real-time data feed (e.g., MT5, OANDA API, IGgetMarkets)
- Update `PaperTradingEngine.load_historical_data()` to fetch live data
- Run continuously: `python deploy_paper_trading.py --live`

### 3. Live Trading (Final Step)

After 20+ successful paper trades:

- Connect to broker API (FIX, MT5, etc.)
- Start with minimal capital ($500-1000)
- Monitor for 1 month before scaling

## 📊 Monitoring

### Real-time Console Output

```
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
```

### Performance Summary (every 5 trades)

```
================================================================================
📊 PERFORMANCE SUMMARY
================================================================================
Total Trades: 10
Wins: 6 (60.0%) | Losses: 4
Total Pips: 45.3
Total P&L: $4,530.00
Account Balance: $14,530.00
Return: 45.30%
Avg Win: 22.3 pips | Avg Loss: -18.5 pips
================================================================================
```

### Trade Log CSV

```csv
Timestamp,TradeID,Action,Direction,EntryPrice,ExitPrice,EntryTime,ExitTime,ExitReason,GrossPips,NetPips,PnL_USD,AccountBalance,BarsHeld
2024-11-15 08:05:23,1,OPEN,LONG,1.25347,,,,,,,10000.00,0
2024-11-15 18:10:45,1,CLOSE,LONG,1.25347,1.25547,2024-11-15 08:00:00,2024-11-15 18:00:00,TIME_EXIT,20.00,17.50,175.00,10175.00,10
```

## 🛡️ Risk Management

### Position Sizing

- **Method**: Half-Kelly Criterion
- **Risk per trade**: 9.3% of capital
- **Max positions**: 1 concurrent
- **Account needed**: Minimum $1,000 recommended

### Stop Management

- **Stop Loss**: Set from Part 14 optimization results
- **Take Profit**: Set from Part 14 optimization results
- **Time Exit**: 10 hours (validated)
- **Max consecutive losses**: Monitor (historical max ~5-7)

## ⚠️ Important Notes

1. **Update Config First**: Add SL/TP from notebook Part 14 before running
2. **Paper Trade First**: Run 2-4 weeks simulation before live
3. **Monitor Closely**: Check logs daily during first month
4. **Start Small**: Use $500-1000 initial live capital
5. **Validate Continuously**: Compare live results to backtest expectations

## 📞 Next Steps

1. **Review Part 14** (SL/TP optimization) → Update config
2. **Run simulation** → `python deploy_paper_trading.py`
3. **Analyze logs** → Check `logs/paper_trades.csv`
4. **Validate performance** → Should match backtest metrics
5. **Deploy live** → After 2 weeks successful paper trading

## 📚 Reference Documentation

- **Strategy Research**: `notebooks/04_exhaustion_reversal_hypothesis.ipynb`
- **Backtest Code**: `src/backtest/engine.py`
- **Signal Detection**: `src/features/exhaustion.py`
- **Data Loading**: `src/data/h1_loader.py`

---

**Status**: Ready for paper trading after SL/TP configuration update
**Last Updated**: 2026-02-24
**Backtest Period**: 2015-2026 (10.9 years)
**Validation**: ✅ Out-of-sample tested, ✅ Sensitivity analyzed, ✅ Kelly sized
