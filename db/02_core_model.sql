-- =============================================================
-- 02_core_model.sql
-- Layer 2: the core star schema.
--
-- 8 dimensions (Type 1 = overwrite, no history tracking)
-- 5 fact tables, one per grain. Grains are NEVER mixed.
--
-- Design notes for the team:
--  * Dimension keys are nullable everywhere. Real data has gaps;
--    a NOT NULL here would reject rows at load time. Views use
--    LEFT JOIN accordingly.
--  * trip_id foreign keys are deliberately NOT enforced on the
--    child facts. Verified on alerts_data: only 27.9% of alerts
--    point at a trip that exists in ride_data_trip. A real FK
--    would reject the other 72%.
--  * dq_flags is a text array of quality problems found at load.
--    Bad rows stay visible instead of being silently dropped.
-- =============================================================

CREATE SCHEMA IF NOT EXISTS core;

-- =============================================================
-- DIMENSIONS
-- =============================================================

-- Calendar. Pre-populated well past the data so nothing breaks
-- when new months arrive.
DROP TABLE IF EXISTS core.dim_date CASCADE;
CREATE TABLE core.dim_date (
    date_key      date PRIMARY KEY,
    year          smallint NOT NULL,
    quarter       smallint NOT NULL,
    month_num     smallint NOT NULL,
    month_name    text     NOT NULL,
    year_month    text     NOT NULL,     -- '2026-05', the usual group-by
    day_of_month  smallint NOT NULL,
    day_of_week   smallint NOT NULL,     -- 1 = Monday
    day_name      text     NOT NULL,
    iso_week      smallint NOT NULL,
    is_weekend    boolean  NOT NULL
);

INSERT INTO core.dim_date
SELECT  d::date,
        EXTRACT(YEAR    FROM d)::smallint,
        EXTRACT(QUARTER FROM d)::smallint,
        EXTRACT(MONTH   FROM d)::smallint,
        TRIM(TO_CHAR(d, 'Month')),
        TO_CHAR(d, 'YYYY-MM'),
        EXTRACT(DAY  FROM d)::smallint,
        EXTRACT(ISODOW FROM d)::smallint,
        TRIM(TO_CHAR(d, 'Day')),
        EXTRACT(WEEK FROM d)::smallint,
        EXTRACT(ISODOW FROM d) >= 6
FROM generate_series('2025-01-01'::date, '2030-12-31'::date, interval '1 day') AS d;

-- Shift. shift_code is the raw 'HH:MM' string, zero-padded on
-- load so '0:15' and '00:15' collapse to one row.
DROP TABLE IF EXISTS core.dim_shift CASCADE;
CREATE TABLE core.dim_shift (
    shift_key   smallint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    shift_code  text NOT NULL UNIQUE,
    shift_hour  smallint NOT NULL,
    shift_band  text NOT NULL
        CHECK (shift_band IN ('night','early_morning','morning','afternoon','evening'))
);

DROP TABLE IF EXISTS core.dim_business_unit CASCADE;
CREATE TABLE core.dim_business_unit (
    business_unit_key   smallint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    business_unit_name  text NOT NULL UNIQUE
);

-- ASSUMPTION: one office belongs to exactly one business unit.
-- Verify before trusting it:
--   SELECT office, COUNT(DISTINCT business_unit)
--     FROM staging.emp_data GROUP BY 1 HAVING COUNT(DISTINCT business_unit) > 1;
-- If that returns rows, drop the UNIQUE on office_name and make
-- the natural key (business_unit_key, office_name) instead.
DROP TABLE IF EXISTS core.dim_office CASCADE;
CREATE TABLE core.dim_office (
    office_key         smallint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    office_name        text NOT NULL UNIQUE,
    business_unit_key  smallint REFERENCES core.dim_business_unit(business_unit_key)
);

DROP TABLE IF EXISTS core.dim_vendor CASCADE;
CREATE TABLE core.dim_vendor (
    vendor_key   smallint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    vendor_name  text NOT NULL UNIQUE
);

-- Registration plate is the only vehicle identity available.
-- capacity and fuel_type are recorded per trip, so this dimension
-- takes the most recently seen value (Type 1 overwrite).
DROP TABLE IF EXISTS core.dim_vehicle CASCADE;
CREATE TABLE core.dim_vehicle (
    vehicle_key   integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    registration  text NOT NULL UNIQUE,
    capacity      smallint,
    fuel_type     text CHECK (fuel_type IN ('Diesel','Electric','Petrol'))
);

-- stwid is a stable natural key, so no surrogate is needed.
-- stwid = 0 is a placeholder and must NEVER be inserted here.
DROP TABLE IF EXISTS core.dim_employee CASCADE;
CREATE TABLE core.dim_employee (
    stwid      bigint PRIMARY KEY CHECK (stwid > 0),
    gender     text,
    emp_role   text
);

DROP TABLE IF EXISTS core.dim_contract CASCADE;
CREATE TABLE core.dim_contract (
    contract_key   smallint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    contract_code  text,
    slab_name      text,
    UNIQUE (contract_code, slab_name)
);

-- =============================================================
-- FACT 1: fact_trip   — grain: one trip
-- =============================================================
DROP TABLE IF EXISTS core.fact_trip CASCADE;
CREATE TABLE core.fact_trip (
    trip_id              bigint PRIMARY KEY,

    trip_date            date     REFERENCES core.dim_date(date_key),
    business_unit_key    smallint REFERENCES core.dim_business_unit(business_unit_key),
    office_key           smallint REFERENCES core.dim_office(office_key),
    vendor_key           smallint REFERENCES core.dim_vendor(vendor_key),
    shift_key            smallint REFERENCES core.dim_shift(shift_key),
    planned_vehicle_key  integer  REFERENCES core.dim_vehicle(vehicle_key),
    actual_vehicle_key   integer  REFERENCES core.dim_vehicle(vehicle_key),

    product_type    text CHECK (product_type   IN ('CAB','BUS','SPOT_2.0')),
    trip_direction  text CHECK (trip_direction IN ('LOGIN','LOGOUT')),
    trip_nodal      text CHECK (trip_nodal     IN ('NODAL','HOME','SHUTTLE')),
    route_source    text CHECK (route_source   IN ('AUTO','MANUAL','RENTLZ','SHUTTLE_SERVICE')),
    delay_reason    text CHECK (delay_reason   IN ('NODELAY','TRAFFIC','DRIVER','EMPLOYEE')),

    actual_escort   boolean,
    is_driver_nc    boolean,
    is_cab_nc       boolean,

    planned_km      numeric(8,3) CHECK (planned_km  >= 0),
    traveled_km     numeric(8,3) CHECK (traveled_km >= 0),

    planned_start_ts  timestamptz,
    planned_end_ts    timestamptz,
    actual_start_ts   timestamptz,
    actual_end_ts     timestamptz,

    delay_minutes         integer  CHECK (delay_minutes >= 0),
    planned_employee_cnt  smallint,
    actual_employee_cnt   smallint,
    noshow_cnt            smallint,

    -- HYPOTHESIS, NOT YET VERIFIED: actual_employee_cnt appears to
    -- include the escort. In every sample row, escort = true implies
    -- actual = planned + 1. Verify with:
    --   SELECT actual_escort, AVG(actual_employee_cnt - planned_employee_cnt)
    --     FROM core.fact_trip WHERE noshow_cnt = 0 GROUP BY 1;
    -- If it does not hold, DROP this column.
    riders_actual smallint GENERATED ALWAYS AS
        (actual_employee_cnt - CASE WHEN actual_escort THEN 1 ELSE 0 END) STORED,

    planned_duration_min integer GENERATED ALWAYS AS
        ((EXTRACT(EPOCH FROM (planned_end_ts - planned_start_ts))/60)::integer) STORED,
    actual_duration_min integer GENERATED ALWAYS AS
        ((EXTRACT(EPOCH FROM (actual_end_ts - actual_start_ts))/60)::integer) STORED,

    dq_flags     text[] NOT NULL DEFAULT '{}',
    source_file  text,
    loaded_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX ix_trip_date        ON core.fact_trip (trip_date);
CREATE INDEX ix_trip_office_date ON core.fact_trip (office_key, trip_date);
CREATE INDEX ix_trip_vendor_date ON core.fact_trip (vendor_key, trip_date);
CREATE INDEX ix_trip_delay       ON core.fact_trip (delay_reason) WHERE delay_reason <> 'NODELAY';

-- =============================================================
-- FACT 2: fact_trip_leg   — grain: one employee on one trip
-- Largest table (~1.6M rows). Dimension keys are repeated here
-- rather than joined through fact_trip, because a leg may belong
-- to a trip that does not exist in ride_data_trip.
-- =============================================================
DROP TABLE IF EXISTS core.fact_trip_leg CASCADE;
CREATE TABLE core.fact_trip_leg (
    leg_key   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    trip_id         bigint NOT NULL,   -- intentionally not a FK
    trip_is_orphan  boolean NOT NULL DEFAULT false,
    stwid           bigint REFERENCES core.dim_employee(stwid),

    trip_date          date     REFERENCES core.dim_date(date_key),
    business_unit_key  smallint REFERENCES core.dim_business_unit(business_unit_key),
    office_key         smallint REFERENCES core.dim_office(office_key),
    shift_key          smallint REFERENCES core.dim_shift(shift_key),
    product_type       text CHECK (product_type IN ('CAB','BUS','SPOT_2.0')),

    planned_pickup_ts  timestamptz,
    planned_drop_ts    timestamptz,
    actual_pickup_ts   timestamptz,
    actual_drop_ts     timestamptz,

    -- Negative distances are set to NULL on load and recorded in
    -- dq_flags. The CHECK then guarantees nothing negative lands.
    planned_km   numeric(9,3) CHECK (planned_km  >= 0),
    traveled_km  numeric(9,3) CHECK (traveled_km >= 0),

    signintype           text CHECK (signintype      IN ('Planned','Adhoc','Guest')),
    boarding_status      text CHECK (boarding_status IN ('Boarded','Not Boarded')),
    not_boarding_reason  text,
    is_no_show           boolean NOT NULL,

    pickup_delay_min integer GENERATED ALWAYS AS
        ((EXTRACT(EPOCH FROM (actual_pickup_ts - planned_pickup_ts))/60)::integer) STORED,

    dq_flags   text[] NOT NULL DEFAULT '{}',
    loaded_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX ix_leg_trip    ON core.fact_trip_leg (trip_id);
CREATE INDEX ix_leg_stwid   ON core.fact_trip_leg (stwid);
CREATE INDEX ix_leg_date    ON core.fact_trip_leg (trip_date);
CREATE INDEX ix_leg_noshow  ON core.fact_trip_leg (trip_date, office_key) WHERE is_no_show;

-- Grain check, not yet verified. Run this first:
--   SELECT trip_id, stwid, COUNT(*) FROM core.fact_trip_leg
--    GROUP BY 1,2 HAVING COUNT(*) > 1 LIMIT 5;
-- If it returns nothing, uncomment to enforce the grain:
-- CREATE UNIQUE INDEX ux_leg_grain ON core.fact_trip_leg (trip_id, stwid);

-- =============================================================
-- FACT 3: fact_trip_feedback   — grain: one rating submission
-- =============================================================
DROP TABLE IF EXISTS core.fact_trip_feedback CASCADE;
CREATE TABLE core.fact_trip_feedback (
    feedback_key  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    trip_id            bigint NOT NULL,
    trip_is_orphan     boolean NOT NULL DEFAULT false,
    stwid              bigint REFERENCES core.dim_employee(stwid),
    trip_date          date     REFERENCES core.dim_date(date_key),
    business_unit_key  smallint REFERENCES core.dim_business_unit(business_unit_key),
    trip_type          text CHECK (trip_type IN ('LOGIN','LOGOUT')),

    trip_ts      timestamptz,
    creation_ts  timestamptz,

    -- Raw ratings kept verbatim; 0 is ambiguous (unrated vs genuine
    -- zero), so the *_score columns null it out for averaging.
    route_rating    smallint CHECK (route_rating   BETWEEN 0 AND 5),
    driver_rating   smallint CHECK (driver_rating  BETWEEN 0 AND 5),
    cab_rating      smallint CHECK (cab_rating     BETWEEN 0 AND 5),
    safety_rating   smallint CHECK (safety_rating  BETWEEN 0 AND 5),
    marshal_rating  smallint CHECK (marshal_rating BETWEEN 0 AND 5),

    route_score   smallint GENERATED ALWAYS AS (NULLIF(route_rating,0))   STORED,
    driver_score  smallint GENERATED ALWAYS AS (NULLIF(driver_rating,0))  STORED,
    cab_score     smallint GENERATED ALWAYS AS (NULLIF(cab_rating,0))     STORED,
    safety_score  smallint GENERATED ALWAYS AS (NULLIF(safety_rating,0))  STORED,
    marshal_score smallint GENERATED ALWAYS AS (NULLIF(marshal_rating,0)) STORED,

    response_lag_min integer GENERATED ALWAYS AS
        ((EXTRACT(EPOCH FROM (creation_ts - trip_ts))/60)::integer) STORED,

    loaded_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX ix_fb_trip  ON core.fact_trip_feedback (trip_id);
CREATE INDEX ix_fb_stwid ON core.fact_trip_feedback (stwid);
CREATE INDEX ix_fb_date  ON core.fact_trip_feedback (trip_date);

-- =============================================================
-- FACT 4: fact_alert   — grain: one alert event
-- Column design here is driven by the alerts_data profiling:
--  * severity_raw holds all five observed values verbatim.
--    'False' is 29% of rows and 'NA' is 32% — neither is junk.
--  * severity holds only the three real triage levels.
--  * alert_scope is derived from event_type, which determines
--    with no exceptions whether stwid is a rider or the 0
--    placeholder.
-- =============================================================
DROP TABLE IF EXISTS core.fact_alert CASCADE;
CREATE TABLE core.fact_alert (
    event_id  uuid PRIMARY KEY,

    trip_id            bigint NOT NULL,
    trip_is_orphan     boolean NOT NULL DEFAULT false,
    stwid              bigint REFERENCES core.dim_employee(stwid),  -- NULL for vehicle-scope
    business_unit_key  smallint REFERENCES core.dim_business_unit(business_unit_key),
    alert_date         date REFERENCES core.dim_date(date_key),

    event_type   text NOT NULL,
    alert_scope  text NOT NULL CHECK (alert_scope IN ('VEHICLE','EMPLOYEE')),

    severity_raw text NOT NULL CHECK (severity_raw IN ('Sev-1','Sev-2','Sev-3','NA','False')),
    severity     text GENERATED ALWAYS AS
        (CASE WHEN severity_raw LIKE 'Sev-%' THEN severity_raw END) STORED,
    was_triaged  boolean GENERATED ALWAYS AS (severity_raw LIKE 'Sev-%') STORED,

    -- triaged        = human assigned a severity
    -- auto_fast      = closed quickly, no severity assigned
    -- auto_overnight = closed by the next-day sweep (~24h latency)
    -- unresolved     = never acknowledged
    resolution_path text CHECK (resolution_path IN
        ('triaged','auto_fast','auto_overnight','unresolved')),

    start_ts        timestamptz NOT NULL,
    acknowledge_ts  timestamptz,
    ack_latency_min integer GENERATED ALWAYS AS
        ((EXTRACT(EPOCH FROM (acknowledge_ts - start_ts))/60)::integer) STORED,

    state_text  text CHECK (state_text IN ('CLOSED','OPEN','NEW')),
    source      text,     -- 'NA' string in 76% of rows; kept verbatim

    loaded_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX ix_alert_trip  ON core.fact_alert (trip_id);
CREATE INDEX ix_alert_stwid ON core.fact_alert (stwid) WHERE stwid IS NOT NULL;
CREATE INDEX ix_alert_date  ON core.fact_alert (alert_date, business_unit_key);
CREATE INDEX ix_alert_sev1  ON core.fact_alert (alert_date) WHERE severity_raw = 'Sev-1';

-- =============================================================
-- FACT 5: fact_trip_billing   — grain: one billed line item
-- NOT one per trip: 620,942 rows across 613,784 trip_ids.
-- =============================================================
DROP TABLE IF EXISTS core.fact_trip_billing CASCADE;
CREATE TABLE core.fact_trip_billing (
    bill_line_key  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    trip_id            bigint NOT NULL,
    trip_is_orphan     boolean NOT NULL DEFAULT false,
    business_unit_key  smallint REFERENCES core.dim_business_unit(business_unit_key),
    office_key         smallint REFERENCES core.dim_office(office_key),
    vendor_key         smallint REFERENCES core.dim_vendor(vendor_key),
    contract_key       smallint REFERENCES core.dim_contract(contract_key),

    cycle_start  date REFERENCES core.dim_date(date_key),
    cycle_end    date REFERENCES core.dim_date(date_key),

    billed_km  numeric(9,3) CHECK (billed_km >= 0),
    trip_cost  numeric(12,2) CHECK (trip_cost >= 0),   -- numeric, never float, for money

    -- A meaningful share of rows bill a positive cost against 0 km.
    -- Flagging it stops cost-per-km from dividing by zero.
    has_zero_km boolean GENERATED ALWAYS AS (billed_km = 0) STORED,
    cost_per_km numeric(12,4) GENERATED ALWAYS AS
        (trip_cost / NULLIF(billed_km, 0)) STORED,

    loaded_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX ix_bill_trip   ON core.fact_trip_billing (trip_id);
CREATE INDEX ix_bill_cycle  ON core.fact_trip_billing (cycle_start, vendor_key);
CREATE INDEX ix_bill_vendor ON core.fact_trip_billing (vendor_key, business_unit_key);

-- =============================================================
-- Growth path (do NOT implement now — write it in the design doc)
--
-- At ~3.4M rows this model needs no partitioning; a filtered
-- index scan answers any of these queries in milliseconds.
-- Every fact above already carries a real date column, so when
-- volume reaches roughly 50M rows the migration is mechanical:
-- convert fact_trip and fact_trip_leg to monthly RANGE partitions
-- on trip_date, add the date to each primary key, and add BRIN
-- indexes on the timestamp columns.
-- =============================================================
