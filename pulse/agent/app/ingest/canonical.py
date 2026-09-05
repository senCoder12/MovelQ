"""Derive canonical fact tables from loaded raw frames.

Every transformation here is grounded in a confirmed finding from
scripts/find_story.py -- see the docstring on each function for the
specific check it corresponds to.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

_ADHOC_LITERALS = {"NON SHIFT", "ADHOC"}
_SHIFT_HOUR_RE = re.compile(r"^(\d{1,2}):(\d{2})")
_SHIFT_SUFFIX_RE = re.compile(r"(:\d{2})$")


def _is_night_hour(hour: pd.Series) -> pd.Series:
    """hour >= 20 or hour < 6 -- confirmed night boundary (find_story CHECK 3 / 8).

    Reused as the shift_bucket boundary so escort_coverage_night_female's
    "night" and shift_bucket's "night" always agree.
    """
    return (hour >= 20) | (hour < 6)


def split_business_unit(df: pd.DataFrame) -> pd.DataFrame:
    """Split business_unit on "-" into tenant_id and site_code.

    Confirmed values (find_story CHECK 0b, HAZARD 2): tenants catalyst /
    orbit / pinnacle / vanta, sites Aus / Sac / Sea / Slc, 5 distinct
    business_unit values total (one tenant has two sites).
    """
    parts = df["business_unit"].astype(str).str.split("-", n=1, expand=True)
    df = df.copy()
    df["tenant_id"] = parts[0]
    df["site_code"] = parts[1] if parts.shape[1] > 1 else np.nan
    return df


def shift_suffix(shift_type: pd.Series) -> pd.Series:
    """Extract the minute portion of shift_type, e.g. "16:16" -> ":16".

    This is the :16 finding's join key (find_story CHECK 8): it must be
    kept as its own column, never collapsed into shift_bucket, or the
    :16 cluster becomes unqueryable.
    """
    return shift_type.astype(str).str.extract(_SHIFT_SUFFIX_RE, expand=False)


def shift_bucket(shift_type: pd.Series) -> pd.Series:
    """Bucket a shift_type column into morning/afternoon/evening/night/adhoc.

    "Non Shift" and "Adhoc" literals, and any shift_type that doesn't
    parse to an HH:MM hour, go to "adhoc". The night boundary
    (hour >= 20 or hour < 6) matches the escort-compliance night
    definition confirmed in find_story CHECK 3, so shift_bucket == "night"
    is exactly the population escort_coverage_night_female measures over.
    """
    raw = shift_type.astype(str).str.strip()
    hour = pd.to_numeric(raw.str.extract(_SHIFT_HOUR_RE, expand=False)[0], errors="coerce")

    bucket = pd.Series("adhoc", index=shift_type.index, dtype=object)
    parsed = hour.notna()
    bucket[parsed & _is_night_hour(hour)] = "night"
    bucket[parsed & hour.between(6, 11)] = "morning"
    bucket[parsed & hour.between(12, 16)] = "afternoon"
    bucket[parsed & hour.between(17, 19)] = "evening"
    bucket[raw.str.upper().isin(_ADHOC_LITERALS)] = "adhoc"
    return bucket


def normalise_slab(slab_name: pd.Series) -> pd.Series:
    """Collapse the ~28 slab_name spellings into their ~8 real bands.

    "0-20", "0 - 20", "Slab-0-20" all become "0-20". Steps: strip, lower,
    drop a leading "slab" token (with any separator), collapse whitespace
    around dashes, then drop remaining whitespace. The raw value is kept
    alongside in slab_name; this only populates slab_normalised.
    """
    s = slab_name.astype(str).str.strip().str.lower()
    s = s.str.replace(r"^slab[\s_-]*", "", regex=True)
    s = s.str.replace(r"\s*-\s*", "-", regex=True)
    s = s.str.replace(r"\s+", "", regex=True)
    s = s.where(slab_name.notna(), np.nan)
    s = s.mask(s == "", np.nan)
    return s


def build_fact_trip(ride: pd.DataFrame) -> pd.DataFrame:
    """Build fact_trip from a loaded ride frame.

    computed_arrival_delay_min and computed_start_delay_min are the
    confirmed CHECK 2 formulas: (actual - planned) epoch, in minutes.
    """
    ride = split_business_unit(ride)
    out = pd.DataFrame(
        {
            "tenant_id": ride["tenant_id"],
            "site_code": ride["site_code"],
            "trip_id": ride["trip_id"].astype("Int64"),
            "trip_date": ride["trip_date"].dt.date,
            "office": ride["office"],
            "product_type": ride["product_type"],
            "shift_type": ride["shift_type"],
            "shift_bucket": shift_bucket(ride["shift_type"]),
            "shift_suffix": shift_suffix(ride["shift_type"]),
            "trip_direction": ride["trip_direction"],
            "vendor_id": ride["vendor_id"],
            "route_source": ride["route_source"],
            "planned_start_epoch": ride["planned_start_epoch"],
            "planned_end_epoch": ride["planned_end_epoch"],
            "actual_start_epoch": ride["actual_start_epoch"],
            "actual_end_epoch": ride["actual_end_epoch"],
            "computed_start_delay_min": (ride["actual_start_epoch"] - ride["planned_start_epoch"]) / 60.0,
            "computed_arrival_delay_min": (ride["actual_end_epoch"] - ride["planned_end_epoch"]) / 60.0,
            "reported_delay_minutes": ride["delay_minutes"],
            "delay_reason": ride["delay_reason"],
            "planned_km": ride["planned_km"],
            "traveled_km": ride["traveled_km"],
            "actual_cab_capacity": ride["actual_cab_capacity"],
            "actual_cab_fuel_type": ride["actual_cab_fuel_type"],
            "planned_employee_cnt": ride["plannedemployee_cnt"],
            "actual_employee_cnt": ride["actualemployee_cnt"],
            "noshow_cnt": ride["noshow_cnt"],
            "actual_escort": ride["actual_escort"],
            "is_driver_nc": ride["is_driver_nc"],
            "is_cab_nc": ride["is_cab_nc"],
            "trip_nodal": ride["trip_nodal"],
        }
    )
    return out


def build_fact_trip_employee(emp: pd.DataFrame, fact_trip: pd.DataFrame) -> pd.DataFrame:
    """Build fact_trip_employee from a loaded emp frame.

    actual_escort is denormalised from fact_trip (see schema.sql):
    escort is recorded once per trip, not per employee leg, but the
    escort_coverage_night_female metric needs it alongside gender and
    shift_bucket, and app/metrics/compiler.py queries a single table
    with no JOIN.
    """
    emp = split_business_unit(emp)
    # emp_data covers far more trip_ids than the July ride_data drop
    # (608,793 distinct vs. 215,885): restrict to legs whose trip is one
    # ride actually recorded, matching find_story CHECK 3's inner join.
    # Otherwise "actual_escort" is NaN for the unmatched majority and
    # every downstream flag/metric built on it is silently wrong.
    emp = emp[emp["trip_id"].isin(fact_trip["trip_id"])].copy()
    escort_by_trip = fact_trip.set_index("trip_id")["actual_escort"]

    out = pd.DataFrame(
        {
            "tenant_id": emp["tenant_id"],
            "site_code": emp["site_code"],
            "trip_id": emp["trip_id"].astype("Int64"),
            "stwid": emp["stwid"].astype("Int64"),
            "trip_date": emp["trip_date"].dt.date,
            "office": emp["office"],
            "product_type": emp["product_type"],
            "shift_type": emp["shift_type"],
            "shift_bucket": shift_bucket(emp["shift_type"]),
            "planned_pickup_epoch": emp["planned_pickup_epoch"],
            "planned_drop_epoch": emp["planned_drop_epoch"],
            "actual_pickup_epoch": emp["actual_pickup_epoch"],
            "actual_drop_epoch": emp["actual_drop_epoch"],
            "computed_pickup_delay_min": (emp["actual_pickup_epoch"] - emp["planned_pickup_epoch"]) / 60.0,
            "computed_drop_delay_min": (emp["actual_drop_epoch"] - emp["planned_drop_epoch"]) / 60.0,
            "planned_km": emp["planned_km"],
            "traveled_km": emp["traveled_km"],
            "signintype": emp["signintype"],
            "gender": emp["gender"],
            "emp_role": emp["emp_role"],
            "boarding_status": emp["boarding_status"],
            "not_boarding_reason": emp["not_boarding_reason"],
            "is_no_show": emp["is_no_show"],
        }
    )
    out["actual_escort"] = emp["trip_id"].map(escort_by_trip).values
    return out


def build_fact_trip_billing(bill: pd.DataFrame, fact_trip: pd.DataFrame) -> pd.DataFrame:
    """Build fact_trip_billing from a loaded bill frame.

    traveled_km, actual_cab_fuel_type and actual_employee_cnt are
    denormalised from fact_trip for the same single-table-query reason
    as fact_trip_employee.actual_escort above.
    """
    bill = split_business_unit(bill)
    # bill_data covers more trip_ids than fact_trip too (613,783 distinct
    # vs. 215,885): restrict to billed trips ride actually recorded, same
    # reasoning as fact_trip_employee above -- matches find_story CHECK 4's
    # inner join (ride.merge(bill, on="trip_id", how="inner")).
    bill = bill[bill["trip_id"].isin(fact_trip["trip_id"])].copy()
    trip_cols = fact_trip.set_index("trip_id")[["traveled_km", "actual_cab_fuel_type", "actual_employee_cnt"]]

    out = pd.DataFrame(
        {
            "tenant_id": bill["tenant_id"],
            "site_code": bill["site_code"],
            "trip_id": bill["trip_id"].astype("Int64"),
            "cycle_start": bill["cycle_start"],
            "cycle_end": bill["cycle_end"],
            "office": bill["office"],
            "vendor": bill["vendor"],
            "contract": bill["contract"],
            "slab_name": bill["slab_name"],
            "slab_normalised": normalise_slab(bill["slab_name"]),
            "billed_km": bill["total_trip_km"],
            "trip_cost": bill["trip_cost"],
        }
    )
    joined = trip_cols.reindex(bill["trip_id"].values)
    out["traveled_km"] = joined["traveled_km"].values
    out["actual_cab_fuel_type"] = joined["actual_cab_fuel_type"].values
    out["actual_employee_cnt"] = joined["actual_employee_cnt"].values
    return out
