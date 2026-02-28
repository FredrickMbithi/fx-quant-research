#!/usr/bin/env python
"""
Test script: Execute a buy order on GBPJPY
Uses paper trading simulator (no real money)
"""

import time
from datetime import datetime

from src.events import EventQueue, OrderEvent, OrderType, OrderSide
from src.execution.simulator import PaperTradingSimulator
from src.portfolio import Portfolio

# Initialize components
event_queue = EventQueue()
portfolio = Portfolio(initial_capital=100000.0)
simulator = PaperTradingSimulator('config/brokers/pepperstone_fix.yaml', event_queue)

# Set current market price for GBPJPY (example price)
# In live trading, this would come from real market data
current_bid = 189.50
current_ask = 189.52
simulator.update_market_price('GBPJPY', current_bid, current_ask)

print("=" * 70)
print("EXECUTING TEST BUY ORDER - GBPJPY")
print("=" * 70)
print(f"Timestamp:     {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
print(f"Pair:          GBPJPY")
print(f"Side:          BUY")
print(f"Size:          1 lot (100,000 units)")
print(f"Market Bid:    {current_bid:.2f}")
print(f"Market Ask:    {current_ask:.2f}")
print(f"Fill Price:    ~{current_ask:.2f} (buying at ask)")
print(f"Mode:          PAPER TRADING (simulated)")
print("=" * 70)
print()

# Create buy order (1 standard lot = 100,000 units)
order = OrderEvent(
    symbol='GBPJPY',
    order_type=OrderType.MARKET,
    side=OrderSide.BUY,
    quantity=100000  # 1 standard lot
)

print(f"[1] Creating order: {order.order_id}")
print(f"    → Symbol: {order.symbol}")
print(f"    → Type: {order.order_type.value}")
print(f"    → Side: {order.side.value}")
print(f"    → Quantity: {order.quantity:,} units")
print()

# Execute order through simulator
print("[2] Submitting order to paper trading simulator...")
simulator.execute_order(order)
print("    → Order submitted (simulating broker delay...)")
print()

# Wait for fill event (simulator creates fill asynchronously)
print("[3] Waiting for fill confirmation...")
max_wait = 5  # seconds
start_time = time.time()
fill_event = None

while time.time() - start_time < max_wait:
    if not event_queue.empty():
        fill_event = event_queue.get()
        break
    time.sleep(0.1)

if fill_event:
    print("    → Fill received!")
    print()
    print("=" * 70)
    print("FILL DETAILS")
    print("=" * 70)
    print(f"Order ID:      {fill_event.order_id}")
    print(f"Symbol:        {fill_event.symbol}")
    print(f"Side:          {fill_event.side.value}")
    print(f"Quantity:      {fill_event.quantity:,} units")
    print(f"Fill Price:    {fill_event.fill_price:.5f}")
    print(f"Commission:    ${fill_event.commission:.2f}")
    print(f"Slippage Cost: ${fill_event.slippage:.2f}")
    print(f"Total Cost:    ${fill_event.total_cost:.2f}")
    print(f"Timestamp:     {fill_event.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 70)
    print()
    
    # Update portfolio
    portfolio.on_fill(fill_event)
    
    print("=" * 70)
    print("PORTFOLIO UPDATE")
    print("=" * 70)
    print(f"Initial Capital:  ${portfolio.initial_capital:,.2f}")
    print(f"Cash:             ${portfolio.cash:,.2f}")
    print(f"Positions:        {len(portfolio.positions)}")
    print()
    
    if 'GBPJPY' in portfolio.positions:
        position = portfolio.positions['GBPJPY']
        # Calculate unrealized PnL with current market price
        unrealized = position.unrealized_pnl(current_bid)  # Use current bid for long position
        
        print(f"GBPJPY Position:")
        print(f"  Entry Price:    {position.entry_price:.5f}")
        print(f"  Quantity:       {position.quantity:,} units")
        print(f"  Side:           {position.side.value}")
        print(f"  Notional Value: ${position.quantity * current_bid:,.2f}")
        print(f"  Unrealized PnL: ${unrealized:.2f}")
        print(f"  Total Costs:    ${position.total_commission + position.total_slippage:.2f}")
        print()
        print(f"  Note: In FX margin trading, you control ${position.quantity * current_bid:,.2f}")
        print(f"        notional value with only a fraction as margin requirement.")
        print(f"        At typical 1:100 leverage, margin needed: ${position.quantity * current_bid / 100:,.2f}")
    
    print("=" * 70)
    print()
    print("✓ TEST BUY ORDER COMPLETED SUCCESSFULLY")
    
else:
    print("    ✗ ERROR: Fill not received within timeout")
    print()
    print("This may indicate:")
    print("- Simulator thread issue")
    print("- Event queue problem")
    print("- Check logs for errors")

print()
print("NOTE: This was a SIMULATED trade (paper trading mode)")
print("      No real money was used or at risk.")
print()
