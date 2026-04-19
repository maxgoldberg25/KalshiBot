"""
SQLite persistence layer.

Stores:
- Kalshi contracts
- Odds quotes
- Alerts history
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
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
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                email TEXT UNIQUE,
                password_salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_login_at TEXT,
                is_admin INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1
            )
        """)
        await self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)"
        )
        for column_sql in (
            "ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE users ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1",
        ):
            try:
                await self._conn.execute(column_sql)
            except Exception:
                pass

        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS waitlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                email TEXT,
                reason TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                decided_at TEXT,
                decided_by_user_id INTEGER,
                invite_token TEXT UNIQUE,
                invite_expires_at TEXT,
                ip_hash TEXT,
                FOREIGN KEY(decided_by_user_id) REFERENCES users(id) ON DELETE SET NULL
            )
        """)
        await self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_waitlist_status_created ON waitlist(status, created_at)"
        )
        await self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_waitlist_username ON waitlist(username)"
        )

        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        await self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)"
        )

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

    async def get_last_alert_edge(self, market_key: str, direction: str) -> Optional[float]:
        """Return edge_bps of the most recent alert for (market_key, direction), or None."""
        assert self._conn is not None
        cursor = await self._conn.execute(
            """
            SELECT edge_bps FROM alerts
            WHERE market_key = ? AND direction = ?
            ORDER BY timestamp DESC LIMIT 1
            """,
            (market_key, direction),
        )
        row = await cursor.fetchone()
        return float(row[0]) if row else None

    async def should_alert(self, market_key: str, direction: str, edge_bps: float, threshold_bps: float = 20.0) -> bool:
        """True if no prior alert exists or edge changed by more than threshold_bps."""
        last = await self.get_last_alert_edge(market_key, direction)
        if last is None:
            return True
        return abs(edge_bps - last) >= threshold_bps

    async def get_expired_contract_ids(self) -> set[str]:
        """Return contract_ids whose close_time is in the past."""
        assert self._conn is not None
        now_iso = datetime.now(timezone.utc).isoformat()
        cursor = await self._conn.execute(
            "SELECT contract_id FROM kalshi_contracts WHERE close_time IS NOT NULL AND close_time < ?",
            (now_iso,),
        )
        rows = await cursor.fetchall()
        return {row[0] for row in rows}

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

    async def create_user(
        self,
        username: str,
        email: Optional[str],
        password_salt: str,
        password_hash: str,
    ) -> dict:
        """Insert a user. Raises sqlite3.IntegrityError on duplicate username/email."""
        assert self._conn is not None
        now = datetime.now(timezone.utc).isoformat()
        await self._conn.execute(
            """
            INSERT INTO users (username, email, password_salt, password_hash, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (username, email, password_salt, password_hash, now),
        )
        await self._conn.commit()
        cur = await self._conn.execute("SELECT last_insert_rowid()")
        row = await cur.fetchone()
        user_id = int(row[0]) if row else 0
        return {"id": user_id, "username": username, "email": email, "created_at": now}

    async def get_user_by_username(self, username: str) -> Optional[dict]:
        assert self._conn is not None
        cur = await self._conn.execute(
            "SELECT id, username, email, password_salt, password_hash, created_at, "
            "last_login_at, is_admin, is_active FROM users WHERE username = ?",
            (username,),
        )
        row = await cur.fetchone()
        if not row:
            return None
        return {
            "id": int(row[0]),
            "username": row[1],
            "email": row[2],
            "password_salt": row[3],
            "password_hash": row[4],
            "created_at": row[5],
            "last_login_at": row[6],
            "is_admin": bool(row[7]),
            "is_active": bool(row[8]),
        }

    async def get_user_by_id(self, user_id: int) -> Optional[dict]:
        assert self._conn is not None
        cur = await self._conn.execute(
            "SELECT id, username, email, created_at, last_login_at, is_admin, is_active "
            "FROM users WHERE id = ?",
            (user_id,),
        )
        row = await cur.fetchone()
        if not row:
            return None
        return {
            "id": int(row[0]),
            "username": row[1],
            "email": row[2],
            "created_at": row[3],
            "last_login_at": row[4],
            "is_admin": bool(row[5]),
            "is_active": bool(row[6]),
        }

    async def touch_user_login(self, user_id: int) -> None:
        assert self._conn is not None
        await self._conn.execute(
            "UPDATE users SET last_login_at = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), user_id),
        )
        await self._conn.commit()

    async def create_session(self, user_id: int, token: str, expires_at: datetime) -> None:
        assert self._conn is not None
        await self._conn.execute(
            "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (
                token,
                user_id,
                datetime.now(timezone.utc).isoformat(),
                expires_at.isoformat(),
            ),
        )
        await self._conn.commit()

    async def get_session_user(self, token: str) -> Optional[dict]:
        """Return the user owning this session token if the session is not expired and active."""
        assert self._conn is not None
        cur = await self._conn.execute(
            """
            SELECT u.id, u.username, u.email, u.created_at, u.last_login_at,
                   u.is_admin, u.is_active, s.expires_at
            FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token = ?
            """,
            (token,),
        )
        row = await cur.fetchone()
        if not row:
            return None
        try:
            expires = datetime.fromisoformat(row[7])
        except (TypeError, ValueError):
            return None
        if expires < datetime.now(timezone.utc):
            await self.delete_session(token)
            return None
        if not bool(row[6]):
            # deactivated user - invalidate all their sessions
            await self._conn.execute(
                "DELETE FROM sessions WHERE user_id = ?", (int(row[0]),)
            )
            await self._conn.commit()
            return None
        return {
            "id": int(row[0]),
            "username": row[1],
            "email": row[2],
            "created_at": row[3],
            "last_login_at": row[4],
            "is_admin": bool(row[5]),
            "is_active": bool(row[6]),
        }

    async def delete_session(self, token: str) -> None:
        assert self._conn is not None
        await self._conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        await self._conn.commit()

    async def purge_expired_sessions(self) -> int:
        assert self._conn is not None
        now_iso = datetime.now(timezone.utc).isoformat()
        cur = await self._conn.execute(
            "DELETE FROM sessions WHERE expires_at < ?", (now_iso,)
        )
        await self._conn.commit()
        return cur.rowcount or 0

    # ── Waitlist & admin ────────────────────────────────────────────────────

    async def create_waitlist_entry(
        self,
        *,
        username: str,
        email: Optional[str],
        reason: Optional[str],
        ip_hash: Optional[str],
    ) -> dict:
        assert self._conn is not None
        now = datetime.now(timezone.utc).isoformat()
        await self._conn.execute(
            """
            INSERT INTO waitlist (username, email, reason, status, created_at, ip_hash)
            VALUES (?, ?, ?, 'pending', ?, ?)
            """,
            (username, email, reason, now, ip_hash),
        )
        await self._conn.commit()
        cur = await self._conn.execute("SELECT last_insert_rowid()")
        row = await cur.fetchone()
        return {
            "id": int(row[0]) if row else 0,
            "username": username,
            "email": email,
            "reason": reason,
            "status": "pending",
            "created_at": now,
        }

    async def count_recent_waitlist_by_ip(self, ip_hash: str, since_iso: str) -> int:
        assert self._conn is not None
        cur = await self._conn.execute(
            "SELECT COUNT(*) FROM waitlist WHERE ip_hash = ? AND created_at >= ?",
            (ip_hash, since_iso),
        )
        row = await cur.fetchone()
        return int(row[0]) if row else 0

    async def list_waitlist(self, status: Optional[str] = None) -> list[dict]:
        assert self._conn is not None
        if status:
            cur = await self._conn.execute(
                "SELECT id, username, email, reason, status, created_at, decided_at, "
                "decided_by_user_id, invite_token, invite_expires_at "
                "FROM waitlist WHERE status = ? ORDER BY created_at DESC",
                (status,),
            )
        else:
            cur = await self._conn.execute(
                "SELECT id, username, email, reason, status, created_at, decided_at, "
                "decided_by_user_id, invite_token, invite_expires_at "
                "FROM waitlist ORDER BY created_at DESC"
            )
        rows = await cur.fetchall()
        return [
            {
                "id": int(r[0]),
                "username": r[1],
                "email": r[2],
                "reason": r[3],
                "status": r[4],
                "created_at": r[5],
                "decided_at": r[6],
                "decided_by_user_id": r[7],
                "invite_token": r[8],
                "invite_expires_at": r[9],
            }
            for r in rows
        ]

    async def get_waitlist_entry(self, entry_id: int) -> Optional[dict]:
        assert self._conn is not None
        cur = await self._conn.execute(
            "SELECT id, username, email, reason, status, created_at, decided_at, "
            "decided_by_user_id, invite_token, invite_expires_at "
            "FROM waitlist WHERE id = ?",
            (entry_id,),
        )
        r = await cur.fetchone()
        if not r:
            return None
        return {
            "id": int(r[0]),
            "username": r[1],
            "email": r[2],
            "reason": r[3],
            "status": r[4],
            "created_at": r[5],
            "decided_at": r[6],
            "decided_by_user_id": r[7],
            "invite_token": r[8],
            "invite_expires_at": r[9],
        }

    async def approve_waitlist_entry(
        self,
        entry_id: int,
        *,
        decided_by_user_id: int,
        invite_token: str,
        invite_expires_at: datetime,
    ) -> Optional[dict]:
        assert self._conn is not None
        now = datetime.now(timezone.utc).isoformat()
        cur = await self._conn.execute(
            """
            UPDATE waitlist
            SET status = 'approved',
                decided_at = ?,
                decided_by_user_id = ?,
                invite_token = ?,
                invite_expires_at = ?
            WHERE id = ? AND status = 'pending'
            """,
            (now, decided_by_user_id, invite_token, invite_expires_at.isoformat(), entry_id),
        )
        await self._conn.commit()
        if cur.rowcount == 0:
            return None
        return await self.get_waitlist_entry(entry_id)

    async def reject_waitlist_entry(
        self, entry_id: int, *, decided_by_user_id: int
    ) -> Optional[dict]:
        assert self._conn is not None
        now = datetime.now(timezone.utc).isoformat()
        cur = await self._conn.execute(
            """
            UPDATE waitlist
            SET status = 'rejected', decided_at = ?, decided_by_user_id = ?
            WHERE id = ? AND status = 'pending'
            """,
            (now, decided_by_user_id, entry_id),
        )
        await self._conn.commit()
        if cur.rowcount == 0:
            return None
        return await self.get_waitlist_entry(entry_id)

    async def consume_invite_token(self, token: str) -> Optional[dict]:
        """Return the waitlist entry if the token is valid and unused; mark as consumed."""
        assert self._conn is not None
        cur = await self._conn.execute(
            "SELECT id, username, email, status, invite_expires_at "
            "FROM waitlist WHERE invite_token = ?",
            (token,),
        )
        row = await cur.fetchone()
        if not row:
            return None
        entry_id, username, email, status, expires_iso = row
        if status != "approved":
            return None
        try:
            expires = datetime.fromisoformat(expires_iso) if expires_iso else None
        except (TypeError, ValueError):
            expires = None
        if expires is None or expires < datetime.now(timezone.utc):
            return None
        now = datetime.now(timezone.utc).isoformat()
        upd = await self._conn.execute(
            "UPDATE waitlist SET status = 'consumed', decided_at = ? "
            "WHERE id = ? AND status = 'approved'",
            (now, int(entry_id)),
        )
        await self._conn.commit()
        if upd.rowcount == 0:
            return None
        return {"id": int(entry_id), "username": username, "email": email}

    async def list_users(self) -> list[dict]:
        assert self._conn is not None
        cur = await self._conn.execute(
            "SELECT id, username, email, created_at, last_login_at, is_admin, is_active "
            "FROM users ORDER BY created_at DESC"
        )
        rows = await cur.fetchall()
        return [
            {
                "id": int(r[0]),
                "username": r[1],
                "email": r[2],
                "created_at": r[3],
                "last_login_at": r[4],
                "is_admin": bool(r[5]),
                "is_active": bool(r[6]),
            }
            for r in rows
        ]

    async def set_user_admin(self, user_id: int, is_admin: bool) -> None:
        assert self._conn is not None
        await self._conn.execute(
            "UPDATE users SET is_admin = ? WHERE id = ?",
            (1 if is_admin else 0, user_id),
        )
        await self._conn.commit()

    async def set_user_active(self, user_id: int, is_active: bool) -> None:
        assert self._conn is not None
        await self._conn.execute(
            "UPDATE users SET is_active = ? WHERE id = ?",
            (1 if is_active else 0, user_id),
        )
        if not is_active:
            await self._conn.execute(
                "DELETE FROM sessions WHERE user_id = ?", (user_id,)
            )
        await self._conn.commit()

    async def promote_admin_by_username(self, username: str) -> bool:
        assert self._conn is not None
        cur = await self._conn.execute(
            "UPDATE users SET is_admin = 1 WHERE LOWER(username) = LOWER(?)",
            (username,),
        )
        await self._conn.commit()
        return (cur.rowcount or 0) > 0

    async def __aenter__(self) -> Repository:
        await self.connect()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()
