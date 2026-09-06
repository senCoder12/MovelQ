#!/usr/bin/env python3
"""Import CSV files into Neon PostgreSQL (staging + core + analytics).

Handles Neon 512MB project disk limit by:
- Filtering for target month (default: July 2026 for hackathon MVP)
- Fast streaming COPY via psycopg
- Staging-to-core transformations
- Truncating staging to reclaim disk space after populating core star schema

Usage:
    python backend/import_csv_to_neon.py
    python backend/import_csv_to_neon.py --month July
    python backend/import_csv_to_neon.py --month all --keep-staging
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
import psycopg
from dotenv import load_dotenv

# Load environment variables
load_dotenv("backend/.env")
raw_url = os.environ.get("NEON_DATABASE_URL", "")
if not raw_url:
    print("ERROR: NEON_DATABASE_URL not set in backend/.env")
    sys.exit(1)

clean_url = raw_url.split("?")[0]
if "sslmode=" not in clean_url:
    clean_url += "?sslmode=require"


def find_file(directory: Path, *candidates: str) -> Path | None:
    for c in candidates:
        p = directory / c
        if p.exists():
            return p
    cand_lower = [c.lower() for c in candidates]
    for p in directory.glob("*.csv"):
        if p.name.lower() in cand_lower:
            return p
    return None


def copy_csv(cur, table: str, csv_path: Path, columns: str, filter_pattern: str | None = None):
    """Fast stream COPY from CSV file into PostgreSQL table with optional row filter."""
    print(f"  -> Streaming {csv_path.name} into {table}...")
    copy_sql = f"COPY {table}({columns}) FROM STDIN WITH (FORMAT csv, HEADER true)"
    
    start = time.time()
    rows_streamed = 0
    with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
        with cur.copy(copy_sql) as copy:
            header = f.readline()
            copy.write(header)
            for line in f:
                if filter_pattern and filter_pattern not in line:
                    continue
                copy.write(line)
                rows_streamed += 1
    elapsed = time.time() - start
    print(f"     Loaded {rows_streamed:,} rows in {elapsed:.1f}s")


def main():
    parser = argparse.ArgumentParser(description="Import CSV dataset into Neon PostgreSQL")
    parser.add_argument("--data-dir", default="data/raw", help="Directory containing CSV files")
    parser.add_argument("--month", default="July", choices=["all", "may", "June", "July"],
                        help="Trip month to import (default: July)")
    parser.add_argument("--staging-only", action="store_true", help="Only load into staging tables")
    parser.add_argument("--skip-staging", action="store_true", help="Skip staging load and transform existing staging data")
    parser.add_argument("--keep-staging", action="store_true", help="Do not truncate staging after transform")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        alt_dirs = [
            Path("pulse/data/raw"),
            Path.home() / "Downloads/Rakshit_Docs/drive-download-20260905T091011Z-1-001",
        ]
        for alt in alt_dirs:
            if alt.exists() and any(alt.glob("*.csv")):
                data_dir = alt
                break

    month_filter_code = {"July": "2026-07", "June": "2026-06", "may": "2026-05"}.get(args.month)
    month_name = args.month if args.month != "all" else None

    print("=" * 70)
    print(" MoveIQ — CSV to Neon DB Ingestion Pipeline")
    print("=" * 70)
    print(f"Data directory: {data_dir.resolve()}")
    print(f"Neon host:      {clean_url.split('@')[-1].split('/')[0]}")
    print(f"Target month:   {args.month}")
    print("-" * 70)

    # 1. Connect
    print("\n[Step 1/4] Connecting to Neon database...")
    conn = psycopg.connect(clean_url, autocommit=True)
    cur = conn.cursor()
    cur.execute("SELECT current_database(), current_user;")
    db, user = cur.fetchone()
    print(f"Connected to database '{db}' as '{user}'")

    if not args.skip_staging:
        # 2. Reset staging
        print("\n[Step 2/4] Resetting staging tables...")
        cur.execute("""
            TRUNCATE TABLE staging.ride_data_trip;
            TRUNCATE TABLE staging.emp_data;
            TRUNCATE TABLE staging.trip_feedback;
            TRUNCATE TABLE staging.alerts_data;
            TRUNCATE TABLE staging.bill_data;
        """)

        # 3. Stream CSVs into staging
        print("\n[Step 3/4] Streaming CSV files into staging...")

        # Alerts (always load full alert dataset ~51k rows, 7.6MB)
        f_alerts = find_file(data_dir, "alerts_data.csv")
        if f_alerts:
            copy_csv(cur, "staging.alerts_data", f_alerts,
                     "business_unit,trip_id,stwid,event_id,event_type,start_time,acknowledge_time,state_text,severity,source")

        # Billing (filter by month name if applicable)
        f_bill = find_file(data_dir, "bill_data.csv")
        if f_bill:
            copy_csv(cur, "staging.bill_data", f_bill,
                     "business_unit,office,vendor,cycle_start,cycle_end,trip_id,contract,slab_name,total_trip_km,trip_cost",
                     filter_pattern=month_name)

        # Employee Legs (filter by ISO month date e.g. '2026-07')
        f_emp = find_file(data_dir, "emp_Data.csv", "emp_data.csv")
        if f_emp:
            copy_csv(cur, "staging.emp_data", f_emp,
                     "business_unit,office,product_type,trip_date,shift_type,trip_id,planned_pickup_epoch,planned_drop_epoch,actual_pickup_epoch,actual_drop_epoch,planned_km,traveled_km,stwid,signintype,gender,emp_role,boarding_status,not_boarding_reason,is_no_show",
                     filter_pattern=month_filter_code)

        # Trips
        months = ["may", "June", "July"] if args.month == "all" else [args.month]
        trip_cols = ("business_unit,office,product_type,trip_date,shift_type,trip_id,trip_direction,"
                     "actual_escort,vendor_id,planned_cab_registration,actual_cab_registration,"
                     "actual_cab_capacity,planned_km,traveled_km,planned_start_epoch,planned_end_epoch,"
                     "actual_start_epoch,actual_end_epoch,delay_reason,delay_minutes,route_source,"
                     "actual_cab_fuel_type,is_driver_nc,is_cab_nc,trip_nodal,plannedemployee_cnt,"
                     "actualemployee_cnt,noshow_cnt")
        for m in months:
            f_ride = find_file(data_dir, f"Ride_data _trip-{m}_2026.csv", f"Ride_data_trip_{m}_2026.csv")
            if f_ride:
                copy_csv(cur, "staging.ride_data_trip", f_ride, trip_cols)
                cur.execute(f"UPDATE staging.ride_data_trip SET source_file='{m}_2026' WHERE source_file IS NULL;")
    else:
        print("\n--skip-staging flag set. Using existing staging data.")

    print("\nStaging summary:")
    for t in ["ride_data_trip", "emp_data", "alerts_data", "bill_data"]:
        cur.execute(f"SELECT COUNT(*) FROM staging.{t};")
        cnt = cur.fetchone()[0]
        print(f"  * staging.{t:18s}: {cnt:>10,}")

    if args.staging_only:
        print("\n--staging-only flag set. Skipping core transform.")
        cur.close()
        conn.close()
        return

    # 4. Transform Staging -> Core
    print("\n[Step 4/4] Transforming staging into core star schema...")
    print("  -> Resetting core schema tables with RESTART IDENTITY CASCADE...")
    cur.execute("""
        TRUNCATE TABLE 
            core.fact_trip_feedback,
            core.fact_alert,
            core.fact_trip_leg,
            core.fact_trip_billing,
            core.fact_trip,
            core.dim_contract,
            core.dim_vehicle,
            core.dim_vendor,
            core.dim_office,
            core.dim_business_unit,
            core.dim_shift,
            core.dim_employee
        RESTART IDENTITY CASCADE;
    """)

    print("  -> Populating dim_business_unit...")
    cur.execute("""
        INSERT INTO core.dim_business_unit (business_unit_name)
        SELECT DISTINCT business_unit FROM (
            SELECT business_unit FROM staging.ride_data_trip
            UNION SELECT business_unit FROM staging.alerts_data
            UNION SELECT business_unit FROM staging.emp_data
            UNION SELECT business_unit FROM staging.bill_data
        ) t
        WHERE business_unit IS NOT NULL AND business_unit <> ''
        ON CONFLICT (business_unit_name) DO NOTHING;
    """)

    print("  -> Populating dim_office...")
    cur.execute("""
        INSERT INTO core.dim_office (office_name, business_unit_key)
        SELECT DISTINCT s.office, bu.business_unit_key
        FROM (
            SELECT office, business_unit FROM staging.ride_data_trip WHERE office IS NOT NULL
            UNION SELECT office, business_unit FROM staging.emp_data WHERE office IS NOT NULL
            UNION SELECT office, business_unit FROM staging.bill_data WHERE office IS NOT NULL
        ) s
        LEFT JOIN core.dim_business_unit bu ON bu.business_unit_name = s.business_unit
        WHERE s.office IS NOT NULL AND s.office <> ''
        ON CONFLICT (office_name) DO NOTHING;
    """)

    print("  -> Populating dim_vendor...")
    cur.execute("""
        INSERT INTO core.dim_vendor (vendor_name)
        SELECT DISTINCT s.vendor FROM (
            SELECT vendor_id as vendor FROM staging.ride_data_trip WHERE vendor_id IS NOT NULL
            UNION SELECT vendor FROM staging.bill_data WHERE vendor IS NOT NULL
        ) s
        WHERE s.vendor IS NOT NULL AND s.vendor <> ''
        ON CONFLICT (vendor_name) DO NOTHING;
    """)

    print("  -> Populating dim_shift...")
    cur.execute("""
        INSERT INTO core.dim_shift (shift_code, shift_hour, shift_band)
        SELECT DISTINCT
            s.shift_code,
            s.shift_hour,
            CASE
                WHEN s.shift_hour >= 20 OR s.shift_hour < 4 THEN 'night'
                WHEN s.shift_hour BETWEEN 4 AND 6 THEN 'early_morning'
                WHEN s.shift_hour BETWEEN 7 AND 11 THEN 'morning'
                WHEN s.shift_hour BETWEEN 12 AND 16 THEN 'afternoon'
                ELSE 'evening'
            END as shift_band
        FROM (
            SELECT DISTINCT
                TRIM(shift_type) as shift_code,
                COALESCE(NULLIF(SPLIT_PART(TRIM(shift_type), ':', 1), ''), '0')::smallint as shift_hour
            FROM (
                SELECT shift_type FROM staging.ride_data_trip WHERE shift_type ~ '^[0-9]{1,2}:[0-9]{2}$'
                UNION SELECT shift_type FROM staging.emp_data WHERE shift_type ~ '^[0-9]{1,2}:[0-9]{2}$'
            ) raw_shifts
        ) s
        ON CONFLICT (shift_code) DO NOTHING;
    """)

    print("  -> Populating dim_vehicle...")
    cur.execute("""
        INSERT INTO core.dim_vehicle (registration, capacity, fuel_type)
        SELECT DISTINCT ON (actual_cab_registration)
            actual_cab_registration as registration,
            NULLIF(REPLACE(actual_cab_capacity, ',', ''), '')::smallint as capacity,
            CASE
                WHEN actual_cab_fuel_type IN ('Diesel', 'Electric', 'Petrol') THEN actual_cab_fuel_type
                ELSE 'Diesel'
            END as fuel_type
        FROM staging.ride_data_trip
        WHERE actual_cab_registration IS NOT NULL AND actual_cab_registration <> '' AND actual_cab_registration <> 'NA'
        ORDER BY actual_cab_registration, loaded_at DESC
        ON CONFLICT (registration) DO NOTHING;
    """)

    print("  -> Populating dim_contract...")
    cur.execute("""
        INSERT INTO core.dim_contract (contract_code, slab_name)
        SELECT DISTINCT contract, slab_name
        FROM staging.bill_data
        WHERE contract IS NOT NULL
        ON CONFLICT (contract_code, slab_name) DO NOTHING;
    """)

    print("  -> Populating dim_employee...")
    cur.execute("""
        INSERT INTO core.dim_employee (stwid, gender, emp_role)
        SELECT DISTINCT ON (stwid_clean)
            stwid_clean as stwid,
            gender,
            emp_role
        FROM (
            SELECT
                REPLACE(stwid, ',', '')::bigint as stwid_clean,
                gender,
                emp_role
            FROM staging.emp_data
            WHERE stwid IS NOT NULL AND REPLACE(stwid, ',', '') ~ '^[0-9]+$' AND REPLACE(stwid, ',', '')::bigint > 0
            UNION ALL
            SELECT
                REPLACE(stwid, ',', '')::bigint as stwid_clean,
                NULL as gender,
                NULL as emp_role
            FROM staging.alerts_data
            WHERE stwid IS NOT NULL AND REPLACE(stwid, ',', '') ~ '^[0-9]+$' AND REPLACE(stwid, ',', '')::bigint > 0
        ) e
        ORDER BY stwid_clean, gender NULLS LAST
        ON CONFLICT (stwid) DO NOTHING;
    """)

    print("  -> Inserting core.fact_trip...")
    cur.execute("""
        INSERT INTO core.fact_trip (
            trip_id, trip_date, business_unit_key, office_key, vendor_key, shift_key,
            planned_vehicle_key, actual_vehicle_key, product_type, trip_direction,
            trip_nodal, route_source, delay_reason, actual_escort, is_driver_nc,
            is_cab_nc, planned_km, traveled_km, planned_start_ts, planned_end_ts,
            actual_start_ts, actual_end_ts, delay_minutes, planned_employee_cnt,
            actual_employee_cnt, noshow_cnt, source_file
        )
        SELECT
            REPLACE(s.trip_id, ',', '')::bigint,
            TO_DATE(s.trip_date, 'FMMonth DD, YYYY'),
            bu.business_unit_key,
            o.office_key,
            v.vendor_key,
            sh.shift_key,
            pv.vehicle_key,
            av.vehicle_key,
            CASE WHEN s.product_type IN ('CAB','BUS','SPOT_2.0') THEN s.product_type ELSE 'CAB' END,
            CASE WHEN s.trip_direction IN ('LOGIN','LOGOUT') THEN s.trip_direction ELSE 'LOGIN' END,
            CASE WHEN s.trip_nodal IN ('NODAL','HOME','SHUTTLE') THEN s.trip_nodal ELSE 'HOME' END,
            CASE WHEN s.route_source IN ('AUTO','MANUAL','RENTLZ','SHUTTLE_SERVICE') THEN s.route_source ELSE 'AUTO' END,
            CASE WHEN s.delay_reason IN ('NODELAY','TRAFFIC','DRIVER','EMPLOYEE') THEN s.delay_reason ELSE 'NODELAY' END,
            LOWER(s.actual_escort) = 'true',
            LOWER(s.is_driver_nc) = 'true',
            LOWER(s.is_cab_nc) = 'true',
            GREATEST(0, COALESCE(NULLIF(REPLACE(s.planned_km, ',', ''), '')::numeric, 0)),
            GREATEST(0, COALESCE(NULLIF(REPLACE(s.traveled_km, ',', ''), '')::numeric, 0)),
            TO_TIMESTAMP(NULLIF(REPLACE(s.planned_start_epoch, ',', ''), '')::double precision),
            TO_TIMESTAMP(NULLIF(REPLACE(s.planned_end_epoch, ',', ''), '')::double precision),
            TO_TIMESTAMP(NULLIF(REPLACE(s.actual_start_epoch, ',', ''), '')::double precision),
            TO_TIMESTAMP(NULLIF(REPLACE(s.actual_end_epoch, ',', ''), '')::double precision),
            GREATEST(0, COALESCE(NULLIF(REPLACE(s.delay_minutes, ',', ''), '')::integer, 0)),
            COALESCE(NULLIF(REPLACE(s.plannedemployee_cnt, ',', ''), '')::smallint, 0),
            COALESCE(NULLIF(REPLACE(s.actualemployee_cnt, ',', ''), '')::smallint, 0),
            COALESCE(NULLIF(REPLACE(s.noshow_cnt, ',', ''), '')::smallint, 0),
            s.source_file
        FROM staging.ride_data_trip s
        LEFT JOIN core.dim_business_unit bu ON bu.business_unit_name = s.business_unit
        LEFT JOIN core.dim_office o ON o.office_name = s.office
        LEFT JOIN core.dim_vendor v ON v.vendor_name = s.vendor_id
        LEFT JOIN core.dim_shift sh ON sh.shift_code = TRIM(s.shift_type)
        LEFT JOIN core.dim_vehicle pv ON pv.registration = s.planned_cab_registration
        LEFT JOIN core.dim_vehicle av ON av.registration = s.actual_cab_registration
        WHERE s.trip_id IS NOT NULL AND REPLACE(s.trip_id, ',', '') ~ '^[0-9]+$'
        ON CONFLICT (trip_id) DO NOTHING;
    """)

    print("  -> Inserting core.fact_alert...")
    cur.execute("""
        INSERT INTO core.fact_alert (
            event_id, trip_id, stwid, business_unit_key, alert_date,
            event_type, alert_scope, severity_raw, resolution_path,
            start_ts, acknowledge_ts, state_text, source
        )
        SELECT
            s.event_id::uuid,
            REPLACE(s.trip_id, ',', '')::bigint,
            de.stwid,
            bu.business_unit_key,
            st.start_ts::date,
            s.event_type,
            CASE WHEN s.event_type IN ('DEVICE_NOT_REACHABLE','VEHICLE_STOPPAGE','OVER_SPEEDING','PANIC_DEVICE','PANIC_FIXED_DEVICE')
                 THEN 'VEHICLE' ELSE 'EMPLOYEE' END,
            s.severity,
            CASE
                WHEN st.ack_ts IS NULL THEN 'unresolved'
                WHEN s.severity LIKE 'Sev-%' THEN 'triaged'
                WHEN EXTRACT(EPOCH FROM (st.ack_ts - st.start_ts))/60 > 720 THEN 'auto_overnight'
                ELSE 'auto_fast'
            END,
            st.start_ts,
            st.ack_ts,
            NULLIF(s.state_text, 'NA'),
            NULLIF(s.source, 'NA')
        FROM staging.alerts_data s
        CROSS JOIN LATERAL (
            SELECT TO_TIMESTAMP(s.start_time,       'FMMonth DD, YYYY, HH12:MI AM') AS start_ts,
                   TO_TIMESTAMP(s.acknowledge_time, 'FMMonth DD, YYYY, HH12:MI AM') AS ack_ts
        ) st
        LEFT JOIN core.dim_business_unit bu ON bu.business_unit_name = s.business_unit
        LEFT JOIN core.dim_employee de ON de.stwid = NULLIF(REPLACE(s.stwid, ',', '')::bigint, 0)
        ON CONFLICT (event_id) DO NOTHING;
    """)

    print("  -> Inserting core.fact_trip_leg...")
    cur.execute("""
        INSERT INTO core.fact_trip_leg (
            trip_id, trip_is_orphan, stwid, trip_date, business_unit_key, office_key,
            shift_key, product_type, signintype, boarding_status, not_boarding_reason,
            is_no_show, planned_pickup_ts, planned_drop_ts, actual_pickup_ts, actual_drop_ts,
            planned_km, traveled_km
        )
        SELECT
            REPLACE(s.trip_id, ',', '')::bigint,
            false,
            de.stwid,
            s.trip_date::date,
            bu.business_unit_key,
            o.office_key,
            sh.shift_key,
            CASE WHEN s.product_type IN ('CAB','BUS','SPOT_2.0') THEN s.product_type ELSE 'CAB' END,
            CASE WHEN s.signintype IN ('Planned','Adhoc','Guest') THEN s.signintype ELSE 'Planned' END,
            CASE WHEN LOWER(s.boarding_status) = 'boarded' THEN 'Boarded' ELSE 'Not Boarded' END,
            s.not_boarding_reason,
            LOWER(s.is_no_show) = 'true',
            TO_TIMESTAMP(NULLIF(REPLACE(s.planned_pickup_epoch, ',', ''), '')::double precision),
            TO_TIMESTAMP(NULLIF(REPLACE(s.planned_drop_epoch, ',', ''), '')::double precision),
            TO_TIMESTAMP(NULLIF(REPLACE(s.actual_pickup_epoch, ',', ''), '')::double precision),
            TO_TIMESTAMP(NULLIF(REPLACE(s.actual_drop_epoch, ',', ''), '')::double precision),
            GREATEST(0, COALESCE(NULLIF(REPLACE(s.planned_km, ',', ''), '')::numeric, 0)),
            GREATEST(0, COALESCE(NULLIF(REPLACE(s.traveled_km, ',', ''), '')::numeric, 0))
        FROM staging.emp_data s
        LEFT JOIN core.dim_business_unit bu ON bu.business_unit_name = s.business_unit
        LEFT JOIN core.dim_office o ON o.office_name = s.office
        LEFT JOIN core.dim_shift sh ON sh.shift_code = TRIM(s.shift_type)
        LEFT JOIN core.dim_employee de ON de.stwid = NULLIF(REPLACE(s.stwid, ',', '')::bigint, 0)
        WHERE s.trip_id IS NOT NULL AND REPLACE(s.trip_id, ',', '') ~ '^[0-9]+$';
    """)

    print("  -> Inserting core.fact_trip_billing...")
    cur.execute("""
        INSERT INTO core.fact_trip_billing (
            trip_id, trip_is_orphan, business_unit_key, office_key, vendor_key, contract_key,
            cycle_start, cycle_end, billed_km, trip_cost
        )
        SELECT
            REPLACE(s.trip_id, ',', '')::bigint,
            false,
            bu.business_unit_key,
            o.office_key,
            v.vendor_key,
            c.contract_key,
            TO_TIMESTAMP(s.cycle_start, 'FMMonth DD, YYYY, HH12:MI AM')::date,
            TO_TIMESTAMP(s.cycle_end, 'FMMonth DD, YYYY, HH12:MI AM')::date,
            GREATEST(0, COALESCE(NULLIF(REPLACE(s.total_trip_km, ',', ''), '')::numeric, 0)),
            GREATEST(0, COALESCE(NULLIF(REPLACE(s.trip_cost, ',', ''), '')::numeric, 0))
        FROM staging.bill_data s
        LEFT JOIN core.dim_business_unit bu ON bu.business_unit_name = s.business_unit
        LEFT JOIN core.dim_office o ON o.office_name = s.office
        LEFT JOIN core.dim_vendor v ON v.vendor_name = s.vendor
        LEFT JOIN core.dim_contract c ON c.contract_code = s.contract AND c.slab_name = s.slab_name
        WHERE s.trip_id IS NOT NULL AND REPLACE(s.trip_id, ',', '') ~ '^[0-9]+$';
    """)

    print("  -> Updating trip_is_orphan flags...")
    cur.execute("""
        UPDATE core.fact_alert a
        SET trip_is_orphan = NOT EXISTS (SELECT 1 FROM core.fact_trip t WHERE t.trip_id = a.trip_id);

        UPDATE core.fact_trip_leg l
        SET trip_is_orphan = NOT EXISTS (SELECT 1 FROM core.fact_trip t WHERE t.trip_id = l.trip_id);

        UPDATE core.fact_trip_billing b
        SET trip_is_orphan = NOT EXISTS (SELECT 1 FROM core.fact_trip t WHERE t.trip_id = b.trip_id);
    """)

    # Reclaim disk space by truncating staging tables
    if not args.keep_staging:
        print("  -> Reclaiming disk space (truncating staging)...")
        cur.execute("""
            TRUNCATE TABLE staging.ride_data_trip;
            TRUNCATE TABLE staging.emp_data;
            TRUNCATE TABLE staging.trip_feedback;
            TRUNCATE TABLE staging.alerts_data;
            TRUNCATE TABLE staging.bill_data;
        """)

    print("  -> Refreshing materialized views...")
    try:
        cur.execute("REFRESH MATERIALIZED VIEW analytics.mv_daily_alert_metrics;")
    except Exception as e:
        print("     Note on alert view:", e)
    try:
        cur.execute("REFRESH MATERIALIZED VIEW analytics.mv_daily_trip_metrics;")
    except Exception as e:
        print("     Note on trip view:", e)

    # 5. Verification summary
    print("\n" + "=" * 70)
    print(" INGESTION & TRANSFORMATION SUMMARY")
    print("=" * 70)
    for v in ["v_trip", "v_leg", "v_alert", "v_billing"]:
        cur.execute(f"SELECT COUNT(*) FROM analytics.{v};")
        cnt = cur.fetchone()[0]
        print(f"  * analytics.{v:12s}: {cnt:>10,} rows")

    cur.execute("SELECT pg_size_pretty(pg_database_size(current_database()));")
    dbsize = cur.fetchone()[0]
    print(f"\nFinal Neon DB Storage Used: {dbsize} (Quota: 512 MB)")

    cur.close()
    conn.close()
    print("\nCSV data successfully imported to Neon PostgreSQL!")


if __name__ == "__main__":
    main()
