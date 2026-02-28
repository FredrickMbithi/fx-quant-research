#!/bin/bash
# Quick deployment script for paper trading

set -e

echo "============================================================================="
echo "📊 EXHAUSTION REVERSAL PAPER TRADING DEPLOYMENT"
echo "============================================================================="

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if running from project root
if [ ! -f "deploy_paper_trading.py" ]; then
    echo -e "${RED}❌ Error: Must run from fx-quant-research directory${NC}"
    exit 1
fi

# Step 1: Check dependencies
echo -e "\n${YELLOW}[1/5] Checking dependencies...${NC}"
python -c "from src.features.exhaustion import ExhaustionDetector; from src.data.h1_loader import load_processed_data; print('✓ All imports OK')" || {
    echo -e "${RED}❌ Missing dependencies${NC}"
    exit 1
}

# Step 2: Check data
echo -e "\n${YELLOW}[2/5] Checking data availability...${NC}"
if [ ! -f "data/processed/GBPUSD_H1_processed.pkl" ]; then
    echo -e "${RED}❌ Processed data not found${NC}"
    echo "   Run data processing first:"
    echo "   python -c 'from src.data.h1_loader import H1DataLoader; loader = H1DataLoader(); df = loader.load_gbpusd_h1(); loader.save_processed(loader.prepare_for_backtest(df))'"
    exit 1
fi
echo -e "${GREEN}✓ Data file exists${NC}"

# Step 3: Check configuration
echo -e "\n${YELLOW}[3/5] Checking configuration...${NC}"
python -c "
import json
with open('config/paper_trading_config.json', 'r') as f:
    cfg = json.load(f)
    print(f'✓ Strategy: {cfg[\"strategy_name\"]}')
    print(f'✓ Capital: \${cfg[\"initial_capital\"]:,}')
    print(f'✓ Risk: {cfg[\"risk_per_trade_pct\"]*100:.1f}% per trade')
    
    # Warning if SL/TP not set
    if cfg['stop_loss_pips'] is None or cfg['take_profit_pips'] is None:
        print('⚠️  SL/TP not configured - using time-based exit only')
        print('   Run: python update_paper_config.py')
    else:
        print(f'✓ SL: {cfg[\"stop_loss_pips\"]} pips, TP: {cfg[\"take_profit_pips\"]} pips')
"

# Step 4: Create logs directory
echo -e "\n${YELLOW}[4/5] Setting up logging...${NC}"
mkdir -p logs
echo -e "${GREEN}✓ Logs directory ready${NC}"

# Step 5: Run simulation
echo -e "\n${YELLOW}[5/5] Launching paper trading simulation...${NC}"
echo "============================================================================="
echo ""

python deploy_paper_trading.py

echo ""
echo "============================================================================="
echo -e "${GREEN}✅ PAPER TRADING COMPLETE${NC}"
echo "============================================================================="
echo ""
echo "📁 Results saved to:"
echo "   - logs/paper_trades.csv     (Trade history)"
echo "   - logs/paper_trading.log    (Execution log)"
echo ""
echo "📊 Next steps:"
echo "   1. Review trade log: cat logs/paper_trades.csv"
echo "   2. Analyze performance: python analyze_paper_results.py"
echo "   3. If successful (>20 trades, positive PnL), proceed to live deployment"
echo ""
