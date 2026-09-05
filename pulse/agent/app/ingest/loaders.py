"""Raw CSV resolution and loading for the pulse warehouse.

Confirmed hazards this module handles (see scripts/find_story.py):

- Comma-mangled numerics: ride and feedback are fully mangled ("1,234"),
  emp is clean, bill is mixed. ``to_num`` is applied unconditionally to
  every numeric column of every file -- it is idempotent on already-clean
  input, so there is no need to special-case which files are dirty.
- Three date formats, each file internally consistent: ISO for emp,
  "July 1, 2026" for ride, "May 1, 2026, 12:00 AM" for bill. Each file is
  parsed with its own explicit strptime format -- no format sniffing.
- Epochs are seconds, not milliseconds. ``_assert_epoch_is_seconds``
  checks one sample value lands in 2026 under the seconds interpretation.

Feedback and alert data are out of scope: feedback ratings are
effectively constant (>=90% modal share on every rating column) and
marshal_rating is null-coded-as-zero, so the file is not ingested;
alert_data.csv is not present on disk.
"""

from __future__ import annotations

import glob
import os

import pandas as pd

from app.config import get_settings

# Directories searched, in order, for the source CSVs. Mirrors the approach
# in scripts/find_story.py so ad-hoc analysis and the ingest pipeline agree
# on where data lives.
SEARCH_DIRS = [
    "data/raw",
    ".",
    os.path.expanduser("~/Downloads"),
]

RIDE_NUMERIC_COLS = [
    "trip_id",
    "actual_cab_capacity",
    "planned_km",
    "traveled_km",
    "planned_start_epoch",
    "planned_end_epoch",
    "actual_start_epoch",
    "actual_end_epoch",
    "delay_minutes",
    "plannedemployee_cnt",
    "actualemployee_cnt",
    "noshow_cnt",
]
EMP_NUMERIC_COLS = [
    "trip_id",
    "planned_pickup_epoch",
    "planned_drop_epoch",
    "actual_pickup_epoch",
    "actual_drop_epoch",
    "planned_km",
    "traveled_km",
    "stwid",
]
BILL_NUMERIC_COLS = [
    "trip_id",
    "total_trip_km",
    "trip_cost",
]

RIDE_DATE_FORMAT = "%B %d, %Y"          # "July 1, 2026"
EMP_DATE_FORMAT = "%Y-%m-%d"            # ISO
BILL_DATETIME_FORMAT = "%B %d, %Y, %I:%M %p"  # "May 1, 2026, 12:00 AM"


def to_num(series: pd.Series) -> pd.Series:
    """Coerce a comma-mangled numeric string column to float.

    Idempotent: applying it to an already-clean numeric/str column is a
    no-op beyond the dtype coercion, so callers never need to know in
    advance whether a given file's column is dirty.
    """
    return pd.to_numeric(
        series.astype(str).str.replace(",", "", regex=False),
        errors="coerce",
    )


def _find_file(*name_fragments: str, search_dirs: list[str] | None = None) -> str | None:
    """Find a CSV whose normalised filename contains every fragment.

    Normalisation lowercases the basename and strips non-alphanumeric
    characters, so "Ride_data _trip-July_2026.csv" matches ("ride", "data").
    """
    dirs = search_dirs if search_dirs is not None else SEARCH_DIRS
    for d in dirs:
        for path in sorted(glob.glob(os.path.join(d, "*.csv"))):
            normalised = "".join(ch for ch in os.path.basename(path).lower() if ch.isalnum())
            if all(fragment in normalised for fragment in name_fragments):
                return path
    return None


def _search_dirs() -> list[str]:
    settings = get_settings()
    raw_dir = str(settings.raw_data_dir)
    dirs = [raw_dir]
    dirs.extend(d for d in SEARCH_DIRS if d != "data/raw")
    return dirs


def resolve_ride_path() -> str | None:
    return _find_file("ride", "data", search_dirs=_search_dirs())


def resolve_emp_path() -> str | None:
    return _find_file("emp", "data", search_dirs=_search_dirs())


def resolve_bill_path() -> str | None:
    return _find_file("bill", "data", search_dirs=_search_dirs())


def _assert_epoch_is_seconds(df: pd.DataFrame, column: str) -> None:
    """Sanity-check that ``column`` holds Unix seconds landing in 2026.

    Guards against a future data drop silently switching to millisecond
    epochs, which would make every downstream delay computation wrong by
    a factor of 1000 without raising an obvious error.
    """
    sample = df[column].dropna()
    if sample.empty:
        return
    as_seconds = pd.to_datetime(sample.iloc[0], unit="s", errors="coerce")
    if as_seconds is pd.NaT or as_seconds.year != 2026:
        raise AssertionError(
            f"{column} sample value {sample.iloc[0]!r} does not land in 2026 "
            "when interpreted as Unix seconds -- epoch unit assumption is wrong"
        )


def load_ride(path: str | os.PathLike | None = None) -> pd.DataFrame:
    """Load ride_data: one row per trip."""
    path = path or resolve_ride_path()
    if path is None:
        raise FileNotFoundError("ride_data CSV not found in any search directory")
    df = pd.read_csv(path, dtype=str, low_memory=False)
    for col in RIDE_NUMERIC_COLS:
        df[col] = to_num(df[col])
    _assert_epoch_is_seconds(df, "planned_start_epoch")
    df["trip_date"] = pd.to_datetime(
        df["trip_date"].astype(str).str.strip(), format=RIDE_DATE_FORMAT, errors="coerce"
    )
    return df


def load_emp(path: str | os.PathLike | None = None) -> pd.DataFrame:
    """Load emp_data: one row per employee per trip."""
    path = path or resolve_emp_path()
    if path is None:
        raise FileNotFoundError("emp_data CSV not found in any search directory")
    df = pd.read_csv(path, dtype=str, low_memory=False)
    for col in EMP_NUMERIC_COLS:
        df[col] = to_num(df[col])
    _assert_epoch_is_seconds(df, "planned_pickup_epoch")
    df["trip_date"] = pd.to_datetime(
        df["trip_date"].astype(str).str.strip(), format=EMP_DATE_FORMAT, errors="coerce"
    )
    return df


def load_bill(path: str | os.PathLike | None = None) -> pd.DataFrame:
    """Load bill_data: one row per billed trip."""
    path = path or resolve_bill_path()
    if path is None:
        raise FileNotFoundError("bill_data CSV not found in any search directory")
    df = pd.read_csv(path, dtype=str, low_memory=False)
    for col in BILL_NUMERIC_COLS:
        df[col] = to_num(df[col])
    for col in ("cycle_start", "cycle_end"):
        df[col] = pd.to_datetime(
            df[col].astype(str).str.strip(), format=BILL_DATETIME_FORMAT, errors="coerce"
        )
    return df
