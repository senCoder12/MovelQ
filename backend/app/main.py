"""MoveIQ FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle — startup and shutdown."""
    settings = get_settings()
    logger.info("moveiq.startup", app_name=settings.app_name, demo_mode=settings.demo_mode)

    # Initialize database pool
    from app.infrastructure.database import create_pool, close_pool

    try:
        await create_pool()
        logger.info("moveiq.db_connected")
    except Exception as e:
        logger.warning("moveiq.db_connection_failed", error=str(e))

    # Initialize services and wire dependencies
    from app.api.dependencies import init_services, get_alert_stream_service
    await init_services()

    # Start the dedicated Postgres LISTEN connection for important_alert
    # (see db/05_alert_stream_trigger.sql). Runs on its own connection,
    # separate from the pool above -- see neon_direct_database_url in config.py.
    from app.infrastructure import alert_listener

    alert_stream_svc = get_alert_stream_service()
    try:
        await alert_listener.start(alert_stream_svc.handle_notification)
        logger.info("moveiq.alert_listener_started")
    except Exception as e:
        logger.warning("moveiq.alert_listener_failed_to_start", error=str(e))

    yield

    # Shutdown
    try:
        await alert_listener.stop()
    except Exception:
        pass
    try:
        await close_pool()
    except Exception:
        pass
    logger.info("moveiq.shutdown")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="MoveIQ — Mobility Decision Intelligence",
        description=(
            "An agentic mobility intelligence layer that turns fragmented trip, "
            "employee, safety, cost and experience signals into business situations, "
            "quantifies their impact, compares possible interventions, and recommends "
            "the best action."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS for frontend dev
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routes
    from app.api.routes import home, shifts, readiness, situations, decisions, ask, health, simulate

    app.include_router(health.router, prefix="/api/v1", tags=["health"])
    app.include_router(home.router, prefix="/api/v1", tags=["home"])
    app.include_router(shifts.router, prefix="/api/v1", tags=["shifts"])
    app.include_router(readiness.router, prefix="/api/v1", tags=["readiness"])
    app.include_router(situations.router, prefix="/api/v1", tags=["situations"])
    app.include_router(decisions.router, prefix="/api/v1", tags=["decisions"])
    app.include_router(ask.router, prefix="/api/v1", tags=["ask-move"])
    app.include_router(simulate.router, prefix="/api/v1", tags=["simulate"])

    # Replay routes (demo/development)
    try:
        from app.api.routes import replay
        app.include_router(replay.router, prefix="/api/v1", tags=["replay"])
    except ImportError:
        pass  # Replay module optional

    return app


# Module-level app for uvicorn
app = create_app()
