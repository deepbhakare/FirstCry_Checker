"""
db.py — PostgreSQL state management for FirstCry Tracker
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Handles all DB operations via a thread-safe connection pool.
Schema is auto-created on first run — no manual setup needed.
"""

import logging
from contextlib import contextmanager

import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

from config import DatabaseConfig

logger = logging.getLogger(__name__)


# ─── SCHEMA ───────────────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tracked_products (
    id              SERIAL          PRIMARY KEY,
    product_key     TEXT            UNIQUE NOT NULL,
    product_id      TEXT            NOT NULL,
    name            TEXT            NOT NULL,
    url             TEXT            NOT NULL,
    price           TEXT            DEFAULT '',
    brand           TEXT            DEFAULT '',
    category        TEXT            NOT NULL,        -- 'listing' | 'watched'
    in_stock        BOOLEAN         NOT NULL DEFAULT FALSE,
    first_seen_at   TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    last_checked_at TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    last_updated_at TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tracked_product_key ON tracked_products(product_key);
CREATE INDEX IF NOT EXISTS idx_tracked_category    ON tracked_products(category);
CREATE INDEX IF NOT EXISTS idx_tracked_brand       ON tracked_products(brand);
"""


# ─── DATABASE ─────────────────────────────────────────────────────────────────

class Database:
    """
    Thread-safe PostgreSQL wrapper with connection pooling.

    Usage:
        db = Database(config.database)
        product = db.get_product(key)
        db.upsert_product(data)
        db.close()
    """

    def __init__(self, config: DatabaseConfig) -> None:
        self._pool = pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=5,
            dsn=config.url,
            cursor_factory=RealDictCursor,
        )
        self._apply_schema()
        logger.info("Database initialised ✅")

    # ── Schema ────────────────────────────────────────────────────────────────

    def _apply_schema(self) -> None:
        """Create tables and indexes if they do not already exist."""
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(_SCHEMA)
            conn.commit()

    # ── Connection context manager ────────────────────────────────────────────

    @contextmanager
    def _conn(self):
        conn = self._pool.getconn()
        try:
            yield conn
        except Exception:
            conn.rollback()
            raise
        finally:
            self._pool.putconn(conn)

    # ── Public queries ────────────────────────────────────────────────────────

    def get_product(self, product_key: str) -> dict | None:
        """
        Fetch a single product by its stable MD5 key.
        Returns None if the product has never been seen before.
        """
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM tracked_products WHERE product_key = %s",
                    (product_key,),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def upsert_product(self, product: dict) -> None:
        """
        Insert a new product or update an existing one.

        - On INSERT: stores all fields and timestamps.
        - On UPDATE: refreshes in_stock, price, last_checked_at.
          last_updated_at only advances when in_stock actually changes.
        """
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO tracked_products
                        (product_key, product_id, name, url, price,
                         brand, category, in_stock,
                         first_seen_at, last_checked_at, last_updated_at)
                    VALUES
                        (%(product_key)s, %(product_id)s, %(name)s, %(url)s,
                         %(price)s, %(brand)s, %(category)s, %(in_stock)s,
                         NOW(), NOW(), NOW())
                    ON CONFLICT (product_key) DO UPDATE SET
                        in_stock        = EXCLUDED.in_stock,
                        price           = EXCLUDED.price,
                        name            = EXCLUDED.name,
                        last_checked_at = NOW(),
                        last_updated_at = CASE
                            WHEN tracked_products.in_stock != EXCLUDED.in_stock
                            THEN NOW()
                            ELSE tracked_products.last_updated_at
                        END
                    """,
                    product,
                )
            conn.commit()

    def get_all_by_category(self, category: str) -> list[dict]:
        """
        Fetch all stored products for a given category.
        Used to detect first-run (empty result = first run).
        """
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM tracked_products WHERE category = %s",
                    (category,),
                )
                return [dict(row) for row in cur.fetchall()]

    def close(self) -> None:
        """Release all pooled connections gracefully."""
        self._pool.closeall()
        logger.info("Database connections closed.")
