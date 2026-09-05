-- =============================================================
-- 01_staging.sql
-- Layer 1: raw landing zone.
--
-- Rule: EVERY column is text, and there are NO constraints.
-- Nothing here is allowed to reject a row. Cleaning happens on
-- the way OUT of staging, not on the way in. This is what lets
-- you load messy CSVs once and then profile them with SQL.
--
-- Rule: NO TABLE IN THIS FILE IS EVER DROPPED. staging.alerts_data
-- carries a live trigger (05_alert_stream_trigger.sql) that must
-- survive every re-run of this file; DROP TABLE would take the
-- trigger down with it. All CREATE statements below are
-- IF NOT EXISTS, so re-running this file is a safe no-op once the
-- tables exist. To reload a specific batch of the bulk-CSV tables
-- (ride_data_trip, emp_data, trip_feedback, bill_data), the loader
-- script should target the batch directly, e.g.
--   DELETE FROM staging.ride_data_trip WHERE source_file = 'may_2026';
-- rather than truncating or dropping the whole table.
-- =============================================================

CREATE SCHEMA IF NOT EXISTS staging;

-- -------------------------------------------------------------
-- ride_data_trip: load all three monthly CSVs into this ONE
-- table. source_file records which month a row came from, so a
-- month can be reloaded independently.
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS staging.ride_data_trip (
    business_unit             text,
    office                    text,
    product_type              text,
    trip_date                 text,
    shift_type                text,
    trip_id                   text,
    trip_direction            text,
    actual_escort             text,
    vendor_id                 text,
    planned_cab_registration  text,
    actual_cab_registration   text,
    actual_cab_capacity       text,
    planned_km                text,
    traveled_km               text,
    planned_start_epoch       text,
    planned_end_epoch         text,
    actual_start_epoch        text,
    actual_end_epoch          text,
    delay_reason              text,
    delay_minutes             text,
    route_source              text,
    actual_cab_fuel_type      text,
    is_driver_nc              text,
    is_cab_nc                 text,
    trip_nodal                text,
    plannedemployee_cnt       text,
    actualemployee_cnt        text,
    noshow_cnt                text,
    source_file               text,
    loaded_at                 timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS staging.emp_data (
    business_unit         text,
    office                text,
    product_type          text,
    trip_date             text,
    shift_type            text,
    trip_id               text,
    planned_pickup_epoch  text,
    planned_drop_epoch    text,
    actual_pickup_epoch   text,
    actual_drop_epoch     text,
    planned_km            text,
    traveled_km           text,
    stwid                 text,
    signintype            text,
    gender                text,
    emp_role              text,
    boarding_status       text,
    not_boarding_reason   text,
    is_no_show            text,
    loaded_at             timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS staging.trip_feedback (
    business_unit   text,
    trip_id         text,
    trip_type       text,
    trip_date       text,
    stwid           text,
    route_rating    text,
    driver_rating   text,
    cab_rating      text,
    safety_rating   text,
    marshal_rating  text,
    creation_time   text,
    loaded_at       timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS staging.alerts_data (
    business_unit     text,
    trip_id           text,
    stwid             text,
    event_id          text,
    event_type        text,
    start_time        text,
    acknowledge_time  text,
    state_text        text,
    severity          text,
    source            text,
    loaded_at         timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS staging.bill_data (
    business_unit   text,
    office          text,
    vendor          text,
    cycle_start     text,
    cycle_end       text,
    trip_id         text,
    contract        text,
    slab_name       text,
    total_trip_km   text,
    trip_cost       text,
    loaded_at       timestamptz DEFAULT now()
);

-- =============================================================
-- Loading from psql (fastest path into Neon for files this size)
--
--   \copy staging.alerts_data(business_unit,trip_id,stwid,event_id,
--         event_type,start_time,acknowledge_time,state_text,severity,source)
--     FROM 'alerts_data.csv' WITH (FORMAT csv, HEADER true);
--
-- IMPORTANT: do NOT add NULL 'NA' to the \copy options.
-- In alerts_data, the literal string 'NA' is a real category that
-- identifies auto-closed alerts. Converting it to NULL destroys
-- that signal. Load it as text and interpret it in the transform.
--
-- For the three monthly trip files, set source_file afterwards:
--   UPDATE staging.ride_data_trip SET source_file = 'may_2026'
--    WHERE source_file IS NULL;
-- =============================================================
