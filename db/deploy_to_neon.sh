#!/usr/bin/env bash
# =============================================================
# deploy_to_neon.sh
#
# Builds the schema on Neon and loads the CSVs into staging.
#
# Usage:
#   export NEON="postgresql://user:pass@ep-xxx.neon.tech/neondb?sslmode=require"
#   ./deploy_to_neon.sh /path/to/folder-with-csvs
#
# Re-runnable: the DDL files never drop a table (staging.alerts_data
# carries a live trigger that a DROP would take down with it -- see
# 09_alert_stream_trigger.sql). Step 3 below TRUNCATEs each staging
# table before its \copy instead, so a re-run is still a clean
# reload rather than duplicated rows.
# =============================================================

set -euo pipefail

CSV_DIR="${1:-.}"

if [[ -z "${NEON:-}" ]]; then
  echo "ERROR: set NEON to your Neon connection string first."
  echo '  export NEON="postgresql://...?sslmode=require"'
  exit 1
fi

# Never let a big \copy get killed halfway by a timeout.
PSQL=(psql "$NEON" -v ON_ERROR_STOP=1 -q
      -c "SET statement_timeout = 0;"
      -c "SET idle_in_transaction_session_timeout = 0;")

run_sql () {
  echo ">> running $1"
  psql "$NEON" -v ON_ERROR_STOP=1 -q -f "$1"
}

# -------------------------------------------------------------
echo "== step 1: connection check =="
psql "$NEON" -tAc "SELECT 'connected to ' || current_database();"

echo "== step 2: build schemas and tables =="
run_sql 01_staging.sql
run_sql 02_core_model.sql
run_sql 03_analytics_layer.sql
run_sql 09_alert_stream_trigger.sql

# -------------------------------------------------------------
echo "== step 3: load CSVs into staging =="

# Loads one CSV into one staging table. Does NOT truncate -- call
# truncate_once first for tables that get exactly one load per run.
#   $1 = table name   $2 = csv filename   $3 = column list
load_csv () {
  local table="$1" file="$CSV_DIR/$2" cols="$3"
  if [[ ! -f "$file" ]]; then
    echo "   SKIP $2 (not found)"
    return
  fi
  echo "   loading $2 -> $table"
  psql "$NEON" -v ON_ERROR_STOP=1 -q \
    -c "SET statement_timeout = 0;" \
    -c "\\copy $table($cols) FROM '$file' WITH (FORMAT csv, HEADER true)"
}

truncate_once () {
  echo "   truncating $1"
  psql "$NEON" -v ON_ERROR_STOP=1 -q -c "TRUNCATE TABLE $1;"
}

TRIP_COLS="business_unit,office,product_type,trip_date,shift_type,trip_id,trip_direction,actual_escort,vendor_id,planned_cab_registration,actual_cab_registration,actual_cab_capacity,planned_km,traveled_km,planned_start_epoch,planned_end_epoch,actual_start_epoch,actual_end_epoch,delay_reason,delay_minutes,route_source,actual_cab_fuel_type,is_driver_nc,is_cab_nc,trip_nodal,plannedemployee_cnt,actualemployee_cnt,noshow_cnt"

# The three monthly trip files land in ONE table -- truncate once,
# before the loop, not per file. After each load, stamp source_file
# so a single month can be reloaded later.
truncate_once staging.ride_data_trip
for m in may June July; do
  f="Ride_data _trip-${m}_2026.csv"
  if [[ -f "$CSV_DIR/$f" ]]; then
    load_csv staging.ride_data_trip "$f" "$TRIP_COLS"
    psql "$NEON" -q -c \
      "UPDATE staging.ride_data_trip SET source_file='${m}_2026' WHERE source_file IS NULL;"
  else
    echo "   SKIP $f (not found)"
  fi
done

truncate_once staging.emp_data
load_csv staging.emp_data "emp_data.csv" \
  "business_unit,office,product_type,trip_date,shift_type,trip_id,planned_pickup_epoch,planned_drop_epoch,actual_pickup_epoch,actual_drop_epoch,planned_km,traveled_km,stwid,signintype,gender,emp_role,boarding_status,not_boarding_reason,is_no_show"

truncate_once staging.trip_feedback
load_csv staging.trip_feedback "trip_feedback.csv" \
  "business_unit,trip_id,trip_type,trip_date,stwid,route_rating,driver_rating,cab_rating,safety_rating,marshal_rating,creation_time"

# alerts_data is NOT truncated: it now takes live single-row inserts
# from the streaming trigger path (09_alert_stream_trigger.sql)
# between reloads, and truncating would discard those. Re-running
# this CSV load duplicates the file's raw rows in staging, but
# core.fact_alert's ON CONFLICT (event_id) DO NOTHING keeps the
# transformed data idempotent, so it's a no-op downstream.
load_csv staging.alerts_data "alerts_data.csv" \
  "business_unit,trip_id,stwid,event_id,event_type,start_time,acknowledge_time,state_text,severity,source"

truncate_once staging.bill_data
load_csv staging.bill_data "bill_data.csv" \
  "business_unit,office,vendor,cycle_start,cycle_end,trip_id,contract,slab_name,total_trip_km,trip_cost"

# -------------------------------------------------------------
echo "== step 4: staging row counts =="
psql "$NEON" -c "
SELECT 'ride_data_trip' AS table, COUNT(*) FROM staging.ride_data_trip
UNION ALL SELECT 'emp_data',      COUNT(*) FROM staging.emp_data
UNION ALL SELECT 'trip_feedback', COUNT(*) FROM staging.trip_feedback
UNION ALL SELECT 'alerts_data',   COUNT(*) FROM staging.alerts_data
UNION ALL SELECT 'bill_data',     COUNT(*) FROM staging.bill_data;"

# -------------------------------------------------------------
echo "== step 5: transform staging -> core =="
run_sql 04_transform_alerts.sql
# Add the remaining transforms here as you write them:
# run_sql 05_transform_trips.sql
# run_sql 06_transform_legs.sql
# run_sql 07_transform_feedback.sql
# run_sql 08_transform_billing.sql

echo "== step 6: refresh rollups =="
psql "$NEON" -q \
  -c "REFRESH MATERIALIZED VIEW analytics.mv_daily_alert_metrics;"
# -c "REFRESH MATERIALIZED VIEW analytics.mv_daily_trip_metrics;"   # once trips are loaded

echo
echo "Done. Check the analytics layer:"
echo "  psql \"\$NEON\" -c 'SELECT resolution_path, COUNT(*) FROM analytics.v_alert GROUP BY 1;'"
