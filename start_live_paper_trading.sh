#!/bin/bash
# Quick deployment script for live exhaustion paper trading
# This automates the setup and launch process

set -e  # Exit on error

echo "========================================"
echo "LIVE EXHAUSTION PAPER TRADING DEPLOYMENT"
echo "========================================"
echo ""

# Check .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found!"
    echo ""
    echo "Creating .env from template..."
    cp .env.example .env
    echo ""
    echo "❌ STOP: You must edit .env and add your FIX_PASSWORD"
    echo ""
    echo "1. Open .env file"
    echo "2. Replace 'your_fix_password_here' with your actual password"
    echo "3. Save and run this script again"
    echo ""
    exit 1
fi

# Check FIX_PASSWORD is set
if grep -q "your_fix_password_here" .env; then
    echo "❌ ERROR: .env still has placeholder password!"
    echo ""
    echo "Edit .env and replace 'your_fix_password_here' with real password"
    echo ""
    exit 1
fi

echo "✅ .env file configured"

# Check database directory
if [ ! -d state ]; then
    echo "Creating state/ directory..."
    mkdir -p state
fi

if [ ! -d logs ]; then
    echo "Creating logs/ directory..."
    mkdir -p logs
fi

echo "✅ Directories ready"
echo ""

# Test FIX connection (optional)
read -p "Test FIX connection first? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Testing FIX connection..."
    python test_fix_logon.py
    echo ""
fi

# Choose mode
echo "Select trading mode:"
echo "  1) Paper Trading (RECOMMENDED - logs only, no real orders)"
echo "  2) Live Trading (⚠️  WARNING - real orders to broker!)"
echo ""
read -p "Enter choice (1 or 2): " -n 1 -r
echo ""

if [[ $REPLY == "1" ]]; then
    MODE="paper"
    echo "✅ Paper trading mode selected"
elif [[ $REPLY == "2" ]]; then
    MODE="live"
    echo "⚠️  LIVE TRADING MODE - Real orders will be sent!"
    read -p "Are you absolutely sure? (yes/no): " CONFIRM
    if [[ $CONFIRM != "yes" ]]; then
        echo "Cancelled."
        exit 0
    fi
else
    echo "Invalid choice"
    exit 1
fi

echo ""

# Choose symbols
echo "Select symbols to trade:"
echo "  1) NZDJPY only (RECOMMENDED - better performance)"
echo "  2) GBPUSD only (marginal performance, needs optimization)"
echo "  3) Both NZDJPY + GBPUSD"
echo ""
read -p "Enter choice (1, 2, or 3): " -n 1 -r
echo ""

if [[ $REPLY == "1" ]]; then
    SYMBOLS="NZDJPY"
elif [[ $REPLY == "2" ]]; then
    SYMBOLS="GBPUSD"
elif [[ $REPLY == "3" ]]; then
    SYMBOLS="NZDJPY,GBPUSD"
else
    echo "Invalid choice, defaulting to NZDJPY"
    SYMBOLS="NZDJPY"
fi

echo "✅ Symbols: $SYMBOLS"
echo ""

# Summary
echo "========================================"
echo "DEPLOYMENT SUMMARY"
echo "========================================"
echo "Mode:    $MODE"
echo "Symbols: $SYMBOLS"
echo "Capital: \$100,000"
echo "Risk:    1% per trade"
echo ""
echo "Starting in 3 seconds..."
echo "(Press Ctrl+C to cancel)"
sleep 3

# Launch
echo ""
echo "🚀 LAUNCHING LIVE TRADER..."
echo ""
python deploy_exhaustion_live_paper.py --mode $MODE --symbols $SYMBOLS

echo ""
echo "Trading session ended."
