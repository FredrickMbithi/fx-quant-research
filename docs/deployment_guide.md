# Deployment Guide

**Production FX Trading with Pepperstone cTrader FIX API**

---

## 🚀 Quick Start

### Prerequisites

```bash
# Install dependencies
pip install -r requirements.txt

# Install additional packages for production
pip install python-dotenv
```

### Setup Credentials

Create `.env` file in project root:

```bash
FIX_PASSWORD=your_fix_password_here
FIX_USERNAME=5227001
```

**Note**: Your FIX password is different from your web login password. See [FIX Setup](fix_setup.md) for instructions on obtaining it.

### Test in Simulation Mode

```bash
python deploy_momentum_production.py --mode simulation
```

This will:

- Generate random walk M5 bars for testing
- Test strategy signal generation
- Verify risk checks and exit logic
- Log all trades to `state/trades.db`
- No real market connection required

### Run Live Trading (Demo Account)

```bash
python deploy_momentum_production.py --mode live
```

This will:

- Connect to Pepperstone FIX API (SSL)
- Subscribe to GBPUSD tick stream
- Aggregate ticks → M5 bars in real-time
- Send real market orders
- Handle ExecutionReports
- Auto-reconnect if connection drops

---

## 📊 System Modes

The deployment script supports **two modes** via command-line flag:

### 1. Simulation Mode (`--mode simulation`)

**Purpose**: Infrastructure testing without market risk

- Random walk price feed generates realistic M5 bars
- Simulated fills with realistic latency (~100-300ms)
- No FIX connection required
- Tests full pipeline: signals → orders → fills → exits → database
- Safe for validating strategy logic and exit management

**Use cases:**

- Verify deployment script works
- Test database logging
- Validate exit logic (trailing stops)
- Check risk limits (position size, daily loss)

### 2. Live Mode (`--mode live`)

**Purpose**: Real trading with Pepperstone cTrader

- Real FIX tick stream from Pepperstone
- Real market orders with ExecutionReport handling
- Position reconciliation on startup
- Auto-reconnection with exponential backoff
- Full latency tracking (signal → fill)

**Use cases:**

- Production demo trading
- Live paper trading validation
- Real market testing

---

## 🔧 System Architecture

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

### Connection Flow (Live Mode)

1. Load credentials from `.env`
2. Connect to QUOTE session (SSL port 5211)
3. Connect to TRADE session (SSL port 5212)
4. Send Logon (MsgType=A) to both sessions
5. Request position reconciliation on startup
6. Subscribe to GBPUSD market data (MsgType=V)
7. Receive ticks (MsgType=W, X)
8. Aggregate ticks → M5 bars
9. Strategy detects exhaustion signals
10. Send market orders (MsgType=D)
11. Receive ExecutionReports (MsgType=8)
12. Monitor positions with trailing stops

---

## 🛡️ Safety Controls

| Control            | Value                  | Purpose                     |
| ------------------ | ---------------------- | --------------------------- |
| Max positions      | 1                      | Prevent over-exposure       |
| Position size      | 10,000 units (0.1 lot) | Fixed risk per trade        |
| Daily loss limit   | $500                   | Stop trading on bad day     |
| Max drawdown       | $2,000                 | Circuit breaker             |
| Trades/day         | 10                     | Prevent runaway trading     |
| Quote staleness    | 5 seconds              | Reject old prices           |
| Reconnect attempts | 10                     | Auto-recovery (exp backoff) |

---

## 📈 Exit Logic

The system uses dynamic trailing stops:

```
Entry (Market Order)
  ↓
Monitor position every tick (live) or 10 seconds (simulation)
  ↓
┌─────────────────────────────────────┐
│ Hard Stop (-10 pips)        → EXIT  │
│ Profit ≥ 4 pips             → ACTIVATE TRAILING  │
│ Trailing stop (3 pips)      → EXIT  │
│ Max hold time (25 minutes)  → EXIT  │
└─────────────────────────────────────┘
```

**Example:**

- Entry: 1.2700 LONG
- Hard stop: 1.2690 (-10 pips)
- Price moves to 1.2704 (+4 pips) → trailing activates
- Trailing stop: 1.2701 (3 pips behind current price)
- Price moves to 1.2708 → trailing stop moves to 1.2705
- Price reverses to 1.2705 → EXIT with +5 pips profit

---

## 🗄️ Database Logging

All trades are logged to `state/trades.db` (SQLite) with full audit trail:

### Tables

**`trades`** - Complete trade lifecycle:

- Trade ID, session ID, timestamp
- Entry/exit prices, P&L
- Hold time, position size
- MAE/MFE (Maximum Adverse/Favorable Excursion)
- Signal → fill latency (milliseconds)

**`sessions`** - Trading sessions:

- Session ID, start/end times
- Git commit hash
- Mode (simulation/live)
- Total trades, total P&L

**`events`** - System events:

- Connection events (logon, reconnect, disconnect)
- Errors and warnings
- Position reconciliation

### Query Examples

```sql
-- Get all trades from latest session
SELECT * FROM trades
WHERE session_id = (SELECT session_id FROM sessions ORDER BY start_time DESC LIMIT 1);

-- Calculate win rate
SELECT
  COUNT(CASE WHEN realized_pnl > 0 THEN 1 END) * 100.0 / COUNT(*) as win_rate_pct,
  AVG(realized_pnl) as avg_pnl,
  AVG(latency_ms) as avg_latency_ms
FROM trades;

-- Find trades with high MAE (near stop)
SELECT * FROM trades WHERE mae_pips > -8 ORDER BY mae_pips DESC LIMIT 10;
```

---

## 📋 Command Reference

### Basic Commands

```bash
# Simulation mode (safe testing)
python deploy_momentum_production.py --mode simulation

# Live mode (real market)
python deploy_momentum_production.py --mode live

# View database
sqlite3 state/trades.db
> SELECT * FROM trades ORDER BY entry_time DESC LIMIT 10;
> .quit
```

### Environment Variables

Create `.env` file:

```bash
# Required
FIX_PASSWORD=your_password_here
FIX_USERNAME=5227001

# Optional (defaults shown)
FIX_SENDER_COMP_ID=demo.pepperstone.5227001
FIX_TARGET_COMP_ID=cServer
FIX_PRICE_HOST=demo-us-eqx-01.p.c-trader.com
FIX_PRICE_PORT=5211
FIX_TRADE_HOST=demo-us-eqx-01.p.c-trader.com
FIX_TRADE_PORT=5212
```

---

## 🔍 Monitoring

### Live Status Updates

The system prints status every 5 minutes:

```
💓 ALIVE 🟢 - Runtime: 175.0 min | Bars: 35 | Signals: 2 | Orders: 2 | Fills: 2 | Position: FLAT | P&L: $12.34
```

**Indicators:**

- 🟢 Green = FIX connected and healthy
- 🔴 Red = FIX disconnected (attempting reconnection)

### Log Files

Deployment logs are written to `logs/deploy_YYYYMMDD_HHMMSS.log`

### Database Queries

```bash
# Open database
sqlite3 state/trades.db

# Check latest session stats
SELECT * FROM sessions ORDER BY start_time DESC LIMIT 1;

# Recent trades
SELECT entry_time, side, entry_price, exit_price, realized_pnl
FROM trades
ORDER BY entry_time DESC
LIMIT 10;

# Connection events
SELECT timestamp, event_type, details
FROM events
WHERE event_type = 'CONNECTION'
ORDER BY timestamp DESC
LIMIT 20;
```

---

## ⚠️ Troubleshooting

### Connection Issues

**Problem**: `Failed to connect to price/trade server`

**Solutions:**

1. Check credentials in `.env` file
2. Verify Pepperstone demo account is active
3. Check firewall allows SSL connections on ports 5211/5212
4. Try alternate server: `demo-us-eqx-02.p.c-trader.com`

**Problem**: `Connection reset by peer` or `Broken pipe`

**Solution**: Auto-reconnection is implemented. System will:

1. Detect connection loss within 10 seconds
2. Attempt reconnection with exponential backoff
3. Resubscribe to market data on success
4. Continue trading

### No Signals Generated

**Problem**: Running for hours with no signals

**Cause**: Strategy is highly selective (2-3% signal rate)

**Expected behavior:**

- M5 timeframe: ~8,640 bars/month
- Expected signals: ~240/month (~8/day)
- May go hours without signals during quiet markets

**Validation**: Check `Bars: X` in status updates is incrementing

### Database Locked

**Problem**: `OperationalError: database is locked`

**Solution:**

1. Close any SQLite browser connections to `state/trades.db`
2. Only one process should write to database
3. Stop duplicate deployment scripts

---

## 🎯 Strategy: Exhaustion Momentum

The deployed strategy trades **with** exhaustion bars (momentum continuation):

- **LONG**: Bullish exhaustion (upward momentum)
- **SHORT**: Bearish exhaustion (downward momentum)

**Entry criteria:**

- High buying/selling pressure (2+ consecutive bars same direction)
- Range expansion (current range > 80th percentile of 10-bar lookback)
- Bar closes in entry zone (upper 35% for long, lower 35% for short)
- Optional: Momentum confirmation (close > open for long)

**Exit criteria:**

- Hard stop: -10 pips
- Profit trigger: +4 pips → activate trailing
- Trailing stop: 3 pips
- Max hold: 25 minutes

---

## 📚 Additional Resources

- **FIX Setup**: [fix_setup.md](fix_setup.md) - How to obtain FIX password
- **Backtesting**: [backtesting.md](backtesting.md) - Run historical backtests
- **Implementation Status**: [implementation_status.md](implementation_status.md) - Feature completion tracking

---

## 📞 Support

For issues or questions:

1. Check logs in `logs/deploy_*.log`
2. Query database for trade history
3. Review archived documentation in `archive/docs/` for legacy context

---

_Last updated: February 25, 2026_
