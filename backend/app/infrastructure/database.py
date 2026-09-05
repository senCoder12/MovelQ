from __future__ import annotations

from typing import Any, List, Optional

import asyncpg
import structlog

from app.config import get_settings

logger = structlog.get_logger()

_pool: Optional[asyncpg.Pool] = None


async def create_pool(database_url: Optional[str] = None) -> Optional[asyncpg.Pool]:
    """Create asyncpg connection pool for Neon PostgreSQL."""
    global _pool
    settings = get_settings()
    url = database_url or settings.neon_database_url

    if not url or "localhost" in url:
        logger.warning("db.skipped_invalid_url", url=url)
        return None

    try:
        # Neon PostgreSQL requires ssl='require'
        _pool = await asyncpg.create_pool(
            url,
            min_size=settings.db_pool_min,
            max_size=settings.db_pool_max,
            ssl="require",
            command_timeout=10,
        )
        logger.info("db.pool_created")
        return _pool
    except Exception as e:
        logger.warning("db.pool_creation_failed", error=str(e))
        _pool = None
        return None


async def close_pool() -> None:
    """Close the connection pool."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("db.pool_closed")


def get_pool() -> Optional[asyncpg.Pool]:
    """Return the active connection pool if initialized."""
    return _pool


async def fetch_rows(sql: str, *params: Any) -> List[asyncpg.Record]:
    """Execute query and fetch all rows. Gracefully returns empty list if DB is uninitialized."""
    pool = get_pool()
    if not pool:
        return []
    async with pool.acquire() as conn:
        logger.debug("db.exec_query", sql=sql, params=params)
        return await conn.fetch(sql, *params)


async def fetch_one(sql: str, *params: Any) -> Optional[asyncpg.Record]:
    """Execute query and fetch a single row. Gracefully returns None if DB is uninitialized."""
    pool = get_pool()
    if not pool:
        return None
    async with pool.acquire() as conn:
        logger.debug("db.exec_one", sql=sql, params=params)
        return await conn.fetchrow(sql, *params)


async def execute(sql: str, *params: Any) -> Optional[str]:
    """Execute statement. Gracefully returns None if DB is uninitialized."""
    pool = get_pool()
    if not pool:
        return None
    async with pool.acquire() as conn:
        logger.debug("db.exec_stmt", sql=sql, params=params)
        return await conn.execute(sql, *params)
