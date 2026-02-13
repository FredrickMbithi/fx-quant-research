# FX Quant Research

Research codebase for FX quantitative strategies and backtests.

Repository layout:

- `data/` - raw, interim, processed datasets and swap rates
- `src/` - project source code (data ingestion, features, backtests, strategies, risk, execution, portfolio, utils)
- `notebooks/` - exploratory notebooks
- `experiments/` - experiment artifacts
- `reports/` - generated reports and figures
- `tests/` - unit and integration tests
- `services/` - external service integration (MT5 bridge, clients, monitoring)
- `config/` - YAML configuration files

Getting started

1. Create a virtual environment and activate it.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Run tests:

```bash
make test
```

3. See `Makefile` for common commands.
