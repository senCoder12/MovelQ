import asyncio
from datetime import date
from dotenv import load_dotenv
load_dotenv("backend/.env")

from app.infrastructure.database import create_pool, close_pool, fetch_rows
from app.infrastructure.repositories.pg_trip_repository import PgTripRepository
from app.infrastructure.repositories.pg_employee_repository import PgEmployeeRepository
from app.infrastructure.repositories.pg_alert_repository import PgAlertRepository
from app.infrastructure.repositories.pg_baseline_repository import PgBaselineRepository
from app.infrastructure.repositories.pg_episode_repository import InMemoryEpisodeRepository
from app.infrastructure.repositories.pg_situation_repository import InMemorySituationRepository
from app.infrastructure.repositories.pg_decision_repository import InMemoryDecisionRepository
from app.application.services.alert_episode_service import AlertEpisodeService
from app.application.services.signal_service import SignalService
from app.application.services.impact_service import ImpactService
from app.application.services.readiness_service import ReadinessService
from app.application.services.situation_service import SituationService
from app.application.services.decision_service import DecisionService

async def test():
    await create_pool()
    trip_repo = PgTripRepository()
    emp_repo = PgEmployeeRepository()
    alert_repo = PgAlertRepository()
    base_repo = PgBaselineRepository()
    ep_repo = InMemoryEpisodeRepository()
    sit_repo = InMemorySituationRepository()
    dec_repo = InMemoryDecisionRepository()
    
    ep_svc = AlertEpisodeService(alert_repo, ep_repo)
    sig_svc = SignalService()
    imp_svc = ImpactService()
    read_svc = ReadinessService(trip_repo, emp_repo, base_repo)
    sit_svc = SituationService(sit_repo, ep_repo, trip_repo, emp_repo, sig_svc, imp_svc)
    dec_svc = DecisionService(dec_repo, base_repo)

    target_date = date(2026, 7, 15)
    rows = await fetch_rows("SELECT * FROM analytics.v_trip WHERE trip_date = $1", target_date)
    print(f"Total trips on {target_date}: {len(rows)}")
    trips = [trip_repo._row_to_trip(dict(r)) for r in rows]

    created = 0
    for trip in trips:
        episodes = await ep_svc.build_episodes_for_trip(trip.trip_id)
        readiness = await read_svc.calculate_shift_readiness(trip.business_unit, trip.office or '', trip.shift or '', trip.trip_direction or '', target_date)
        baseline = None
        signals = sig_svc.detect_signals(trip, episodes, baseline, readiness)
        sit = await sit_svc.evaluate_situation(trip, episodes, signals, baseline, readiness)
        if sit:
            created += 1
            print(f"-> Situation: {sit.situation_type.value} | {sit.title} | Priority: {sit.priority.value}")

    sits = await sit_svc.get_active_situations()
    print(f"\nTotal active situations: {len(sits)}")
    for s in sits:
        d = await dec_svc.generate_decision(s)
        print(f"Decision for {s.situation_id[:8]} ({s.situation_type.value}): recommended={d.recommended_action}, options={len(d.options)}")

    await close_pool()

if __name__ == "__main__":
    asyncio.run(test())
