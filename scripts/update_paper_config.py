"""
Update paper trading configuration with optimal SL/TP from notebook
Run this after completing Part 14 (SL/TP optimization) in the notebook
"""

import json
from pathlib import Path


def update_config_from_notebook(
    stop_loss_pips: float = None,
    take_profit_pips: float = None,
    config_path: str = 'config/paper_trading_config.json'
):
    """
    Update paper trading config with SL/TP values
    
    Args:
        stop_loss_pips: Stop loss in pips (from Part 14)
        take_profit_pips: Take profit in pips (from Part 14)
        config_path: Path to config file
    """
    # Load existing config
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    # Update SL/TP if provided
    if stop_loss_pips is not None:
        config['stop_loss_pips'] = stop_loss_pips
        print(f"✓ Updated stop_loss_pips: {stop_loss_pips}")
    
    if take_profit_pips is not None:
        config['take_profit_pips'] = take_profit_pips
        print(f"✓ Updated take_profit_pips: {take_profit_pips}")
    
    # Save updated config
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"\n✅ Configuration updated: {config_path}")
    print("\nCurrent SL/TP settings:")
    print(f"  Stop Loss: {config.get('stop_loss_pips')} pips")
    print(f"  Take Profit: {config.get('take_profit_pips')} pips")


def extract_from_notebook_results():
    """
    Interactive helper to extract SL/TP from notebook results
    
    Run this AFTER executing Part 14 in the notebook and inspecting best_sltp_trades
    """
    print("="*80)
    print("EXTRACT SL/TP FROM NOTEBOOK PART 14")
    print("="*80)
    print("\nIn your Jupyter notebook, run:")
    print("```python")
    print("# Print best SL/TP configuration")
    print("print(f\"Best SL: {best_sltp['sl']} pips\")")
    print("print(f\"Best TP: {best_sltp['tp']} pips\")")
    print("print(f\"Total profit: {best_sltp['total_pips']:.1f} pips\")")
    print("```")
    print("\nThen enter the values below:")
    print("-"*80)
    
    try:
        sl = input("\nEnter Stop Loss in pips (or press Enter to skip): ").strip()
        tp = input("Enter Take Profit in pips (or press Enter to skip): ").strip()
        
        sl_value = float(sl) if sl else None
        tp_value = float(tp) if tp else None
        
        if sl_value or tp_value:
            update_config_from_notebook(sl_value, tp_value)
        else:
            print("\n⚠️  No values entered. Config not updated.")
            print("   Using time-based exit only (10 hours)")
    
    except ValueError as e:
        print(f"\n❌ Error: Invalid input - {e}")
        print("   Please enter numeric values only")
    except Exception as e:
        print(f"\n❌ Error: {e}")


if __name__ == '__main__':
    """
    Usage:
    
    # Option 1: Direct values (if you know them)
    python update_paper_config.py
    # Then enter SL and TP when prompted
    
    # Option 2: From Python script
    from update_paper_config import update_config_from_notebook
    update_config_from_notebook(stop_loss_pips=50, take_profit_pips=100)
    
    # Option 3: With None for time-based exit only
    update_config_from_notebook(stop_loss_pips=None, take_profit_pips=None)
    """
    extract_from_notebook_results()
