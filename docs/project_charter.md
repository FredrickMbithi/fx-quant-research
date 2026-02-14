FX Quant Research System
Project Charter

1. Project Goal
   Build a statistically robust, production-ready foreign exchange trading system that demonstrates consistent alpha generation through rigorous quantitative methods. The system will prioritize statistical validity, reproducibility, and risk management over raw performance metrics.
2. Project Scope
   2.1 In Scope
   • Timeframes: Daily and 4-hour bars only
   • Instruments: FX major pairs (EUR/USD, GBP/USD, USD/JPY, USD/CHF, AUD/USD, USD/CAD, NZD/USD)
   • Strategy types: Mean reversion, momentum, carry, and statistical arbitrage
   • Data sources: MetaTrader 5 historical data and real-time feeds
   • Execution: Automated via MT5 bridge
   • Risk management: Position sizing, stop-loss, portfolio-level exposure limits
   2.2 Out of Scope
   • Intraday timeframes below 4 hours
   • Exotic currency pairs
   • High-frequency trading strategies
   • Options, futures, or other derivative instruments
   • Machine learning models (initial phase; may be added later)
3. Success Criteria
   The system will be considered successful when it meets ALL of the following quantitative benchmarks on out-of-sample data:
   • Sharpe Ratio > 1.0 (measured on daily returns, risk-free rate = 0)
   • Maximum Drawdown < 15% (peak-to-trough decline in equity)
   • Out-of-Sample Period: Minimum 2 years of unseen data
   • Statistical Significance: p-value < 0.05 on returns vs. zero mean (t-test)
   • Win Rate: No specific target, but must be positive expectancy (avg win > avg loss × loss rate)
   • Turnover: < 20 trades per instrument per year (to minimize transaction costs)
   3.1 Additional Quality Metrics
   • Sortino Ratio > 1.5 (downside risk-adjusted returns)
   • Calmar Ratio > 0.5 (annual return / max drawdown)
   • Positive returns in at least 60% of rolling 12-month periods
   • No catastrophic single-day loss > 5% of equity
4. Failure Criteria & Shutdown Triggers
   The project will be halted or the system decommissioned if ANY of the following conditions are met:
   4.1 Statistical Drift Detection
   • Rolling Sharpe Ratio: Falls below 0.5 for 3 consecutive months
   • Return Distribution Shift: Kolmogorov-Smirnov test p-value < 0.05 comparing recent 6-month returns to training distribution
   • Feature Drift: Population Stability Index (PSI) > 0.25 for key strategy features
   4.2 Risk Management Breaches
   • Drawdown Breach: Exceeds 20% (5% buffer above success threshold)
   • Single Loss Event: Any single trade loss > 10% of account equity
   • Consecutive Losses: 10 or more consecutive losing trades
   4.3 Operational Failures
   • Data Quality: More than 5% missing or corrupted data in a rolling 30-day window
   • Execution Slippage: Average slippage exceeds 2 pips on EUR/USD for 20 consecutive trades
   • System Downtime: More than 48 hours of unplanned downtime in a rolling 90-day period
   4.4 Market Regime Change
   • Volatility Regime Shift: Realized volatility moves outside [0.5×, 2.0×] of training period median for > 60 days
   • Correlation Breakdown: Cross-pair correlations deviate by > 0.3 from historical norms for > 90 days
5. Research Philosophy
   • Reproducibility First: Every result must be reproducible from pinned dependencies and versioned data
   • No Overfitting: Limit hyperparameter tuning; prefer simple models with strong economic intuition
   • Walk-Forward Testing: Continuously validate on unseen data; never re-optimize on OOS periods
   • Transaction Costs Matter: Always include realistic spread, slippage, and commission in backtests
   • Risk Before Return: Sharpe ratio and drawdown are primary objectives; absolute return is secondary
6. Project Timeline
   • Phase 1 (Days 1-7): Infrastructure, data pipeline, exploratory analysis
   • Phase 2 (Days 8-14): Strategy development, backtesting framework
   • Phase 3 (Days 15-21): Walk-forward validation, risk management integration
   • Phase 4 (Days 22+): Production deployment, paper trading, continuous monitoring
7. Stakeholders & Review Cadence
   • Primary Researcher: Responsible for model development and backtesting
   • Weekly Reviews: Assess progress against success criteria, identify blocking issues
   • Go/No-Go Decision Point: End of Phase 3 (Day 21) - proceed to live trading only if all success criteria met on OOS data
8. Appendix: Definitions
   • Sharpe Ratio: (Mean daily return - risk-free rate) / Standard deviation of daily returns × √252
   • Maximum Drawdown: Largest peak-to-trough decline in equity curve
   • Out-of-Sample (OOS): Data that was never used during strategy development or parameter optimization
   • Population Stability Index (PSI): Measure of distribution shift between training and live data (PSI > 0.25 indicates significant drift)
