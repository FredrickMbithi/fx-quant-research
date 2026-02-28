#!/usr/bin/env python
"""
Live FIX Order Execution - GBPJPY Buy

Connects to Pepperstone cTrader demo account via FIX protocol
and executes a real buy order on GBPJPY.

WARNING: This connects to a LIVE broker (demo account).
"""

import logging
import time
import sys
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)

from src.events import EventQueue, OrderEvent, OrderType, OrderSide
from src.execution.fix_client import FIXSessionManager
from src.execution.pepperstone_adapter import PepperstoneOrderAdapter
from src.portfolio import Portfolio

def main():
    print("=" * 70)
    print("LIVE FIX ORDER EXECUTION - GBPJPY BUY")
    print("=" * 70)
    print(f"Timestamp:        {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"Broker:           Pepperstone cTrader")
    print(f"Account:          demo.pepperstone.5227001 (DEMO)")
    print(f"Protocol:         FIX 4.4")
    print(f"")
    print(f"Order Details:")
    print(f"  Symbol:         GBPJPY")
    print(f"  Side:           BUY (Long)")
    print(f"  Size:           1 lot (100,000 units)")
    print(f"  Order Type:     MARKET")
    print("=" * 70)
    print()
    
    # Confirm
    response = input("Execute order on LIVE demo account? (yes/no): ")
    if response.lower() != 'yes':
        print("Cancelled by user.")
        return
    
    print("\n[1/5] Initializing FIX session manager...")
    
    # Initialize components
    event_queue = EventQueue()
    portfolio = Portfolio(initial_capital=100000.0)
    
    # Create FIX session manager
    fix_manager = FIXSessionManager('config/brokers/pepperstone_fix.yaml')
    
    print("[2/5] Connecting to Pepperstone via FIX...")
    print(f"      → Establishing SSL connection to demo servers...")
    
    # Track fills
    fills_received = []
    
    def handle_price_message(msg):
        """Handle market data messages."""
        msg_type = msg.get(35)
        if msg_type:
            msg_type_str = msg_type.decode() if isinstance(msg_type, bytes) else msg_type
            logging.debug(f"Price message: MsgType={msg_type_str}")
    
    def handle_trade_message(msg):
        """Handle trade execution messages."""
        msg_type = msg.get(35)
        if msg_type:
            msg_type_str = msg_type.decode() if isinstance(msg_type, bytes) else msg_type
            logging.info(f"Trade message: MsgType={msg_type_str}")
            
            # ExecutionReport (35=8)
            if msg_type_str == '8':
                adapter.handle_execution_report(msg)
    
    def on_fill(fill_event):
        """Handle fill events."""
        fills_received.append(fill_event)
        portfolio.on_fill(fill_event)
        print(f"\n✓ FILL RECEIVED!")
        print(f"  Symbol:      {fill_event.symbol}")
        print(f"  Side:        {fill_event.side.value}")
        print(f"  Quantity:    {fill_event.quantity:,} units")
        print(f"  Fill Price:  {fill_event.fill_price:.5f}")
        print(f"  Commission:  ${fill_event.commission:.2f}")
        print(f"  Exec ID:     {fill_event.exchange_order_id}")
    
    # Connect to FIX
    success = fix_manager.connect_all(
        price_handler=handle_price_message,
        trade_handler=handle_trade_message
    )
    
    if not success:
        print("✗ Failed to connect to FIX. Check credentials and network.")
        return
    
    print("✓ Connected to Pepperstone FIX")
    print()
    
    # Give connection time to stabilize
    time.sleep(2)
    
    print("[3/5] Creating order adapter...")
    
    # Create Pepperstone adapter
    adapter = PepperstoneOrderAdapter(
        fix_session=fix_manager.trade_session,
        account="5227001"  # Demo account number
    )
    adapter.set_fill_callback(on_fill)
    
    print("[4/5] Submitting MARKET BUY order for GBPJPY...")
    
    # Create order
    order = OrderEvent(
        symbol='GBPJPY',
        order_type=OrderType.MARKET,
        side=OrderSide.BUY,
        quantity=100000  # 1 standard lot
    )
    
    # Submit order
    submitted = adapter.submit_order(order)
    
    if not submitted:
        print("✗ Failed to submit order")
        fix_manager.disconnect_all()
        return
    
    print("✓ Order submitted to broker")
    print()
    
    print("[5/5] Waiting for execution report...")
    print("      (Broker typically responds within 1-3 seconds)")
    
    # Wait for fill
    max_wait = 30  # seconds
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        if fills_received:
            break
        time.sleep(0.5)
        print(".", end="", flush=True)
    
    print()
    print()
    
    if fills_received:
        print("=" * 70)
        print("ORDER EXECUTION COMPLETE")
        print("=" * 70)
        
        fill = fills_received[0]
        
        print(f"Portfolio Status:")
        print(f"  Cash:             ${portfolio.cash:,.2f}")
        print(f"  Open Positions:   {len(portfolio.positions)}")
        
        if 'GBPJPY' in portfolio.positions:
            pos = portfolio.positions['GBPJPY']
            print(f"\nGBPJPY Position:")
            print(f"  Entry Price:      {pos.entry_price:.5f}")
            print(f"  Quantity:         {pos.quantity:,} units")
            print(f"  Side:             {pos.side.value}")
            print(f"  Notional Value:   ${pos.quantity * pos.entry_price:,.2f}")
        
        print("=" * 70)
        print("\n✓ SUCCESS - Order executed on live demo account!")
        
    else:
        print("=" * 70)
        print("⚠ WARNING - No fill received within timeout")
        print("=" * 70)
        print("Possible reasons:")
        print("- Broker is processing order")
        print("- Market is closed")
        print("- Order was rejected (check FIX logs)")
        print("- Symbol not available")
        print("\nCheck log output above for ExecutionReport messages.")
    
    print()
    print("Disconnecting from FIX...")
    fix_manager.disconnect_all()
    print("✓ Disconnected")
    print()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(0)
    except Exception as e:
        logging.error(f"Error: {e}", exc_info=True)
        sys.exit(1)
