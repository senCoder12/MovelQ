"""Ingest layer tests, asserted against confirmed figures from
scripts/find_story.py.

These tests run against the real source CSVs (resolved the same way
app/ingest/loaders.py resolves them in production: RAW_DATA_DIR, then a
handful of fallback locations including ~/Downloads). If none of the
three files can be found, the whole module is skipped rather than
failed -- CI environments without the hackathon data drop shouldn't
report a false ingest failure.

Per the brief: if an assertion here fails against real data, the ingest
is wrong -- these expected values must not be adjusted to make a test
pass.
"""

from __future__ import annotations

import pandas as pd
import pytest

from app.ingest import canonical, loaders, quality

RIDE_PATH = loaders.resolve_ride_path()
EMP_PATH = loaders.resolve_emp_path()
BILL_PATH = loaders.resolve_bill_path()

pytestmark = pytest.mark.skipif(
    not (RIDE_PATH and EMP_PATH and BILL_PATH),
    reason="ride/emp/bill source CSVs not found in any search directory",
)


@pytest.fixture(scope="module")
def facts():
    ride = loaders.load_ride(RIDE_PATH)
    emp = loaders.load_emp(EMP_PATH)
    bill = loaders.load_bill(BILL_PATH)

    fact_trip = canonical.build_fact_trip(ride)
    fact_trip_employee = canonical.build_fact_trip_employee(emp, fact_trip)
    fact_trip_billing = canonical.build_fact_trip_billing(bill, fact_trip)

    billed_trip_ids = set(fact_trip_billing["trip_id"].dropna())
    fact_trip["dq_flags"] = quality.flag_trip(fact_trip, billed_trip_ids)
    fact_trip_billing["dq_flags"] = quality.flag_billing(fact_trip_billing)
    fact_trip_employee["dq_flags"] = quality.propagate_employee_flags(fact_trip_employee, fact_trip)

    return {
        "ride": ride,
        "emp": emp,
        "bill": bill,
        "fact_trip": fact_trip,
        "fact_trip_employee": fact_trip_employee,
        "fact_trip_billing": fact_trip_billing,
    }


def _escorted_false(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.upper().isin(["FALSE", "0", "NO", "F"])


def test_ride_emp_trip_id_overlap(facts):
    ride_ids = set(facts["fact_trip"]["trip_id"].dropna())
    emp_ids = set(facts["fact_trip_employee"]["trip_id"].dropna())
    overlap = ride_ids & emp_ids
    assert len(overlap) == 215_885
    assert len(overlap) / min(len(ride_ids), len(emp_ids)) == pytest.approx(1.00, abs=0.001)


def test_ride_bill_trip_id_overlap(facts):
    """fact_trip_billing is built as an inner join onto fact_trip (see
    canonical.build_fact_trip_billing), so it is always a subset of
    fact_trip's trip_ids by construction -- the 99.79%-of-smaller-set
    ratio is only meaningful measured on the raw, pre-join CSVs."""
    ride_ids = set(facts["ride"]["trip_id"].dropna().astype("int64"))
    bill_ids = set(facts["bill"]["trip_id"].dropna().astype("int64"))
    overlap = ride_ids & bill_ids
    assert len(overlap) == 215_423
    assert len(overlap) / min(len(ride_ids), len(bill_ids)) == pytest.approx(0.9979, abs=0.0005)

    fact_bill_ids = set(facts["fact_trip_billing"]["trip_id"].dropna())
    assert fact_bill_ids <= set(facts["fact_trip"]["trip_id"].dropna())
    assert len(fact_bill_ids) == 215_423


def test_delay_unreported_flag_count(facts):
    """DELAY_UNREPORTED: computed_arrival_delay_min > 10 AND reported_delay_minutes = 0."""
    fact_trip = facts["fact_trip"]
    flagged = int(((fact_trip["dq_flags"] & quality.DELAY_UNREPORTED) != 0).sum())
    assert flagged == 117_605


def test_16_suffix_share_of_all_trips(facts):
    """Share of :16 among trips with a determinable shift_suffix (excludes
    the ~2.3% of trips whose shift_type doesn't end in an HH:MM suffix)."""
    fact_trip = facts["fact_trip"]
    with_suffix = fact_trip["shift_suffix"].notna()
    n16 = int((fact_trip["shift_suffix"] == ":16").sum())
    share = n16 / int(with_suffix.sum())
    assert n16 == 29_854
    assert share == pytest.approx(0.1415, abs=0.0005)


def _contradiction_rate(fact_trip: pd.DataFrame, suffix: str) -> float:
    """Among NODELAY-labelled trips of one shift_suffix, the fraction that
    are actually > 10 min late by the epoch computation -- the exact
    per-suffix rate scripts/find_story.py CHECK 8a-bis computes."""
    grp = fact_trip[fact_trip["shift_suffix"] == suffix]
    valid = grp["computed_arrival_delay_min"].notna()
    nodelay = grp["delay_reason"].astype(str).str.upper() == "NODELAY"
    denom = int((nodelay & valid).sum())
    numer = int(((grp["computed_arrival_delay_min"] > 10) & nodelay & valid).sum())
    return numer / denom


def test_16_contradiction_rate(facts):
    rate = _contradiction_rate(facts["fact_trip"], ":16")
    assert rate == pytest.approx(0.584, abs=0.001)


def test_next_worst_suffix_contradiction_rate(facts):
    rate = _contradiction_rate(facts["fact_trip"], ":30")
    assert rate == pytest.approx(0.382, abs=0.001)


def test_female_night_legs_without_escort(facts):
    emp = facts["fact_trip_employee"]
    female_night = emp[(emp["gender"].astype(str).str.upper() == "FEMALE") & (emp["shift_bucket"] == "night")]
    without_escort = female_night[_escorted_false(female_night["actual_escort"])]
    assert len(female_night) == 81_174
    assert len(without_escort) == 31_838


def test_billed_km_zero_count(facts):
    billing = facts["fact_trip_billing"]
    flagged = int(((billing["dq_flags"] & quality.BILLED_KM_ZERO) != 0).sum())
    assert flagged == 82_803


def test_fuel_contract_mismatch_count(facts):
    billing = facts["fact_trip_billing"]
    flagged = int(((billing["dq_flags"] & quality.FUEL_CONTRACT_MISMATCH) != 0).sum())
    assert flagged == 2_056
