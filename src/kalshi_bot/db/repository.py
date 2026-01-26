"""
Database repository for persisting trading data.

Uses SQLite for local persistence with async support.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiosqlite
import structlog

from kalshi_bot.config import settings
from kalshi_bot.models.order import Fill, Order, OrderSide, OrderStatus, OrderType
from kalshi_bot.models.position import DailyPnL
from kalshi_bot.models.snapshot import MarketSnapshot

logger = structlog.get_logger()


class Repository:
    """
    Async repository for persisting trading data.
    
    Tables:
    - orders: Order records with idempotency
    - fills: Executed trades
    - snapshots: Market snapshots for backtesting
    - daily_pnl: Daily P&L records
    """
    
    def __init__(self, db_path: Optional[str] = None):
        # Extract path from connection string
        db_url = db_path or settings.database_url
        if db_url.startswith("sqlite:///"):
            self.db_path = db_url.replace("sqlite:///", "")
        else:
            self.db_path = db_url
        
        self._initialized = False
    
    async def initialize(self) -> None:
        """Create database tables if they don't exist."""
        if self._initialized:
            return
        
        async with aiosqlite.connect(self.db_path) as db:
            # Orders table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id TEXT PRIMARY KEY,
                    idempotency_key TEXT UNIQUE,
                    kalshi_order_id TEXT,
                    ticker TEXT NOT NULL,
                    side TEXT NOT NULL,
                    order_type TEXT NOT NULL,
                    price INTEGER NOT NULL,
                    quantity INTEGER NOT NULL,
                    strategy_name TEXT,
                    signal_confidence REAL,
                    expected_value REAL,
                    status TEXT NOT NULL,
                    filled_quantity INTEGER DEFAULT 0,
                    average_fill_price REAL,
                    created_at TEXT NOT NULL,
                    submitted_at TEXT,
                    filled_at TEXT,
                    error_message TEXT
                )
            """)
            
            # Fills table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS fills (
                    id TEXT PRIMARY KEY,
                    order_id TEXT NOT NULL,
                    kalshi_trade_id TEXT,
                    ticker TEXT NOT NULL,
                    side TEXT NOT NULL,
                    price INTEGER NOT NULL,
                    quantity INTEGER NOT NULL,
                    notional REAL NOT NULL,
                    fees REAL DEFAULT 0,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (order_id) REFERENCES orders(id)
                )
            """)
            
            # Snapshots table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    last_price INTEGER NOT NULL,
                    bid INTEGER,
                    ask INTEGER,
                    mid REAL,
                    spread INTEGER,
                    volume_24h INTEGER,
                    bid_depth INTEGER,
                    ask_depth INTEGER,
                    depth_imbalance REAL,
                    orderbook_json TEXT
                )
            """)
            
            # Daily PnL table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS daily_pnl (
                    date TEXT PRIMARY KEY,
                    realized_pnl REAL DEFAULT 0,
                    unrealized_pnl REAL DEFAULT 0,
                    fees REAL DEFAULT 0,
                    trades_placed INTEGER DEFAULT 0,
                    trades_filled INTEGER DEFAULT 0,
                    trades_won INTEGER DEFAULT 0,
                    trades_lost INTEGER DEFAULT 0,
                    peak_exposure REAL DEFAULT 0,
                    ending_exposure REAL DEFAULT 0,
                    markets_traded TEXT
                )
            """)
            
            # Create indexes
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_orders_ticker ON orders(ticker)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_snapshots_ticker ON snapshots(ticker)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_snapshots_timestamp ON snapshots(timestamp)"
            )
            
            await db.commit()
        
        self._initialized = True
        logger.info("database_initialized", path=self.db_path)
    
    # ─────────────────────────────────────────────────────────────────────────
    # ORDERS
    # ─────────────────────────────────────────────────────────────────────────
    
    async def save_order(self, order: Order) -> None:
        """Save or update an order."""
        await self.initialize()
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO orders (
                    id, idempotency_key, kalshi_order_id, ticker, side,
                    order_type, price, quantity, strategy_name,
                    signal_confidence, expected_value, status,
                    filled_quantity, average_fill_price, created_at,
                    submitted_at, filled_at, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                order.id,
                order.idempotency_key,
                order.kalshi_order_id,
                order.ticker,
                order.side.value,
                order.order_type.value,
                order.price,
                order.quantity,
                order.strategy_name,
                order.signal_confidence,
                order.expected_value,
                order.status.value,
                order.filled_quantity,
                order.average_fill_price,
                order.created_at.isoformat(),
                order.submitted_at.isoformat() if order.submitted_at else None,
                order.filled_at.isoformat() if order.filled_at else None,
                order.error_message,
            ))
            await db.commit()
    
    async def get_order(self, order_id: str) -> Optional[Order]:
        """Get an order by ID."""
        await self.initialize()
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM orders WHERE id = ?", (order_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return self._row_to_order(dict(row))
        return None
    
    async def get_order_by_idempotency_key(self, key: str) -> Optional[Order]:
        """Get an order by idempotency key."""
        await self.initialize()
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM orders WHERE idempotency_key = ?", (key,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return self._row_to_order(dict(row))
        return None
    
    async def get_orders_by_date(self, date: datetime) -> list[Order]:
        """Get all orders for a specific date."""
        await self.initialize()
        
        date_str = date.strftime("%Y-%m-%d")
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM orders WHERE created_at LIKE ?",
                (f"{date_str}%",)
            ) as cursor:
                rows = await cursor.fetchall()
                return [self._row_to_order(dict(row)) for row in rows]
    
    def _row_to_order(self, row: dict) -> Order:
        """Convert database row to Order model."""
        return Order(
            id=row["id"],
            idempotency_key=row["idempotency_key"],
            kalshi_order_id=row["kalshi_order_id"],
            ticker=row["ticker"],
            side=OrderSide(row["side"]),
            order_type=OrderType(row["order_type"]),
            price=row["price"],
            quantity=row["quantity"],
            strategy_name=row["strategy_name"] or "",
            signal_confidence=row["signal_confidence"] or 0,
            expected_value=row["expected_value"] or 0,
            status=OrderStatus(row["status"]),
            filled_quantity=row["filled_quantity"] or 0,
            average_fill_price=row["average_fill_price"],
            created_at=datetime.fromisoformat(row["created_at"]),
            submitted_at=datetime.fromisoformat(row["submitted_at"]) if row["submitted_at"] else None,
            filled_at=datetime.fromisoformat(row["filled_at"]) if row["filled_at"] else None,
            error_message=row["error_message"],
        )
    
    # ─────────────────────────────────────────────────────────────────────────
    # FILLS
    # ─────────────────────────────────────────────────────────────────────────
    
    async def save_fill(self, fill: Fill) -> None:
        """Save a fill record."""
        await self.initialize()
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO fills (
                    id, order_id, kalshi_trade_id, ticker, side,
                    price, quantity, notional, fees, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                fill.id,
                fill.order_id,
                fill.kalshi_trade_id,
                fill.ticker,
                fill.side.value,
                fill.price,
                fill.quantity,
                fill.notional,
                fill.fees,
                fill.timestamp.isoformat(),
            ))
            await db.commit()
    
    async def get_fills_by_date(self, date: datetime) -> list[Fill]:
        """Get all fills for a specific date."""
        await self.initialize()
        
        date_str = date.strftime("%Y-%m-%d")
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM fills WHERE timestamp LIKE ?",
                (f"{date_str}%",)
            ) as cursor:
                rows = await cursor.fetchall()
                return [self._row_to_fill(dict(row)) for row in rows]
    
    def _row_to_fill(self, row: dict) -> Fill:
        """Convert database row to Fill model."""
        return Fill(
            id=row["id"],
            order_id=row["order_id"],
            kalshi_trade_id=row["kalshi_trade_id"],
            ticker=row["ticker"],
            side=OrderSide(row["side"]),
            price=row["price"],
            quantity=row["quantity"],
            notional=row["notional"],
            fees=row["fees"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
        )
    
    # ─────────────────────────────────────────────────────────────────────────
    # SNAPSHOTS
    # ─────────────────────────────────────────────────────────────────────────
    
    async def save_snapshot(self, snapshot: MarketSnapshot) -> None:
        """Save a market snapshot."""
        await self.initialize()
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO snapshots (
                    ticker, timestamp, last_price, bid, ask, mid, spread,
                    volume_24h, bid_depth, ask_depth, depth_imbalance, orderbook_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                snapshot.ticker,
                snapshot.timestamp.isoformat(),
                snapshot.last_price,
                snapshot.bid,
                snapshot.ask,
                snapshot.mid,
                snapshot.spread,
                snapshot.volume_24h,
                snapshot.bid_depth,
                snapshot.ask_depth,
                snapshot.depth_imbalance,
                snapshot.orderbook_json,
            ))
            await db.commit()
    
    async def get_snapshots(
        self,
        ticker: str,
        since: Optional[datetime] = None,
        limit: int = 1000,
    ) -> list[MarketSnapshot]:
        """Get snapshots for a market, optionally filtered by date."""
        await self.initialize()
        
        query = "SELECT * FROM snapshots WHERE ticker = ?"
        params: list = [ticker]
        
        if since:
            query += " AND timestamp >= ?"
            params.append(since.isoformat())
        
        query += " ORDER BY timestamp ASC LIMIT ?"
        params.append(limit)
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [self._row_to_snapshot(dict(row)) for row in rows]
    
    async def delete_old_snapshots(self, before: datetime) -> int:
        """Delete snapshots older than the given date."""
        await self.initialize()
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM snapshots WHERE timestamp < ?",
                (before.isoformat(),)
            )
            await db.commit()
            return cursor.rowcount
    
    def _row_to_snapshot(self, row: dict) -> MarketSnapshot:
        """Convert database row to MarketSnapshot model."""
        return MarketSnapshot(
            ticker=row["ticker"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            last_price=row["last_price"],
            bid=row["bid"],
            ask=row["ask"],
            mid=row["mid"],
            spread=row["spread"],
            volume_24h=row["volume_24h"],
            bid_depth=row["bid_depth"],
            ask_depth=row["ask_depth"],
            depth_imbalance=row["depth_imbalance"],
            orderbook_json=row["orderbook_json"],
        )
    
    # ─────────────────────────────────────────────────────────────────────────
    # DAILY PNL
    # ─────────────────────────────────────────────────────────────────────────
    
    async def save_daily_pnl(self, pnl: DailyPnL) -> None:
        """Save or update daily P&L record."""
        await self.initialize()
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO daily_pnl (
                    date, realized_pnl, unrealized_pnl, fees,
                    trades_placed, trades_filled, trades_won, trades_lost,
                    peak_exposure, ending_exposure, markets_traded
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                pnl.date.strftime("%Y-%m-%d"),
                pnl.realized_pnl,
                pnl.unrealized_pnl,
                pnl.fees,
                pnl.trades_placed,
                pnl.trades_filled,
                pnl.trades_won,
                pnl.trades_lost,
                pnl.peak_exposure,
                pnl.ending_exposure,
                json.dumps(pnl.markets_traded),
            ))
            await db.commit()
    
    async def get_daily_pnl(self, date: datetime) -> Optional[DailyPnL]:
        """Get daily P&L for a specific date."""
        await self.initialize()
        
        date_str = date.strftime("%Y-%m-%d")
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM daily_pnl WHERE date = ?", (date_str,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return self._row_to_daily_pnl(dict(row))
        return None
    
    def _row_to_daily_pnl(self, row: dict) -> DailyPnL:
        """Convert database row to DailyPnL model."""
        return DailyPnL(
            date=datetime.strptime(row["date"], "%Y-%m-%d"),
            realized_pnl=row["realized_pnl"],
            unrealized_pnl=row["unrealized_pnl"],
            fees=row["fees"],
            trades_placed=row["trades_placed"],
            trades_filled=row["trades_filled"],
            trades_won=row["trades_won"],
            trades_lost=row["trades_lost"],
            peak_exposure=row["peak_exposure"],
            ending_exposure=row["ending_exposure"],
            markets_traded=json.loads(row["markets_traded"]) if row["markets_traded"] else [],
        )
