from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import date, datetime
from typing import Dict, List, Optional

import structlog

from app.config import get_settings
from app.domain.entities import Alert, AlertEpisode
from app.domain.enums import EpisodeState
from app.domain.interfaces import AlertEpisodeRepository, AlertRepository

logger = structlog.get_logger(__name__)


class AlertEpisodeService:
    """Deterministic alert episode grouping engine.

    Converts high-volume raw alerts into compact AlertEpisodes based on:
    Key: (business_unit, trip_id, event_type, source)
    Gap: alerts within alert_episode_gap_minutes (default 15) form one continuous episode.
    """

    def __init__(
        self,
        alert_repository: AlertRepository,
        episode_repository: AlertEpisodeRepository,
    ):
        self.alert_repository = alert_repository
        self.episode_repository = episode_repository
        self.settings = get_settings()

    async def build_episodes_for_trip(self, trip_id: int) -> List[AlertEpisode]:
        logger.info("episode.build_for_trip", trip_id=trip_id)
        alerts = await self.alert_repository.get_alerts_for_trip(trip_id)
        return await self._build_and_save_episodes(alerts)

    async def build_episodes_for_date(
        self, business_unit: str, alert_date: date
    ) -> List[AlertEpisode]:
        logger.info("episode.build_for_date", business_unit=business_unit, alert_date=alert_date)
        alerts = await self.alert_repository.get_alerts_for_date(business_unit, alert_date)
        return await self._build_and_save_episodes(alerts)

    async def _build_and_save_episodes(self, alerts: List[Alert]) -> List[AlertEpisode]:
        gap_minutes = self.settings.alert_episode_gap_minutes

        # Group by primary correlation key: (business_unit, trip_id, event_type, source)
        groups: Dict[tuple, List[Alert]] = defaultdict(list)
        for alert in alerts:
            key = (alert.business_unit, alert.trip_id, alert.event_type, alert.source or "")
            groups[key].append(alert)

        episodes: List[AlertEpisode] = []

        for key, group_alerts in groups.items():
            # Sort chronologically by start_ts
            group_alerts.sort(key=lambda a: a.start_ts)
            business_unit, trip_id, event_type, source = key

            current_alerts: List[Alert] = []

            for alert in group_alerts:
                if not current_alerts:
                    current_alerts.append(alert)
                    continue

                prev_alert = current_alerts[-1]
                gap = (alert.start_ts - prev_alert.start_ts).total_seconds() / 60.0

                if gap <= gap_minutes:
                    current_alerts.append(alert)
                else:
                    # Gap exceeded: close current episode and start new
                    ep = self._create_episode(business_unit, trip_id, event_type, source, current_alerts)
                    episodes.append(ep)
                    current_alerts = [alert]

            if current_alerts:
                ep = self._create_episode(business_unit, trip_id, event_type, source, current_alerts)
                episodes.append(ep)

        # Persist all generated episodes
        for ep in episodes:
            await self.episode_repository.save_episode(ep)

        logger.info("episode.episodes_created", count=len(episodes))
        return episodes

    def _create_episode(
        self,
        business_unit: str,
        trip_id: int,
        event_type: str,
        source: str,
        alerts: List[Alert],
    ) -> AlertEpisode:
        first_seen = alerts[0].start_ts
        last_seen = alerts[-1].start_ts
        duration = max(0.0, (last_seen - first_seen).total_seconds() / 60.0)

        # Severity summary
        sev_summary: Dict[str, int] = defaultdict(int)
        ack_latencies = []
        for a in alerts:
            sev = a.severity or a.severity_raw or "UNASSIGNED"
            sev_summary[sev] += 1
            if a.ack_latency_min is not None:
                ack_latencies.append(a.ack_latency_min)

        ack_summary: Dict[str, Optional[float]] = {
            "min": float(min(ack_latencies)) if ack_latencies else None,
            "max": float(max(ack_latencies)) if ack_latencies else None,
            "avg": float(sum(ack_latencies) / len(ack_latencies)) if ack_latencies else None,
        }

        return AlertEpisode(
            episode_id=str(uuid.uuid4()),
            business_unit=business_unit,
            trip_id=trip_id,
            event_type=event_type,
            source=source if source else None,
            first_seen=first_seen,
            last_seen=last_seen,
            occurrence_count=len(alerts),
            duration_minutes=round(duration, 2),
            severity_summary=dict(sev_summary),
            ack_latency_summary=ack_summary,
            raw_alert_ids=[a.event_id for a in alerts],
            state=EpisodeState.ACTIVE,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
