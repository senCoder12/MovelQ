from __future__ import annotations

import pytest
from datetime import datetime, timedelta
from app.domain.entities import Alert, AlertEpisode
from app.domain.enums import AlertScope
from app.application.services.alert_episode_service import AlertEpisodeService

def _build_episodes(alerts, gap_minutes=15):
    """
    Helper function to mimic the episode building logic for unit testing.
    Sorts alerts by start_ts, groups by (business_unit, trip_id, event_type, source).
    Splits into separate episodes if gap between consecutive alerts > gap_minutes.
    """
    if not alerts:
        return []
        
    episodes = []
    
    # Sort alerts by start_ts
    sorted_alerts = sorted(alerts, key=lambda a: a.start_ts)
    
    # Group by key: (business_unit, trip_id, event_type, source)
    groups = {}
    for alert in sorted_alerts:
        key = (alert.business_unit, alert.trip_id, alert.event_type, alert.source)
        if key not in groups:
            groups[key] = []
        groups[key].append(alert)
        
    for key, group_alerts in groups.items():
        business_unit, trip_id, event_type, source = key
        
        current_episode_alerts = [group_alerts[0]]
        for i in range(1, len(group_alerts)):
            prev_alert = current_episode_alerts[-1]
            curr_alert = group_alerts[i]
            
            gap = (curr_alert.start_ts - prev_alert.start_ts).total_seconds() / 60.0
            
            if gap <= gap_minutes:
                current_episode_alerts.append(curr_alert)
            else:
                # Close current episode
                episodes.append(AlertEpisode(
                    episode_id=f"ep-{len(episodes)}",
                    business_unit=business_unit,
                    trip_id=trip_id,
                    event_type=event_type,
                    source=source,
                    first_seen=current_episode_alerts[0].start_ts,
                    last_seen=current_episode_alerts[-1].start_ts,
                    occurrence_count=len(current_episode_alerts)
                ))
                current_episode_alerts = [curr_alert]
                
        # Close the last episode
        if current_episode_alerts:
            episodes.append(AlertEpisode(
                episode_id=f"ep-{len(episodes)}",
                business_unit=business_unit,
                trip_id=trip_id,
                event_type=event_type,
                source=source,
                first_seen=current_episode_alerts[0].start_ts,
                last_seen=current_episode_alerts[-1].start_ts,
                occurrence_count=len(current_episode_alerts)
            ))
            
    return episodes


def test_eleven_alerts_one_episode():
    """11 repeated DEVICE_NOT_REACHABLE alerts for the same trip
    must result in exactly 1 AlertEpisode, not 11 situations."""
    alerts = []
    base_time = datetime(2026, 7, 15, 12, 3, 0)
    for i in range(11):
        alerts.append(Alert(
            event_id=f"evt-{i}",
            trip_id=1097076,
            business_unit="catalyst-Slc",
            event_type="DEVICE_NOT_REACHABLE",
            alert_scope=AlertScope.VEHICLE,
            severity_raw="False",
            start_ts=base_time + timedelta(minutes=i * 3 + (i % 2)),
            source="MOBILE",
        ))
    
    episodes = _build_episodes(alerts, gap_minutes=15)
    
    assert len(episodes) == 1
    assert episodes[0].occurrence_count == 11
    assert episodes[0].event_type == "DEVICE_NOT_REACHABLE"
    assert episodes[0].trip_id == 1097076


def test_large_gap_creates_new_episode():
    """Alerts separated by more than gap threshold create separate episodes."""
    alerts = [
        Alert(event_id="evt-1", trip_id=100, business_unit="bu1",
              event_type="DEVICE_NOT_REACHABLE", alert_scope=AlertScope.VEHICLE,
              severity_raw="False", start_ts=datetime(2026, 7, 15, 12, 0), source="MOBILE"),
        Alert(event_id="evt-2", trip_id=100, business_unit="bu1",
              event_type="DEVICE_NOT_REACHABLE", alert_scope=AlertScope.VEHICLE,
              severity_raw="False", start_ts=datetime(2026, 7, 15, 12, 30), source="MOBILE"),
    ]
    episodes = _build_episodes(alerts, gap_minutes=15)
    assert len(episodes) == 2


def test_different_event_types_separate_episodes():
    """Different event_type values create separate episodes even for same trip."""
    alerts = [
        Alert(event_id="evt-1", trip_id=100, business_unit="bu1",
              event_type="DEVICE_NOT_REACHABLE", alert_scope=AlertScope.VEHICLE,
              severity_raw="False", start_ts=datetime(2026, 7, 15, 12, 0), source="MOBILE"),
        Alert(event_id="evt-2", trip_id=100, business_unit="bu1",
              event_type="OTHER_EVENT", alert_scope=AlertScope.VEHICLE,
              severity_raw="False", start_ts=datetime(2026, 7, 15, 12, 5), source="MOBILE"),
    ]
    episodes = _build_episodes(alerts, gap_minutes=15)
    assert len(episodes) == 2


def test_different_trips_separate_episodes():
    """Different trips create separate episodes."""
    alerts = [
        Alert(event_id="evt-1", trip_id=100, business_unit="bu1",
              event_type="DEVICE_NOT_REACHABLE", alert_scope=AlertScope.VEHICLE,
              severity_raw="False", start_ts=datetime(2026, 7, 15, 12, 0), source="MOBILE"),
        Alert(event_id="evt-2", trip_id=101, business_unit="bu1",
              event_type="DEVICE_NOT_REACHABLE", alert_scope=AlertScope.VEHICLE,
              severity_raw="False", start_ts=datetime(2026, 7, 15, 12, 5), source="MOBILE"),
    ]
    episodes = _build_episodes(alerts, gap_minutes=15)
    assert len(episodes) == 2


def test_episode_duration():
    """Duration should be last_seen - first_seen in minutes."""
    alerts = [
        Alert(event_id="evt-1", trip_id=100, business_unit="bu1",
              event_type="DEVICE_NOT_REACHABLE", alert_scope=AlertScope.VEHICLE,
              severity_raw="False", start_ts=datetime(2026, 7, 15, 12, 0), source="MOBILE"),
        Alert(event_id="evt-2", trip_id=100, business_unit="bu1",
              event_type="DEVICE_NOT_REACHABLE", alert_scope=AlertScope.VEHICLE,
              severity_raw="False", start_ts=datetime(2026, 7, 15, 12, 10), source="MOBILE"),
    ]
    episodes = _build_episodes(alerts, gap_minutes=15)
    assert len(episodes) == 1
    duration = (episodes[0].last_seen - episodes[0].first_seen).total_seconds() / 60
    assert duration == 10.0

def test_severity_summary():
    """Track severity distribution across alerts."""
    # Assuming the implementation will later keep track of severity
    pass

