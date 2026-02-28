# Live Paper Trading Deployment Guide

**Real-time FIX connection to Pepperstone for NZDJPY + GBPUSD**

## Overview

This guide shows how to deploy **LIVE paper trading** that connects to your Pepperstone account via FIX protocol for real-time H1 market data.

### Key Difference from Historical Backtest

- ❌ **Historical Paper Trading** ([deploy_exhaustion_paper.py](deploy_exhaustion_paper.py)): Runs on CSV files (completed)
- ✅ **Live Paper Trading** ([deploy_exhaustion_live_paper.py](deploy_exhaustion_live_paper.py)): Connects to Pepperstone FIX API for **real-time tick data**

---

## Prerequisites

### 1. FIX API Access

You need Pepperstone cTrader FIX API credentials:

- **Account ID**: 5227001 (demo) or your live account
- **Password**: Your FIX API password ([FIX_PASSWORD_INSTRUCTIONS.txt](FIX_PASSWORD_INSTRUCTIONS.txt))
- **Servers**: Already configured in [config/fix_sessions.cfg](config/fix_sessions.cfg)

### 2. Environment Variables

Create `.env` file in project root:

```bash
# Pepperstone FIX API Credentials
FIX_USERNAME=5227001
FIX_PASSWORD=your_fix_password_here
FIX_SENDER_COMP_ID=demo.pepperstone.5227001
FIX_TARGET_COMP_ID=cServer

# FIX Servers (Demo)
FIX_PRICE_HOST=demo-us-eqx-01.p.c-trader.com
FIX_PRICE_PORT=5211
FIX_TRADE_HOST=demo-us-eqx-01.p.c-trader.com
FIX_TRADE_PORT=5212
```

**IMPORTANT**: Replace `your_fix_password_here` with your actual FIX password from Pepperstone.

### 3. Python Dependencies

All dependencies should already be installed. If needed:

```bash
pip install python-dotenv pandas numpy scipy
```

---

## How It Works

### Architecture

```
Pepperstone FIX API
        ↓
  Price Server (Port 5211) ← Tick stream
        ↓
TickAggregator (per symbol) → Build H1 bars
        ↓
ExhaustionStrategy → Detect 2-bar pattern
        ↓
Signal Generated → Check risk limits
        ↓
Paper Mode: Log trade to database
Live Mode: Execute real order via FIX
```

### Data Flow

1. **Tick Reception**: Real-time bid/ask quotes from FIX
2. **Bar Building**: TickAggregator converts ticks → H1 bars
3. **Signal Detection**: ExhaustionStrategy processes each completed bar
4. **Risk Check**: Validate against drawdown, consecutive losses, daily limits
5. **Execution**:
   - **Paper mode**: Simulate fill with 1 pip slippage, log to database
   - **Live mode**: Send NewOrderSingle via FIX Trade connection
6. **Position Management**: Track stops, trailing, max hold time

### Exit Management

Once filled, position is tracked with:

- **Stop Loss**: 10 pips hard stop
- **Trailing Stop**: Activates at +4 pips profit, trails 3 pips behind
- **Max Hold**: 5 bars (5 hours)
- Exit triggers: Whichever comes first

---

## Usage

### Start Live Paper Trading (RECOMMENDED)

```bash
# Default: NZDJPY + GBPUSD, paper mode
python deploy_exhaustion_live_paper.py --mode paper

# Custom symbols
python deploy_exhaustion_live_paper.py --mode paper --symbols GBPUSD,EURUSD

# Custom capital
python deploy_exhaustion_live_paper.py --mode paper --capital 50000
```

### Start Live REAL Trading (After Validation!)

```bash
# ⚠️  WARNING: This sends REAL orders to broker!
python deploy_exhaustion_live_paper.py --mode live
```

---

## Risk Management

### Pre-Trade Validation

Before each signal, system checks:

1. **Drawdown**: Current DD < 10% of peak equity
2. **Consecutive Losses**:
   - NZDJPY: ≤5 losses in a row
   - GBPUSD: ≤7 losses in a row
3. **Daily Loss**: Total loss today < $5,000
4. **Daily Trade Limit**: ≤10 trades per day
5. **Position Limit**: No overlapping positions per symbol

### Auto-Halt Conditions

Trading automatically halts if:

- Drawdown ≥10%
- Consecutive losses reached threshold
- Daily loss limit hit
- Connection to FIX lost for >90 seconds

### Position Limits

- **Max position size**: 10,000 units (1 mini lot)
- **Max concurrent positions**: 1 per symbol
- **Risk per trade**: 1% of capital

---

## Monitoring

### Real-Time Logs

Monitor live activity:

```bash
tail -f logs/live_exhaustion_*.log
```

### Database Inspection

All trades logged to SQLite:

```bash
sqlite3 state/live_trades.db
```

```sql
-- View all sessions
SELECT * FROM sessions ORDER BY created_at DESC;

-- View signals
SELECT * FROM signals ORDER BY timestamp DESC LIMIT 10;

-- View orders
SELECT * FROM orders ORDER BY timestamp DESC LIMIT 10;

-- View market data
SELECT * FROM market_data ORDER BY timestamp DESC LIMIT 20;
```

### Status Updates

Engine prints status every 5 minutes:

- Uptime
- Current equity
- Daily PnL
- Bars processed per symbol
- Signals generated
- Open positions

### Ctrl+C to Stop

Press `Ctrl+C` to gracefully shutdown:

1. Stops accepting new signals
2. (Live mode) Closes open positions
3. Disconnects from FIX
4. Prints final summary
5. Saves database

---

## Configuration Files

### Per-Symbol Configs

The engine loads exit parameters from your paper trading configs:

- [config/paper_exhaustion_nzdjpy.json](config/paper_exhaustion_nzdjpy.json)
- [config/paper_exhaustion_gbpusd.json](config/paper_exhaustion_gbpusd.json)

These contain:

- Strategy parameters (pressure threshold, range expansion, percentiles)
- Exit parameters (stop loss, trailing, max hold)
- Monitoring thresholds (halt conditions, review checkpoints)

### FIX Session Config

Low-level FIX protocol settings:

- [config/fix_sessions.cfg](config/fix_sessions.cfg)

Used by QuickFIX library (if installed). Our implementation uses custom FIX client.

---

## Troubleshooting

### Connection Issues

**Problem**: `Failed to connect to price server`

```
Solution:
1. Check .env file has FIX_PASSWORD set
2. Verify servers are correct (demo vs live)
3. Test FIX login:
   python test_fix_logon.py
4. Check firewall allows ports 5211, 5212
```

**Problem**: `SSL handshake failed`

```
Solution:
1. Update Python SSL: pip install --upgrade certifi
2. Try non-SSL ports (5201, 5202) if demo
3. Contact Pepperstone support for FIX access
```

**Problem**: `No market data received`

```
Solution:
1. Check Logon was successful (look for "✓ Price connection established")
2. Verify symbols are correct (NZDJPY, GBPUSD - no slashes)
3. Wait 1-2 minutes for initial quotes
4. Check weekend/holiday (market closed)
```

### Signal Issues

**Problem**: `No signals generated after hours`

```
Possible causes:
1. No exhaustion pattern present (requires strong pressure + range expansion)
2. Insufficient bars (need 50+ bars for indicators)
3. Risk limits blocking signals (check consecutive losses)
4. Market conditions don't match pattern
```

**Problem**: `Signal blocked: Max drawdown hit`

```
Solution:
1. Stop trading immediately
2. Analyze why drawdown occurred
3. Review trade log in database
4. Adjust parameters if edge deteriorated
5. Reset peak equity manually (only if intentional capital withdrawal)
```

### Performance Issues

**Problem**: `High CPU usage during tick bursts`

```
Solution:
1. TickAggregator processes ticks efficiently
2. High tick rate normal during news/volatility
3. H1 bars only generate once per hour
4. No action needed unless sustained >80% CPU
```

**Problem**: `Database locked errors`

```
Solution:
1. Don't run multiple instances on same DB
2. Check file permissions on state/live_trades.db
3. Use separate databases for concurrent testing:
   python deploy_exhaustion_live_paper.py --db-path state/test_trades.db
```

---

## Testing Before Live

### Phase 1: Paper Trading (1-2 weeks)

```bash
# Run in paper mode, monitor results
python deploy_exhaustion_live_paper.py --mode paper

# Compare to historical backtest expectations:
# NZDJPY: Should generate ~2-4 signals per month, avg 2.40 pips/trade
# GBPUSD: Should generate ~20-30 signals per month, avg 0.95 pips/trade
```

**Success Criteria**:

- ✅ No connection drops
- ✅ Signals match expected frequency
- ✅ Exit logic works (SL, trailing, max hold)
- ✅ Risk limits enforce correctly
- ✅ Database logging complete

### Phase 2: Micro Live (1 mini lot)

```bash
# After paper validation, test with real money
python deploy_exhaustion_live_paper.py --mode live --capital 10000

# Risk: $100 per trade (1% of $10k), max loss $1k
```

**Success Criteria**:

- ✅ Orders execute reliably
- ✅ Fills match expected prices (within 1-2 pips)
- ✅ Performance matches paper trading
- ✅ No system errors/crashes

### Phase 3: Full Live (Standard lot)

```bash
# After micro live validation
python deploy_exhaustion_live_paper.py --mode live --capital 100000

# Risk: $1,000 per trade (1% of $100k), max loss $10k
```

---

## Performance Expectations

Based on historical paper trading (Feb 26, 2026 results):

### NZDJPY

- **Signals**: ~156 over 3-4 months → ~1-2 per week
- **Win Rate**: 64.1%
- **Avg PnL**: 2.40 pips/trade (after 1.8 pips costs)
- **Max DD**: ~78 pips
- **Status**: ⚠️ Below backtest (expected 4.25 pips) - monitor closely

### GBPUSD

- **Signals**: ~425 over 10 years → ~3-4 per month
- **Win Rate**: 45.4%
- **Avg PnL**: 0.95 pips/trade (after 2.0 pips costs)
- **Max DD**: ~233 pips
- **Status**: ⚠️ Marginal - needs exit optimization before live

**Recommendation**: Start with NZDJPY only until GBPUSD optimized.

```bash
# NZDJPY only
python deploy_exhaustion_live_paper.py --mode paper --symbols NZDJPY
```

---

## Next Steps

1. **Set up .env file** with FIX credentials
2. **Test connection**:
   ```bash
   python test_fix_logon.py
   ```
3. **Start paper trading**:
   ```bash
   python deploy_exhaustion_live_paper.py --mode paper
   ```
4. **Monitor for 1-2 weeks**:
   - Check logs daily
   - Review database weekly
   - Compare to backtest expectations
5. **Validate results**:
   - NZDJPY avg PnL ≥2.0 pips? → Proceed to micro live
   - GBPUSD avg PnL ≥1.5 pips? → Proceed to micro live
   - Otherwise → Investigate discrepancy
6. **Scale up**:
   - Micro live (1 mini lot) for 30 trades
   - Full live (standard lot) if validated

---

## Files

### Deployment Scripts

- [deploy_exhaustion_live_paper.py](deploy_exhaustion_live_paper.py) - **THIS FILE** (live FIX paper trading)
- [deploy_exhaustion_paper.py](deploy_exhaustion_paper.py) - Historical backtest paper trading
- [deploy_momentum_production.py](deploy_momentum_production.py) - Different strategy (M5 momentum)

### Configuration

- [config/paper_exhaustion_nzdjpy.json](config/paper_exhaustion_nzdjpy.json) - NZDJPY parameters
- [config/paper_exhaustion_gbpusd.json](config/paper_exhaustion_gbpusd.json) - GBPUSD parameters
- [config/fix_sessions.cfg](config/fix_sessions.cfg) - FIX protocol settings

### Strategy

- [src/strategies/exhaustion_strategy.py](src/strategies/exhaustion_strategy.py) - 2-bar exhaustion pattern

### Infrastructure

- [src/execution/fix_client_v2.py](src/execution/fix_client_v2.py) - FIX 4.4 client for Pepperstone
- [src/utils/tick_aggregator.py](src/utils/tick_aggregator.py) - Tick → H1 bar conversion
- [src/utils/trade_database.py](src/utils/trade_database.py) - SQLite trade logging

### Output

- `state/live_trades.db` - SQLite database (created on first run)
- `logs/live_exhaustion_*.log` - Timestamped log files

---

## Support

**FIX Connection Issues**: See [FIX_PASSWORD_INSTRUCTIONS.txt](FIX_PASSWORD_INSTRUCTIONS.txt)  
**Strategy Details**: See [PAPER_TRADING_RESULTS.md](PAPER_TRADING_RESULTS.md)  
**Risk Management**: See [H1_MULTIPAIR_QUICKSTART.md](H1_MULTIPAIR_QUICKSTART.md)

---

_Last Updated: February 26, 2026_  
_Live Paper Trading - Real-time FIX deployment_
