"""
SQLite persistence layer.

Stores:
- Kalshi contracts
- Odds quotes
- Alerts history
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiosqlite

from kalshi_odds.models.kalshi import KalshiContract, KalshiTopOfBook
from kalshi_odds.models.odds import OddsQuote
from kalshi_odds.models.comparison import Alert
from kalshi_odds.core.portfolio import Position, PositionStatus, PnLSummary


class Repository:
    """Async SQLite repository."""

    def __init__(self, db_path: str = "kalshi_odds.db") -> None:
        self.db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None

    async def connect(self) -> None:
        """Initialize database and create tables."""
        self._conn = await aiosqlite.connect(self.db_path)
        await self._create_tables()

    async def close(self) -> None:
        """Close connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def _create_tables(self) -> None:
        """Create tables if they don't exist."""
        assert self._conn is not None

        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS kalshi_contracts (
                contract_id TEXT PRIMARY KEY,
                kalshi_market_id TEXT,
                title TEXT,
                outcome_side TEXT,
                close_time TEXT,
                status TEXT,
                last_price REAL,
                fetched_at TEXT,
                data_json TEXT
            )
        """)

        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS odds_quotes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT,
                bookmaker TEXT,
                event_id TEXT,
                market_type TEXT,
                selection TEXT,
                odds_format TEXT,
                odds_value REAL,
                timestamp TEXT,
                data_json TEXT
            )
        """)

        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                alert_id TEXT PRIMARY KEY,
                timestamp TEXT,
                market_key TEXT,
                direction TEXT,
                edge_pct REAL,
                edge_bps REAL,
                confidence TEXT,
                confidence_score REAL,
                kalshi_contract_id TEXT,
                sportsbook_bookmaker TEXT,
                data_json TEXT
            )
        """)

        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                direction TEXT NOT NULL,
                shares INTEGER NOT NULL,
                entry_price_cents INTEGER NOT NULL,
                market_key TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'open',
                entered_at TEXT NOT NULL,
                settled_at TEXT,
                realized_pnl REAL,
                notes TEXT DEFAULT ''
            )
        """)
        await self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_positions_ticker_open ON positions(ticker, status)"
        )

        await self._conn.commit()

    async def save_kalshi_contract(self, contract: KalshiContract) -> None:
        """Save or update a Kalshi contract."""
        assert self._conn is not None

        await self._conn.execute(
            """
            INSERT OR REPLACE INTO kalshi_contracts
            (contract_id, kalshi_market_id, title, outcome_side, close_time, status, last_price, fetched_at, data_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                contract.contract_id,
                contract.kalshi_market_id,
                contract.title,
                contract.outcome_side.value,
                contract.close_time.isoformat() if contract.close_time else None,
                contract.status,
                contract.last_price,
                contract.fetched_at.isoformat() if contract.fetched_at else None,
                contract.model_dump_json(),
            ),
        )
        await self._conn.commit()

    async def save_odds_quote(self, quote: OddsQuote) -> None:
        """Save an odds quote."""
        assert self._conn is not None

        await self._conn.execute(
            """
            INSERT INTO odds_quotes
            (source, bookmaker, event_id, market_type, selection, odds_format, odds_value, timestamp, data_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                quote.source,
                quote.bookmaker,
                quote.event_id,
                quote.market_type.value,
                quote.selection,
                quote.odds_format.value,
                quote.odds_value,
                quote.timestamp.isoformat(),
                quote.model_dump_json(),
            ),
        )
        await self._conn.commit()

    async def save_alert(self, alert: Alert) -> None:
        """Save an alert."""
        assert self._conn is not None

        await self._conn.execute(
            """
            INSERT OR REPLACE INTO alerts
            (alert_id, timestamp, market_key, direction, edge_pct, edge_bps, confidence, confidence_score, kalshi_contract_id, sportsbook_bookmaker, data_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                alert.alert_id,
                alert.timestamp.isoformat(),
                alert.market_key,
                alert.direction.value,
                alert.edge_pct,
                alert.edge_bps,
                alert.confidence.value,
                alert.confidence_score,
                alert.kalshi_contract_id,
                alert.sportsbook_bookmaker,
                alert.model_dump_json(),
            ),
        )
        await self._conn.commit()

    async def get_recent_alerts(self, limit: int = 20) -> list[Alert]:
        """Get recent alerts."""
        assert self._conn is not None

        cursor = await self._conn.execute(
            "SELECT data_json FROM alerts ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        rows = await cursor.fetchall()
        
        alerts = []
        for row in rows:
            data = json.loads(row[0])
            alerts.append(Alert(**data))
        
        return alerts

    async def save_position(self, position: Position) -> int:
        """Insert a position and return its row id."""
        assert self._conn is not None
        await self._conn.execute(
            """
            INSERT INTO positions
            (ticker, direction, shares, entry_price_cents, market_key, status, entered_at, settled_at, realized_pnl, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                position.ticker,
                position.direction.value,
                position.shares,
                position.entry_price_cents,
                position.market_key,
                position.status.value,
                position.entered_at.isoformat(),
                position.settled_at.isoformat() if position.settled_at else None,
                position.realized_pnl,
                position.notes,
            ),
        )
        await self._conn.commit()
        cur = await self._conn.execute("SELECT last_insert_rowid()")
        row = await cur.fetchone()
        return int(row[0]) if row else 0

    async def has_open_position(self, ticker: str, direction: str) -> bool:
        """True if an open row exists for this ticker and direction (dedupe auto-exec)."""
        assert self._conn is not None
        cursor = await self._conn.execute(
            """
            SELECT 1 FROM positions
            WHERE ticker = ? AND direction = ? AND status = ?
            LIMIT 1
            """,
            (ticker, direction, PositionStatus.OPEN.value),
        )
        row = await cursor.fetchone()
        return row is not None

    async def get_open_positions(self) -> list[Position]:
        assert self._conn is not None
        from kalshi_odds.models.comparison import Direction

        cursor = await self._conn.execute(
            """
            SELECT id, ticker, direction, shares, entry_price_cents, market_key, status, entered_at, settled_at, realized_pnl, notes
            FROM positions WHERE status = ? ORDER BY entered_at DESC
            """,
            (PositionStatus.OPEN.value,),
        )
        rows = await cursor.fetchall()
        out: list[Position] = []
        for row in rows:
            out.append(
                Position(
                    id=row[0],
                    ticker=row[1],
                    direction=Direction(row[2]),
                    shares=row[3],
                    entry_price_cents=row[4],
                    market_key=row[5] or "",
                    status=PositionStatus(row[6]),
                    entered_at=datetime.fromisoformat(row[7]),
                    settled_at=datetime.fromisoformat(row[8]) if row[8] else None,
                    realized_pnl=row[9],
                    notes=row[10] or "",
                )
            )
        return out

    async def get_settled_positions(self, limit: int = 100) -> list[Position]:
        assert self._conn is not None
        from kalshi_odds.models.comparison import Direction

        cursor = await self._conn.execute(
            """
            SELECT id, ticker, direction, shares, entry_price_cents, market_key, status, entered_at, settled_at, realized_pnl, notes
            FROM positions WHERE status = ? ORDER BY COALESCE(settled_at, entered_at) DESC LIMIT ?
            """,
            (PositionStatus.SETTLED.value, limit),
        )
        rows = await cursor.fetchall()
        out: list[Position] = []
        for row in rows:
            out.append(
                Position(
                    id=row[0],
                    ticker=row[1],
                    direction=Direction(row[2]),
                    shares=row[3],
                    entry_price_cents=row[4],
                    market_key=row[5] or "",
                    status=PositionStatus(row[6]),
                    entered_at=datetime.fromisoformat(row[7]),
                    settled_at=datetime.fromisoformat(row[8]) if row[8] else None,
                    realized_pnl=row[9],
                    notes=row[10] or "",
                )
            )
        return out

    async def get_pnl_summary(self) -> PnLSummary:
        assert self._conn is not None
        open_cur = await self._conn.execute(
            "SELECT COUNT(*) FROM positions WHERE status = ?",
            (PositionStatus.OPEN.value,),
        )
        open_row = await open_cur.fetchone()
        open_count = int(open_row[0]) if open_row else 0

        settled_cur = await self._conn.execute(
            """
            SELECT COUNT(*), COALESCE(SUM(realized_pnl), 0),
                   SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END),
                   SUM(CASE WHEN realized_pnl < 0 THEN 1 ELSE 0 END)
            FROM positions WHERE status = ? AND realized_pnl IS NOT NULL
            """,
            (PositionStatus.SETTLED.value,),
        )
        settled_row = await settled_cur.fetchone()
        settled_count = int(settled_row[0]) if settled_row else 0
        total = float(settled_row[1]) if settled_row and settled_row[1] is not None else 0.0
        winning = int(settled_row[2]) if settled_row and settled_row[2] is not None else 0
        losing = int(settled_row[3]) if settled_row and settled_row[3] is not None else 0

        return PnLSummary(
            total_realized_pnl=total,
            settled_count=settled_count,
            open_count=open_count,
            winning_count=winning,
            losing_count=losing,
        )

    async def __aenter__(self) -> Repository:
        await self.connect()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()
