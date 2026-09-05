from __future__ import annotations

import pytest
from datetime import date
from unittest.mock import AsyncMock
from app.domain.entities import Trip
from app.application.services.readiness_service import ReadinessService


@pytest.fixture
def mock_repos():
    trip_repo = AsyncMock()
    emp_repo = AsyncMock()
    baseline_repo = AsyncMock()
    baseline_repo.get_shift_baseline.return_value = {
        "readiness_score_mean": 0.92,
        "p90_delay": 8.0,
        "p95_delay": 12.0,
    }
    return trip_repo, emp_repo, baseline_repo


@pytest.mark.asyncio
async def test_perfect_readiness(mock_repos):
    """All employees on time -> 1.0 (100%)."""
    trip_repo, emp_repo, baseline_repo = mock_repos
    trip_repo.get_trips_for_shift.return_value = [
        Trip(
            trip_id=1,
            trip_date=date(2026, 7, 15),
            business_unit="catalyst-Slc",
            office="Oakmont",
            planned_employee_cnt=50,
            actual_employee_cnt=50,
            noshow_cnt=0,
            is_on_time=True,
        )
    ]
    emp_repo.get_shift_employee_stats.return_value = {
        "total_employees": 50,
        "boarded_on_time_cnt": 50,
        "late_pickups": 0,
        "no_shows": 0,
    }

    svc = ReadinessService(trip_repo, emp_repo, baseline_repo)
    result = await svc.calculate_shift_readiness("catalyst-Slc", "Oakmont", "03:00", "LOGIN", date(2026, 7, 15))

    assert result.readiness_score == 1.0
    assert result.employees_expected == 50
    assert result.employees_ready_on_time == 50
    assert result.employees_late == 0
    assert result.delta_pp == pytest.approx(8.0, 0.1)  # 100 - 92 = +8pp


@pytest.mark.asyncio
async def test_partial_readiness(mock_repos):
    """Some late, some no-show -> accurate transparent calculation."""
    trip_repo, emp_repo, baseline_repo = mock_repos
    trip_repo.get_trips_for_shift.return_value = [
        Trip(
            trip_id=2,
            trip_date=date(2026, 7, 15),
            business_unit="catalyst-Slc",
            office="Oakmont",
            planned_employee_cnt=100,
            actual_employee_cnt=95,
            noshow_cnt=5,
            is_on_time=False,
        )
    ]
    emp_repo.get_shift_employee_stats.return_value = {
        "total_employees": 100,
        "boarded_on_time_cnt": 75,
        "late_pickups": 20,
        "no_shows": 5,
    }

    svc = ReadinessService(trip_repo, emp_repo, baseline_repo)
    result = await svc.calculate_shift_readiness("catalyst-Slc", "Oakmont", "03:00", "LOGIN", date(2026, 7, 15))

    assert result.readiness_score == 0.75
    assert result.employees_expected == 100
    assert result.employees_ready_on_time == 75
    assert result.employees_late == 20
    assert result.employees_noshow == 5
    assert result.delta_pp == pytest.approx(-17.0, 0.1)  # 75 - 92 = -17pp


@pytest.mark.asyncio
async def test_readiness_empty_shift(mock_repos):
    """No trips -> handles gracefully without divide-by-zero."""
    trip_repo, emp_repo, baseline_repo = mock_repos
    trip_repo.get_trips_for_shift.return_value = []
    emp_repo.get_shift_employee_stats.return_value = {}

    svc = ReadinessService(trip_repo, emp_repo, baseline_repo)
    result = await svc.calculate_shift_readiness("catalyst-Slc", "Oakmont", "03:00", "LOGIN", date(2026, 7, 15))

    assert result.readiness_score == 0.0
    assert result.employees_expected == 0
    assert result.affected_trips == 0


@pytest.mark.asyncio
async def test_readiness_deterministic(mock_repos):
    """Same inputs always produce strictly identical outputs."""
    trip_repo, emp_repo, baseline_repo = mock_repos
    trip_repo.get_trips_for_shift.return_value = [
        Trip(
            trip_id=3,
            trip_date=date(2026, 7, 15),
            business_unit="catalyst-Slc",
            office="Oakmont",
            planned_employee_cnt=40,
            actual_employee_cnt=36,
            noshow_cnt=4,
            is_on_time=True,
        )
    ]
    emp_repo.get_shift_employee_stats.return_value = {
        "total_employees": 40,
        "boarded_on_time_cnt": 32,
        "late_pickups": 4,
        "no_shows": 4,
    }

    svc = ReadinessService(trip_repo, emp_repo, baseline_repo)
    r1 = await svc.calculate_shift_readiness("catalyst-Slc", "Oakmont", "03:00", "LOGIN", date(2026, 7, 15))
    r2 = await svc.calculate_shift_readiness("catalyst-Slc", "Oakmont", "03:00", "LOGIN", date(2026, 7, 15))

    assert r1.readiness_score == r2.readiness_score
    assert r1.delta_pp == r2.delta_pp
    assert r1.employees_at_risk == r2.employees_at_risk
