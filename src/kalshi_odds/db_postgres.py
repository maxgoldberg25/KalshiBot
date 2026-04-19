"""
PostgreSQL persistence (e.g. Neon) via asyncpg.

Schema mirrors SQLite tables in db.py for a single logical model.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

import asyncpg

from kalshi_odds.core.portfolio import Position, PositionStatus, PnLSummary
from kalshi_odds.models.comparison import Alert
from kalshi_odds.models.kalshi import KalshiContract
from kalshi_odds.models.odds import OddsQuote


def _ssl_arg(dsn: str) -> bool | str | None:
    d = dsn.lower()
    if "sslmode=require" in d or "ssl=require" in d or ".neon.tech" in d:
        return True
    return None


class PostgresRepository:
    """Async PostgreSQL repository (Neon-compatible)."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn.strip()
        self._pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> None:
        self._pool = await asyncpg.create_pool(
            self._dsn,
            min_size=1,
            max_size=8,
            ssl=_ssl_arg(self._dsn),
            command_timeout=120,
        )
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            await self._create_tables(conn)

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def _create_tables(self, conn: asyncpg.Connection) -> None:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                email TEXT UNIQUE,
                password_salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_login_at TEXT,
                is_admin BOOLEAN NOT NULL DEFAULT FALSE,
                is_active BOOLEAN NOT NULL DEFAULT TRUE
            )
            """
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)"
        )

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS waitlist (
                id SERIAL PRIMARY KEY,
                username TEXT NOT NULL,
                email TEXT,
                reason TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                decided_at TEXT,
                decided_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                invite_token TEXT UNIQUE,
                invite_expires_at TEXT,
                ip_hash TEXT
            )
            """
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_waitlist_status_created ON waitlist(status, created_at)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_waitlist_username ON waitlist(username)"
        )

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            )
            """
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)"
        )

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS kalshi_contracts (
                contract_id TEXT PRIMARY KEY,
                kalshi_market_id TEXT,
                title TEXT,
                outcome_side TEXT,
                close_time TEXT,
                status TEXT,
                last_price DOUBLE PRECISION,
                fetched_at TEXT,
                data_json TEXT
            )
            """
        )

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS odds_quotes (
                id SERIAL PRIMARY KEY,
                source TEXT,
                bookmaker TEXT,
                event_id TEXT,
                market_type TEXT,
                selection TEXT,
                odds_format TEXT,
                odds_value DOUBLE PRECISION,
                timestamp TEXT,
                data_json TEXT
            )
            """
        )

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS alerts (
                alert_id TEXT PRIMARY KEY,
                timestamp TEXT,
                market_key TEXT,
                direction TEXT,
                edge_pct DOUBLE PRECISION,
                edge_bps DOUBLE PRECISION,
                confidence TEXT,
                confidence_score DOUBLE PRECISION,
                kalshi_contract_id TEXT,
                sportsbook_bookmaker TEXT,
                data_json TEXT
            )
            """
        )

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS positions (
                id SERIAL PRIMARY KEY,
                ticker TEXT NOT NULL,
                direction TEXT NOT NULL,
                shares INTEGER NOT NULL,
                entry_price_cents INTEGER NOT NULL,
                market_key TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'open',
                entered_at TEXT NOT NULL,
                settled_at TEXT,
                realized_pnl DOUBLE PRECISION,
                notes TEXT DEFAULT ''
            )
            """
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_positions_ticker_open ON positions(ticker, status)"
        )

    async def save_kalshi_contract(self, contract: KalshiContract) -> None:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO kalshi_contracts
                (contract_id, kalshi_market_id, title, outcome_side, close_time, status, last_price, fetched_at, data_json)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                ON CONFLICT (contract_id) DO UPDATE SET
                    kalshi_market_id = EXCLUDED.kalshi_market_id,
                    title = EXCLUDED.title,
                    outcome_side = EXCLUDED.outcome_side,
                    close_time = EXCLUDED.close_time,
                    status = EXCLUDED.status,
                    last_price = EXCLUDED.last_price,
                    fetched_at = EXCLUDED.fetched_at,
                    data_json = EXCLUDED.data_json
                """,
                contract.contract_id,
                contract.kalshi_market_id,
                contract.title,
                contract.outcome_side.value,
                contract.close_time.isoformat() if contract.close_time else None,
                contract.status,
                contract.last_price,
                contract.fetched_at.isoformat() if contract.fetched_at else None,
                contract.model_dump_json(),
            )

    async def save_odds_quote(self, quote: OddsQuote) -> None:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO odds_quotes
                (source, bookmaker, event_id, market_type, selection, odds_format, odds_value, timestamp, data_json)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                """,
                quote.source,
                quote.bookmaker,
                quote.event_id,
                quote.market_type.value,
                quote.selection,
                quote.odds_format.value,
                quote.odds_value,
                quote.timestamp.isoformat(),
                quote.model_dump_json(),
            )

    async def save_alert(self, alert: Alert) -> None:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO alerts
                (alert_id, timestamp, market_key, direction, edge_pct, edge_bps, confidence, confidence_score, kalshi_contract_id, sportsbook_bookmaker, data_json)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                ON CONFLICT (alert_id) DO UPDATE SET
                    timestamp = EXCLUDED.timestamp,
                    market_key = EXCLUDED.market_key,
                    direction = EXCLUDED.direction,
                    edge_pct = EXCLUDED.edge_pct,
                    edge_bps = EXCLUDED.edge_bps,
                    confidence = EXCLUDED.confidence,
                    confidence_score = EXCLUDED.confidence_score,
                    kalshi_contract_id = EXCLUDED.kalshi_contract_id,
                    sportsbook_bookmaker = EXCLUDED.sportsbook_bookmaker,
                    data_json = EXCLUDED.data_json
                """,
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
            )

    async def get_recent_alerts(self, limit: int = 20) -> list[Alert]:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT data_json FROM alerts ORDER BY timestamp DESC LIMIT $1",
                limit,
            )
        out: list[Alert] = []
        for row in rows:
            data = json.loads(row["data_json"])
            out.append(Alert(**data))
        return out

    async def get_last_alert_edge(self, market_key: str, direction: str) -> Optional[float]:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT edge_bps FROM alerts
                WHERE market_key = $1 AND direction = $2
                ORDER BY timestamp DESC LIMIT 1
                """,
                market_key,
                direction,
            )
        return float(row["edge_bps"]) if row else None

    async def should_alert(self, market_key: str, direction: str, edge_bps: float, threshold_bps: float = 20.0) -> bool:
        last = await self.get_last_alert_edge(market_key, direction)
        if last is None:
            return True
        return abs(edge_bps - last) >= threshold_bps

    async def get_expired_contract_ids(self) -> set[str]:
        assert self._pool is not None
        now_iso = datetime.now(timezone.utc).isoformat()
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT contract_id FROM kalshi_contracts WHERE close_time IS NOT NULL AND close_time < $1",
                now_iso,
            )
        return {r["contract_id"] for r in rows}

    async def save_position(self, position: Position) -> int:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO positions
                (ticker, direction, shares, entry_price_cents, market_key, status, entered_at, settled_at, realized_pnl, notes)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                RETURNING id
                """,
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
            )
        return int(row["id"]) if row else 0

    async def has_open_position(self, ticker: str, direction: str) -> bool:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT 1 AS one FROM positions
                WHERE ticker = $1 AND direction = $2 AND status = $3
                LIMIT 1
                """,
                ticker,
                direction,
                PositionStatus.OPEN.value,
            )
        return row is not None

    async def get_open_positions(self) -> list[Position]:
        from kalshi_odds.models.comparison import Direction

        assert self._pool is not None
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, ticker, direction, shares, entry_price_cents, market_key, status, entered_at, settled_at, realized_pnl, notes
                FROM positions WHERE status = $1 ORDER BY entered_at DESC
                """,
                PositionStatus.OPEN.value,
            )
        out: list[Position] = []
        for row in rows:
            out.append(
                Position(
                    id=row["id"],
                    ticker=row["ticker"],
                    direction=Direction(row["direction"]),
                    shares=row["shares"],
                    entry_price_cents=row["entry_price_cents"],
                    market_key=row["market_key"] or "",
                    status=PositionStatus(row["status"]),
                    entered_at=datetime.fromisoformat(row["entered_at"]),
                    settled_at=datetime.fromisoformat(row["settled_at"]) if row["settled_at"] else None,
                    realized_pnl=row["realized_pnl"],
                    notes=row["notes"] or "",
                )
            )
        return out

    async def get_settled_positions(self, limit: int = 100) -> list[Position]:
        from kalshi_odds.models.comparison import Direction

        assert self._pool is not None
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, ticker, direction, shares, entry_price_cents, market_key, status, entered_at, settled_at, realized_pnl, notes
                FROM positions WHERE status = $1 ORDER BY COALESCE(settled_at, entered_at) DESC LIMIT $2
                """,
                PositionStatus.SETTLED.value,
                limit,
            )
        out: list[Position] = []
        for row in rows:
            out.append(
                Position(
                    id=row["id"],
                    ticker=row["ticker"],
                    direction=Direction(row["direction"]),
                    shares=row["shares"],
                    entry_price_cents=row["entry_price_cents"],
                    market_key=row["market_key"] or "",
                    status=PositionStatus(row["status"]),
                    entered_at=datetime.fromisoformat(row["entered_at"]),
                    settled_at=datetime.fromisoformat(row["settled_at"]) if row["settled_at"] else None,
                    realized_pnl=row["realized_pnl"],
                    notes=row["notes"] or "",
                )
            )
        return out

    async def get_pnl_summary(self) -> PnLSummary:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            open_row = await conn.fetchrow(
                "SELECT COUNT(*)::int AS c FROM positions WHERE status = $1",
                PositionStatus.OPEN.value,
            )
            open_count = int(open_row["c"]) if open_row else 0

            settled_row = await conn.fetchrow(
                """
                SELECT COUNT(*)::int AS c, COALESCE(SUM(realized_pnl), 0)::float AS total,
                       COALESCE(SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END), 0)::int AS win,
                       COALESCE(SUM(CASE WHEN realized_pnl < 0 THEN 1 ELSE 0 END), 0)::int AS lose
                FROM positions WHERE status = $1 AND realized_pnl IS NOT NULL
                """,
                PositionStatus.SETTLED.value,
            )
        settled_count = int(settled_row["c"]) if settled_row else 0
        total = float(settled_row["total"]) if settled_row and settled_row["total"] is not None else 0.0
        winning = int(settled_row["win"]) if settled_row and settled_row["win"] is not None else 0
        losing = int(settled_row["lose"]) if settled_row and settled_row["lose"] is not None else 0

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
        assert self._pool is not None
        now = datetime.now(timezone.utc).isoformat()
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO users (username, email, password_salt, password_hash, created_at)
                VALUES ($1,$2,$3,$4,$5)
                RETURNING id
                """,
                username,
                email,
                password_salt,
                password_hash,
                now,
            )
        user_id = int(row["id"]) if row else 0
        return {"id": user_id, "username": username, "email": email, "created_at": now}

    async def get_user_by_username(self, username: str) -> Optional[dict]:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, username, email, password_salt, password_hash, created_at, "
                "last_login_at, is_admin, is_active FROM users WHERE username = $1",
                username,
            )
        if not row:
            return None
        return {
            "id": int(row["id"]),
            "username": row["username"],
            "email": row["email"],
            "password_salt": row["password_salt"],
            "password_hash": row["password_hash"],
            "created_at": row["created_at"],
            "last_login_at": row["last_login_at"],
            "is_admin": bool(row["is_admin"]),
            "is_active": bool(row["is_active"]),
        }

    async def get_user_by_id(self, user_id: int) -> Optional[dict]:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, username, email, created_at, last_login_at, is_admin, is_active "
                "FROM users WHERE id = $1",
                user_id,
            )
        if not row:
            return None
        return {
            "id": int(row["id"]),
            "username": row["username"],
            "email": row["email"],
            "created_at": row["created_at"],
            "last_login_at": row["last_login_at"],
            "is_admin": bool(row["is_admin"]),
            "is_active": bool(row["is_active"]),
        }

    async def touch_user_login(self, user_id: int) -> None:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET last_login_at = $1 WHERE id = $2",
                datetime.now(timezone.utc).isoformat(),
                user_id,
            )

    async def create_session(self, user_id: int, token: str, expires_at: datetime) -> None:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES ($1,$2,$3,$4)",
                token,
                user_id,
                datetime.now(timezone.utc).isoformat(),
                expires_at.isoformat(),
            )

    async def get_session_user(self, token: str) -> Optional[dict]:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT u.id, u.username, u.email, u.created_at, u.last_login_at,
                       u.is_admin, u.is_active, s.expires_at
                FROM sessions s
                JOIN users u ON u.id = s.user_id
                WHERE s.token = $1
                """,
                token,
            )
        if not row:
            return None
        try:
            expires = datetime.fromisoformat(row["expires_at"])
        except (TypeError, ValueError):
            return None
        if expires < datetime.now(timezone.utc):
            await self.delete_session(token)
            return None
        if not bool(row["is_active"]):
            async with self._pool.acquire() as conn:
                await conn.execute("DELETE FROM sessions WHERE user_id = $1", int(row["id"]))
            return None
        return {
            "id": int(row["id"]),
            "username": row["username"],
            "email": row["email"],
            "created_at": row["created_at"],
            "last_login_at": row["last_login_at"],
            "is_admin": bool(row["is_admin"]),
            "is_active": bool(row["is_active"]),
        }

    async def delete_session(self, token: str) -> None:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            await conn.execute("DELETE FROM sessions WHERE token = $1", token)

    async def purge_expired_sessions(self) -> int:
        assert self._pool is not None
        now_iso = datetime.now(timezone.utc).isoformat()
        async with self._pool.acquire() as conn:
            st = await conn.execute("DELETE FROM sessions WHERE expires_at < $1", now_iso)
        parts = st.split()
        if len(parts) >= 2 and parts[0] == "DELETE":
            try:
                return int(parts[-1])
            except ValueError:
                return 0
        return 0

    async def create_waitlist_entry(
        self,
        *,
        username: str,
        email: Optional[str],
        reason: Optional[str],
        ip_hash: Optional[str],
    ) -> dict:
        assert self._pool is not None
        now = datetime.now(timezone.utc).isoformat()
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO waitlist (username, email, reason, status, created_at, ip_hash)
                VALUES ($1,$2,$3,'pending',$4,$5)
                RETURNING id
                """,
                username,
                email,
                reason,
                now,
                ip_hash,
            )
        return {
            "id": int(row["id"]) if row else 0,
            "username": username,
            "email": email,
            "reason": reason,
            "status": "pending",
            "created_at": now,
        }

    async def count_recent_waitlist_by_ip(self, ip_hash: str, since_iso: str) -> int:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT COUNT(*)::int AS c FROM waitlist WHERE ip_hash = $1 AND created_at >= $2",
                ip_hash,
                since_iso,
            )
        return int(row["c"]) if row else 0

    async def list_waitlist(self, status: Optional[str] = None) -> list[dict]:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            if status:
                rows = await conn.fetch(
                    "SELECT id, username, email, reason, status, created_at, decided_at, "
                    "decided_by_user_id, invite_token, invite_expires_at "
                    "FROM waitlist WHERE status = $1 ORDER BY created_at DESC",
                    status,
                )
            else:
                rows = await conn.fetch(
                    "SELECT id, username, email, reason, status, created_at, decided_at, "
                    "decided_by_user_id, invite_token, invite_expires_at "
                    "FROM waitlist ORDER BY created_at DESC"
                )
        return [
            {
                "id": int(r["id"]),
                "username": r["username"],
                "email": r["email"],
                "reason": r["reason"],
                "status": r["status"],
                "created_at": r["created_at"],
                "decided_at": r["decided_at"],
                "decided_by_user_id": r["decided_by_user_id"],
                "invite_token": r["invite_token"],
                "invite_expires_at": r["invite_expires_at"],
            }
            for r in rows
        ]

    async def get_waitlist_entry(self, entry_id: int) -> Optional[dict]:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            r = await conn.fetchrow(
                "SELECT id, username, email, reason, status, created_at, decided_at, "
                "decided_by_user_id, invite_token, invite_expires_at "
                "FROM waitlist WHERE id = $1",
                entry_id,
            )
        if not r:
            return None
        return {
            "id": int(r["id"]),
            "username": r["username"],
            "email": r["email"],
            "reason": r["reason"],
            "status": r["status"],
            "created_at": r["created_at"],
            "decided_at": r["decided_at"],
            "decided_by_user_id": r["decided_by_user_id"],
            "invite_token": r["invite_token"],
            "invite_expires_at": r["invite_expires_at"],
        }

    async def approve_waitlist_entry(
        self,
        entry_id: int,
        *,
        decided_by_user_id: int,
        invite_token: str,
        invite_expires_at: datetime,
    ) -> Optional[dict]:
        assert self._pool is not None
        now = datetime.now(timezone.utc).isoformat()
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE waitlist
                SET status = 'approved',
                    decided_at = $1,
                    decided_by_user_id = $2,
                    invite_token = $3,
                    invite_expires_at = $4
                WHERE id = $5 AND status = 'pending'
                RETURNING id
                """,
                now,
                decided_by_user_id,
                invite_token,
                invite_expires_at.isoformat(),
                entry_id,
            )
        if row is None:
            return None
        return await self.get_waitlist_entry(entry_id)

    async def reject_waitlist_entry(self, entry_id: int, *, decided_by_user_id: int) -> Optional[dict]:
        assert self._pool is not None
        now = datetime.now(timezone.utc).isoformat()
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE waitlist
                SET status = 'rejected', decided_at = $1, decided_by_user_id = $2
                WHERE id = $3 AND status = 'pending'
                RETURNING id
                """,
                now,
                decided_by_user_id,
                entry_id,
            )
        if row is None:
            return None
        return await self.get_waitlist_entry(entry_id)

    async def consume_invite_token(self, token: str) -> Optional[dict]:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, username, email, status, invite_expires_at "
                "FROM waitlist WHERE invite_token = $1",
                token,
            )
            if not row:
                return None
            entry_id = int(row["id"])
            username = row["username"]
            email = row["email"]
            status = row["status"]
            expires_iso = row["invite_expires_at"]
            if status != "approved":
                return None
            try:
                expires = datetime.fromisoformat(expires_iso) if expires_iso else None
            except (TypeError, ValueError):
                expires = None
            if expires is None or expires < datetime.now(timezone.utc):
                return None
            now = datetime.now(timezone.utc).isoformat()
            upd = await conn.fetchrow(
                "UPDATE waitlist SET status = 'consumed', decided_at = $1 "
                "WHERE id = $2 AND status = 'approved' RETURNING id",
                now,
                entry_id,
            )
            if upd is None:
                return None
        return {"id": entry_id, "username": username, "email": email}

    async def list_users(self) -> list[dict]:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, username, email, created_at, last_login_at, is_admin, is_active "
                "FROM users ORDER BY created_at DESC"
            )
        return [
            {
                "id": int(r["id"]),
                "username": r["username"],
                "email": r["email"],
                "created_at": r["created_at"],
                "last_login_at": r["last_login_at"],
                "is_admin": bool(r["is_admin"]),
                "is_active": bool(r["is_active"]),
            }
            for r in rows
        ]

    async def set_user_admin(self, user_id: int, is_admin: bool) -> None:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET is_admin = $1 WHERE id = $2",
                is_admin,
                user_id,
            )

    async def set_user_active(self, user_id: int, is_active: bool) -> None:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET is_active = $1 WHERE id = $2",
                is_active,
                user_id,
            )
            if not is_active:
                await conn.execute("DELETE FROM sessions WHERE user_id = $1", user_id)

    async def promote_admin_by_username(self, username: str) -> bool:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "UPDATE users SET is_admin = TRUE WHERE LOWER(username) = LOWER($1) RETURNING id",
                username,
            )
        return row is not None

    async def __aenter__(self) -> PostgresRepository:
        await self.connect()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()
