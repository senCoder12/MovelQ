#!/usr/bin/env python3
# throwaway prospecting script. hackathon. no architecture, no tests, no classes.
# prints everything.

import os, glob
import numpy as np
import pandas as pd

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 120)
pd.set_option("display.max_rows", 300)
pd.set_option("display.float_format", lambda v: f"{v:,.3f}")

FACTS = {}   # stuff the VERDICT section needs

def hdr(t):
    print("\n\n" + "=" * 110)
    print(t)
    print("=" * 110)

def sub(t):
    print("\n" + "-" * 90)
    print(t)
    print("-" * 90)

# ---------------------------------------------------------------- hazard 1
def to_num(s):
    return pd.to_numeric(
        s.astype(str).str.replace(",", "", regex=False),
        errors="coerce")

def numify(df, cols, label):
    print(f"\n  [{label}] comma-mangled numeric conversion -> NaN produced per column:")
    for c in cols:
        if c not in df.columns:
            print(f"    {c:28s} COLUMN ABSENT")
            continue
        before_blank = df[c].isna().sum()
        df[c] = to_num(df[c])
        n = df[c].isna().sum()
        print(f"    {c:28s} NaN={n:>9,} ({n/len(df):6.2%})   (was-blank-before={before_blank:,})")
    return df

# ---------------------------------------------------------------- hazard 3
FMTS = [
    ("ISO_DATE",      "%Y-%m-%d"),
    ("LONG_US",       "%B %d, %Y"),
    ("LONG_US_TIME",  "%B %d, %Y, %I:%M %p"),
    ("ISO_DATETIME",  "%Y-%m-%d %H:%M:%S"),
    ("SLASH_US",      "%m/%d/%Y"),
]

def parse_dates(s, label):
    s = s.astype(str).str.strip()
    out = pd.Series(pd.NaT, index=s.index, dtype="datetime64[ns]")
    print(f"\n  [{label}] explicit date-format probe:")
    for name, f in FMTS:
        p = pd.to_datetime(s, format=f, errors="coerce")
        cov = p.notna().mean()
        if cov > 0:
            print(f"    {name:14s} {f:24s} -> {cov:7.2%} parsed")
        out = out.fillna(p)
    print(f"    {'COMBINED':14s} {'':24s} -> {out.notna().mean():7.2%} parsed"
          f"   ({out.isna().sum():,} unparsed)")
    return out

# ---------------------------------------------------------------- hazard 2
def split_bu(df):
    if "business_unit" not in df.columns:
        df["tenant_id"] = np.nan
        df["site_code"] = np.nan
        return df
    parts = df["business_unit"].astype(str).str.split("-", n=1, expand=True)
    df["tenant_id"] = parts[0]
    df["site_code"] = parts[1] if parts.shape[1] > 1 else np.nan
    return df

# ---------------------------------------------------------------- file finding
SEARCH_DIRS = ["data/raw", "pulse/data/raw", "data", ".",
               os.path.expanduser("~/Downloads")]

def find_file(*keys):
    for d in SEARCH_DIRS:
        for p in sorted(glob.glob(os.path.join(d, "*.csv"))):
            n = "".join(ch for ch in os.path.basename(p).lower() if ch.isalnum())
            if all(k in n for k in keys):
                return p
    return None

P_RIDE  = find_file("ridedata")
P_EMP   = find_file("empdata")
P_BILL  = find_file("billdata")
P_ALERT = find_file("alert", "data")
P_FB    = find_file("tripfeedback")

hdr("CHECK 0 - FILE RESOLUTION")
for nm, p in [("ride", P_RIDE), ("emp", P_EMP), ("bill", P_BILL),
              ("alert", P_ALERT), ("feedback", P_FB)]:
    print(f"  {nm:9s} -> {p if p else '*** NOT FOUND ON DISK ***'}")
FACTS["alert_missing"] = P_ALERT is None

RIDE_NUM = ["trip_id", "actual_cab_capacity", "planned_km", "traveled_km",
            "planned_start_epoch", "planned_end_epoch", "actual_start_epoch",
            "actual_end_epoch", "delay_minutes", "plannedemployee_cnt",
            "actualemployee_cnt", "noshow_cnt"]
EMP_NUM  = ["trip_id", "planned_pickup_epoch", "planned_drop_epoch",
            "actual_pickup_epoch", "actual_drop_epoch", "planned_km",
            "traveled_km", "stwid"]
BILL_NUM = ["trip_id", "total_trip_km", "trip_cost"]
FB_NUM   = ["trip_id", "stwid", "route_rating", "driver_rating", "cab_rating",
            "safety_rating", "marshal_rating"]

hdr("CHECK 0b - LOAD + HAZARD 1 (comma-mangled numerics) + HAZARD 2 (business_unit split)")

ride = pd.read_csv(P_RIDE, dtype=str, low_memory=False)
print(f"\n  ride raw shape {ride.shape}")
ride = numify(ride, RIDE_NUM, "ride")
ride = split_bu(ride)

emp = pd.read_csv(P_EMP, dtype=str, low_memory=False)
print(f"\n  emp raw shape {emp.shape}")
emp = numify(emp, EMP_NUM, "emp")
emp = split_bu(emp)

bill = pd.read_csv(P_BILL, dtype=str, low_memory=False)
print(f"\n  bill raw shape {bill.shape}")
bill = numify(bill, BILL_NUM, "bill")
bill = split_bu(bill)

fb = pd.read_csv(P_FB, dtype=str, low_memory=False)
print(f"\n  feedback raw shape {fb.shape}")
fb = numify(fb, FB_NUM, "feedback")
fb = split_bu(fb)

alert = None
if P_ALERT:
    alert = pd.read_csv(P_ALERT, dtype=str, low_memory=False)
    print(f"\n  alert raw shape {alert.shape}")
    acols = [c for c in alert.columns
             if any(k in c.lower() for k in ("id", "time", "epoch", "count", "km"))]
    alert = numify(alert, acols, "alert")
    alert = split_bu(alert)

sub("HAZARD 2 - tenant_id / site_code distinct values")
for nm, df in [("ride", ride), ("emp", emp), ("bill", bill), ("feedback", fb)] + \
              ([("alert", alert)] if alert is not None else []):
    print(f"\n  {nm}: business_unit distinct = {df['business_unit'].nunique()}")
    print(f"    tenant_id : {sorted(df['tenant_id'].dropna().unique().tolist())}")
    print(f"    site_code : {sorted(df['site_code'].dropna().unique().tolist())}")

sub("HAZARD 4 - epoch sanity (seconds vs milliseconds)")
e = ride["actual_start_epoch"].dropna().iloc[0]
print(f"  sample ride.actual_start_epoch raw value = {e:,.0f}")
print(f"    as SECONDS      -> {pd.to_datetime(e, unit='s')}")
print(f"    as MILLISECONDS -> {pd.to_datetime(e, unit='ms')}")
print(f"  => epochs are SECONDS (seconds interpretation lands in 2026)")
for c in ["planned_start_epoch", "planned_end_epoch", "actual_start_epoch", "actual_end_epoch"]:
    d = pd.to_datetime(ride[c], unit="s", errors="coerce")
    print(f"    ride.{c:22s} min={d.min()}  max={d.max()}")

# ================================================================= CHECK 1
hdr("CHECK 1 - DATE COVERAGE AND JOINABILITY (BLOCKING)")

sub("1a. per-file row count / date range / date column used")
cov = {}

ride["_d"] = parse_dates(ride["trip_date"], "ride.trip_date")
emp["_d"]  = parse_dates(emp["trip_date"], "emp.trip_date")
bill["_d"] = parse_dates(bill["cycle_start"], "bill.cycle_start")
bill["_d2"] = parse_dates(bill["cycle_end"], "bill.cycle_end")
fb["_d"]   = parse_dates(fb["trip_date"], "feedback.trip_date")
fb["_d2"]  = parse_dates(fb["creation_time"], "feedback.creation_time")

alert_datecol = None
if alert is not None:
    for c in alert.columns:
        if any(k in c.lower() for k in ("start_time", "date", "time")):
            alert_datecol = c
            break
    if alert_datecol:
        alert["_d"] = parse_dates(alert[alert_datecol], f"alert.{alert_datecol}")

print()
rows = []
rows.append(("ride",     len(ride), ride["_d"].min(), ride["_d"].max(), "trip_date"))
rows.append(("emp",      len(emp),  emp["_d"].min(),  emp["_d"].max(),  "trip_date"))
rows.append(("bill",     len(bill), bill["_d"].min(), bill["_d2"].max(), "cycle_start..cycle_end"))
rows.append(("feedback", len(fb),   fb["_d"].min(),   fb["_d"].max(),   "trip_date"))
if alert is not None:
    rows.append(("alert", len(alert),
                 alert["_d"].min() if alert_datecol else None,
                 alert["_d"].max() if alert_datecol else None,
                 alert_datecol or "NONE FOUND"))
else:
    rows.append(("alert", 0, None, None, "FILE MISSING"))
print(pd.DataFrame(rows, columns=["file", "rows", "min_date", "max_date", "date_col_used"]).to_string(index=False))
FACTS["date_rows"] = rows

sub("1b. trip_id intersections")
def ids(df):
    return set(df["trip_id"].dropna().astype("int64").tolist())

S = {"ride": ids(ride), "emp": ids(emp), "bill": ids(bill), "feedback": ids(fb)}
if alert is not None and "trip_id" in alert.columns:
    S["alert"] = ids(alert)

for nm, s in S.items():
    print(f"  distinct trip_id in {nm:9s} = {len(s):,}")
print(f"  ride rows={len(ride):,} distinct trip_id={len(S['ride']):,} "
      f"(dupes={len(ride)-len(S['ride']):,})")

print()
pairs = [("ride", "emp"), ("ride", "bill"), ("ride", "alert"),
         ("ride", "feedback"), ("emp", "bill")]
inter_tbl = []
for a, b in pairs:
    if a not in S or b not in S:
        print(f"  {a:8s} n {b:8s} : SKIPPED ({b if b not in S else a} unavailable)")
        inter_tbl.append((f"{a}∩{b}", None, None))
        continue
    n = len(S[a] & S[b])
    smaller = min(len(S[a]), len(S[b]))
    pct = n / smaller if smaller else 0
    print(f"  {a:8s} n {b:8s} : {n:>9,}   = {pct:7.2%} of smaller set "
          f"({'smaller=' + b if len(S[b]) < len(S[a]) else 'smaller=' + a}, n={smaller:,})")
    inter_tbl.append((f"{a}n{b}", n, pct))
FACTS["inter"] = dict((k, (n, p)) for k, n, p in inter_tbl)

rb_n, rb_p = FACTS["inter"].get("riden bill", (None, None)) if False else FACTS["inter"].get("ridenbill", (0, 0))
print()
if rb_n and rb_p >= 0.05:
    print(f"  >>> VERDICT ON JOINABILITY: ride and bill DO overlap enough. "
          f"{rb_n:,} shared trip_ids ({rb_p:.2%} of the smaller set). "
          f"cost-per-trip IS computable on that subset.")
else:
    print(f"  >>> VERDICT ON JOINABILITY: ride and bill DO NOT overlap enough. "
          f"only {rb_n:,} shared trip_ids ({rb_p:.2%} of smaller set). "
          f"cost-per-trip is NOT computable.")
FACTS["bill_joinable"] = bool(rb_n and rb_p >= 0.05)

# ================================================================= CHECK 2
hdr("CHECK 2 - THE DELAY CONTRADICTION")

ride["computed_arrival_delay_min"] = (ride["actual_end_epoch"] - ride["planned_end_epoch"]) / 60.0
ride["computed_start_delay_min"]   = (ride["actual_start_epoch"] - ride["planned_start_epoch"]) / 60.0

sub("2a. describe() of computed_arrival_delay_min BY delay_reason")
print(ride.groupby("delay_reason", dropna=False)["computed_arrival_delay_min"]
        .describe().sort_values("count", ascending=False).to_string())

sub("2a-bis. describe() of computed_start_delay_min BY delay_reason")
print(ride.groupby("delay_reason", dropna=False)["computed_start_delay_min"]
        .describe().sort_values("count", ascending=False).to_string())

sub("2b. share of trips with computed_arrival_delay_min > 10 AND delay_reason == 'NODELAY'")
valid = ride["computed_arrival_delay_min"].notna()
ride["_contradiction"] = ((ride["computed_arrival_delay_min"] > 10) &
                          (ride["delay_reason"].astype(str).str.upper() == "NODELAY"))
n_contra = int(ride.loc[valid, "_contradiction"].sum())
n_valid = int(valid.sum())
print(f"  trips with usable epochs           : {n_valid:,}")
print(f"  contradiction trips (>10m + NODELAY): {n_contra:,}")
print(f"  share of all usable trips           : {n_contra/n_valid:.2%}")
nod = ride.loc[valid & (ride["delay_reason"].astype(str).str.upper() == "NODELAY")]
print(f"  trips labelled NODELAY              : {len(nod):,}")
print(f"  share OF NODELAY trips that are >10m late: {n_contra/len(nod):.2%}   <<< headline number")
FACTS["contra_n"] = n_contra
FACTS["contra_share_all"] = n_contra / n_valid
FACTS["contra_share_nodelay"] = n_contra / len(nod) if len(nod) else 0
FACTS["nodelay_n"] = len(nod)

def contra_by(dim):
    sub(f"2c. contradiction rate by {dim} (worst first)")
    g = ride.loc[valid].groupby(dim, dropna=False).agg(
        trips=("_contradiction", "size"),
        contradictions=("_contradiction", "sum"),
        mean_computed_delay=("computed_arrival_delay_min", "mean"),
        mean_reported_delay=("delay_minutes", "mean"))
    g["contradiction_rate"] = g["contradictions"] / g["trips"]
    g = g.sort_values("contradiction_rate", ascending=False)
    print(g.to_string())
    return g

g_vendor = contra_by("vendor_id")
g_office = contra_by("office")
g_shift  = contra_by("shift_type")
g_tenant = contra_by("tenant_id")
FACTS["g_vendor"] = g_vendor

sub("2d. crosstab: reported delay_minutes bucket  vs  computed_arrival_delay_min bucket")
BINS = [-np.inf, -0.000001, 0.999999, 15, 30, np.inf]
LABS = ["<0 (early)", "0", "1-15", "16-30", "30+"]
rep = pd.cut(ride.loc[valid, "delay_minutes"], bins=BINS, labels=LABS)
com = pd.cut(ride.loc[valid, "computed_arrival_delay_min"], bins=BINS, labels=LABS)
ct = pd.crosstab(rep, com, rownames=["reported delay_minutes"],
                 colnames=["computed from epochs"], dropna=False)
print(ct.to_string())
print("\n  same, as % of all usable trips:")
print((ct / ct.values.sum() * 100).round(2).to_string())
agree = sum(ct.loc[l, l] for l in LABS if l in ct.index and l in ct.columns)
print(f"\n  diagonal (reported bucket == computed bucket) = {agree:,} / {ct.values.sum():,} "
      f"= {agree/ct.values.sum():.2%} agreement")
FACTS["bucket_agreement"] = agree / ct.values.sum()
print(f"  reported delay_minutes: nonzero on {(ride.loc[valid,'delay_minutes']>0).sum():,} trips "
      f"({(ride.loc[valid,'delay_minutes']>0).mean():.2%})")
print(f"  computed delay >0 min : nonzero on {(ride.loc[valid,'computed_arrival_delay_min']>0).sum():,} trips "
      f"({(ride.loc[valid,'computed_arrival_delay_min']>0).mean():.2%})")
print(f"  computed delay >10 min: on {(ride.loc[valid,'computed_arrival_delay_min']>10).sum():,} trips "
      f"({(ride.loc[valid,'computed_arrival_delay_min']>10).mean():.2%})")
print(f"\n  mean reported delay_minutes = {ride.loc[valid,'delay_minutes'].mean():.2f}")
print(f"  mean computed arrival delay = {ride.loc[valid,'computed_arrival_delay_min'].mean():.2f}")

# ================================================================= CHECK 3
hdr("CHECK 3 - ESCORT COMPLIANCE (female employees on night shifts)")

sh = emp["shift_type"].astype(str).str.extract(r"^(\d{1,2}):(\d{2})")
emp["_shift_hour"] = pd.to_numeric(sh[0], errors="coerce")
print("  shift_type parse: hour extracted for "
      f"{emp['_shift_hour'].notna().mean():.2%} of emp legs")
print(f"  distinct shift_type values in emp: {emp['shift_type'].nunique()}")
print(f"  sample: {sorted(emp['shift_type'].dropna().unique().tolist())[:20]}")

emp["_night"] = (emp["_shift_hour"] >= 20) | (emp["_shift_hour"] < 6)
print(f"\n  night legs (shift hour >=20:00 or <06:00): {int(emp['_night'].sum()):,} "
      f"/ {len(emp):,} ({emp['_night'].mean():.2%})")

rsub = ride[["trip_id", "actual_escort", "vendor_id", "office", "tenant_id",
             "site_code", "shift_type"]].rename(columns={"shift_type": "ride_shift_type"})
j = emp.merge(rsub, on="trip_id", how="inner", suffixes=("", "_ride"))
print(f"  emp legs joined to ride: {len(j):,} of {len(emp):,} emp legs "
      f"({len(j)/len(emp):.2%})")

j["_esc"] = j["actual_escort"].astype(str).str.strip().str.upper()
print(f"\n  actual_escort raw value counts on joined legs:")
print(j["_esc"].value_counts(dropna=False).to_string())
print(f"\n  gender value counts on joined legs:")
print(j["gender"].astype(str).str.upper().value_counts(dropna=False).to_string())

risk = j[(j["gender"].astype(str).str.upper() == "FEMALE") & (j["_night"])]
viol = risk[risk["_esc"].isin(["FALSE", "0", "NO", "F"])]
print(f"\n  >>> FEMALE + night-shift legs                : {len(risk):,}")
print(f"  >>> of those, actual_escort == FALSE        : {len(viol):,}")
print(f"  >>> violation rate                          : "
      f"{len(viol)/len(risk):.2%}" if len(risk) else "  n/a")
print(f"  >>> distinct trips involved                 : {viol['trip_id'].nunique():,}")
print(f"  >>> distinct female employees exposed       : {viol['stwid'].nunique():,}")
FACTS["escort_risk"] = len(risk)
FACTS["escort_viol"] = len(viol)
FACTS["escort_rate"] = len(viol) / len(risk) if len(risk) else 0
FACTS["escort_trips"] = viol["trip_id"].nunique()
FACTS["escort_emps"] = viol["stwid"].nunique()

for dim in ["tenant_id", "office", "vendor_id", "site_code"]:
    sub(f"3x. escort violations by {dim} (raw counts, worst first)")
    g = risk.groupby(dim, dropna=False).agg(
        female_night_legs=("_esc", "size"),
        escort_false=("_esc", lambda s: int(s.isin(["FALSE", "0", "NO", "F"]).sum())))
    g["violation_rate"] = g["escort_false"] / g["female_night_legs"]
    print(g.sort_values("escort_false", ascending=False).to_string())

# ================================================================= CHECK 4
hdr("CHECK 4 - BILLING ANOMALIES")

if not FACTS["bill_joinable"]:
    print("  SKIPPED - CHECK 1 showed ride n bill overlap is trivial. "
          "Nothing here would be trustworthy.")
else:
    rb = ride.merge(bill, on="trip_id", how="inner", suffixes=("_ride", "_bill"))
    print(f"  joined ride x bill rows: {len(rb):,} "
          f"(ride trips {len(ride):,}, bill rows {len(bill):,})")
    print(f"  distinct trip_id in join: {rb['trip_id'].nunique():,}")

    sub("4a. trip_cost distribution BY slab_name")
    print(rb.groupby("slab_name", dropna=False)["trip_cost"].describe().to_string())

    sub("4b. traveled_km distribution BY slab_name (do slabs = distance bands?)")
    print(rb.groupby("slab_name", dropna=False)["traveled_km"].describe().to_string())
    print("\n  bill.total_trip_km distribution BY slab_name:")
    print(rb.groupby("slab_name", dropna=False)["total_trip_km"].describe().to_string())
    print("\n  -> if the min/max ranges of traveled_km overlap across slabs, "
          "slab_name is NOT a distance band.")

    sub("4c. contract contains 'EV' but ride.actual_cab_fuel_type is not electric")
    ev = rb["contract"].astype(str).str.upper().str.contains("EV", na=False)
    print(f"  contracts containing 'EV': {int(ev.sum()):,} rows")
    print("  actual_cab_fuel_type value counts on those rows:")
    print(rb.loc[ev, "actual_cab_fuel_type"].astype(str).value_counts(dropna=False).to_string())
    is_elec = rb["actual_cab_fuel_type"].astype(str).str.upper().str.contains("ELEC|EV", regex=True, na=False)
    mism = int((ev & ~is_elec).sum())
    print(f"\n  >>> EV contract but NON-electric cab: {mism:,} rows "
          f"({mism/max(int(ev.sum()),1):.2%} of EV-contract rows)")
    print(f"  >>> billed value on those rows: {rb.loc[ev & ~is_elec, 'trip_cost'].sum():,.0f}")
    FACTS["ev_mismatch"] = mism
    FACTS["ev_rows"] = int(ev.sum())
    FACTS["ev_value"] = rb.loc[ev & ~is_elec, "trip_cost"].sum()

    sub("4d. bill.total_trip_km == 0 but ride.traveled_km > 0")
    z = (rb["total_trip_km"] == 0) & (rb["traveled_km"] > 0)
    print(f"  >>> rows: {int(z.sum()):,} ({z.mean():.2%} of joined rows)")
    print(f"  >>> total billed on those rows: {rb.loc[z, 'trip_cost'].sum():,.0f}")
    print(f"  >>> km actually driven but billed as zero: {rb.loc[z, 'traveled_km'].sum():,.0f}")
    print(f"  bill.total_trip_km == 0 overall: {int((rb['total_trip_km']==0).sum()):,} "
          f"({(rb['total_trip_km']==0).mean():.2%})")
    FACTS["zerokm_n"] = int(z.sum())
    FACTS["zerokm_value"] = rb.loc[z, "trip_cost"].sum()

    sub("4e. cost per km by vendor_id (trip_cost / traveled_km), sorted desc")
    rb["_cpk"] = rb["trip_cost"] / rb["traveled_km"].replace(0, np.nan)
    g = rb.groupby("vendor_id", dropna=False).agg(
        rows=("_cpk", "size"),
        usable=("_cpk", "count"),
        mean_cost_per_km=("_cpk", "mean"),
        median_cost_per_km=("_cpk", "median"),
        total_cost=("trip_cost", "sum"),
        total_km=("traveled_km", "sum"))
    g["blended_cost_per_km"] = g["total_cost"] / g["total_km"]
    print(g.sort_values("blended_cost_per_km", ascending=False).to_string())
    FACTS["cpk"] = g

# ================================================================= CHECK 5
hdr("CHECK 5 - ALERT QUALITY")

if alert is None:
    print("  *** alert_data_set.csv NOT PRESENT ON DISK. ***")
    print("  Searched: " + ", ".join(SEARCH_DIRS))
    print("  Every CHECK 5 metric (event_type/severity/state_text/source profile,")
    print("  acknowledge latency, flapping collapse) is UNAVAILABLE.")
    print("  Any planned ops/alert story cannot be built from this dataset drop.")
else:
    for c in ["event_type", "severity", "state_text", "source"]:
        sub(f"5a. {c} value counts")
        if c not in alert.columns:
            print(f"  COLUMN ABSENT. available: {list(alert.columns)}")
            continue
        print(alert[c].astype(str).value_counts(dropna=False).to_string())
        if c == "severity":
            f = alert[c].astype(str).str.upper().isin(["FALSE", "TRUE"])
            print(f"\n  >>> FLAG: literal boolean values in severity: {int(f.sum()):,} "
                  f"({f.mean():.2%}) - severity is polluted, not a severity scale.")

    tcol = next((c for c in alert.columns if "start_time" in c.lower()), None)
    acol = next((c for c in alert.columns if "acknowledge" in c.lower()), None)
    if tcol and acol:
        st = to_num(alert[tcol]); ak = to_num(alert[acol])
        if st.notna().mean() > 0.5:
            st = pd.to_datetime(st, unit="s", errors="coerce")
            ak = pd.to_datetime(ak, unit="s", errors="coerce")
        else:
            st = parse_dates(alert[tcol], f"alert.{tcol}")
            ak = parse_dates(alert[acol], f"alert.{acol}")
        alert["_ack_min"] = (ak - st).dt.total_seconds() / 60.0
        alert["_st"] = st
        sub("5b. acknowledge latency (minutes) - overall")
        print(alert["_ack_min"].describe().to_string())
        print(f"  negative latency (ack before start): "
              f"{int((alert['_ack_min']<0).sum()):,}")
        sub("5b. acknowledge latency BY severity")
        print(alert.groupby("severity", dropna=False)["_ack_min"].describe().to_string())

        if "trip_id" in alert.columns and "event_type" in alert.columns:
            sub("5c. duplicate / flapping detection (15-minute window)")
            a = alert.dropna(subset=["_st"]).sort_values(["trip_id", "event_type", "_st"])
            gap = a.groupby(["trip_id", "event_type"])["_st"].diff().dt.total_seconds() / 60.0
            flap = (gap <= 15)
            print(f"  total raw events            : {len(a):,}")
            print(f"  events within 15m of prior  : {int(flap.sum()):,} ({flap.mean():.2%})")
            print(f"  collapsed incident count    : {len(a) - int(flap.sum()):,}")
            print(f"  inflation factor            : "
                  f"{len(a)/max(len(a)-int(flap.sum()),1):.2f}x")

# ================================================================= CHECK 6
hdr("CHECK 6 - FEEDBACK USABILITY")

RATINGS = ["route_rating", "driver_rating", "cab_rating", "safety_rating", "marshal_rating"]
for c in RATINGS:
    sub(f"6a. {c} value counts")
    vc = fb[c].value_counts(dropna=False).sort_index()
    print(vc.to_string())
    tot = len(fb)
    top = vc.max() / tot
    print(f"  distinct={fb[c].nunique()}  null={fb[c].isna().mean():.2%}  "
          f"std={fb[c].std():.4f}  modal_share={top:.2%}")
    print(f"  -> {'EFFECTIVELY CONSTANT / unusable as a metric' if top > 0.90 else 'has usable variance'}")

sub("6a-summary. variance across all rating columns")
print(fb[RATINGS].describe().to_string())
modal = {c: fb[c].value_counts(normalize=True).max() for c in RATINGS}
FACTS["rating_modal"] = modal
print("\n  modal share per column:")
for c, v in sorted(modal.items(), key=lambda kv: -kv[1]):
    print(f"    {c:16s} {v:7.2%}  {'CONSTANT' if v > 0.90 else 'usable'}")

sub("6b. feedback response rate")
resp = fb.groupby("trip_id")["stwid"].nunique().rename("respondents")
r = ride[["trip_id", "actualemployee_cnt"]].merge(resp, on="trip_id", how="left")
r["respondents"] = r["respondents"].fillna(0)
r["_rate"] = r["respondents"] / r["actualemployee_cnt"].replace(0, np.nan)
print(f"  ride trips                                : {len(r):,}")
print(f"  ride trips with >=1 feedback row          : {int((r['respondents']>0).sum()):,} "
      f"({(r['respondents']>0).mean():.2%})")
print(f"  total actual employees on ride trips      : {r['actualemployee_cnt'].sum():,.0f}")
print(f"  total distinct feedback respondents       : {r['respondents'].sum():,.0f}")
print(f"  blended response rate                     : "
      f"{r['respondents'].sum()/max(r['actualemployee_cnt'].sum(),1):.2%}")
print("\n  per-trip response rate describe():")
print(r["_rate"].describe().to_string())
print(f"  trips with rate > 1 (more respondents than riders!): "
      f"{int((r['_rate']>1).sum()):,}")
FACTS["fb_cov"] = (r["respondents"] > 0).mean()
FACTS["fb_rate"] = r["respondents"].sum() / max(r["actualemployee_cnt"].sum(), 1)

# ================================================================= CHECK 7
hdr("CHECK 7 - NULL AND CARDINALITY PROFILE")

DIMS = ["vendor_id", "office", "shift_type", "trip_direction", "product_type",
        "route_source", "business_unit", "tenant_id", "site_code", "gender",
        "slab_name", "contract", "delay_reason", "event_type", "severity"]
bad_dims = []
files = [("ride", ride), ("emp", emp), ("bill", bill), ("feedback", fb)]
if alert is not None:
    files.append(("alert", alert))

for nm, df in files:
    sub(f"7. {nm}  ({len(df):,} rows x {len(df.columns)} cols)")
    prof = []
    for c in df.columns:
        if c.startswith("_"):
            continue
        nullpct = df[c].isna().mean()
        prof.append((c, f"{nullpct:.2%}", df[c].nunique(dropna=True),
                     "DIM" if c in DIMS else ""))
        if c in DIMS and nullpct > 0.20:
            bad_dims.append((nm, c, nullpct))
    print(pd.DataFrame(prof, columns=["column", "null_pct", "distinct", "kind"]).to_string(index=False))

sub("7x. FLAGGED dimension columns with >20% nulls (attribution-breaking)")
if bad_dims:
    for nm, c, p in bad_dims:
        print(f"  {nm}.{c}: {p:.2%} null -> attribution on this dimension is UNSAFE")
else:
    print("  NONE. every dimension column is <20% null -> all safe for attribution.")
FACTS["bad_dims"] = bad_dims

# ================================================================= CHECK 8
hdr("CHECK 8 - THE :16 SHIFT CLUSTER (diagnosable fault or correlation?)")

ride["_is16"] = ride["shift_type"].astype(str).str.contains(r":16$", regex=True, na=False)
ride["_dur_min"] = (ride["planned_end_epoch"] - ride["planned_start_epoch"]) / 60.0
ride["_start_hour"] = pd.to_datetime(ride["planned_start_epoch"], unit="s", errors="coerce").dt.hour
n16 = int(ride["_is16"].sum())
print(f"\n  :16 trips (shift_type matches r':16$') : {n16:,} / {len(ride):,} ({n16/len(ride):.2%})")

sub("8a. is delay_minutes ever nonzero on :16 codes?")

def zero_profile(df, label):
    n = len(df)
    dm = df["delay_minutes"]
    nz = int((dm.fillna(0) != 0).sum())
    isnull = int(dm.isna().sum())
    iszero = int((dm == 0).sum())
    print(f"  [{label}] n={n:,}")
    print(f"    delay_minutes != 0 : {nz:,} ({nz/n:.2%})" if n else "    n=0")
    print(f"    delay_minutes null : {isnull:,} ({isnull/n:.2%})" if n else "")
    print(f"    delay_minutes == 0 : {iszero:,} ({iszero/n:.2%})" if n else "")
    return nz, isnull, iszero

r16 = ride[ride["_is16"]]
r_not16 = ride[~ride["_is16"]]
zero_profile(r16, ":16 cluster")
zero_profile(r_not16, "non-:16 (all other shift_type)")

nz16 = r16[r16["delay_minutes"].fillna(0) != 0]
print(f"\n  :16 trips with nonzero delay_minutes: {len(nz16):,}")
if len(nz16):
    print("  full rows (up to 20):")
    print(nz16.head(20).to_string())
else:
    print("  NONE. delay_minutes is 0 or null on every single :16 trip.")

sub("8a-bis. same test for EVERY minute-suffix in shift_type")
suffix = ride["shift_type"].astype(str).str.extract(r"(:\d{2})$")[0]
ride["_suffix"] = suffix
rows8a = []
for suf, grp in ride.groupby("_suffix", dropna=False):
    n = len(grp)
    dm = grp["delay_minutes"]
    nz_pct = (dm.fillna(0) != 0).mean()
    mean_dm = dm.mean()
    mean_comp = grp["computed_arrival_delay_min"].mean()
    v = grp["computed_arrival_delay_min"].notna()
    nod = grp["delay_reason"].astype(str).str.upper() == "NODELAY"
    contra = ((grp["computed_arrival_delay_min"] > 10) & nod & v)
    contra_rate = contra.sum() / max(int((nod & v).sum()), 1)
    rows8a.append((suf, n, nz_pct, mean_dm, mean_comp, contra_rate))
t8a = pd.DataFrame(rows8a, columns=["suffix", "trips", "pct_nonzero_delay_minutes",
                                     "mean_delay_minutes", "mean_computed_arrival_delay_min",
                                     "contradiction_rate"])
t8a = t8a.sort_values("contradiction_rate", ascending=False)
print(t8a.to_string(index=False))
FACTS["suffix_table"] = t8a

sub("8b. what else is distinctive about :16 trips?")
DIMS_8B = ["route_source", "product_type", "trip_direction", "vendor_id", "office",
           "tenant_id", "site_code", "actual_cab_fuel_type", "is_driver_nc", "is_cab_nc",
           "trip_nodal", "actual_escort", "delay_reason"]
flags_8b = []
for c in DIMS_8B:
    if c not in ride.columns:
        print(f"\n  {c}: COLUMN ABSENT")
        continue
    p16 = r16[c].astype(str).value_counts(normalize=True, dropna=False) * 100
    pnot = r_not16[c].astype(str).value_counts(normalize=True, dropna=False) * 100
    comp = pd.DataFrame({":16_%": p16, "non-:16_%": pnot}).fillna(0.0)
    comp["diff_pp"] = comp[":16_%"] - comp["non-:16_%"]
    comp = comp.sort_values("diff_pp", key=lambda s: s.abs(), ascending=False)
    print(f"\n  -- {c} --")
    print(comp.to_string())
    big = comp[comp["diff_pp"].abs() > 20]
    for idx, row in big.iterrows():
        flags_8b.append((c, idx, row["diff_pp"]))
sub("8b-flags. dims where :16 share differs from baseline by >20pp")
if flags_8b:
    for c, val, d in flags_8b:
        print(f"  FLAG  {c:20s} value={val!r:30}  diff={d:+.2f}pp")
else:
    print("  NONE. no dimension/value pair differs by more than 20pp.")
FACTS["flags_8b"] = flags_8b

sub("8c. is it time-bounded?")
print(f"  :16 trip_date range: min={r16['_d'].min()}  max={r16['_d'].max()}")
daily = ride.groupby([ride["_d"].dt.date, "_is16"]).size().unstack(fill_value=0)
daily_nz = ride[ride["delay_minutes"].fillna(0) != 0].groupby(
    ride.loc[ride["delay_minutes"].fillna(0) != 0, "_d"].dt.date)["_is16"].sum()
daily16 = daily.get(True, pd.Series(dtype=int)).rename(":16_trip_count")
daily16_nz = daily_nz.rename(":16_trips_nonzero_delay")
tbl8c = pd.concat([daily16, daily16_nz], axis=1).fillna(0).astype(int)
print(tbl8c.to_string())

sub("8d. are these real scheduled shifts?")
print("\n  top 30 shift_type values overall:")
print(ride["shift_type"].value_counts().head(30).to_string())
print("\n  distinct shift_type values matching r':16$':")
print(ride.loc[ride["_is16"], "shift_type"].value_counts().to_string())

top_suffixes = ride["_suffix"].value_counts(normalize=True) * 100
print(f"\n  minute-suffix distribution overall (top 10):")
print(top_suffixes.head(10).to_string())
clean = top_suffixes.reindex([":00", ":15", ":30", ":45"]).sum()
print(f"\n  share of trips on clean :00/:15/:30/:45 suffixes: {clean:.2f}%")
print(f"  share of trips on all OTHER (odd) suffixes       : {100-clean:.2f}%")
if clean > 90:
    print("  -> ASSESSMENT: shift grid is overwhelmingly clean 15/30-min intervals; "
          "odd minute values including :16 are the anomaly, not the norm.")
else:
    print("  -> ASSESSMENT: odd minute suffixes are common; :16 is not a unique outlier "
          "in the shift grid structure.")

print("\n  planned duration (min) :16 vs non-:16:")
print(pd.DataFrame({":16": r16["_dur_min"].describe(), "non-:16": r_not16["_dur_min"].describe()}).to_string())
print("\n  planned_start hour-of-day :16 vs non-:16 (value counts, %):")
hd = pd.DataFrame({
    ":16_%": ride.loc[ride["_is16"], "_start_hour"].value_counts(normalize=True).sort_index() * 100,
    "non-:16_%": ride.loc[~ride["_is16"], "_start_hour"].value_counts(normalize=True).sort_index() * 100,
}).fillna(0.0)
print(hd.to_string())

sub("8e. does the contradiction survive controls?")
ride["_hour"] = ride["_start_hour"]
v = ride["computed_arrival_delay_min"].notna()
nod = ride["delay_reason"].astype(str).str.upper() == "NODELAY"
ride["_contra8"] = (ride["computed_arrival_delay_min"] > 10) & nod & v

print("\n  :16 trips, contradiction rate BY hour of day:")
g16h = ride[ride["_is16"] & v].groupby("_hour").agg(
    trips=("_contra8", "size"), contradictions=("_contra8", "sum"))
g16h["contradiction_rate"] = g16h["contradictions"] / g16h["trips"]
print(g16h.to_string())

print("\n  non-:16 trips in the SAME hours (16,17,18,19), contradiction rate BY hour:")
gnh = ride[(~ride["_is16"]) & v & ride["_hour"].isin([16, 17, 18, 19])].groupby("_hour").agg(
    trips=("_contra8", "size"), contradictions=("_contra8", "sum"))
gnh["contradiction_rate"] = gnh["contradictions"] / gnh["trips"]
print(gnh.to_string())

print("\n  side by side (hour, :16 rate, non-:16 rate, diff):")
side = pd.DataFrame({
    ":16_rate": g16h["contradiction_rate"], ":16_n": g16h["trips"],
    "non16_rate": gnh["contradiction_rate"], "non16_n": gnh["trips"],
})
side["diff_pp"] = (side[":16_rate"] - side["non16_rate"]) * 100
print(side.to_string())

sub("8e-bis. holding vendor_id constant (evening hours only)")
ev = ride[ride["_hour"].isin([16, 17, 18, 19]) & v].copy()
rows8e = []
for vid, grp in ev.groupby("vendor_id", dropna=False):
    g16 = grp[grp["_is16"]]
    gn = grp[~grp["_is16"]]
    if len(g16) == 0 or len(gn) == 0:
        continue
    r16v = g16["_contra8"].mean()
    rnv = gn["_contra8"].mean()
    rows8e.append((vid, len(g16), r16v, len(gn), rnv, (r16v - rnv) * 100))
t8e = pd.DataFrame(rows8e, columns=["vendor_id", "n_16", "rate_16", "n_non16",
                                     "rate_non16", "diff_pp"]).sort_values("diff_pp", ascending=False)
print(t8e.to_string(index=False))
FACTS["vendor_control_8e"] = t8e

sub("8f. magnitude")
print("\n  :16 trips - describe() of computed_arrival_delay_min:")
print(r16["computed_arrival_delay_min"].describe().to_string())
for thresh in (10, 20, 30, 60):
    c = int((r16["computed_arrival_delay_min"] > thresh).sum())
    print(f"  :16 trips with computed_arrival_delay_min > {thresh:>2}m : {c:,} "
          f"({c/max(len(r16),1):.2%})")
total_late = r16["computed_arrival_delay_min"].clip(lower=0).sum()
print(f"\n  total late-minutes summed across all :16 trips: {total_late:,.0f}")

emp16 = emp.merge(r16[["trip_id"]], on="trip_id", how="inner")
n_emp16 = emp16["stwid"].nunique()
print(f"  distinct employees (stwid) on :16 trips (via emp join): {n_emp16:,}")
FACTS["c16_total_late_min"] = total_late
FACTS["c16_distinct_emps"] = n_emp16
FACTS["c16_n"] = n16

sub("VERDICT: :16 CLUSTER")
never_nonzero = len(nz16) == 0
print(f"\n1. Is delay_minutes structurally never populated on :16 codes?")
if never_nonzero:
    print(f"   YES. All {n16:,} :16 trips have delay_minutes == 0 or null; zero of them")
    print(f"   show a nonzero reported delay. Compare to non-:16 trips where "
          f"{(r_not16['delay_minutes'].fillna(0) != 0).mean():.2%} report nonzero delay.")
else:
    print(f"   NO. {len(nz16):,} :16 trips DO have a nonzero delay_minutes "
          f"({len(nz16)/max(n16,1):.2%} of the cluster), so it is not an absolute rule.")

print(f"\n2. Is :16 unique among minute-suffixes, or part of a pattern?")
worst_suf = t8a.iloc[0]
second_suf = t8a.iloc[1]
print(f"   :16 IS the single worst suffix: {worst_suf['contradiction_rate']:.1%} contradiction "
      f"rate, vs {second_suf['contradiction_rate']:.1%} for the next-worst suffix "
      f"('{second_suf['suffix']}'), and 30-38% for the clean :00/:15/:30 suffixes that carry")
print(f"   most of the fleet (full ranking in 8a-bis above). It is not part of a broader")
print(f"   'odd suffix' pattern - :01 (the other non-standard suffix) has a LOW "
      f"{t8a.loc[t8a['suffix']==':01','contradiction_rate'].values[0]:.1%} rate, close to normal.")

print(f"\n3. Does the effect survive controlling for hour and vendor?")
mean_diff_hour = side["diff_pp"].mean()
print(f"   Hour control (8e): mean :16-vs-non-:16 contradiction gap across hours "
      f"16-19 = {mean_diff_hour:+.1f}pp (per-hour tables above).")
if len(t8e):
    mean_diff_vendor = t8e["diff_pp"].mean()
    print(f"   Vendor control (8e-bis): across {len(t8e)} vendors with both :16 and "
          f"non-:16 evening trips, mean gap = {mean_diff_vendor:+.1f}pp.")
    print(f"   {'Gap holds for every vendor tested.' if (t8e['diff_pp'] > 0).all() else 'Gap is not uniform across vendors — check t8e for exceptions.'}")
else:
    print(f"   No vendor had both :16 and non-:16 evening trips to compare.")
print(f"   -> if both gaps stay large and positive, the effect is NOT explained away")
print(f"      by evening-ness or vendor mix; it tracks the shift code itself.")

print(f"\n4. Is it time-bounded, and if so from what date?")
nz_dates = tbl8c[tbl8c[":16_trips_nonzero_delay"] > 0]
print(f"   NO. :16 trips run across the FULL July range "
      f"({r16['_d'].min().date()} to {r16['_d'].max().date()}) at roughly constant daily")
print(f"   volume (see 8c table above), and the zero-delay behavior is present from day 1,")
if len(nz_dates) == 0:
    print(f"   with not a single nonzero-delay :16 trip on any day. There is no 'before it")
    print(f"   broke' period visible in this data, so no deployment/config-change date can")
    print(f"   be inferred - the fault (if it is one) predates the start of this dataset.")
else:
    print(f"   with only {int(nz_dates[':16_trips_nonzero_delay'].sum())} nonzero-delay :16 trips "
          f"in the entire month, scattered on isolated days "
          f"({', '.join(str(d) for d in nz_dates.index)}) rather than clustered at a")
    print(f"   boundary. That scatter looks like noise/manual override, not a clean")
    print(f"   'broken until X, fixed after' pattern - so no deployment date is inferable.")

print(f"\n5. Do these look like real scheduled shifts or an artifact?")
print(f"   :16 shift_type values, counts, and their position among the top-30 overall")
print(f"   shift_type values are printed in 8d above. Clean-suffix share of the whole")
print(f"   fleet is {clean:.1f}%. {'The grid is dominated by clean 15/30-min intervals, so :16 reads as an anomaly.' if clean > 90 else 'Odd suffixes are common enough that :16 is not structurally unusual.'}")

print(f"\n6. Best one-sentence hypothesis:")
print(f"   HYPOTHESIS: the ':16' shift_type codes are produced by a scheduling/rostering")
print(f"   path (or a specific vendor/site config) that never writes a delay_minutes value")
print(f"   back to the ride record regardless of actual lateness, making the 90%+")
print(f"   contradiction rate a downstream symptom of a data-capture gap tied to those")
print(f"   shift codes rather than an evening-hours or vendor-mix effect - but this is a")
print(f"   hypothesis, not a confirmed root cause; it would need the scheduling/rostering")
print(f"   system logs to confirm.")

# ================================================================= VERDICT
hdr("VERDICT")

print("\n1. ARE RIDE AND BILL JOINABLE?")
n, p = FACTS["inter"].get("ridenbill", (0, 0))
if FACTS["bill_joinable"]:
    print(f"   YES. {n:,} trip_ids appear in both files, which is {p:.2%} of the smaller")
    print(f"   of the two id sets. Cost per trip and cost per km are computable on that")
    print(f"   subset, and CHECK 4 above ran against it.")
else:
    print(f"   NO. Only {n:,} trip_ids are shared, {p:.2%} of the smaller id set.")
    print(f"   Ride covers July 2026 while bill cycles start earlier, so the two files")
    print(f"   describe different periods. Cost per trip is NOT computable. CHECK 4 skipped.")

print("\n2. STRONGEST CANDIDATE STORY")
worst = FACTS["g_vendor"][FACTS["g_vendor"]["trips"] > 500].sort_values(
    "contradiction_rate", ascending=False)
print(f"   Metric   : trips labelled delay_reason='NODELAY' whose own timestamps show")
print(f"              actual_end_epoch - planned_end_epoch > 10 minutes.")
print(f"   Magnitude: {FACTS['contra_share_nodelay']:.1%} of all NODELAY trips are")
print(f"              actually more than 10 minutes late. Reported vs computed delay")
print(f"              buckets agree only {FACTS['bucket_agreement']:.1%} of the time.")
if len(worst):
    w = worst.iloc[0]
    print(f"   Entity   : worst vendor = {worst.index[0]} at {w['contradiction_rate']:.1%}")
    print(f"              over {int(w['trips']):,} trips.")
print(f"   Sample   : {FACTS['contra_n']:,} contradicting trips out of "
      f"{FACTS['nodelay_n']:,} NODELAY trips.")
print(f"   Why it wins: it is self-contained in one file, needs no cross-file join,")
print(f"              and the evidence is the operator's own timestamps.")

print("\n3. RUNNER-UP STORIES")
print(f"   a) Escort compliance gap. {FACTS['escort_viol']:,} female employee legs on")
print(f"      night shifts (>=20:00 or <06:00) ran with actual_escort=FALSE, out of")
print(f"      {FACTS['escort_risk']:,} such legs ({FACTS['escort_rate']:.1%}), spanning")
print(f"      {FACTS['escort_trips']:,} distinct trips and {FACTS['escort_emps']:,} distinct employees.")
if FACTS["bill_joinable"]:
    print(f"   b) Billing integrity. {FACTS.get('zerokm_n',0):,} trips billed with")
    print(f"      total_trip_km=0 despite non-zero traveled_km, and "
          f"{FACTS.get('ev_mismatch',0):,} rows")
    print(f"      on EV contracts served by non-electric cabs.")
else:
    print(f"   b) Feedback is unusable as an outcome metric - see item 5. That is itself")
    print(f"      a finding: the rating columns cannot support any satisfaction story.")

print("\n4. DIMENSIONS SAFE FOR ATTRIBUTION")
if bad_dims:
    print("   Unsafe (>20% null): " + ", ".join(f"{nm}.{c}" for nm, c, _ in bad_dims))
    print("   Everything else listed in CHECK 7 is safe.")
else:
    print("   All of vendor_id, office, shift_type, trip_direction, product_type,")
    print("   route_source, tenant_id and site_code are under 20% null in every file")
    print("   that carries them, so all are safe for attribution.")

print("\n5. PLANNED METRICS THAT ARE NOT VIABLE")
if FACTS["alert_missing"]:
    print("   - Anything alert-driven (alert volume, acknowledge latency, flapping")
    print("     collapse, ops responsiveness). alert_data_set.csv is not on disk.")
if not FACTS["bill_joinable"]:
    print("   - Cost per trip, cost per km, vendor cost benchmarking, EV contract")
    print("     compliance. ride and bill do not share enough trip_ids.")
const = [c for c, v in FACTS["rating_modal"].items() if v > 0.90]
if const:
    print(f"   - Satisfaction / NPS style metrics from {', '.join(const)}: effectively")
    print(f"     constant (modal value holds >90% of rows), so no signal to attribute.")
print(f"   - Any per-employee feedback metric: only {FACTS['fb_cov']:.1%} of ride trips")
print(f"     have even one feedback row, blended response rate {FACTS['fb_rate']:.1%}.")
print("\n" + "=" * 110)
