"""FastAPI entrypoint for the Pulse agent."""

from __future__ import annotations

from fastapi import FastAPI, Request
from pydantic import BaseModel

from app.api import actions, chat, insights, leadership, metrics, scan
from app.config import get_settings
from app.llm import context

settings = get_settings()

app = FastAPI(title=settings.app_name, version=settings.version)

app.include_router(leadership.router)
app.include_router(actions.router)
app.include_router(insights.router)
app.include_router(chat.router)
app.include_router(scan.router)
app.include_router(metrics.router)

#: Set by the backend on every call it makes. The tenant is required for any
#: request that can reach a model (app/llm/client.py refuses an unattributable
#: call); the scan id is present only when the backend is calling from inside a
#: scan, and is what ties the resulting token_usage rows to a scan_run.
TENANT_HEADER = "X-Tenant-Id"
SCAN_RUN_HEADER = "X-Scan-Run-Id"


@app.middleware("http")
async def bind_call_context(request: Request, call_next):
    """Put the caller's tenant and scan id into context for the whole request.

    Here rather than in each handler on purpose: this is the one place every
    request passes through, so there is no handler that can be added later and
    forget to do it. A request without the headers binds nothing and any model
    call it makes is refused rather than recorded against no one.
    """
    with context.bind(
        tenant_id=request.headers.get(TENANT_HEADER),
        scan_run_id=request.headers.get(SCAN_RUN_HEADER),
    ):
        return await call_next(request)


class Health(BaseModel):
    status: str
    service: str
    version: str


@app.get("/health", response_model=Health)
def health() -> Health:
    return Health(status="UP", service=settings.app_name, version=settings.version)
