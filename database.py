"""
Async SQLite database layer using aiosqlite.
"""

import aiosqlite
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, path: str):
        self.path = path

    async def init(self):
        async with aiosqlite.connect(self.path) as db:
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id     INTEGER PRIMARY KEY,
                    username    TEXT,
                    full_name   TEXT,
                    balance     REAL    DEFAULT 0.0,
                    total_spent REAL    DEFAULT 0.0,
                    is_banned   INTEGER DEFAULT 0,
                    created_at  TEXT    DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS orders (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id         INTEGER NOT NULL,
                    activation_id   TEXT    NOT NULL,
                    phone_number    TEXT,
                    service         TEXT,
                    country         INTEGER,
                    base_price      REAL,
                    charged_price   REAL,
                    status          TEXT    DEFAULT 'pending',
                    sms_code        TEXT,
                    created_at      TEXT    DEFAULT (datetime('now')),
                    updated_at      TEXT    DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS payments (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id         INTEGER NOT NULL,
                    amount          REAL    NOT NULL,
                    method          TEXT    NOT NULL,  -- 'crypto' | 'manual'
                    status          TEXT    DEFAULT 'pending',
                    tx_id           TEXT,
                    note            TEXT,
                    created_at      TEXT    DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key   TEXT PRIMARY KEY,
                    value TEXT
                );
            """)
            await db.commit()
        logger.info("Database initialised at %s", self.path)

    # ── Users ──────────────────────────────────────────────────────────────────

    async def get_or_create_user(self, user_id: int, username: str, full_name: str) -> Dict:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute(
                "INSERT OR IGNORE INTO users (user_id, username, full_name) VALUES (?,?,?)",
                (user_id, username, full_name)
            )
            await db.execute(
                "UPDATE users SET username=?, full_name=? WHERE user_id=?",
                (username, full_name, user_id)
            )
            await db.commit()
            async with db.execute("SELECT * FROM users WHERE user_id=?", (user_id,)) as cur:
                row = await cur.fetchone()
                return dict(row)

    async def get_user(self, user_id: int) -> Optional[Dict]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM users WHERE user_id=?", (user_id,)) as cur:
                row = await cur.fetchone()
                return dict(row) if row else None

    async def get_balance(self, user_id: int) -> float:
        user = await self.get_user(user_id)
        return user["balance"] if user else 0.0

    async def update_balance(self, user_id: int, delta: float) -> float:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                (delta, user_id)
            )
            await db.commit()
            async with db.execute("SELECT balance FROM users WHERE user_id=?", (user_id,)) as cur:
                row = await cur.fetchone()
                return row[0] if row else 0.0

    async def set_balance(self, user_id: int, amount: float):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("UPDATE users SET balance=? WHERE user_id=?", (amount, user_id))
            await db.commit()

    async def ban_user(self, user_id: int, ban: bool = True):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("UPDATE users SET is_banned=? WHERE user_id=?", (1 if ban else 0, user_id))
            await db.commit()

    async def all_users(self) -> List[Dict]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM users ORDER BY created_at DESC") as cur:
                return [dict(r) for r in await cur.fetchall()]

    # ── Orders ─────────────────────────────────────────────────────────────────

    async def create_order(self, user_id: int, activation_id: str, phone_number: str,
                           service: str, country: int, base_price: float, charged_price: float) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                """INSERT INTO orders
                   (user_id, activation_id, phone_number, service, country, base_price, charged_price)
                   VALUES (?,?,?,?,?,?,?)""",
                (user_id, activation_id, phone_number, service, country, base_price, charged_price)
            )
            await db.commit()
            return cur.lastrowid

    async def get_order(self, order_id: int) -> Optional[Dict]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM orders WHERE id=?", (order_id,)) as cur:
                row = await cur.fetchone()
                return dict(row) if row else None

    async def get_order_by_activation(self, activation_id: str) -> Optional[Dict]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM orders WHERE activation_id=?", (activation_id,)) as cur:
                row = await cur.fetchone()
                return dict(row) if row else None

    async def update_order(self, order_id: int, **kwargs):
        fields = ", ".join(f"{k}=?" for k in kwargs)
        values = list(kwargs.values()) + [order_id]
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                f"UPDATE orders SET {fields}, updated_at=datetime('now') WHERE id=?", values
            )
            await db.commit()

    async def user_orders(self, user_id: int, limit: int = 10) -> List[Dict]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM orders WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit)
            ) as cur:
                return [dict(r) for r in await cur.fetchall()]

    async def all_orders(self, limit: int = 50) -> List[Dict]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM orders ORDER BY created_at DESC LIMIT ?", (limit,)
            ) as cur:
                return [dict(r) for r in await cur.fetchall()]

    # ── Payments ───────────────────────────────────────────────────────────────

    async def create_payment(self, user_id: int, amount: float, method: str,
                              tx_id: str = None, note: str = None) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "INSERT INTO payments (user_id, amount, method, tx_id, note) VALUES (?,?,?,?,?)",
                (user_id, amount, method, tx_id, note)
            )
            await db.commit()
            return cur.lastrowid

    async def confirm_payment(self, payment_id: int):
        async with aiosqlite.connect(self.path) as db:
            async with db.execute("SELECT * FROM payments WHERE id=?", (payment_id,)) as cur:
                row = await cur.fetchone()
            if row:
                await db.execute(
                    "UPDATE payments SET status='confirmed' WHERE id=?", (payment_id,)
                )
                await db.execute(
                    "UPDATE users SET balance=balance+? WHERE user_id=?",
                    (row[2], row[1])
                )
                await db.commit()

    async def pending_payments(self) -> List[Dict]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM payments WHERE status='pending' ORDER BY created_at DESC"
            ) as cur:
                return [dict(r) for r in await cur.fetchall()]

    # ── Stats ──────────────────────────────────────────────────────────────────

    async def stats(self) -> Dict[str, Any]:
        async with aiosqlite.connect(self.path) as db:
            async def scalar(q):
                async with db.execute(q) as c:
                    row = await c.fetchone()
                    return row[0] if row else 0

            return {
                "total_users":    await scalar("SELECT COUNT(*) FROM users"),
                "total_orders":   await scalar("SELECT COUNT(*) FROM orders"),
                "total_revenue":  await scalar("SELECT COALESCE(SUM(charged_price),0) FROM orders WHERE status='completed'"),
                "active_orders":  await scalar("SELECT COUNT(*) FROM orders WHERE status='active'"),
                "pending_topups": await scalar("SELECT COUNT(*) FROM payments WHERE status='pending'"),
            }
