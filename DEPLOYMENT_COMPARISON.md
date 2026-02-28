# Deployment Types Comparison

## Overview

You now have **TWO types of paper trading** implemented:

1. ✅ **Historical Paper Trading** (COMPLETED - Feb 26)
2. 🆕 **Live Paper Trading** (NEW - Ready to deploy)

---

## Historical Paper Trading (Backtest)

**File**: [deploy_exhaustion_paper.py](deploy_exhaustion_paper.py)

### How It Works
```
data/raw/NZDJPY60.csv   ← Load historical CSV files
        ↓
Process bar by bar      ← Simulate live processing
        ↓
ExhaustionStrategy      ← Detect signals
        ↓
Simulate exits          ← 10 SL / 4 trigger / 3 trail / 5 bars
        ↓
Apply costs             ← 1.8 pips (NZDJPY), 2.0 pips (GBPUSD)
        ↓
Output CSV              → state/paper_trades_nzdjpy.csv
```

### Results (Already Completed)
- **NZDJPY**: 156 trades, 2.40 pips/trade, 64.1% WR
- **GBPUSD**: 425 trades, 0.95 pips/trade, 45.4% WR

### Usage
```bash
# Already ran these:
python deploy_exhaustion_paper.py --symbol NZDJPY
python deploy_exhaustion_paper.py --symbol GBPUSD
```

### Purpose
- ✅ Validate strategy logic on past data
- ✅ Test exit parameters (SL/trailing/max hold)
- ✅ Estimate transaction costs
- ✅ Prove edge exists historically

### Limitations
- ❌ Uses OLD data (Oct 2025 - Feb 2026)
- ❌ No real-time market conditions
- ❌ No connection issues/latency
- ❌ Perfect fills (no slippage variance)

---

## Live Paper Trading (Real-Time FIX)

**File**: [deploy_exhaustion_live_paper.py](deploy_exhaustion_live_paper.py) ← **NEW!**

### How It Works
```
Pepperstone FIX API     ← REAL-TIME tick stream
        ↓
Price Server :5211      ← Bid/ask quotes (live market)
        ↓
TickAggregator          ← Build H1 bars from ticks
        ↓
ExhaustionStrategy      ← Detect signals on new bars
        ↓
Risk Management         ← Check limits BEFORE trading
        ↓
Paper Mode: Log only    ← Simulate fill, write to database
Live Mode: Send FIX     ← Real NewOrderSingle via FIX
        ↓
Database Logging        → state/live_trades.db
```

### Results (Not Yet Run)
- **Status**: Ready to deploy NOW
- **Expected**: Similar to historical (NZDJPY ~2.40 pips/trade)
- **Duration**: Run continuously (days/weeks)

### Usage
```bash
# DEPLOY THIS NOW:
./start_live_paper_trading.sh

# Or manually:
python deploy_exhaustion_live_paper.py --mode paper --symbols NZDJPY
```

### Purpose
- ✅ Test real-time execution infrastructure
- ✅ Validate FIX connection stability
- ✅ See CURRENT market conditions
- ✅ Monitor for regime changes
- ✅ Prepare for live trading

### Advantages
- ✅ REAL market data (not historical)
- ✅ Tests full infrastructure stack
- ✅ Detects connection/latency issues
- ✅ True market hours (weekends closed)
- ✅ Can switch to live mode when validated

---

## Side-by-Side Comparison

| Feature | Historical Paper | Live Paper |
|---------|-----------------|------------|
| **Data Source** | CSV files (old) | FIX API (real-time) |
| **Connection** | None (offline) | Pepperstone FIX |
| **Processing** | All bars at once | One bar per hour |
| **Signals** | 156 (NZDJPY) in minutes | ~1-2 per week (wait) |
| **Fills** | Instant (simulated) | Simulated with slippage |
| **Market Hours** | N/A (always on) | Respects open/close |
| **Latency** | Zero | Real network latency |
| **Database** | CSV files | SQLite (audit trail) |
| **Risk Management** | Post-hoc analysis | Live enforcement |
| **Duration** | Seconds to run | Days/weeks continuous |
| **Purpose** | Validate strategy | Validate infrastructure |
| **Next Step** | → Live paper | → Micro live |

---

## Which One Should You Use?

### Historical Paper Trading ✅
**Already done!** You ran this and got results:
- NZDJPY: 2.40 pips/trade (below expected)
- GBPUSD: 0.95 pips/trade (marginal)

**Use when**:
- Fast testing of parameter changes
- Comparing different exit strategies
- Running 1000s of trades quickly
- Analyzing past market regimes

### Live Paper Trading 🆕
**Deploy NOW!** This connects to your Pepperstone account:

**Use when**:
- Ready to test REAL market conditions
- Want to validate infrastructure
- Preparing for actual live trading
- Need confidence system works 24/7

---

## Deployment Sequence (What to Do Now)

### Step 1: Historical Validation ✅ DONE
```bash
# Already completed Feb 26
python deploy_exhaustion_paper.py --symbol NZDJPY  # 156 trades, 2.40 pips
python deploy_exhaustion_paper.py --symbol GBPUSD  # 425 trades, 0.95 pips
```

**Decision**: 
- NZDJPY shows positive edge (2.40 pips) but below backtest
- GBPUSD marginal (0.95 pips) - needs optimization

### Step 2: Live Paper Trading ← **YOU ARE HERE**
```bash
# Deploy NOW for real-time validation
./start_live_paper_trading.sh

# Choose:
# - Mode: Paper (recommended)
# - Symbols: NZDJPY only (recommended)
# - Let run for 1-2 weeks
```

**Expected**:
- ~1-2 signals per week (NZDJPY)
- Similar performance to historical (2.40 pips/trade)
- May differ due to current market regime

### Step 3: Analysis (After 1-2 Weeks)
```sql
-- Query live trades
sqlite3 state/live_trades.db
SELECT COUNT(*), AVG(pnl), AVG(CASE WHEN pnl>0 THEN 1 ELSE 0 END) 
FROM orders WHERE status='FILLED';
```

**Decision Criteria**:
- ✅ If avg PnL ≥2.0 pips → Proceed to micro live
- ⚠️ If avg PnL 1.0-2.0 pips → Continue monitoring
- ❌ If avg PnL <1.0 pips → Investigate discrepancy

### Step 4: Micro Live (After Validation)
```bash
# ONLY if Step 3 validates!
python deploy_exhaustion_live_paper.py --mode live --capital 10000 --symbols NZDJPY
```

**Risk**: $100/trade (1% of $10k)

### Step 5: Full Live (After Micro Validation)
```bash
# ONLY after 30+ successful micro trades
python deploy_exhaustion_live_paper.py --mode live --capital 100000 --symbols NZDJPY
```

**Risk**: $1,000/trade (1% of $100k)

---

## Key Differences to Remember

### Historical = Fast Testing
- Run in **minutes**
- Process **months of data**
- Get **100s of trades**
- Perfect for **optimization**

### Live = Real World
- Run for **weeks**
- Get **1-2 trades/week**
- Real **market conditions**
- Test **infrastructure**

---

## Your Next Command

Based on historical results showing NZDJPY has 2.40 pips/trade edge:

```bash
# Set up .env with FIX password
cp .env.example .env
nano .env  # Add your FIX_PASSWORD

# Test connection
python test_fix_logon.py

# Deploy live paper trading
./start_live_paper_trading.sh
# Choose: Paper mode, NZDJPY only
```

Then **monitor logs** and **wait for signals** (expect ~1-2 per week).

---

## Summary

You've completed **Phase 1** (historical validation) and are ready for **Phase 2** (live validation):

| Phase | Type | Status | Action |
|-------|------|--------|--------|
| 1 | Historical Paper | ✅ DONE | Review results ([PAPER_TRADING_RESULTS.md](PAPER_TRADING_RESULTS.md)) |
| 2 | Live Paper | ⏳ READY | **Deploy NOW** (this file explains how) |
| 3 | Micro Live | 🔒 LOCKED | Wait for Phase 2 validation |
| 4 | Full Live | 🔒 LOCKED | Wait for Phase 3 validation |

**Your next step**: Deploy live paper trading to validate the system works on real-time market data!

---

*Created: February 26, 2026*  
*Comparing historical backtest vs live deployment approaches*
