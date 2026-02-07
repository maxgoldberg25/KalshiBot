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

    async def __aenter__(self) -> Repository:
        await self.connect()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()
