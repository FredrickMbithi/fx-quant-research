# FX Quant Research

Production-grade FX quantitative trading system with real-time FIX execution, backtesting engine, and statistical research framework.

## 🚀 Quick Start

### Production Deployment

```bash
# Install dependencies
pip install -r requirements.txt

# Configure credentials (create .env file)
FIX_PASSWORD=your_password_here

# Test in simulation mode
python deploy_momentum_production.py --mode simulation

# Run live trading (demo account)
python deploy_momentum_production.py --mode live
```

**See**: [docs/deployment_guide.md](docs/deployment_guide.md) for complete setup

### Research & Backtesting

```bash
# Run example backtest
python examples/backtest_demo.py

# Run tests
make test
```

## 📁 Project Structure

```
fx-quant-research/
├── deploy_momentum_production.py  # Main production deployment
├── archive/               # Legacy deployment scripts
├── config/                # Configuration files
│   ├── config.yaml
│   ├── fix_sessions.cfg
│   └── brokers/          # Broker credentials
├── dashboards/            # Generated HTML reports (gitignored)
├── data/                  # Data storage
│   ├── raw/              # Raw OHLC data (CSV)
│   ├── processed/        # Cleaned data (PKL)
│   └── backtests/        # Backtest results
├── docs/                  # User guides & documentation
│   ├── deployment_guide.md      # Production deployment
│   ├── backtesting.md           # Backtest usage guide
│   ├── fix_setup.md             # FIX API credentials
│   └── project_charter.md       # Project goals
├── examples/              # Educational demos
│   ├── backtest_demo.py
│   ├── paper_trading_demo.py
│   └── trading_engine_demo.py
├── notebooks/             # Jupyter research notebooks
├── reports/               # Technical analysis & findings
│   ├── backtest_spec.md
│   ├── data_pipeline_spec.md
│   ├── feature_engineering_findings.md
│   └── ...
├── scripts/               # Production utilities
│   ├── download_multipair_data.py
│   ├── export_backtest_dashboard.py
│   ├── analyze_paper_results.py
│   └── ...
├── src/                   # Core library
│   ├── backtest/         # Backtest engine
│   ├── data/             # Data loaders
│   ├── events/           # Event system
│   ├── execution/        # FIX client & trading engine
│   ├── features/         # Feature engineering
│   ├── portfolio/        # Portfolio tracking
│   ├── risk/             # Risk management
│   ├── strategies/       # Trading strategies
│   └── utils/            # Utilities
├── state/                 # Runtime data
│   └── trades.db         # SQLite trade database
└── tests/                 # Unit & integration tests
    ├── integration/      # FIX & system integration tests
    └── ...
```

## ✨ Key Features

### Production Trading System

- ✅ **Real FIX API Integration** - Pepperstone cTrader connectivity
- ✅ **Dual Mode Operation** - Simulation (testing) & Live (real market)
- ✅ **SQLite Trade Database** - Full audit trail with P&L, latency, MAE/MFE
- ✅ **Auto-Reconnection** - Exponential backoff on connection loss
- ✅ **Position Reconciliation** - Sync positions on startup
- ✅ **Trailing Stops** - Dynamic exit management
- ✅ **Safety Controls** - Position limits, daily loss caps, quote staleness

**See**: [docs/deployment_guide.md](docs/deployment_guide.md)

**See**: [docs/deployment_guide.md](docs/deployment_guide.md)

### Research Infrastructure

- ✅ **Data Pipeline** - UTC normalized, lookahead bias prevention, validation
- ✅ **Feature Engineering** - 10+ indicators, stationarity-tested
- ✅ **Vectorized Backtest Engine** - Realistic costs, trade-level analysis
- ✅ **Exhaustion Strategy** - Momentum continuation ("trade with exhaustion")
- ✅ **Comprehensive Testing** - Unit, integration, and end-to-end tests

**See**: [docs/backtesting.md](docs/backtesting.md)

## 📚 Documentation

### User Guides ([docs/](docs/))

- **[deployment_guide.md](docs/deployment_guide.md)** - Production deployment (FIX API, modes, safety controls)
- **[fix_setup.md](docs/fix_setup.md)** - How to obtain FIX password from Pepperstone
- **[backtesting.md](docs/backtesting.md)** - Backtest engine usage guide
- **[project_charter.md](docs/project_charter.md)** - Project goals and success criteria

### Technical Reports ([reports/](reports/))

- **[backtest_spec.md](reports/backtest_spec.md)** - Backtest architecture
- **[data_pipeline_spec.md](reports/data_pipeline_spec.md)** - Data pipeline design
- **[feature_engineering_findings.md](reports/feature_engineering_findings.md)** - Feature engineering research
- **[stationarity_analysis.md](reports/stationarity_analysis.md)** - Statistical foundations
- **[autocorrelation_findings.md](reports/autocorrelation_findings.md)** - Volatility clustering
- **[fx_microstructure.md](reports/fx_microstructure.md)** - FX market mechanics
- **[EXHAUSTION_H1_FINAL_REPORT.md](reports/EXHAUSTION_H1_FINAL_REPORT.md)** - Strategy validation report

### Legacy Documentation ([archive/docs/](archive/docs/))

Historical guides preserved for reference (paper trading iterations, multi-pair implementations, etc.)

## 💻 Usage Examples

### Production Trading

```bash
# Simulation mode (safe testing)
python deploy_momentum_production.py --mode simulation

# Live trading (demo account)
python deploy_momentum_production.py --mode live

# Query trade database
sqlite3 state/trades.db
> SELECT * FROM trades ORDER BY entry_time DESC LIMIT 10;
```

### Research & Backtesting

```python
from src.data.loader import FXDataLoader
from src.backtest.engine import VectorizedBacktest, CostModel

# Load data
loader = FXDataLoader('data/raw')
df = loader.load('EURUSD', start_date='2023-01-01', end_date='2023-12-31')

# Generate features
from src.features.library import FeatureLibrary
lib = FeatureLibrary(df['close'])
features = lib.generate_all_features()

# Configure cost model
cost_model = CostModel({
    'commission_per_share': 0.0,
    'slippage_pct': 0.00009,  # 0.9 pips
})

# Run backtest
backtest = VectorizedBacktest(
    data=df,
    signal=features['momentum_20'],
    cost_model=cost_model,
    initial_capital=100000.0,
)

results = backtest.run()
print(f"Sharpe Ratio: {results['sharpe_ratio']:.2f}")
```

### Utility Scripts

```bash
# Download multi-pair data
python scripts/download_multipair_data.py

# Export backtest dashboard
python scripts/export_backtest_dashboard.py

# Analyze results
python scripts/analyze_paper_results.py
```

## 🎯 Current Strategy: Exhaustion Momentum

Trades **with** exhaustion bars (momentum continuation):

**Entry:**

- High pressure (2+ consecutive bars same direction)
- Range expansion (> 80th percentile)
- Close in entry zone (upper/lower 35%)

**Exit:**

- Hard stop: -10 pips
- Profit trigger: +4 pips → activate trailing
- Trailing: 3 pips
- Max hold: 25 minutes`

## Project Philosophy

From [project_charter.md](docs/project_charter.md):

1. **Reproducibility First** - All results must be reproducible from versioned code and data
2. **No Overfitting** - Simple models with economic intuition over complex optimization
3. **Transaction Costs Matter** - Always include realistic spreads and slippage
4. **Risk Before Return** - Sharpe ratio and drawdown are primary objectives

**Success Criteria:**

- Sharpe Ratio > 1.0 (out-of-sample)
- Maximum Drawdown < 15%
- Statistical significance p < 0.05
- Minimum 2 years OOS validation

## Development Commands

```bash
# Run all tests
make test

# Run specific test file
pytest tests/test_backtest.py -v

# Run with coverage
pytest --cov=src tests/

# Lint code
make lint

# Format code
make format
```

## 📊 Project Status

**Current Version**: Production deployment with live FIX trading

✅ **Complete:**

- Production trading engine (`deploy_momentum_production.py`)
- FIX API integration (Pepperstone cTrader)
- SQLite trade database with full audit trail
- Auto-reconnection and position reconciliation
- Exhaustion momentum strategy (validated)
- Vectorized backtest engine
- Feature engineering library
- Data pipeline with validation

🚧 **In Progress:**

- Multi-pair deployment scaling
- Walk-forward validation framework
- Advanced risk management features

## 📖 Project Philosophy

From [project_charter.md](docs/project_charter.md):

1. **Reproducibility First** - Versioned code and data
2. **No Overfitting** - Simple models with economic intuition
3. **Transaction Costs Matter** - Realistic spreads and slippage
4. **Risk Before Return** - Sharpe and drawdown are primary metrics

## 🎓 Learning Path

1. **Start**: [docs/deployment_guide.md](docs/deployment_guide.md) - Run production system
2. **Understand**: [docs/backtesting.md](docs/backtesting.md) - Backtest framework
3. **Deep Dive**: [reports/](reports/) - Technical analysis and findings
4. **Experiment**: [examples/](examples/) - Demo scripts
5. **Extend**: [docs/project_charter.md](docs/project_charter.md) - Project goals

## 🗂️ Directory Index

| Directory                  | Purpose                             | Key Files                                 |
| -------------------------- | ----------------------------------- | ----------------------------------------- |
| [archive/](archive/)       | Legacy code preserved for reference | Old deployment scripts, superseded docs   |
| [config/](config/)         | Configuration files                 | Broker credentials, FIX sessions          |
| [dashboards/](dashboards/) | Generated HTML reports (gitignored) | Backtest visualizations                   |
| [data/](data/)             | Market data storage                 | Raw CSVs, processed PKL, backtest results |
| [docs/](docs/)             | User guides                         | deployment_guide.md, fix_setup.md         |
| [examples/](examples/)     | Educational demos                   | backtest_demo.py, trading_engine_demo.py  |
| [notebooks/](notebooks/)   | Jupyter research                    | Statistical analysis, hypothesis testing  |
| [reports/](reports/)       | Technical findings                  | Specs, analysis, validation reports       |
| [scripts/](scripts/)       | Production utilities                | Data download, analysis, export tools     |
| [src/](src/)               | Core library                        | Backtest engine, strategies, FIX client   |
| [state/](state/)           | Runtime data                        | trades.db (SQLite)                        |
| [tests/](tests/)           | Automated tests                     | Unit tests, integration tests             |

## 📞 Support & Contributing

- Check [archive/docs/](archive/docs/) for historical context
- Review test files in `tests/` for code standards
- See [CHANGELOG.md](CHANGELOG.md) for recent changes

---

_Production-ready FX trading system | Last updated: February 25, 2026_
