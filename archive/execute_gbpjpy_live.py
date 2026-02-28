#!/usr/bin/env python
"""
Execute live GBPJPY buy order on Pepperstone cTrader - Interactive version

This script will prompt for your FIX API password and execute the trade.
"""

import sys
import logging
import time
import getpass
from pathlib import Path
from datetime import datetime, UTC

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.execution.fix_client_v2 import PepperstoneFIXClient

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


def main():
    print("\n" + "=" * 70)
    print("PEPPERSTONE CTRADER - LIVE GBPJPY BUY ORDER")
    print("=" * 70)
    print(f"Account:  5227001 (DEMO)")
    print(f"Order:    BUY 100,000 units (1 lot) GBPJPY at MARKET")
    print(f"Time:     {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 70)
    print()
    
    # Get FIX password
    print("FIX API Password:")
    print("  → Use your account 5227001 password")
    print("  (The same password you use to login to cTrader)")
    print()
    print("  If that doesn't work, check:")
    print("    1. In cTrader Web → Settings (gear icon)")
    print("    2. Look for 'FIX API' section")
    print("    3. Use the FIX-specific password shown there")
    print()
    
    # Prompt for password
    fix_password = getpass.getpass("Enter your account password: ").strip()
    
    if not fix_password:
        print("\n✗ No password entered. Exiting.")
        return
    
    # Get GBPJPY symbol ID
    print()
    print("=" * 70)
    print("GBPJPY Symbol ID")
    print("=" * 70)
    print("In cTrader:")
    print("  1. Right-click on GBPJPY chart")
    print("  2. Select 'Symbol Info'")
    print("  3. Scroll to bottom → look for 'FIX symbol ID'")
    print()
    symbol_id = input("Enter GBPJPY FIX Symbol ID (press Enter for '7'): ").strip()
    if not symbol_id:
        symbol_id = "7"
        print(f"  Using default: {symbol_id}")
    
    # Confirm
    print()
    print("=" * 70)
    print("CONFIRMATION")
    print("=" * 70)
    print(f"Account:      5227001")
    print(f"Order:        BUY 100,000 units (1 lot)")
    print(f"Symbol:       GBPJPY (FIX ID: {symbol_id})")
    print(f"Type:         MARKET")
    print(f"Environment:  DEMO ACCOUNT")
    print("=" * 70)
    
    confirm = input("\nExecute this order? (type 'yes' to confirm): ")
    if confirm.lower() != 'yes':
        print("\n✗ Order cancelled")
        return
    
    # Configuration
    config = {
        'sender_comp_id': 'demo.pepperstone.5227001',
        'target_comp_id': 'cServer',
        'username': '5227001',
        'password': fix_password,
        'price_host': 'demo-us-eqx-01.p.c-trader.com',
        'price_port_ssl': 5211,
        'trade_host': 'demo-us-eqx-01.p.c-trader.com',
        'trade_port_ssl': 5212,
    }
    
    print()
    print("=" * 70)
    print("EXECUTION")
    print("=" * 70)
    
    # Track execution
    execution_reports = []
    
    def on_execution(fields):
        """Handle execution report"""
        execution_reports.append(fields)
        exec_type = fields.get('150', 'Unknown')
        ord_status = fields.get('39', 'Unknown')
        
        print(f"\n[Execution Report #{len(execution_reports)}]")
        print(f"  Status:  {_ord_status_name(ord_status)}")
        
        if '6' in fields:  # AvgPx
            print(f"  Price:   {fields['6']}")
        if '14' in fields:  # CumQty
            print(f"  Filled:  {fields['14']} units")
        if '721' in fields:  # Position ID
            print(f"  Pos ID:  {fields['721']}")
        if '58' in fields:  # Text
            print(f"  Message: {fields['58']}")
    
    def _ord_status_name(code):
        statuses = {'0': 'New', '1': 'Partially Filled', '2': 'Filled', 
                    '4': 'Canceled', '8': 'Rejected', 'C': 'Expired'}
        return statuses.get(code, code)
    
    # Initialize client
    client = PepperstoneFIXClient(config)
    client.on_execution_report = on_execution
    
    try:
        # Connect
        print("\n[1/3] Connecting to trade server...")
        if not client.connect_trade():
            print("\n✗ CONNECTION FAILED")
            print("\nPossible issues:")
            print("  • FIX password is incorrect")
            print("  • FIX API not enabled on your account")
            print("  • Check cTrader Settings → FIX API")
            return
        
        print("✓ Connected and logged in")
        
        # Send order
        print("\n[2/3] Sending BUY order...")
        order_id = client.send_new_order(
            symbol=symbol_id,
            side="BUY",
            quantity=100000,
            order_type="MARKET"
        )
        
        if not order_id:
            print("✗ Failed to send order")
            return
        
        print(f"✓ Order submitted (ID: {order_id})")
        
        # Wait for fill
        print("\n[3/3] Waiting for execution...")
        for i in range(10):
            time.sleep(0.5)
            print(".", end="", flush=True)
            
            if execution_reports:
                last = execution_reports[-1]
                if last.get('39') in ['2', '8']:  # Filled or Rejected
                    break
        
        print()
        
        # Summary
        print("\n" + "=" * 70)
        print("RESULT")
        print("=" * 70)
        
        if execution_reports:
            last = execution_reports[-1]
            status = last.get('39')
            
            if status == '2':  # Filled
                print("\n✓ ORDER FILLED SUCCESSFULLY!")
                print(f"\n  Fill Price:  {last.get('6', 'N/A')}")
                print(f"  Quantity:    {last.get('14', 'N/A')} units")
                print(f"  Position ID: {last.get('721', 'N/A')}")
                
                if '6' in last and '14' in last:
                    notional = float(last['6']) * float(last['14'])
                    print(f"  Notional:    ${notional:,.2f}")
                
                print("\n  → Check your cTrader platform to see the position")
                
            elif status == '8':  # Rejected
                print("\n✗ ORDER REJECTED")
                print(f"\n  Reason: {last.get('58', 'Unknown')}")
                
            else:
                print(f"\n⚠ Order status: {_ord_status_name(status)}")
        else:
            print("\n⚠ No execution reports received")
            print("\nPossible reasons:")
            print("  • Incorrect symbol ID")
            print("  • Market closed")
            print("  • Account restrictions")
        
        print("=" * 70)
        
    finally:
        print("\n[4/4] Disconnecting...")
        client.disconnect()
        print("✓ Disconnected\n")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n✗ Cancelled by user\n")
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)
