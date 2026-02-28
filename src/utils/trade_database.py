"""
Trade Database - SQLite persistence for live trading

Stores:
- Trade executions (entry/exit, P&L, timing)
- Performance metrics
- System events
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime, UTC
from typing import Optional, Dict, List
from contextlib import contextmanager


class TradeDatabase:
    """SQLite database for trade logging and audit trail."""
    
    def __init__(self, db_path: str = "state/trades.db"):
        """
        Initialize database connection.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create tables if they don't exist
        self._create_tables()
    
    @contextmanager
    def _get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def _create_tables(self):
        """Create database schema."""
        with self._get_connection() as conn:
            # Trades table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id TEXT UNIQUE NOT NULL,
                    session_id TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    instrument TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    
                    -- Entry
                    entry_time TIMESTAMP NOT NULL,
                    entry_price REAL NOT NULL,
                    entry_size INTEGER NOT NULL,
                    
                    -- Exit
                    exit_time TIMESTAMP,
                    exit_price REAL,
                    exit_reason TEXT,
                    
                    -- P&L
                    pnl_pips REAL,
                    pnl_usd REAL,
                    commission_usd REAL DEFAULT 0.0,
                    slippage_pips REAL DEFAULT 0.0,
                    
                    -- Timing metrics
                    signal_time TIMESTAMP NOT NULL,
                    order_sent_time TIMESTAMP NOT NULL,
                    fill_received_time TIMESTAMP NOT NULL,
                    signal_to_fill_ms INTEGER,
                    hold_duration_minutes INTEGER,
                    
                    -- Exit extremes
                    mae_pips REAL,
                    mfe_pips REAL,
                    
                    -- Metadata
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT
                )
            """)
            
            # Sessions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT UNIQUE NOT NULL,
                    strategy TEXT NOT NULL,
                    start_time TIMESTAMP NOT NULL,
                    end_time TIMESTAMP,
                    
                    -- Configuration
                    initial_capital REAL NOT NULL,
                    position_size INTEGER NOT NULL,
                    risk_params TEXT,
                    detector_params TEXT,
                    
                    -- Performance
                    total_trades INTEGER DEFAULT 0,
                    winning_trades INTEGER DEFAULT 0,
                    losing_trades INTEGER DEFAULT 0,
                    total_pnl_usd REAL DEFAULT 0.0,
                    max_drawdown_usd REAL DEFAULT 0.0,
                    
                    -- System
                    mode TEXT NOT NULL,
                    git_commit TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # System events table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS system_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    event_time TIMESTAMP NOT NULL,
                    event_type TEXT NOT NULL,
                    severity TEXT DEFAULT 'INFO',
                    message TEXT NOT NULL,
                    details TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Market data table (for tick/bar logging)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS market_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    instrument TEXT NOT NULL,
                    data_type TEXT NOT NULL,
                    bid REAL,
                    ask REAL,
                    open_price REAL,
                    high REAL,
                    low REAL,
                    close_price REAL,
                    volume INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_session ON trades(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_instrument ON trades(instrument)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_entry_time ON trades(entry_time)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_session ON system_events(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_market_data_session ON market_data(session_id)")
    
    def create_session(self, session_id: str, strategy: str, config: Dict) -> None:
        """
        Create new trading session.
        
        Args:
            session_id: Unique session identifier
            strategy: Strategy name
            config: Session configuration dict
        """
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO sessions (
                    session_id, strategy, start_time, initial_capital,
                    position_size, risk_params, detector_params, mode, git_commit
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                strategy,
                datetime.now(UTC).isoformat(),
                config.get('initial_capital', 100000.0),
                config.get('position_size', 10000),
                json.dumps(config.get('risk_params', {})),
                json.dumps(config.get('detector_params', {})),
                config.get('mode', 'simulation'),
                config.get('git_commit', 'unknown')
            ))
    
    def log_trade_entry(self, trade_data: Dict) -> None:
        """
        Log trade entry.
        
        Args:
            trade_data: Dict with trade entry details
        """
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO trades (
                    trade_id, session_id, strategy, instrument, direction,
                    entry_time, entry_price, entry_size,
                    signal_time, order_sent_time, fill_received_time, signal_to_fill_ms,
                    metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade_data['trade_id'],
                trade_data['session_id'],
                trade_data.get('strategy', 'ExhaustionMomentum'),
                trade_data['instrument'],
                trade_data['direction'],
                trade_data['entry_time'],
                trade_data['entry_price'],
                trade_data['entry_size'],
                trade_data['signal_time'],
                trade_data['order_sent_time'],
                trade_data['fill_received_time'],
                trade_data.get('signal_to_fill_ms', 0),
                json.dumps(trade_data.get('metadata', {}))
            ))
    
    def log_trade_exit(self, trade_id: str, exit_data: Dict) -> None:
        """
        Log trade exit.
        
        Args:
            trade_id: Trade identifier
            exit_data: Dict with exit details
        """
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE trades SET
                    exit_time = ?,
                    exit_price = ?,
                    exit_reason = ?,
                    pnl_pips = ?,
                    pnl_usd = ?,
                    commission_usd = ?,
                    slippage_pips = ?,
                    hold_duration_minutes = ?,
                    mae_pips = ?,
                    mfe_pips = ?
                WHERE trade_id = ?
            """, (
                exit_data['exit_time'],
                exit_data['exit_price'],
                exit_data['exit_reason'],
                exit_data.get('pnl_pips', 0.0),
                exit_data.get('pnl_usd', 0.0),
                exit_data.get('commission_usd', 0.0),
                exit_data.get('slippage_pips', 0.0),
                exit_data.get('hold_duration_minutes', 0),
                exit_data.get('mae_pips', 0.0),
                exit_data.get('mfe_pips', 0.0),
                trade_id
            ))
            
            # Update session statistics
            self._update_session_stats(exit_data['session_id'])
    
    def _update_session_stats(self, session_id: str) -> None:
        """Update session-level statistics."""
        with self._get_connection() as conn:
            stats = conn.execute("""
                SELECT 
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) as winning_trades,
                    SUM(CASE WHEN pnl_usd < 0 THEN 1 ELSE 0 END) as losing_trades,
                    SUM(pnl_usd) as total_pnl
                FROM trades
                WHERE session_id = ? AND exit_time IS NOT NULL
            """, (session_id,)).fetchone()
            
            conn.execute("""
                UPDATE sessions SET
                    total_trades = ?,
                    winning_trades = ?,
                    losing_trades = ?,
                    total_pnl_usd = ?
                WHERE session_id = ?
            """, (
                stats['total_trades'],
                stats['winning_trades'],
                stats['losing_trades'],
                stats['total_pnl'] or 0.0,
                session_id
            ))
    
    def log_event(self, session_id: str, event_type: str, message: str, 
                  severity: str = 'INFO', details: Optional[Dict] = None) -> None:
        """
        Log system event.
        
        Args:
            session_id: Session identifier
            event_type: Event type (SIGNAL, ORDER, FILL, ERROR, etc.)
            message: Event message
            severity: INFO, WARNING, ERROR, CRITICAL
            details: Optional additional details
        """
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO system_events (
                    session_id, event_time, event_type, severity, message, details
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                datetime.now(UTC).isoformat(),
                event_type,
                severity,
                message,
                json.dumps(details) if details else None
            ))
    
    def log_market_data(self, session_id: str, instrument: str, 
                       data_type: str, data: Dict) -> None:
        """
        Log market data (ticks or bars).
        
        Args:
            session_id: Session identifier
            instrument: Instrument symbol
            data_type: 'tick' or 'bar'
            data: Market data dict
        """
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO market_data (
                    session_id, timestamp, instrument, data_type,
                    bid, ask, open_price, high, low, close_price, volume
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                data.get('timestamp', datetime.now(UTC).isoformat()),
                instrument,
                data_type,
                data.get('bid'),
                data.get('ask'),
                data.get('open'),
                data.get('high'),
                data.get('low'),
                data.get('close'),
                data.get('volume')
            ))
    
    def close_session(self, session_id: str) -> None:
        """Mark session as closed."""
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE sessions SET end_time = ?
                WHERE session_id = ?
            """, (datetime.now(UTC).isoformat(), session_id))
    
    def get_session_summary(self, session_id: str) -> Dict:
        """Get session performance summary."""
        with self._get_connection() as conn:
            session = conn.execute("""
                SELECT * FROM sessions WHERE session_id = ?
            """, (session_id,)).fetchone()
            
            if not session:
                return {}
            
            trades = conn.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN pnl_usd < 0 THEN 1 ELSE 0 END) as losses,
                    SUM(pnl_usd) as total_pnl,
                    AVG(pnl_pips) as avg_pnl_pips,
                    AVG(signal_to_fill_ms) as avg_latency_ms,
                    AVG(hold_duration_minutes) as avg_hold_minutes
                FROM trades
                WHERE session_id = ? AND exit_time IS NOT NULL
            """, (session_id,)).fetchone()
            
            return {
                'session_id': session['session_id'],
                'strategy': session['strategy'],
                'start_time': session['start_time'],
                'end_time': session['end_time'],
                'mode': session['mode'],
                'total_trades': trades['total'] or 0,
                'winning_trades': trades['wins'] or 0,
                'losing_trades': trades['losses'] or 0,
                'win_rate': (trades['wins'] or 0) / (trades['total'] or 1) * 100,
                'total_pnl_usd': trades['total_pnl'] or 0.0,
                'avg_pnl_pips': trades['avg_pnl_pips'] or 0.0,
                'avg_latency_ms': trades['avg_latency_ms'] or 0.0,
                'avg_hold_minutes': trades['avg_hold_minutes'] or 0.0
            }
    
    def get_recent_trades(self, session_id: str, limit: int = 50) -> List[Dict]:
        """Get recent trades for session."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM trades 
                WHERE session_id = ?
                ORDER BY entry_time DESC
                LIMIT ?
            """, (session_id, limit)).fetchall()
            
            return [dict(row) for row in rows]
