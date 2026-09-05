"""Data-quality bitmask flags, all confirmed against the data.

Rows are flagged, never dropped: every flag function returns an integer
bitmask series that gets stored in a fact table's dq_flags column.
app/metrics/compiler.py excludes flagged rows from a metric's
denominator via ``(dq_flags & excluded_mask) = 0``, and reports how many
rows that excluded (total row count minus the filtered count) alongside
the metric value.

Bit layout:

    DELAY_UNREPORTED        1   fact_trip
    BILLED_KM_ZERO          2   fact_trip_billing
    NEGATIVE_COST           4   fact_trip_billing
    FUEL_CONTRACT_MISMATCH  8   fact_trip_billing
    SLAB_MISSING            16  fact_trip_billing
    ROSTER_OVERCOUNT        32  fact_trip
    NO_BILL_MATCH           64  fact_trip
    IMPLAUSIBLE_DURATION    128 fact_trip

fact_trip_employee has no flag definitions of its own -- none of the
eight flags describe employee-leg-grain facts. Its dq_flags column is a
denormalised copy of the owning trip's fact_trip.dq_flags
(``propagate_employee_flags``), so a metric computed at the employee
grain (e.g. escort_coverage_night_female) still excludes rows whose
trip is otherwise known to be bad.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

DELAY_UNREPORTED = 1
BILLED_KM_ZERO = 2
NEGATIVE_COST = 4
FUEL_CONTRACT_MISMATCH = 8
SLAB_MISSING = 16
ROSTER_OVERCOUNT = 32
NO_BILL_MATCH = 64
IMPLAUSIBLE_DURATION = 128

FLAG_BITS: dict[str, int] = {
    "DELAY_UNREPORTED": DELAY_UNREPORTED,
    "BILLED_KM_ZERO": BILLED_KM_ZERO,
    "NEGATIVE_COST": NEGATIVE_COST,
    "FUEL_CONTRACT_MISMATCH": FUEL_CONTRACT_MISMATCH,
    "SLAB_MISSING": SLAB_MISSING,
    "ROSTER_OVERCOUNT": ROSTER_OVERCOUNT,
    "NO_BILL_MATCH": NO_BILL_MATCH,
    "IMPLAUSIBLE_DURATION": IMPLAUSIBLE_DURATION,
}

TRIP_FLAGS = DELAY_UNREPORTED | ROSTER_OVERCOUNT | NO_BILL_MATCH | IMPLAUSIBLE_DURATION
BILLING_FLAGS = BILLED_KM_ZERO | NEGATIVE_COST | FUEL_CONTRACT_MISMATCH | SLAB_MISSING

_ELECTRIC_RE = r"ELEC|EV"


def mask_from_names(names: list[str]) -> int:
    """Resolve a list of flag names (as used in registry.yaml) to a bitmask."""
    mask = 0
    for name in names:
        if name not in FLAG_BITS:
            raise ValueError(f"unknown dq flag {name!r}; declared flags are {sorted(FLAG_BITS)}")
        mask |= FLAG_BITS[name]
    return mask


def flag_trip(fact_trip: pd.DataFrame, billed_trip_ids: set) -> pd.Series:
    """Compute dq_flags for fact_trip rows.

    - DELAY_UNREPORTED: computed_arrival_delay_min > 10 AND reported_delay_minutes = 0
    - ROSTER_OVERCOUNT: actual_employee_cnt > planned_employee_cnt
    - NO_BILL_MATCH: trip_id absent from billing
    - IMPLAUSIBLE_DURATION: actual duration < 1 min or > 6 hours
    """
    flags = np.zeros(len(fact_trip), dtype=np.int64)

    delay_unreported = (fact_trip["computed_arrival_delay_min"] > 10) & (
        fact_trip["reported_delay_minutes"] == 0
    )
    flags |= np.where(delay_unreported.fillna(False), DELAY_UNREPORTED, 0)

    roster_overcount = fact_trip["actual_employee_cnt"] > fact_trip["planned_employee_cnt"]
    flags |= np.where(roster_overcount.fillna(False), ROSTER_OVERCOUNT, 0)

    no_bill_match = ~fact_trip["trip_id"].isin(billed_trip_ids)
    flags |= np.where(no_bill_match.fillna(True), NO_BILL_MATCH, 0)

    actual_duration_min = (fact_trip["actual_end_epoch"] - fact_trip["actual_start_epoch"]) / 60.0
    implausible = (actual_duration_min < 1) | (actual_duration_min > 360)
    flags |= np.where(implausible.fillna(False), IMPLAUSIBLE_DURATION, 0)

    return pd.Series(flags, index=fact_trip.index, dtype="int64")


def flag_billing(fact_trip_billing: pd.DataFrame) -> pd.Series:
    """Compute dq_flags for fact_trip_billing rows.

    - BILLED_KM_ZERO: billed_km = 0 AND traveled_km > 0 (traveled_km denormalised from fact_trip)
    - NEGATIVE_COST: trip_cost < 0
    - FUEL_CONTRACT_MISMATCH: contract contains 'EV' AND actual_cab_fuel_type not electric
      (actual_cab_fuel_type denormalised from fact_trip)
    - SLAB_MISSING: slab_name is null
    """
    flags = np.zeros(len(fact_trip_billing), dtype=np.int64)

    billed_km_zero = (fact_trip_billing["billed_km"] == 0) & (fact_trip_billing["traveled_km"] > 0)
    flags |= np.where(billed_km_zero.fillna(False), BILLED_KM_ZERO, 0)

    negative_cost = fact_trip_billing["trip_cost"] < 0
    flags |= np.where(negative_cost.fillna(False), NEGATIVE_COST, 0)

    is_ev_contract = fact_trip_billing["contract"].astype(str).str.upper().str.contains("EV", na=False)
    is_electric_cab = (
        fact_trip_billing["actual_cab_fuel_type"].astype(str).str.upper().str.contains(_ELECTRIC_RE, regex=True, na=False)
    )
    fuel_mismatch = is_ev_contract & ~is_electric_cab
    flags |= np.where(fuel_mismatch.fillna(False), FUEL_CONTRACT_MISMATCH, 0)

    slab_missing = fact_trip_billing["slab_name"].isna()
    flags |= np.where(slab_missing.fillna(True), SLAB_MISSING, 0)

    return pd.Series(flags, index=fact_trip_billing.index, dtype="int64")


def propagate_employee_flags(fact_trip_employee: pd.DataFrame, fact_trip: pd.DataFrame) -> pd.Series:
    """Copy each employee row's dq_flags from its owning fact_trip row."""
    flags_by_trip = fact_trip.set_index("trip_id")["dq_flags"]
    return fact_trip_employee["trip_id"].map(flags_by_trip).fillna(0).astype("int64")


def flag_counts(flags: pd.Series) -> dict[str, int]:
    """Per-flag set counts, for diagnostics and tests (not a metric input)."""
    return {name: int((flags & bit != 0).sum()) for name, bit in FLAG_BITS.items()}
