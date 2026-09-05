"""FastAPI entrypoint for the Pulse agent."""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from app.api import actions, leadership
from app.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name, version=settings.version)

app.include_router(leadership.router)
app.include_router(actions.router)


class Health(BaseModel):
    status: str
    service: str
    version: str


@app.get("/health", response_model=Health)
def health() -> Health:
    return Health(status="UP", service=settings.app_name, version=settings.version)
