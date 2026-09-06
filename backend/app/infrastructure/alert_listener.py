"""Dedicated Postgres LISTEN connection for the `important_alert` channel.

This is intentionally separate from the asyncpg pool in database.py.
That pool talks to Neon's pooled (PgBouncer, transaction-mode) endpoint,
which does not reliably deliver NOTIFYs -- a LISTEN issued on one
borrowed connection can be silently dropped when the pooler recycles
that connection to a different caller. This module holds one long-lived
connection to Neon's *direct* endpoint for the sole purpose of LISTEN.
"""

from __future__ import annotations

import asyncio
import json
from typing import Awaitable, Callable, Optional

import asyncpg
import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)

NotificationHandler = Callable[[dict], Awaitable[None]]

_listener_conn: Optional[asyncpg.Connection] = None
_listener_task: Optional[asyncio.Task] = None


async def _connect() -> asyncpg.Connection:
    settings = get_settings()
    url = settings.neon_direct_database_url or settings.neon_database_url
    if not settings.neon_direct_database_url:
        logger.warning(
            "alert_listener.no_direct_url_configured",
            hint="set NEON_DIRECT_DATABASE_URL to Neon's non-pooled connection string",
        )
    return await asyncpg.connect(url, ssl="require")


async def _run(handler: NotificationHandler) -> None:
    """Hold LISTEN open, reconnecting with backoff if the connection drops."""
    global _listener_conn
    backoff = 1.0

    while True:
        try:
            _listener_conn = await _connect()

            async def _on_notify(_conn, _pid, channel, payload) -> None:
                try:
                    data = json.loads(payload)
                except json.JSONDecodeError:
                    logger.warning("alert_listener.bad_payload", channel=channel, payload=payload)
                    return
                try:
                    await handler(data)
                except Exception as e:
                    logger.error("alert_listener.handler_failed", error=str(e), payload=data)

            await _listener_conn.add_listener("important_alert", _on_notify)
            logger.info("alert_listener.listening", channel="important_alert")
            backoff = 1.0

            # add_listener dispatches on the connection's own read loop;
            # this just has to keep the connection alive until it drops.
            while not _listener_conn.is_closed():
                await asyncio.sleep(5)

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("alert_listener.connection_lost", error=str(e), retry_in=backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60.0)
        finally:
            if _listener_conn is not None and not _listener_conn.is_closed():
                await _listener_conn.close()
            _listener_conn = None


async def start(handler: NotificationHandler) -> None:
    """Start the listener as a background task. Call once at app startup."""
    global _listener_task
    if _listener_task is not None:
        return
    _listener_task = asyncio.create_task(_run(handler), name="important-alert-listener")


async def stop() -> None:
    """Cancel the listener task and close its connection. Call at app shutdown."""
    global _listener_task, _listener_conn
    if _listener_task is not None:
        _listener_task.cancel()
        try:
            await _listener_task
        except asyncio.CancelledError:
            pass
        _listener_task = None
    if _listener_conn is not None and not _listener_conn.is_closed():
        await _listener_conn.close()
        _listener_conn = None
