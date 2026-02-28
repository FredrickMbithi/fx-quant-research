# Paper Trading Results - Exhaustion + Failure Pattern

**Date**: February 26, 2026  
**Hypothesis**: Two-bar mean reversion after exhaustion + failure-to-continue  
**Status**: ✅ DEPLOYMENT COMPLETE

---

## Executive Summary

Deployed exhaustion+failure pattern for paper trading on **NZDJPY** (PASS status) and **GBPUSD** (MARGINAL status). Both pairs tested with identical exit parameters: 10 pip SL, 4 pip profit trigger, 3 pip trail, 5 bar max hold.

**Key Finding**: Both pairs show positive edge but perform slightly below backtest expectations. NZDJPY achieves 2.40 pips/trade (vs 4.25 expected), GBPUSD achieves 0.95 pips/trade (vs 1.31 expected).

---

## NZDJPY Results (PASS → Paper Trading)

### Performance Metrics

| Metric            | Backtest  | Paper Trading | Difference     |
| ----------------- | --------- | ------------- | -------------- |
| **Total Trades**  | 90        | 156           | +73%           |
| **Avg PnL/trade** | 4.25 pips | 2.40 pips     | **-1.85 pips** |
| **Win Rate**      | 63.3%     | 64.1%         | +0.8%          |
| **Profit Factor** | 2.34      | 1.62          | -0.72          |
| **Max Drawdown**  | N/A       | 78 pips       | -              |

### Trade Breakdown

- **LONG trades**: 71 (45.5%)
- **SHORT trades**: 85 (54.5%)
- **Gross PnL**: 655 pips
- **Transaction Costs**: 281 pips (1.8 pips/trade)
- **NET PnL**: 374 pips

### Exit Statistics

- **TRAIL exits**: 105 (67.3%) - Majority hit profit target
- **SL exits**: 51 (32.7%) - Stopped out
- **Avg bars held**: 1.7 hours

### Statistical Validation

- **t-test**: p=0.0175 (significant at α=0.05)
- **Conclusion**: Edge is statistically significant

### Monitoring Alerts

⚠️ **ALERT**: Avg PnL (2.40 pips) below threshold (3.00 pips)  
📋 **REVIEW**: 156 trades executed (target: 30)  
🛑 **STATUS**: Paper trading **DEVIATES** from backtest expectations

### Analysis

**Why lower performance?**

1. More trades (156 vs 90) suggests different data period
2. Cost drag (1.8 pips) significant at 2.4 pips/trade edge
3. Win rate matches (64.1% vs 63.3%), but avg win size smaller

**Recommendation**:

- ⚠️ **HOLD** - Do NOT proceed to live trading yet
- Investigate why avg PnL dropped from 4.25 → 2.40 pips
- Possible causes: Market regime change, different data sampling, parameter drift
- Next step: Analyze trade-by-trade comparison vs backtest signals

---

## GBPUSD Results (MARGINAL → Optimization)

### Performance Metrics

| Metric            | Backtest  | Paper Trading | Difference   |
| ----------------- | --------- | ------------- | ------------ |
| **Total Trades**  | 3,245     | 425           | Halted early |
| **Avg PnL/trade** | 1.31 pips | 0.95 pips     | -0.36 pips   |
| **Win Rate**      | 50.1%     | 45.4%         | **-4.7%**    |
| **Profit Factor** | 1.23      | 1.15          | -0.08        |
| **Max Drawdown**  | N/A       | 233 pips      | -            |

### Trade Breakdown

- **LONG trades**: 226 (53.2%)
- **SHORT trades**: 199 (46.8%)
- **Gross PnL**: 1,254 pips
- **Transaction Costs**: 850 pips (2.0 pips/trade)
- **NET PnL**: 404 pips

### Exit Statistics

- **TRAIL exits**: 205 (48.2%)
- **SL exits**: 219 (51.5%) - More stopped out than trailed!
- **TIME exits**: 1 (0.2%)
- **Avg bars held**: 1.3 hours

### Statistical Validation

- **t-test**: p=0.2703 (NOT significant at α=0.05)
- **Conclusion**: Edge is NOT statistically significant
- **Result**: Close to breakeven after costs

### Monitoring Alerts

🛑 **HALTED**: 7 consecutive losses triggered auto-halt  
📋 **REVIEW**: 425 trades executed (target: 100)  
✅ **STATUS**: Paper trading **VALIDATES** backtest (within tolerance)

### Analysis

**Why marginal performance?**

1. Win rate dropped 50.1% → 45.4% (losing more than expected)
2. MORE SL hits (51.5%) than TRAIL exits (48.2%) - losing trades faster
3. Avg PnL 0.95 pips barely covers 2.0 pips cost (47% cost drag!)
4. Statistical significance LOST (p=0.27)

**Recommendation**:

- ⚠️ **STOP** - Do NOT trade GBPUSD live with current parameters
- Exit optimization REQUIRED
- Test variations:
  - Wider trail (5 pips instead of 3) to hold winners longer
  - Tighter stop (8 pips instead of 10) to cut losers faster
  - Longer max hold (8 bars instead of 5) to give time to recover
- Goal: Improve 0.95 → 2.0+ pips/trade for PASS status

---

## Configuration Files

### NZDJPY Config

- **File**: [config/paper_exhaustion_nzdjpy.json](config/paper_exhaustion_nzdjpy.json)
- **Strategy**: ExhaustionStrategy (2-bar pattern)
- **Exit**: 10 SL / 4 trigger / 3 trail / 5 bars
- **Costs**: 1.8 pips round-trip (0.9 spread + 0.9 slippage)
- **Risk**: 1% per trade, 10% max DD, halt on 5 consecutive losses

### GBPUSD Config

- **File**: [config/paper_exhaustion_gbpusd.json](config/paper_exhaustion_gbpusd.json)
- **Strategy**: ExhaustionStrategy (2-bar pattern)
- **Exit**: 10 SL / 4 trigger / 3 trail / 5 bars
- **Costs**: 2.0 pips round-trip (1.0 spread + 1.0 slippage)
- **Risk**: 1% per trade, 10% max DD, halt on 7 consecutive losses

---

## Deployment Infrastructure

### Created Files

1. ✅ [deploy_exhaustion_paper.py](deploy_exhaustion_paper.py) - Main paper trading engine (527 lines)
2. ✅ [config/paper_exhaustion_nzdjpy.json](config/paper_exhaustion_nzdjpy.json) - NZDJPY configuration
3. ✅ [config/paper_exhaustion_gbpusd.json](config/paper_exhaustion_gbpusd.json) - GBPUSD configuration
4. ✅ [state/paper_trades_nzdjpy.csv](state/paper_trades_nzdjpy.csv) - 156 trades (19KB)
5. ✅ [state/paper_trades_gbpusd.csv](state/paper_trades_gbpusd.csv) - 425 trades

### Strategy Implementation

- **File**: [src/strategies/exhaustion_strategy.py](src/strategies/exhaustion_strategy.py)
- **Pattern**: Pressure ±2, range >0.8×median, extreme close (35%), reversal confirmation
- **Signal Detection**: Event-driven (processes bars one at a time like live trading)
- **Exit Management**: Simulated stop loss + trailing stop logic

### Running Paper Trading

```bash
# NZDJPY
python deploy_exhaustion_paper.py --symbol NZDJPY

# GBPUSD
python deploy_exhaustion_paper.py --symbol GBPUSD

# Custom date range
python deploy_exhaustion_paper.py --symbol NZDJPY --start 2025-01-01 --end 2026-01-01
```

---

## Risk Management Assessment

### 5-Layer Risk System (from plan)

#### Layer 1: Pre-Trade Validation ✅

- Strategy generates signals using ExhaustionStrategy.calculate_signal()
- Risk per trade: 1% of capital ($1,000 per trade on $100k account)
- Max concurrent positions: 1 (no overlapping trades)

#### Layer 2: Position Limits ✅

- NZDJPY: Halt on 10% drawdown OR 5 consecutive losses
- GBPUSD: Halt on 10% drawdown OR 7 consecutive losses
- **RESULT**: GBPUSD halted after 7 consecutive losses (risk system working!)

#### Layer 3: Exit Management ✅

- Hard stop: 10 pips (prevents catastrophic losses)
- Trailing stop: Activates at +4 pips, trails 3 pips behind
- Max hold: 5 bars (prevents holding losers overnight)
- **RESULT**:
  - NZDJPY: 67.3% exits via TRAIL (good!)
  - GBPUSD: 51.5% exits via SL (bad - losing too fast)

#### Layer 4: Daily Monitoring ✅

- Performance reports every N trades (10 for NZDJPY, 50 for GBPUSD)
- CSV output for trade-by-trade analysis
- Logs every signal + exit in [logs/paper_exhaustion.log](logs/paper_exhaustion.log)

#### Layer 5: Review Checkpoints ✅

- NZDJPY: Review after 30 trades (156 executed - checkpoint passed)
- GBPUSD: Review after 100 trades (425 executed - checkpoint passed)
- Statistical validation (t-test) included in final report

---

## Decision Criteria Results

### NZDJPY Decision Matrix

| Criterion           | Threshold | Actual    | Status  |
| ------------------- | --------- | --------- | ------- |
| **Win Rate**        | ≥55%      | 64.1%     | ✅ PASS |
| **Avg PnL/trade**   | ≥3.0 pips | 2.40 pips | ❌ FAIL |
| **Profit Factor**   | ≥2.0      | 1.62      | ❌ FAIL |
| **Statistical Sig** | p<0.05    | p=0.018   | ✅ PASS |

**Overall**: ⚠️ **MIXED** - High win rate but lower profitability than expected

### GBPUSD Decision Matrix

| Criterion           | Threshold | Actual    | Status  |
| ------------------- | --------- | --------- | ------- |
| **Win Rate**        | ≥45%      | 45.4%     | ✅ PASS |
| **Avg PnL/trade**   | ≥0.5 pips | 0.95 pips | ✅ PASS |
| **Profit Factor**   | ≥1.1      | 1.15      | ✅ PASS |
| **Statistical Sig** | Any edge  | p=0.27    | ❌ FAIL |

**Overall**: ⚠️ **MARGINAL** - Meets thresholds but NOT statistically significant

---

## Next Steps

### NZDJPY (High Confidence → Investigation)

1. ❌ **DO NOT proceed to live trading yet**
2. 🔍 **Investigate performance gap**:
   - Compare paper trading signals vs backtest signals (are they the same trades?)
   - Check if data period differs (NZDJPY has limited history)
   - Analyze why avg PnL dropped 4.25 → 2.40 pips (smaller winners? bigger losers?)
3. ⚙️ **Options**:
   - **Option A**: Re-run backtest on same date range as paper trading
   - **Option B**: Analyze cost impact (1.8 pips is 75% of edge!)
   - **Option C**: Test with tighter spread assumptions (0.5 pips instead of 0.9)

### GBPUSD (Marginal → Optimization)

1. ❌ **DO NOT trade with current parameters**
2. 🔧 **Test exit variations**:
   - **Test 1**: Wider trail (5 pips trail instead of 3) - hold winners longer
   - **Test 2**: Tighter stop (8 pips SL instead of 10) - cut losers faster
   - **Test 3**: Longer max hold (8 bars instead of 5) - more time to recover
   - **Test 4**: Different profit trigger (6 pips instead of 4) - higher bar for trailing
3. 🎯 **Goal**: Improve avg PnL from 0.95 → 2.0+ pips/trade
4. 📊 **Success metric**: Win rate ≥48% AND avg PnL ≥2.0 pips AND p<0.05

### Create Exit Optimization Framework

```bash
# Suggested next script
python optimize_exits_gbpusd.py --param trailing_distance --range 2-6 --step 1
python optimize_exits_gbpusd.py --param stop_loss --range 6-12 --step 2
python optimize_exits_gbpusd.py --param max_hold_bars --range 3-10 --step 1
```

---

## Files Created

### Scripts

- [deploy_exhaustion_paper.py](deploy_exhaustion_paper.py) - Paper trading engine

### Configurations

- [config/paper_exhaustion_nzdjpy.json](config/paper_exhaustion_nzdjpy.json) - NZDJPY params
- [config/paper_exhaustion_gbpusd.json](config/paper_exhaustion_gbpusd.json) - GBPUSD params

### Output

- [state/paper_trades_nzdjpy.csv](state/paper_trades_nzdjpy.csv) - 156 trades
- [state/paper_trades_gbpusd.csv](state/paper_trades_gbpusd.csv) - 425 trades
- [logs/paper_exhaustion.log](logs/paper_exhaustion.log) - Full execution log

### Documentation

- [PAPER_TRADING_RESULTS.md](PAPER_TRADING_RESULTS.md) - This file

---

## Conclusion

**Paper trading deployment COMPLETE**. Both pairs tested with real-world exit simulation:

- **NZDJPY**: Positive edge (2.40 pips/trade) but below expected performance
- **GBPUSD**: Marginal edge (0.95 pips/trade) barely profitable after costs

**Recommendation**:

- ⚠️ **NZDJPY**: Investigate performance gap before live trading
- ❌ **GBPUSD**: Optimize exits to improve profitability beyond 0.95 pips/trade

Both pairs require **additional work** before proceeding to Phase 2 (micro live trading).

---

_Generated: February 26, 2026_  
_Paper Trading Period: Oct 2025 - Feb 2026_  
_Data Source: H1 CSV files in data/raw/_
