-- Pulse warehouse schema (DuckDB).
--
-- Three fact tables, one row grain each:
--   fact_trip           one row per trip                (source: ride_data)
--   fact_trip_employee  one row per employee per trip    (source: emp_data, denormalised escort from ride)
--   fact_trip_billing   one row per billed trip          (source: bill_data, denormalised fields from ride)
--
-- tenant_id is the first column and the leading index key on every table --
-- it is the multi-tenancy boundary enforced by app/db.py at query time.
--
-- A handful of columns on fact_trip_employee and fact_trip_billing are
-- copied over from fact_trip at ingest time (see app/ingest/canonical.py).
-- app/metrics/compiler.py compiles every metric to a single-table
-- "FROM {table}" query with no JOIN, so any metric that needs a field from
-- another grain (e.g. unbilled_km_rate needs traveled_km, which lives on
-- fact_trip, compared against billed_km, which lives on fact_trip_billing)
-- requires that field to already be present on the table being queried.
-- These columns are marked "-- denormalised" below.

CREATE TABLE IF NOT EXISTS fact_trip (
    tenant_id                   VARCHAR NOT NULL,
    site_code                   VARCHAR,
    trip_id                     BIGINT NOT NULL,
    trip_date                   DATE,
    office                      VARCHAR,
    product_type                VARCHAR,
    shift_type                  VARCHAR,
    shift_bucket                VARCHAR,
    shift_suffix                VARCHAR,
    trip_direction              VARCHAR,
    vendor_id                   VARCHAR,
    route_source                VARCHAR,
    planned_start_epoch         BIGINT,
    planned_end_epoch           BIGINT,
    actual_start_epoch          BIGINT,
    actual_end_epoch            BIGINT,
    computed_start_delay_min    DOUBLE,
    computed_arrival_delay_min  DOUBLE,
    reported_delay_minutes      DOUBLE,
    delay_reason                VARCHAR,
    planned_km                  DOUBLE,
    traveled_km                 DOUBLE,
    actual_cab_capacity         DOUBLE,
    actual_cab_fuel_type        VARCHAR,
    planned_employee_cnt        DOUBLE,
    actual_employee_cnt         DOUBLE,
    noshow_cnt                  DOUBLE,
    actual_escort               VARCHAR,
    is_driver_nc                VARCHAR,
    is_cab_nc                   VARCHAR,
    trip_nodal                  VARCHAR,
    dq_flags                    INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (tenant_id, trip_id)
);

CREATE INDEX IF NOT EXISTS idx_fact_trip_tenant
    ON fact_trip (tenant_id, trip_date);

CREATE TABLE IF NOT EXISTS fact_trip_employee (
    tenant_id                   VARCHAR NOT NULL,
    site_code                   VARCHAR,
    trip_id                     BIGINT NOT NULL,
    stwid                       BIGINT,
    trip_date                   DATE,
    office                      VARCHAR,
    product_type                VARCHAR,
    shift_type                  VARCHAR,
    shift_bucket                VARCHAR,
    planned_pickup_epoch        BIGINT,
    planned_drop_epoch          BIGINT,
    actual_pickup_epoch         BIGINT,
    actual_drop_epoch           BIGINT,
    computed_pickup_delay_min   DOUBLE,
    computed_drop_delay_min     DOUBLE,
    planned_km                  DOUBLE,
    traveled_km                 DOUBLE,
    signintype                  VARCHAR,
    gender                      VARCHAR,
    emp_role                    VARCHAR,
    boarding_status              VARCHAR,
    not_boarding_reason         VARCHAR,
    is_no_show                  VARCHAR,
    actual_escort                VARCHAR,   -- denormalised from fact_trip.actual_escort (trip-level, same value for every leg on the trip)
    dq_flags                    INTEGER NOT NULL DEFAULT 0  -- denormalised copy of the owning fact_trip.dq_flags (see app/ingest/quality.py)
);

CREATE INDEX IF NOT EXISTS idx_fact_trip_employee_tenant
    ON fact_trip_employee (tenant_id, trip_date);

CREATE TABLE IF NOT EXISTS fact_trip_billing (
    tenant_id                   VARCHAR NOT NULL,
    site_code                   VARCHAR,
    trip_id                     BIGINT NOT NULL,
    cycle_start                 TIMESTAMP,
    cycle_end                   TIMESTAMP,
    office                      VARCHAR,
    vendor                      VARCHAR,
    contract                    VARCHAR,
    slab_name                   VARCHAR,
    slab_normalised              VARCHAR,
    billed_km                   DOUBLE,
    trip_cost                   DOUBLE,
    traveled_km                 DOUBLE,   -- denormalised from fact_trip.traveled_km (BILLED_KM_ZERO flag, unbilled_km_rate metric)
    actual_cab_fuel_type        VARCHAR,  -- denormalised from fact_trip.actual_cab_fuel_type (FUEL_CONTRACT_MISMATCH flag, ev_contract_mismatch_rate metric)
    actual_employee_cnt         DOUBLE,   -- denormalised from fact_trip.actual_employee_cnt (cost_per_employee_trip metric)
    dq_flags                    INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_fact_trip_billing_tenant
    ON fact_trip_billing (tenant_id, cycle_start);
