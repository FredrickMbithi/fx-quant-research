# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added - February 25, 2026 - Repository Reorganization

**Major restructuring to improve organization and maintainability**

#### New Directories

- `archive/` - Preserved legacy deployment scripts and documentation
- `archive/docs/` - Historical guides and superseded documentation
- `dashboards/` - Generated HTML reports (git-ignored)
- `tests/integration/` - Integration tests for FIX API and system components

#### New Documentation

- `docs/deployment_guide.md` - Consolidated production deployment guide
  - Merged `PRODUCTION_DEPLOYMENT_GUIDE.md`, `LIVE_FIX_TRADING_GUIDE.md`, `QUICK_REFERENCE_LIVE_FIX.md`
  - Comprehensive FIX API setup and usage
  - Safety controls and monitoring
- `docs/fix_setup.md` - FIX API credentials setup guide
  - Converted from `FIX_PASSWORD_INSTRUCTIONS.txt`
  - Step-by-step instructions with troubleshooting
- `CHANGELOG.md` - This file (project change history)

#### Moved Files

**Deployment Scripts** (to `archive/`):

- `deploy_momentum_live.py` → `archive/`
- `deploy_paper_trading.py` → `archive/`
- `deploy_multipair_h1.py` → `archive/`
- `deploy_paper.sh` → `archive/`
- `execute_gbpjpy_live.py` → `archive/`
- `execute_live_gbpjpy_buy.py` → `archive/`
- `execute_pepperstone_gbpjpy.py` → `archive/`

**Primary deployment**: `deploy_momentum_production.py` (kept in root)

**Documentation** (to `archive/docs/`):

- `DEPLOYMENT_GUIDE.md` → `archive/docs/`
- `DEPLOYMENT_README.md` → `archive/docs/`
- `LIVE_TRADING_README.md` → `archive/docs/`
- `PAPER_TRADING_README.md` → `archive/docs/`
- `H1_MULTIPAIR_QUICKSTART.md` → `archive/docs/`
- `H1_3000_TRADES_IMPLEMENTATION.md` → `archive/docs/`
- `IMPLEMENTATION_STATUS.md` → `archive/docs/`
- `FIX_IMPLEMENTATION_SUMMARY.md` → `archive/docs/`
- `LIVE_FIX_IMPLEMENTATION_COMPLETE.md` → `archive/docs/`
- `FIX_PASSWORD_INSTRUCTIONS.txt` → `archive/docs/`
- `PRODUCTION_DEPLOYMENT_GUIDE.md` → `archive/docs/`
- `LIVE_FIX_TRADING_GUIDE.md` → `archive/docs/`
- `QUICK_REFERENCE_LIVE_FIX.md` → `archive/docs/`
- `docs/DAY_8_QUICK_REFERENCE.md` → `archive/docs/`
- `docs/LIVE_TRADING_GUIDE.md` → `archive/docs/`

**Test Files** (to `tests/`):

- `test_database.py` → `tests/test_trade_database.py`
- `test_fix_logon.py` → `tests/integration/test_fix_logon.py`
- `test_gbpjpy_buy.py` → `tests/integration/test_order_execution.py`

**Scripts** (to `scripts/`):

- `analyze_paper_results.py` → `scripts/`
- `analyze_multipair_results.py` → `scripts/`
- `update_paper_config.py` → `scripts/`
- `examples/backtest_exhaustion_h1.py` → `scripts/`
- `examples/backtest_momentum_h1.py` → `scripts/`
- `examples/generate_final_report.py` → `scripts/`

**Generated Artifacts** (to `dashboards/`):

- `dashboard_gbpusd_h1.html` → `dashboards/gbpusd_h1_latest.html`

#### Renamed Files

- `docs/backtest_guide.md` → `docs/backtesting.md`
- `reports/DAY_8_FEATURE_ENGINEERING_GUIDE.md` → `reports/feature_engineering_findings.md`

#### Removed

- `__pycache__/` (root directory)
- `examples/__pycache__/`
- Cache directories now properly git-ignored

#### Documentation Changes

- **`README.md`** - Complete rewrite
  - Updated project structure diagram
  - Fixed all documentation links
  - Added production deployment quick start
  - Added directory index table
  - Clarified project status and learning path
- **`archive/README.md`** - Created to explain archived content
- **`dashboards/.gitignore`** - Ignore generated HTML files

### Changed

#### File Organization

- **Root directory**: Reduced from 45+ files to ~15 essential files
- **Documentation**: Consolidated from 26 files across 3 locations to:
  - 4 files in `docs/` (active guides)
  - 8 files in `reports/` (technical findings)
  - 14 files in `archive/docs/` (historical reference)
- **scripts/ vs examples/**: Clear separation
  - `scripts/` = Production utilities (data management, analysis)
  - `examples/` = Educational demos (backtest_demo.py, etc.)

#### Improved Structure

- Consolidated deployment scripts → single production entry point
- Merged overlapping documentation → coherent guide structure
- Organized test files → proper test/ hierarchy
- Separated generated files → dashboards/ directory

### Fixed

- Broken documentation links in README.md
- Test files in wrong locations (Python convention compliance)
- Unclear scripts/ vs examples/ distinction
- Cache directories tracked in git

---

## [1.0.0] - February 2026 - Production Release

### Added

- Production trading engine (`deploy_momentum_production.py`)
- FIX API integration with Pepperstone cTrader
- SQLite trade database with full audit trail
- Auto-reconnection with exponential backoff
- Position reconciliation on startup
- Dual mode operation (simulation/live)
- Trailing stop management
- Safety controls (position limits, daily loss caps)

### Infrastructure

- Event-driven architecture (EventQueue, BarEvent, SignalEvent, OrderEvent, FillEvent)
- Tick aggregator (real-time tick → bar conversion)
- Exhaustion momentum strategy
- Latency tracking (signal → fill timing)
- MAE/MFE calculation (Maximum Adverse/Favorable Excursion)

---

## Historical Releases

Prior to this changelog, the project evolved through several phases:

**Phase 1 (Early 2024)**: Research infrastructure

- Vectorized backtest engine
- Feature engineering library
- Data pipeline with validation
- Statistical analysis framework

**Phase 2 (Mid 2024)**: Strategy development

- Exhaustion reversal hypothesis
- Mean reversion strategies
- Paper trading validation (3,806 trades)

**Phase 3 (Late 2024-Early 2026)**: Production deployment

- Multiple deployment iterations (paper trading, multi-pair, live FIX)
- Feature accumulation and testing
- Infrastructure hardening

See `archive/docs/` for historical documentation of these phases.

---

## Git Commit Philosophy

**Format**: `type(scope): description`

**Types**:

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `refactor`: Code restructuring
- `test`: Adding tests
- `chore`: Maintenance (dependencies, cleanup)

**Example**: `refactor(structure): reorganize project directories and consolidate documentation`

---

_For older changes, see git commit history or archived documentation._
