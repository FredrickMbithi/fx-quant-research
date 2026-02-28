# Execution Layer

Live trading execution infrastructure for FX automated trading.

## Components

### Event System (`../events/`)

- **Event types**: Tick, Bar, Signal, Order, Fill
- **EventQueue**: Thread-safe FIFO queue for event-driven architecture
- **Purpose**: Asynchronous processing of market data, signals, and executions

### Paper Trading Simulator (`simulator.py`)

- **Purpose**: Simulates order fills without risking real capital
- **Features**:
  - Realistic fill delays (100ms-2s)
  - Applies slippage and commission matching backtest CostModel
  - Bid/ask spread modeling (buy at ask, sell at bid)
  - Thread-safe asynchronous fills
- **Usage**: Set `paper_trading: true` in broker config

### FIX Protocol Components (TODO)

- **fix_client.py**: FIX session management (Logon, Heartbeat, Logout)
- **market_data.py**: FIX market data handler (MarketDataRequest/Snapshot)
- **broker_adapters/**: Broker-specific FIX implementations
  - `pepperstone_fix.py`: Pepperstone cTrader FIX adapter

## Workflow

```
Market Data → TickEvent → BarEvent → SignalEvent → OrderEvent → FillEvent → Portfolio Update
      ↓                        ↓            ↓            ↓            ↓
  FIX Client          Bar Aggregator   Strategy   Risk Manager  Simulator/Broker
```

## Configuration

See `config/brokers/pepperstone_fix.yaml` for:

- Connection settings (host, ports, credentials)
- Trading mode (paper vs live)
- Risk limits
- Execution parameters (slippage, commission)

## Testing

```python
from src.events import EventQueue, OrderEvent, OrderSide, OrderType
from src.execution.simulator import PaperTradingSimulator

# Initialize
queue = EventQueue()
simulator = PaperTradingSimulator('config/brokers/pepperstone_fix.yaml', queue)

# Update market price
simulator.update_market_price('EURUSD', bid=1.08450, ask=1.08452)

# Create and execute order
order = OrderEvent(
    symbol='EURUSD',
    order_type=OrderType.MARKET,
    side=OrderSide.BUY,
    quantity=10000  # 0.1 lot
)
simulator.execute_order(order)

# Wait for fill event
fill = queue.get(timeout=5.0)
print(f"Order filled: {fill}")
```

## Safety Features

- **Paper trading mode**: All orders simulated (default)
- **Risk limits**: Max drawdown, position exposure checks
- **Configuration-based**: Toggle live trading via config file
- **Logging**: All orders and fills logged for audit

## Next Steps

1. Implement FIX client for real market data
2. Build strategy framework for signal generation
3. Implement portfolio state manager
4. Add risk management layer
5. Integration testing with paper trading
6. Enable live trading (requires thorough validation)
