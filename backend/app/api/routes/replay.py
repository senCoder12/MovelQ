from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from datetime import date
from pydantic import BaseModel
from typing import Any

from app.replay.replay_engine import ReplayEngine, ReplayResult, TripReplayResult

router = APIRouter(prefix="/api/v1/replay", tags=["replay"])

class ProcessDateRequest(BaseModel):
    target_date: date

class ProcessTripRequest(BaseModel):
    trip_id: int

# Note: In a real FastAPI app, ReplayEngine would be injected via Depends()
# but for this mock implementation we leave it as Any or create a mock dependency.
def get_replay_engine() -> Any:
    # Stub for Dependency Injection
    return None

@router.post("/process-date", response_model=ReplayResult)
async def process_date(request: ProcessDateRequest, engine: ReplayEngine = Depends(get_replay_engine)):
    """Process all events for a date."""
    if not engine:
        raise HTTPException(status_code=500, detail="ReplayEngine not configured")
    return await engine.process_date(request.target_date)

@router.post("/process-trip", response_model=TripReplayResult)
async def process_trip(request: ProcessTripRequest, engine: ReplayEngine = Depends(get_replay_engine)):
    """Process a single trip."""
    if not engine:
        raise HTTPException(status_code=500, detail="ReplayEngine not configured")
    return await engine.process_trip(request.trip_id)

@router.get("/status")
async def status(engine: ReplayEngine = Depends(get_replay_engine)):
    """Current replay state."""
    if not engine:
        raise HTTPException(status_code=500, detail="ReplayEngine not configured")
    return {
        "state": engine.state,
        "speed": engine.speed,
        "current_time": engine.current_time.isoformat() if engine.current_time else None
    }
