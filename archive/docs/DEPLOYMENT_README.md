# Live Deployment Guide - Exhaustion Momentum Strategy

## ⚠️ Important Notice

**This strategy has NEGATIVE returns (-1.78% over 3 years in backtest)**

This deployment is for:

- Testing live trading infrastructure
- Validating FIX connectivity
- Learning event-driven execution
- **NOT for profitable trading**

## ⏰ CONTINUOUS 24/7 TRADING

**This bot runs CONTINUOUSLY and trades AUTOMATICALLY:**

- Monitors GBPUSD H1 bars every hour, 24/7
- Executes trades automatically when signals appear
- Manages exits via trailing stops
- **You must keep the terminal window open**
- **Runs until you press Ctrl+C**
- Prints heartbeat status every 5 minutes

---

## Quick Start

### 1. Prerequisites

```bash
# Ensure you have your Pepperstone demo account credentials:
- Account: 5227001
- Password: [Your cTrader password]
- FIX API access enabled
```

### 2. Run Deployment (CONTINUOUS)

```bash
python deploy_momentum_live.py
```

**Important:** This starts a continuous trading loop that runs 24/7.

### 3. Enter Credentials

When prompted:

- **FIX Password**: Use your cTrader login password (account 5227001)
- **Position Size**: Default is 10,000 units (0.1 lot)
  - This equals ~$1 per pip at GBPUSD 1.27
  - Risk per trade: ~$10 (10 pip hard stop)

### 4. Confirm Deployment

Type `YES` to start **CONTINUOUS** live trading.

### 5. Monitor Continuously

The bot will display:

- `💓 ALIVE` - Heartbeat every 5 minutes with stats
- `🕐 New H1 bar` - When each hourly bar completes
- `📊 SIGNAL` - When entry signal detected
- `📤 PLACING ORDER` - When order is sent
- `✅ FILL` - When order is executed
- `📍 Position opened` - Position tracking

### 6. Stop Trading

Press `Ctrl+C` to gracefully shutdown:

- Closes any open positions
- Disconnects from FIX
- Displays session statistics

---

## Strategy Overview

### Entry Logic (MOMENTUM - trades WITH exhaustion)

**LONG Entry:**

1. Bullish exhaustion detected (2 consecutive bullish bars, range expansion, close ≥ 65th percentile)
2. Confirmation: Next bar is bullish (close > open) AND doesn't break previous low
3. Enter LONG at market

**SHORT Entry:**

1. Bearish exhaustion detected (2 consecutive bearish bars, range expansion, close ≤ 35th percentile)
2. Confirmation: Next bar is bearish (close < open) AND doesn't break previous high
3. Enter SHORT at market

### Exit Logic

- **Hard Stop**: 10 pips from entry
- **Profit Trigger**: At +4 pips, activate trailing stop
- **Trailing Stop**: 3 pips from highest favorable price
- **Max Hold**: 5 bars (5 hours)

### Risk Management

**Per-Trade Limits:**

- Position size: 10,000 units (0.1 lot) default
- Max risk: $10 per trade (10 pip stop)

**Daily Limits:**

- Max daily loss: $500
- Max trades per day: 10
- Trading stops if either limit hit

**Total Limits:**

- Max total drawdown: $2,000
- Trading stops if hit

---

## Expected Performance

Based on 3-year backtest (2023-2026):

| Metric           | Value                                |
| ---------------- | ------------------------------------ |
| Total Return     | -1.78%                               |
| Sharpe Ratio     | -0.22                                |
| Max Drawdown     | 5.31%                                |
| Win Rate         | ~53% (estimated)                     |
| Avg Trade        | Negative                             |
| Signal Frequency | 10.26% (1,726 signals / 16,820 bars) |

**Interpretation:**

- Strategy loses money slowly over time
- Slightly more wins than losses, but losers are larger
- Low volatility (2.91% annualized)

---

## Monitoring

### While Running

The script will display:

```
STARTING LIVE TRADING - EXHAUSTION MOMENTUM STRATEGY
======================================================================
Strategy:   Momentum (trade WITH exhaustion)
Instrument: GBPUSD
Timeframe:  H1
Position size: 10,000 units (0.10 lots)
Broker:     Pepperstone cTrader Demo (5227001)
======================================================================

🚀 TRADING LIVE - Strategy is active
   Press Ctrl+C to stop
```

### Log Messages

- `📊 SIGNAL: LONG GBPUSD (strength: 1.00)` - Signal generated
- `📤 PLACING ORDER: BUY 10000 GBPUSD @ MARKET` - Order submitted
- `✅ FILL: BUY 10000 GBPUSD @ 1.27050` - Order filled
- `📍 Position opened: LONG 10000 units @ 1.27050` - Position tracking
- `⚠️  Signal rejected: Daily loss limit hit` - Risk limit enforcement

### Stop Trading

Press `Ctrl+C` to gracefully shutdown:

- Closes any open positions
- Disconnects from FIX
- Displays session statistics

---

## Technical Details

### Files Created

1. **deploy_momentum_live.py** - Main deployment script
2. **src/strategies/exhaustion_momentum_strategy.py** - Strategy implementation
3. **src/features/exhaustion.py** - Exhaustion detection (with momentum confirmation)

### Architecture

```
┌─────────────────┐
│  Market Data    │ (Pepperstone FIX)
│  GBPUSD H1      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   BarEvent      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Momentum        │
│ Strategy        │ (Exhaustion detection + confirmation)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  SignalEvent    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Risk Manager    │ (Check limits)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  OrderEvent     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  FIX Adapter    │ (Pepperstone execution)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   FillEvent     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Portfolio     │ (Track P&L)
└─────────────────┘
```

---

## Troubleshooting

### Connection Issues

**Error: "FIX logon rejected"**

- Verify password is correct (cTrader login password)
- Check account is 5227001
- Ensure using demo servers (`demo-us-eqx-01.p.c-trader.com`)

**Error: "Connection timeout"**

- Verify internet connection
- Check firewall/VPN not blocking ports 5211/5212
- Try different cTrader demo server if available

### Strategy Issues

**No signals generated**

- Check GBPUSD market data is being received
- Verify H1 timeframe
- Exhaustion patterns are rare (10% of bars)

**Signal rejected**

- Check risk limits (daily loss, max positions, max trades)
- Reset by starting new session (closes/reopens)

### Performance Issues

**Script not responding**

- Event loop may be blocked
- Press Ctrl+C to force shutdown
- Check logs for errors

---

## Safety Features

1. **Demo Account Only** - Uses Pepperstone demo account 5227001
2. **Position Limits** - Max 1 position at a time
3. **Daily Loss Limit** - Stops at -$500 per day
4. **Total Drawdown Limit** - Stops at -$2,000 total
5. **Graceful Shutdown** - Ctrl+C closes positions cleanly

---

## Next Steps

After testing deployment:

1. **Monitor for 1-2 days** to Validate:
   - FIX connectivity stable
   - Signals generated correctly
   - Orders executed accurately
   - Exit logic works (stops, trailing)
   - Risk limits enforce properly

2. **If Infrastructure Works:**
   - Archive this losing strategy
   - Develop better strategy (see EXHAUSTION_H1_FINAL_REPORT.md for recommendations)
   - Re-test in backtest first
   - Only deploy profitable strategies to demo

3. **Never Deploy to Live** without:
   - Positive backtest returns (Sharpe ≥ 1.2, PF ≥ 1.4)
   - Walk-forward validation
   - Robustness testing
   - Multiple months demo trading success

---

## Contact

For issues or questions:

- Check logs in console output
- Review FIX protocol specs if connection fails
- Pepperstone support: demo account issues

**Remember:** This is a LOSING strategy. Use only for infrastructure testing.
