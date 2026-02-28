#!/usr/bin/env python
"""
Quick test of production database logging
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.utils.trade_database import TradeDatabase
from datetime import datetime, UTC

print("\n" + "="*70)
print("TESTING: Trade Database")
print("="*70)

# Initialize database
db = TradeDatabase('state/trades_test.db')
print("✓ Database initialized")

# Create test session with unique ID
import time
session_id = f'test_session_{int(time.time())}'
db.create_session(
    session_id=session_id,
    strategy='ExhaustionMomentum',
    config={
        'initial_capital': 100000.0,
        'position_size': 10000,
        'risk_params': {'max_daily_loss': 500},
        'detector_params': {'pressure_threshold': 2},
        'mode': 'simulation',
        'git_commit': 'test123'
    }
)
print(f"✓ Session created: {session_id}")

# Log a trade entry
trade_id = f'trade_{int(time.time() * 1000)}'
db.log_trade_entry({
    'trade_id': trade_id,
    'session_id': session_id,
    'instrument': 'GBPUSD',
    'direction': 'LONG',
    'entry_time': datetime.now(UTC).isoformat(),
    'entry_price': 1.2700,
    'entry_size': 10000,
    'signal_time': datetime.now(UTC).isoformat(),
    'order_sent_time': datetime.now(UTC).isoformat(),
    'fill_received_time': datetime.now(UTC).isoformat(),
    'signal_to_fill_ms': 25
})
print("✓ Trade entry logged")

# Log trade exit
db.log_trade_exit(trade_id, {
    'session_id': session_id,
    'exit_time': datetime.now(UTC).isoformat(),
    'exit_price': 1.2705,
    'exit_reason': 'trailing_stop',
    'pnl_pips': 5.0,
    'pnl_usd': 5.0,
    'hold_duration_minutes': 15,
    'mae_pips': -2.5,
    'mfe_pips': 6.2
})
print("✓ Trade exit logged")

# Log system event
db.log_event(
    session_id=session_id,
    event_type='SIGNAL',
    message='LONG signal generated',
    severity='INFO',
    details={'strength': 0.85}
)
print("✓ Event logged")

# Get session summary
summary = db.get_session_summary(session_id)
print("\n" + "="*70)
print("SESSION SUMMARY")
print("="*70)
print(f"Session ID:      {summary['session_id']}")
print(f"Total trades:    {summary['total_trades']}")
print(f"Winning trades:  {summary['winning_trades']}")
print(f"Win rate:        {summary['win_rate']:.1f}%")
print(f"Total P&L:       ${summary['total_pnl_usd']:.2f}")
print(f"Avg latency:     {summary['avg_latency_ms']:.0f}ms")
print("="*70)

# Get recent trades
trades = db.get_recent_trades(session_id)
print(f"\nRecent trades: {len(trades)}")
for trade in trades:
    print(f"  {trade['trade_id']}: {trade['direction']} @ {trade['entry_price']} → {trade['pnl_pips']} pips")

# Close session
db.close_session(session_id)
print("\n✓ Session closed")

print("\n" + "="*70)
print("DATABASE TEST PASSED ✅")
print(f"Test database: state/trades_test.db")
print("="*70)
