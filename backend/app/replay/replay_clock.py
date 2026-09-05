from __future__ import annotations

from datetime import datetime, timedelta

class ReplayClock:
    def __init__(self, initial_time: datetime | None = None):
        self._current_time = initial_time or datetime.utcnow()
        
    @property
    def current_time(self) -> datetime:
        return self._current_time
        
    def advance(self, minutes: float) -> None:
        self._current_time += timedelta(minutes=minutes)
        
    def set_time(self, new_time: datetime) -> None:
        self._current_time = new_time
        
    def is_past(self, dt: datetime) -> bool:
        return self._current_time >= dt
