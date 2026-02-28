# Live FIX Trading Guide

**Production-ready FX trading with Pepperstone cTrader FIX API**

---

## 📋 Overview

The system supports **two modes**:

1. **Simulation Mode** (`--mode simulation`)
   - Random walk price feed for testing infrastructure
   - Simulated fills with realistic latency
   - No FIX connection required
   - Safe for testing strategy logic and database logging

2. **Live Mode** (`--mode live`)
   - Real FIX tick stream from Pepperstone cTrader
   - Real market orders with ExecutionReport handling
   - Position reconciliation on startup
   - Auto-reconnection with exponential backoff

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Credentials

Create `.env` file in project root:

```bash
cp .env.example .env
nano .env  # Edit with your credentials
```

**Example `.env`:**

```bash
# Pepperstone cTrader FIX API Credentials
FIX_PASSWORD=your_fix_password_here
FIX_USERNAME=5227001

# Connection parameters (optional overrides)
FIX_SENDER_COMP_ID=demo.pepperstone.5227001
FIX_TARGET_COMP_ID=cServer
FIX_PRICE_HOST=demo-us-eqx-02.p.c-trader.com
FIX_PRICE_PORT=5211
FIX_TRADE_HOST=demo-us-eqx-02.p.c-trader.com
FIX_TRADE_PORT=5212
```

### 3. Run Simulation Test

```bash
python deploy_momentum_production.py --mode simulation
```

This will:

- Generate M5 bars from random walk
- Test strategy signal generation
- Log all trades to `state/trades.db`
- Verify infrastructure works

### 4. Run Live Trading (Demo)

```bash
python deploy_momentum_production.py --mode live
```

This will:

- Connect to Pepperstone FIX API
- Subscribe to GBPUSD tick stream
- Aggregate ticks → M5 bars
- Send real market orders
- Handle ExecutionReports

---

## 🔧 System Architecture

### Connection Flow (Live Mode)

```
1. Load credentials from .env
2. Connect to QUOTE session (SSL port 5211)
3. Connect to TRADE session (SSL port 5212)
4. Send Logon (MsgType=A) to both sessions
5. Request position reconciliation (MsgType=AF)
6. Subscribe to GBPUSD market data (MsgType=V)
7. Start receiving ticks (MsgType=W, X)
8. Aggregate ticks → M5 bars
9. Strategy detects signals
10. Send NewOrderSingle (MsgType=D)
11. Receive ExecutionReport (MsgType=8)
12. Monitor position with exit logic
```

### FIX Sessions

| Session | Purpose         | Host                          | Port | SenderSubID |
| ------- | --------------- | ----------------------------- | ---- | ----------- |
| QUOTE   | Market data     | demo-us-eqx-02.p.c-trader.com | 5211 | QUOTE       |
| TRADE   | Order execution | demo-us-eqx-02.p.c-trader.com | 5212 | TRADE       |

### Message Types Implemented

| MsgType | Name                   | Purpose                 | Implementation |
| ------- | ---------------------- | ----------------------- | -------------- |
| A       | Logon                  | Authenticate sessions   | ✅ Complete    |
| 0       | Heartbeat              | Keep connection alive   | ✅ Complete    |
| V       | MarketDataRequest      | Subscribe to ticks      | ✅ Complete    |
| W       | MarketDataSnapshot     | Full quote snapshot     | ✅ Complete    |
| X       | MarketDataIncremental  | Tick updates            | ✅ Complete    |
| D       | NewOrderSingle         | Place market order      | ✅ Complete    |
| 8       | ExecutionReport        | Order fills/rejects     | ✅ Complete    |
| AF      | OrderMassStatusRequest | Position reconciliation | ✅ Complete    |
| 5       | Logout                 | Disconnect gracefully   | ✅ Complete    |

---

## 🛡️ Safety Controls

### 1. Stale Quote Detection

Orders rejected if market data >5 seconds old:

```python
if self.fix_client.is_market_data_stale(max_age_seconds=5.0):
    logger.error("Order rejected: Market data is stale")
    return
```

### 2. Position Limits

```python
risk_limits = {
    'max_position_size': 10000,  # units
    'max_positions': 1,           # concurrent positions
    'max_daily_loss': 500.0,      # USD
    'max_total_drawdown': 2000.0, # USD
    'max_trades_per_day': 10      # trade count
}
```

### 3. FIX Connection Monitoring

Engine monitors connection health every 10 seconds:

- Checks `is_price_logged_in` and `is_trade_logged_in`
- If disconnected, triggers `reconnect()` with exponential backoff
- Re-subscribes to market data after reconnection
- Stops engine if max reconnection attempts exhausted

### 4. Graceful Shutdown

```bash
Ctrl+C  # Triggers shutdown
```

- Closes open positions at market price
- Sends Logout to both FIX sessions
- Saves session summary to database
- Prints final statistics

---

## 📊 Database Logging

All activity logged to `state/trades.db`:

### Tables

1. **sessions** - Trading session metadata
2. **trades** - Entry/exit with MAE/MFE/PnL
3. **system_events** - Connection, signals, errors
4. **market_data** - Bars and ticks

### Query Examples

**Show last 10 trades:**

```bash
sqlite3 state/trades.db "SELECT trade_id, direction, pnl_pips, exit_reason FROM trades WHERE exit_time IS NOT NULL ORDER BY exit_time DESC LIMIT 10;"
```

**Session performance:**

```bash
sqlite3 state/trades.db "SELECT session_id, total_trades, win_rate, total_pnl_usd FROM sessions ORDER BY start_time DESC LIMIT 5;"
```

**Average latency:**

```bash
sqlite3 state/trades.db "SELECT AVG(signal_to_fill_ms) FROM trades WHERE signal_to_fill_ms IS NOT NULL;"
```

---

## 🔍 Troubleshooting

### FIX_PASSWORD not set

**Error:**

```
ValueError: FIX_PASSWORD not set in environment
```

**Solution:**

```bash
# Create .env file
cp .env.example .env
nano .env  # Add your password
```

### Logon Rejected

**Error:**

```
✗ Logon rejected: Invalid credentials
```

**Solutions:**

1. Verify password in cTrader desktop app (Settings → FIX API)
2. Check `FIX_USERNAME` matches trader login ID
3. Ensure demo account is active
4. Confirm SSL ports (5211, 5212) not blocked

### Market Data Not Received

**Symptoms:**

- Connected but no ticks
- `is_market_data_stale()` returns True

**Solutions:**

1. Check symbol name is exactly 'GBPUSD' (case-sensitive)
2. Verify MDReqID in logs shows subscription sent
3. Check if broker rejected request (MsgType=j Business Reject)
4. Ensure demo account has market data permissions

### ExecutionReport Rejected

**Error:**

```
ExecutionReport: ExecType=8 | Status=8 | Order rejected
```

**Solutions:**

1. Check order quantity is within broker limits
2. Verify account has sufficient margin
3. Check symbol ID matches broker's FIX symbol list
4. Ensure market is open (FX trades 24/5)

### Connection Drops Frequently

**Symptoms:**

- "FIX connection lost" every few minutes
- Reconnection loops

**Solutions:**

1. Check network stability
2. Verify firewall allows SSL connections to ports 5211, 5212
3. Increase heartbeat interval (default 30s)
4. Check if host is correct (demo-us-eqx-02 vs demo-us-eqx-01)

---

## 📈 Performance Monitoring

### Real-time Stats

Engine prints heartbeat every 5 minutes:

```
💓 ALIVE - Runtime: 45.2 min | Bars: 9 | Signals: 0 | Trades: 0 | Position: FLAT | P&L: $0.00
```

### Session Summary

On shutdown:

```
======================================================================
SESSION SUMMARY
======================================================================
Session ID:      session_1772021234
Total trades:    5
Winning trades:  2
Losing trades:   3
Win rate:        40.0%
Total P&L:       $-12.50
Avg latency:     145ms
======================================================================
```

### Latency Breakdown

- **Signal time:** When strategy detects setup
- **Order sent:** When NewOrderSingle transmitted
- **Fill received:** When ExecutionReport (Filled) arrives

Latency = Fill received - Signal time (typically 50-300ms)

---

## 🔐 Security Best Practices

1. **Never commit `.env` to git**

   ```bash
   # .gitignore already includes .env
   git status  # Confirm .env not staged
   ```

2. **Use demo account first**
   - Test with `demo.pepperstone` credentials
   - Verify strategy behavior
   - Monitor for 24-48 hours

3. **Rotate passwords regularly**
   - Change FIX password monthly
   - Update `.env` file

4. **Monitor database size**

   ```bash
   du -h state/trades.db
   # Archive old sessions if >100MB
   ```

5. **Backup database**
   ```bash
   cp state/trades.db state/trades_backup_$(date +%Y%m%d).db
   ```

---

## 🎯 Strategy Configuration

### Exit Parameters (Hardcoded)

```python
exit_params = {
    'hard_stop_pips': 10.0,       # Max loss per trade
    'profit_trigger_pips': 4.0,   # Profit to activate trailing
    'trailing_distance_pips': 3.0,# Distance to trail
    'max_hold_minutes': 25,       # Time-based exit
    'pip_size': 0.0001            # GBPUSD pip value
}
```

### Risk Limits (Configurable)

```python
risk_limits = {
    'max_position_size': 10000,   # Override with --size flag
    'max_positions': 1,
    'max_daily_loss': 500.0,
    'max_total_drawdown': 2000.0,
    'max_trades_per_day': 10
}
```

---

## 📚 Related Documentation

- **PRODUCTION_DEPLOYMENT_GUIDE.md** - Infrastructure setup
- **LIVE_TRADING_README.md** - Original deployment notes
- **.env.example** - Credential template
- **src/execution/fix_client_v2.py** - FIX protocol implementation

---

## 🆘 Support

**If you encounter issues:**

1. Check logs in `logs/deploy_YYYYMMDD_HHMMSS.log`
2. Query `system_events` table for error details:
   ```bash
   sqlite3 state/trades.db "SELECT * FROM system_events WHERE severity='ERROR' ORDER BY timestamp DESC LIMIT 20;"
   ```
3. Test in simulation mode first
4. Verify credentials in cTrader desktop app

**Common issues are usually:**

- Incorrect password (check `.env`)
- Wrong symbol ID (broker-specific)
- Network/firewall blocking SSL ports
- Demo account expired/inactive

---

**Last updated:** 2026-02-25  
**FIX Protocol Version:** 4.4  
**Broker:** Pepperstone cTrader (Demo)
