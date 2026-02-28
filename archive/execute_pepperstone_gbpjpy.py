#!/usr/bin/env python
"""
Execute live GBPJPY buy order on Pepperstone via FIX API

This script connects to Pepperstone's cTrader demo account via FIX 4.4 protocol
and executes a real market order.

Requirements:
- Pepperstone cTrader demo account with FIX API enabled
- Correct FIX Symbol ID for GBPJPY (check in cTrader Symbol Info window)
"""

import sys
import logging
import time
from pathlib import Path
from datetime import datetime, UTC

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.execution.fix_client_v2 import PepperstoneFIXClient
import yaml

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


def find_gbpjpy_symbol_id():
    """
    Helper to determine GBPJPY symbol ID.
    
    Note: Symbol IDs vary by broker! Check your cTrader platform:
    1. Open GBPJPY chart
    2. Click symbol name → Symbol Info
    3. Scroll to bottom → FIX symbol ID
    
    Common values:
    - Pepperstone: typically "7" or check platform
    - Other brokers: varies
    """
    print("\n" + "=" * 70)
    print("IMPORTANT: FIX Symbol ID Verification")
    print("=" * 70)
    print("To find GBPJPY FIX Symbol ID in cTrader:")
    print("1. Open GBPJPY chart")
    print("2. Click on 'GBPJPY' at top → Symbol Info")
    print("3. Scroll to bottom of Symbol Info window")
    print("4. Look for 'FIX symbol ID'")
    print()
    print("Common Pepperstone values:")
    print("  EURUSD = 1")
    print("  GBPUSD = 2")
    print("  USDJPY = 4")
    print("  GBPJPY = 7 (most common, but VERIFY!)")
    print("=" * 70)
    
    symbol_id = input("\nEnter GBPJPY FIX Symbol ID from your cTrader platform: ").strip()
    
    if not symbol_id or not symbol_id.isdigit():
        print("✗ Invalid symbol ID. Exiting.")
        sys.exit(1)
    
    return symbol_id


def main():
    print("\n" + "=" * 70)
    print("PEPPERSTONE FIX - GBPJPY BUY ORDER (1 LOT)")
    print("=" * 70)
    print(f"Timestamp:  {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"Account:    demo.pepperstone.5227001 (DEMO)")
    print(f"Protocol:   FIX 4.4")
    print(f"Order:      BUY 1 lot (100,000 units) GBPJPY at MARKET")
    print("=" * 70)
    print()
    
    # Load config
    config_path = Path('config/brokers/pepperstone_fix.yaml')
    if not config_path.exists():
        print(f"✗ Config file not found: {config_path}")
        return
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Flatten config for FIX client
    flat_config = {
        'sender_comp_id': config['connection']['sender_comp_id'],
        'target_comp_id': config['connection']['target_comp_id'],
        'username': str(config['connection']['username']),
        'password': config['connection']['password'],
        'price_host': config['connection']['price']['host'],
        'price_port_ssl': config['connection']['price']['port_ssl'],
        'trade_host': config['connection']['trade']['host'],
        'trade_port_ssl': config['connection']['trade']['port_ssl'],
    }
    
    # Get GBPJPY symbol ID from user
    gbpjpy_symbol_id = find_gbpjpy_symbol_id()
    
    # Confirm execution
    print()
    confirm = input("Execute BUY order on LIVE demo account? (yes/no): ")
    if confirm.lower() != 'yes':
        print("\n✗ Order cancelled by user")
        return
    
    print()
    print("=" * 70)
    print("EXECUTION START")
    print("=" * 70)
    
    # Track execution reports
    execution_reports = []
    
    def on_execution(fields):
        """Handle execution report"""
        execution_reports.append(fields)
        exec_type = fields.get('150', 'Unknown')
        ord_status = fields.get('39', 'Unknown')
        
        # Execution types: 0=New, F=Trade (Fill), 4=Canceled, 8=Rejected
        # Order status: 0=New, 1=PartiallyFilled, 2=Filled, 4=Canceled, 8=Rejected
        
        print(f"\n[Execution Report #{len(execution_reports)}]")
        print(f"  ExecType:     {exec_type} ({_exec_type_name(exec_type)})")
        print(f"  OrdStatus:    {ord_status} ({_ord_status_name(ord_status)})")
        print(f"  ClOrdID:      {fields.get('11', 'N/A')}")
        print(f"  OrderID:      {fields.get('37', 'N/A')}")
        
        if '6' in fields:  # AvgPx
            print(f"  Fill Price:   {fields['6']}")
        if '14' in fields:  # CumQty
            print(f"  Filled Qty:   {fields['14']}")
        if '151' in fields:  # LeavesQty
            print(f"  Leaves Qty:   {fields['151']}")
        if '721' in fields:  # Position ID
            print(f"  Position ID:  {fields['721']}")
        if '58' in fields:  # Text (error messages)
            print(f"  Message:      {fields['58']}")
    
    def _exec_type_name(code):
        """Get execution type name"""
        types = {'0': 'New', '4': 'Canceled', '5': 'Replace', '8': 'Rejected', 
                 'C': 'Expired', 'F': 'Trade (Fill)', 'I': 'Order Status'}
        return types.get(code, code)
    
    def _ord_status_name(code):
        """Get order status name"""
        statuses = {'0': 'New', '1': 'Partially Filled', '2': 'Filled', 
                    '4': 'Canceled', '8': 'Rejected', 'C': 'Expired'}
        return statuses.get(code, code)
    
    # Initialize FIX client
    client = PepperstoneFIXClient(flat_config)
    client.on_execution_report = on_execution
    
    try:
        # Step 1: Connect to trade server
        print("\n[1/3] Connecting to trade server...")
        if not client.connect_trade():
            print("✗ Trade connection failed")
            print("\nPossible issues:")
            print("  - Check internet connection")
            print("  - Verify FIX password in config file")
            print("  - Ensure demo account has FIX API enabled")
            print("  - Check Pepperstone server status")
            return
        
        print("✓ Connected and logged in to TRADE session")
        
        # Step 2: Send order
        print("\n[2/3] Sending BUY order for GBPJPY...")
        print(f"  Symbol ID:  {gbpjpy_symbol_id}")
        print(f"  Side:       BUY")
        print(f"  Quantity:   100,000 units (1 standard lot)")
        print(f"  Type:       MARKET")
        
        order_id = client.send_new_order(
            symbol=gbpjpy_symbol_id,
            side="BUY",
            quantity=100000,  # 1 standard lot
            order_type="MARKET"
        )
        
        if not order_id:
            print("✗ Order submission failed")
            return
        
        print(f"✓ Order submitted")
        print(f"  Client Order ID: {order_id}")
        
        # Step 3: Wait for execution reports
        print("\n[3/3] Waiting for execution reports...")
        print("  (Broker typically responds within 1-3 seconds)")
        
        wait_time = 0
        max_wait = 10
        
        while wait_time < max_wait:
            time.sleep(0.5)
            wait_time += 0.5
            print(".", end="", flush=True)
            
            # Check if fully filled
            if execution_reports:
                last_report = execution_reports[-1]
                if last_report.get('39') == '2':  # Filled
                    break
        
        print()
        
        # Summary
        print("\n" + "=" * 70)
        print("EXECUTION SUMMARY")
        print("=" * 70)
        
        if execution_reports:
            last_report = execution_reports[-1]
            ord_status = last_report.get('39')
            
            print(f"Execution Reports Received: {len(execution_reports)}")
            print(f"Final Order Status:         {_ord_status_name(ord_status)}")
            
            if ord_status == '2':  # Filled
                print("\n✓ ORDER FILLED SUCCESSFULLY")
                print(f"  Fill Price:    {last_report.get('6', 'N/A')}")
                print(f"  Filled Qty:    {last_report.get('14', 'N/A')} units")
                print(f"  Position ID:   {last_report.get('721', 'N/A')}")
                
                if '6' in last_report and '14' in last_report:
                    notional = float(last_report['6']) * float(last_report['14'])
                    print(f"  Notional:      ${notional:,.2f}")
                
            elif ord_status == '8':  # Rejected
                print("\n✗ ORDER REJECTED")
                print(f"  Reason: {last_report.get('58', 'Unknown')}")
                
            else:
                print(f"\n⚠ Order in progress (Status: {ord_status})")
        else:
            print("⚠ No execution reports received")
            print("\nPossible reasons:")
            print("  - Market is closed")
            print("  - Symbol ID incorrect")
            print("  - Account restrictions")
            print("  - Insufficient margin")
        
        print("=" * 70)
        
    finally:
        # Step 4: Disconnect
        print("\n[4/4] Disconnecting...")
        client.disconnect()
        print("✓ Disconnected")
        print()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n✗ Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
