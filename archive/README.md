# Archive

This directory contains legacy deployment scripts and documentation that have been superseded by the current production implementation.

## Archived Deployment Scripts

### Legacy Deployment Implementations

- **deploy_momentum_live.py** - Original live FIX trading deployment (Pepperstone demo)
- **deploy_paper_trading.py** - MA Deviation strategy paper trading (validated 3,806 trades, 28K pips)
- **deploy_multipair_h1.py** - Multi-pair H1 exhaustion strategy (target: 3,000 trades)
- **deploy_paper.sh** - Bash wrapper for paper trading deployment

### Direct Execution Scripts

- **execute_gbpjpy_live.py** - Direct GBPJPY order execution
- **execute_live_gbpjpy_buy.py** - Direct GBPJPY buy order
- **execute_pepperstone_gbpjpy.py** - Pepperstone GBPJPY execution

## Current Production System

The active production deployment is now consolidated in:

- **`deploy_momentum_production.py`** (in project root)

This script provides:

- Real FIX market data subscription
- Real FIX order execution
- SQLite trade logging with full audit trail
- Dual mode operation (simulation/live)
- Automatic reconnection with exponential backoff
- Position reconciliation on startup
- Latency tracking

## Why These Were Archived

These scripts represent different development iterations and strategy variations. While they contain valuable logic and have been battle-tested, they:

- Lack the comprehensive infrastructure of the production system
- Have overlapping functionality
- Could cause confusion about which deployment to use

They are preserved here for:

- Reference during debugging
- Historical context
- Potential rollback if needed
- Component extraction for future use

## Documentation

Legacy documentation has been moved to `archive/docs/` and consolidated into the main `docs/` directory.

---

_Archived: February 25, 2026_
