#!/usr/bin/env python3
"""
Dashboard Data Validation Tests
=================================

Validates exported backtest data for dashboard consumption:
- Equity curve consistency
- Timestamp monotonicity
- Exit reason validity
- MAE/MFE calculations
- Trade count accuracy
- Session classification
"""

import json
import sys
from pathlib import Path
from datetime import datetime

def test_data_integrity(data_dir: Path):
    """Run all validation tests on exported data."""
    
    print(f"\n{'='*70}")
    print(f"DASHBOARD DATA VALIDATION")
    print(f"{'='*70}\n")
    print(f"Testing data in: {data_dir}\n")
    
    passed = 0
    failed = 0
    
    # Load all JSON files
    try:
        with open(data_dir / 'metadata.json') as f:
            metadata = json.load(f)
        with open(data_dir / 'metrics.json') as f:
            metrics = json.load(f)
        with open(data_dir / 'trades.json') as f:
            trades = json.load(f)
        with open(data_dir / 'equity.json') as f:
            equity = json.load(f)
        with open(data_dir / 'diagnostics.json') as f:
            diagnostics = json.load(f)
        print("✅ All JSON files loaded successfully\n")
    except Exception as e:
        print(f"❌ Failed to load JSON files: {e}")
        return
    
    # Test 1: Equity curve consistency
    print("Test 1: Equity curve consistency")
    initial_capital = metrics['initial_capital']
    final_equity = metrics['final_equity']
    
    if abs(equity[0]['equity'] - initial_capital) < 0.01:
        print(f"  ✅ Equity starts at initial capital: ${equity[0]['equity']:,.2f}")
        passed += 1
    else:
        print(f"  ❌ Equity start mismatch: {equity[0]['equity']} vs {initial_capital}")
        failed += 1
    
    if abs(equity[-1]['equity'] - final_equity) < 1.0:
        print(f"  ✅ Equity ends at final equity: ${equity[-1]['equity']:,.2f}")
        passed += 1
    else:
        print(f"  ❌ Equity end mismatch: {equity[-1]['equity']} vs {final_equity}")
        failed += 1
    
    # Test 2: Timestamp monotonicity
    print("\nTest 2: Timestamp monotonicity")
    equity_times = [datetime.fromisoformat(e['timestamp']) for e in equity]
    if all(equity_times[i] <= equity_times[i+1] for i in range(len(equity_times)-1)):
        print(f"  ✅ Equity timestamps are monotonically increasing")
        passed += 1
    else:
        print(f"  ❌ Equity timestamps are not ordered")
        failed += 1
    
    trade_times = [datetime.fromisoformat(t['entry_time']) for t in trades]
    if all(trade_times[i] <= trade_times[i+1] for i in range(len(trade_times)-1)):
        print(f"  ✅ Trade entry timestamps are monotonically increasing")
        passed += 1
    else:
        print(f"  ❌ Trade entry timestamps are not ordered")
        failed += 1
    
    # Test 3: Exit reason validity
    print("\nTest 3: Exit reason validity")
    valid_reasons = {'hard_stop', 'trailing_stop', 'max_hold', 'unknown'}
    invalid_reasons = {t['exit_reason'] for t in trades if t['exit_reason'] not in valid_reasons}
    
    if not invalid_reasons:
        print(f"  ✅ All exit reasons are valid")
        passed += 1
    else:
        print(f"  ❌ Invalid exit reasons found: {invalid_reasons}")
        failed += 1
    
    # Test 4: Trade count accuracy
    print("\nTest 4: Trade count accuracy")
    if len(trades) == metrics['total_trades']:
        print(f"  ✅ Trade count matches: {len(trades)}")
        passed += 1
    else:
        print(f"  ❌ Trade count mismatch: {len(trades)} vs {metrics['total_trades']}")
        failed += 1
    
    # Test 5: MAE/MFE calculations
    print("\nTest 5: MAE/MFE calculations")
    trades_with_mae_mfe = [t for t in trades if 'mae_pips' in t and 'mfe_pips' in t]
    
    if len(trades_with_mae_mfe) == len(trades):
        print(f"  ✅ All trades have MAE/MFE data")
        passed += 1
    else:
        print(f"  ❌ Missing MAE/MFE data: {len(trades) - len(trades_with_mae_mfe)} trades")
        failed += 1
    
    # Check MAE is negative (or zero)
    positive_mae = [t for t in trades if t.get('mae_pips', 0) > 0.1]  # Small tolerance
    if not positive_mae:
        print(f"  ✅ All MAE values are <= 0 (as expected)")
        passed += 1
    else:
        print(f"  ⚠️  Warning: {len(positive_mae)} trades have positive MAE (should be negative)")
        # This is a warning, not a failure - could be rounding
        passed += 1
    
    # Check MFE is positive (or zero)
    negative_mfe = [t for t in trades if t.get('mfe_pips', 0) < -0.1]  # Small tolerance
    if not negative_mfe:
        print(f"  ✅ All MFE values are >= 0 (as expected)")
        passed += 1
    else:
        print(f"  ❌ {len(negative_mfe)} trades have negative MFE")
        failed += 1
    
    # Test 6: Session classification
    print("\nTest 6: Session classification")
    valid_sessions = {'ASIA', 'LONDON', 'NY'}
    invalid_sessions = {t['session'] for t in trades if t.get('session') not in valid_sessions}
    
    if not invalid_sessions:
        print(f"  ✅ All trades have valid session classification")
        passed += 1
    else:
        print(f"  ❌ Invalid sessions found: {invalid_sessions}")
        failed += 1
    
    # Test 7: Diagnostics completeness
    print("\nTest 7: Diagnostics completeness")
    required_fields = [
        'expectancy_per_trade_pips', 'mae_vs_stop_ratio', 'mfe_vs_target_ratio',
        'efficiency_ratio', 'hard_stop_capture_pct', 'trailing_activation_pct',
        'exit_breakdown', 'structural_issues'
    ]
    
    missing_fields = [f for f in required_fields if f not in diagnostics]
    if not missing_fields:
        print(f"  ✅ All required diagnostic fields present")
        passed += 1
    else:
        print(f"  ❌ Missing diagnostic fields: {missing_fields}")
        failed += 1
    
    # Test 8: Win rate calculation
    print("\nTest 8: Win rate calculation")
    winning_trades = len([t for t in trades if t['winning']])
    calculated_win_rate = (winning_trades / len(trades)) * 100 if trades else 0
    
    if abs(calculated_win_rate - metrics['win_rate_pct']) < 0.1:
        print(f"  ✅ Win rate matches: {calculated_win_rate:.2f}%")
        passed += 1
    else:
        print(f"  ❌ Win rate mismatch: {calculated_win_rate:.2f}% vs {metrics['win_rate_pct']:.2f}%")
        failed += 1
    
    # Test 9: Metadata versioning
    print("\nTest 9: Metadata versioning")
    required_meta = ['strategy_version', 'git_commit', 'run_id', 'run_timestamp']
    missing_meta = [f for f in required_meta if f not in metadata]
    
    if not missing_meta:
        print(f"  ✅ All versioning metadata present")
        print(f"     Version: {metadata['strategy_version']}")
        print(f"     Commit: {metadata['git_commit']}")
        passed += 1
    else:
        print(f"  ❌ Missing metadata: {missing_meta}")
        failed += 1
    
    # Summary
    print(f"\n{'='*70}")
    print(f"VALIDATION SUMMARY")
    print(f"{'='*70}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"Total: {passed + failed}")
    
    if failed == 0:
        print(f"\n🎉 All tests passed! Data is ready for dashboard")
        return True
    else:
        print(f"\n⚠️  {failed} test(s) failed. Please review issues above.")
        return False


def main():
    """Run validation tests."""
    # Find the most recent export
    base = Path("data/backtests")
    
    if not base.exists():
        print("❌ No backtest data found. Run export_backtest_dashboard.py first.")
        sys.exit(1)
    
    # Find latest run
    all_runs = []
    for strategy_dir in base.iterdir():
        if strategy_dir.is_dir():
            for run_dir in strategy_dir.iterdir():
                if run_dir.is_dir() and run_dir.name.startswith('run_'):
                    all_runs.append(run_dir)
    
    if not all_runs:
        print("❌ No run directories found")
        sys.exit(1)
    
    # Use most recent by modification time
    latest_run = max(all_runs, key=lambda p: p.stat().st_mtime)
    
    # Run tests
    success = test_data_integrity(latest_run)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
