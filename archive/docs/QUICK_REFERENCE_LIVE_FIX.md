# QUICK REFERENCE - Live FIX Trading

## 🚀 Commands

```bash
# Simulation (testing)
python deploy_momentum_production.py --mode simulation

# Live trading (demo)
python deploy_momentum_production.py --mode live

# Install dependencies
pip install python-dotenv
```

## 📋 Setup Checklist

1. Create `.env` file:

   ```bash
   cp .env.example .env
   nano .env  # Add FIX_PASSWORD
   ```

2. Test in simulation:

   ```bash
   python deploy_momentum_production.py --mode simulation
   ```

3. Go live:
   ```bash
   python deploy_momentum_production.py --mode live
   ```

## 🔑 Environment Variables (.env)

```bash
FIX_PASSWORD=your_password_here
FIX_USERNAME=5227001
```

## 📊 File Structure

```
fx-quant-research/
├── deploy_momentum_production.py    # Main deployment script
├── .env                             # Your credentials (DO NOT COMMIT)
├── .env.example                     # Template
├── state/trades.db                  # SQLite database (auto-created)
└── logs/deploy_*.log                # Logs (auto-created)
```

## 🔧 Architecture

```
┌─────────────────────────────────────────────────────────┐
│                 PEPPERSTONE cTRADER FIX API             │
│  ┌──────────────┐              ┌──────────────┐        │
│  │ QUOTE Session│              │ TRADE Session│        │
│  │ Port 5211    │              │ Port 5212    │        │
│  │ (Ticks)      │              │ (Orders)     │        │
│  └──────┬───────┘              └──────┬───────┘        │
└─────────┼──────────────────────────────┼──────────────┘
          │ Bid/Ask                      │ ExecutionReports
          ▼                              ▼
┌─────────────────────────────────────────────────────────┐
│         PRODUCTION TRADING ENGINE                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │TickAggregator│→ │   Strategy   │→ │ Risk Manager │  │
│  │  (M5 Bars)   │  │ (Exhaustion) │  │  (Limits)    │  │
│  └──────────────┘  └──────────────┘  └──────┬───────┘  │
│                                              ▼          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Database   │← │Exit Manager  │← │Order Executor│  │
│  │  (trades.db) │  │ (Trailing)   │  │   (FIX)      │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
```

## 🛡️ Safety Controls

| Control            | Value     | Purpose                 |
| ------------------ | --------- | ----------------------- |
| Max positions      | 1         | Prevent over-exposure   |
| Daily loss limit   | $500      | Stop trading on bad day |
| Max drawdown       | $2,000    | Circuit breaker         |
| Trades/day         | 10        | Prevent runaway trading |
| Quote staleness    | 5 seconds | Reject old prices       |
| Reconnect attempts | 10        | Auto-recovery           |

## 📈 Exit Logic

```
Entry
  ↓
Monitor position every 10 seconds
  ↓
┌─────────────────────────────────────┐
│ Hard Stop (-10 pips)        → EXIT  │
│ Profit ≥4 pips → Enable Trailing    │
│ Trailing Stop (-3 pips)     → EXIT  │
│ Max Hold (25 minutes)       → EXIT  │
└─────────────────────────────────────┘
```

## 📊 Database Queries

```bash
# Recent trades
sqlite3 state/trades.db "SELECT * FROM trades ORDER BY entry_time DESC LIMIT 5;"

# Session summary
sqlite3 state/trades.db "SELECT * FROM sessions ORDER BY start_time DESC LIMIT 1;"

# Errors
sqlite3 state/trades.db "SELECT * FROM system_events WHERE severity='ERROR';"

# Average latency
sqlite3 state/trades.db "SELECT AVG(signal_to_fill_ms) FROM trades;"
```

## 🐛 Common Issues

### Issue: "FIX_PASSWORD not set"

**Fix:** Create `.env` file with `FIX_PASSWORD=your_password`

### Issue: "Logon rejected"

**Fix:** Check password in cTrader app (Settings → FIX API)

### Issue: "No ticks received"

**Fix:** Wait 1-2 minutes; check if market is open

### Issue: "Connection drops"

**Fix:** Check network; verify firewall allows ports 5211, 5212

## 📞 Getting Help

1. Check logs: `tail -f logs/deploy_*.log`
2. Check events: `sqlite3 state/trades.db "SELECT * FROM system_events ORDER BY timestamp DESC LIMIT 20;"`
3. Read docs: `LIVE_FIX_TRADING_GUIDE.md`

## ⚡ Key Features

✅ Real FIX tick stream (live mode)  
✅ Market order execution  
✅ Auto-reconnection  
✅ Position reconciliation  
✅ Latency tracking  
✅ Full database audit trail  
✅ Stale quote protection  
✅ Risk limit enforcement

## 🎯 Modes

| Mode         | Price Feed     | Execution   | Risk         |
| ------------ | -------------- | ----------- | ------------ |
| `simulation` | Random walk    | Simulated   | Zero         |
| `live`       | Real FIX ticks | Real orders | Demo account |

---

**Quick Start:** Copy `.env.example` → `.env`, add password, run `--mode simulation`, then `--mode live`
