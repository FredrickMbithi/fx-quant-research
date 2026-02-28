# Live Paper Trading - Quick Start Checklist

## 🎯 Goal

Deploy **real-time paper trading** for exhaustion+failure pattern on your Pepperstone account via FIX API.

---

## ✅ Pre-Flight Checklist

### 1. FIX Credentials Setup

- [ ] Have Pepperstone cTrader FIX API password
- [ ] Create `.env` file from template:
  ```bash
  cp .env.example .env
  ```
- [ ] Edit `.env` and set `FIX_PASSWORD=your_actual_password`
- [ ] Verify credentials:
  ```bash
  grep FIX_PASSWORD .env  # Should NOT show 'your_fix_password_here'
  ```

### 2. Test FIX Connection

- [ ] Run connection test:
  ```bash
  python test_fix_logon.py
  ```
- [ ] Should see:
  ```
  ✓ Price connection established (SSL)
  ✓ Trade connection established (SSL)
  ✓ Logon successful
  ```
- [ ] If fails, see troubleshooting in [LIVE_PAPER_TRADING_GUIDE.md](LIVE_PAPER_TRADING_GUIDE.md)

### 3. Review Configuration

- [ ] Check NZDJPY config: [config/paper_exhaustion_nzdjpy.json](config/paper_exhaustion_nzdjpy.json)
  - Exit: 10 pip SL, 4 pip trigger, 3 pip trail, 5 bar max hold
  - Halt: 5 consecutive losses
- [ ] Check GBPUSD config: [config/paper_exhaustion_gbpusd.json](config/paper_exhaustion_gbpusd.json)
  - Exit: Same as NZDJPY
  - Halt: 7 consecutive losses (more lenient for marginal performance)
- [ ] Review risk limits in [deploy_exhaustion_live_paper.py](deploy_exhaustion_live_paper.py#L137-L146):
  - Max drawdown: 10%
  - Max daily loss: $5,000
  - Max trades/day: 10

### 4. Understand What Will Happen

- [ ] Read system architecture in [LIVE_PAPER_TRADING_GUIDE.md](LIVE_PAPER_TRADING_GUIDE.md#how-it-works)
- [ ] Understand paper mode vs live mode:
  - **Paper**: Logs trades to database, NO real orders sent
  - **Live**: Sends real NewOrderSingle messages via FIX
- [ ] Know expected performance (from historical backtest):
  - NZDJPY: ~1-2 signals/week, avg 2.40 pips/trade, 64% WR
  - GBPUSD: ~3-4 signals/month, avg 0.95 pips/trade, 45% WR

---

## 🚀 Deployment Options

### Option A: Automated Script (EASIEST)

```bash
./start_live_paper_trading.sh
```

Interactive prompts guide you through:

1. Verify .env setup
2. Choose mode (paper/live)
3. Choose symbols (NZDJPY/GBPUSD/both)
4. Launch trader

### Option B: Manual Command

```bash
# NZDJPY only, paper mode (RECOMMENDED)
python deploy_exhaustion_live_paper.py --mode paper --symbols NZDJPY

# Both pairs, paper mode
python deploy_exhaustion_live_paper.py --mode paper --symbols NZDJPY,GBPUSD

# LIVE mode (⚠️ real orders!)
python deploy_exhaustion_live_paper.py --mode live --symbols NZDJPY
```

---

## 📊 Monitoring

### Real-Time Logs

```bash
# Follow live log
tail -f logs/live_exhaustion_*.log

# Search for signals
grep "SIGNAL:" logs/live_exhaustion_*.log

# Search for fills
grep "FILL:" logs/live_exhaustion_*.log
```

### Database Queries

```bash
sqlite3 state/live_trades.db
```

```sql
-- Latest signals
SELECT * FROM signals ORDER BY timestamp DESC LIMIT 10;

-- Latest orders
SELECT * FROM orders ORDER BY timestamp DESC LIMIT 10;

-- Session summary
SELECT * FROM sessions ORDER BY created_at DESC LIMIT 5;
```

### What You'll See

```
======================================================================
CONNECTING TO PEPPERSTONE FIX API
======================================================================
📡 Connecting to price server...
✅ Price connection established (SSL)
📡 Connecting to trade server...
✅ Trade connection established (SSL)
📊 Requesting position reconciliation...
📈 Subscribing to market data: NZDJPY, GBPUSD
✅ Market data subscription successful (MDReqID: ...)
✅ Connected to Pepperstone
======================================================================
🚀 STARTING LIVE EXHAUSTION PAPER TRADING
======================================================================
Mode: PAPER
Symbols: NZDJPY, GBPUSD
Capital: $100,000
Risk/trade: 1.0%
======================================================================
✅ Engine running. Waiting for H1 bars...
   (Press Ctrl+C to stop)

📊 [NZDJPY] H1 Bar Complete: 2026-02-26 14:00:00+00:00 | O=92.345 H=92.389 L=92.310 C=92.356
🎯 SIGNAL: NZDJPY LONG @ 92.356 | Strength: 1.00
📝 PAPER FILL: NZDJPY BUY 10000 @ 92.366
   SL: 92.266 | Profit Trigger: 92.406
```

---

## ⏱️ Timeline & Expectations

### First Hour

- [x] Connection established
- [ ] Ticks streaming (random tick updates)
- [ ] First H1 bar completes (on the hour: 00:00, 01:00, etc.)
- [ ] Strategy processes bar, may or may not generate signal

**Note**: Signals are NOT guaranteed! Pattern requires:

- Strong directional pressure (±2)
- Range expansion (>0.8× median)
- Extreme close (top/bottom 35%)
- Failure to continue next bar

### First Week

- [ ] Capture 5-10 H1 bars per day (24 bars total)
- [ ] Generate 0-2 signals (depends on market)
- [ ] Observe risk management system
- [ ] Verify database logging

### After 1-2 Weeks

- [ ] Review trades in database
- [ ] Compare to historical backtest expectations
- [ ] Calculate actual avg PnL vs expected
- [ ] Decision point:
  - ✅ If performance matches → consider micro live
  - ⚠️ If deviates significantly → investigate why
  - ❌ If major issues → halt and debug

---

## 🛑 How to Stop

### Graceful Shutdown

```bash
Press Ctrl+C
```

System will:

1. Stop accepting new signals
2. (Live mode) Close open positions
3. Disconnect from FIX
4. Print final summary
5. Save database

### Emergency Stop

```bash
# Find process
ps aux | grep deploy_exhaustion_live

# Kill it
kill -9 <PID>
```

---

## ⚠️ Common Issues

### "Failed to connect to price server"

**Fix**:

1. Check `.env` has correct `FIX_PASSWORD`
2. Verify demo servers: `demo-us-eqx-01.p.c-trader.com`
3. Try test: `python test_fix_logon.py`

### "No market data received"

**Fix**:

1. Wait 1-2 minutes for initial quotes
2. Check market hours (FX trades 24/5, closed weekends)
3. Verify symbols: `NZDJPY` (not `NZD/JPY`)

### "Signal blocked: Consecutive losses"

**Fix**:

- This is EXPECTED! Risk management working correctly
- Review trades to understand why losses occurred
- Adjust halt threshold in config if too strict
- Reset counter: Restart engine (daily auto-reset)

### "No signals for hours"

**Fix**:

- This is NORMAL! Exhaustion pattern is rare
- NZDJPY: Expect ~1-2 signals per week
- GBPUSD: Expect ~3-4 signals per month
- Pattern requires specific setup (pressure + range + reversal)
- Don't force trades - wait for valid setups

---

## 📈 Next Steps After Validation

### Phase 1 Complete: Paper Trading ✅

After 1-2 weeks of stable paper trading with good results:

- [ ] Final performance check
- [ ] Database integrity verified
- [ ] No system errors/crashes
- [ ] Results match backtest expectations

### Phase 2: Micro Live ($10k account)

```bash
python deploy_exhaustion_live_paper.py --mode live --capital 10000 --symbols NZDJPY
```

- Risk: $100/trade (1% of $10k)
- Duration: 30 trades or 1 month
- Success: Avg PnL ≥2.0 pips, no system issues

### Phase 3: Full Live ($100k account)

```bash
python deploy_exhaustion_live_paper.py --mode live --capital 100000 --symbols NZDJPY
```

- Risk: $1,000/trade (1% of $100k)
- Only if Phase 2 validated

---

## 📁 Files Reference

| File                                                                       | Purpose                                  |
| -------------------------------------------------------------------------- | ---------------------------------------- |
| [deploy_exhaustion_live_paper.py](deploy_exhaustion_live_paper.py)         | Main live trading engine                 |
| [start_live_paper_trading.sh](start_live_paper_trading.sh)                 | Automated deployment script              |
| [LIVE_PAPER_TRADING_GUIDE.md](LIVE_PAPER_TRADING_GUIDE.md)                 | Full documentation                       |
| [config/paper_exhaustion_nzdjpy.json](config/paper_exhaustion_nzdjpy.json) | NZDJPY parameters                        |
| [config/paper_exhaustion_gbpusd.json](config/paper_exhaustion_gbpusd.json) | GBPUSD parameters                        |
| [.env.example](.env.example)                                               | Template for credentials                 |
| `.env`                                                                     | Your actual credentials (DO NOT COMMIT!) |

---

## 🆘 Support

**FIX Connection**: See [FIX_PASSWORD_INSTRUCTIONS.txt](FIX_PASSWORD_INSTRUCTIONS.txt)  
**Strategy Details**: See [PAPER_TRADING_RESULTS.md](PAPER_TRADING_RESULTS.md)  
**Full Guide**: See [LIVE_PAPER_TRADING_GUIDE.md](LIVE_PAPER_TRADING_GUIDE.md)

---

## ✅ Ready to Deploy?

### Final Checklist

- [x] `.env` configured with real FIX password
- [x] `test_fix_logon.py` passes
- [x] Understand paper vs live mode
- [x] Know expected performance (NZDJPY: 2.40 pips/trade)
- [x] Know how to monitor (logs + database)
- [x] Know how to stop (Ctrl+C)

### Launch Command

```bash
# Start with easy script
./start_live_paper_trading.sh

# Or manually
python deploy_exhaustion_live_paper.py --mode paper --symbols NZDJPY
```

**Good luck!** 🚀

---

_Last Updated: February 26, 2026_  
_Live Paper Trading Deployment_
