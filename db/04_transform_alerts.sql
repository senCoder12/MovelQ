-- =============================================================
-- 04_transform_alerts.sql
-- Layer 2 -> staging to core, for alerts_data.
-- Use this as the pattern for the other four files.
--
-- Order matters: dimensions first (facts reference them), fact last.
-- Every step is idempotent -- safe to re-run.
-- =============================================================

-- 1. Dimensions: insert any values this file introduces.
INSERT INTO core.dim_business_unit (business_unit_name)
SELECT DISTINCT business_unit FROM staging.alerts_data
WHERE business_unit IS NOT NULL
ON CONFLICT (business_unit_name) DO NOTHING;

-- Riders seen in alerts. stwid '0' is a placeholder and is excluded.
INSERT INTO core.dim_employee (stwid)
SELECT DISTINCT REPLACE(stwid, ',', '')::bigint
FROM staging.alerts_data
WHERE REPLACE(stwid, ',', '')::bigint > 0
ON CONFLICT (stwid) DO NOTHING;

-- 2. The fact.
INSERT INTO core.fact_alert (
    event_id, trip_id, stwid, business_unit_key, alert_date,
    event_type, alert_scope, severity_raw, resolution_path,
    start_ts, acknowledge_ts, state_text, source)
SELECT
    s.event_id::uuid,

    REPLACE(s.trip_id, ',', '')::bigint,

    -- NULL rather than 0, so the FK to dim_employee holds and
    -- "alerts per employee" never counts device events.
    NULLIF(REPLACE(s.stwid, ',', '')::bigint, 0),

    bu.business_unit_key,
    st.start_ts::date,
    s.event_type,

    -- Verified against all 51,699 rows: event_type determines
    -- scope with zero exceptions.
    CASE WHEN s.event_type IN (
            'DEVICE_NOT_REACHABLE','VEHICLE_STOPPAGE','OVER_SPEEDING',
            'PANIC_DEVICE','PANIC_FIXED_DEVICE')
         THEN 'VEHICLE' ELSE 'EMPLOYEE' END,

    -- Kept verbatim. 'NA' and 'False' are real categories here,
    -- not nulls: together they are 61% of the file.
    s.severity,

    CASE
        WHEN st.ack_ts IS NULL              THEN 'unresolved'
        WHEN s.severity LIKE 'Sev-%'        THEN 'triaged'
        WHEN EXTRACT(EPOCH FROM (st.ack_ts - st.start_ts))/60 > 720
                                            THEN 'auto_overnight'
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
ON CONFLICT (event_id) DO NOTHING;

-- 3. Mark alerts whose trip is not in fact_trip. Run this AFTER
--    fact_trip is loaded. Roughly 72% are expected to be orphans
--    (BUS and SPOT_2.0 trips absent from ride_data_trip).
UPDATE core.fact_alert a
SET trip_is_orphan = NOT EXISTS (
    SELECT 1 FROM core.fact_trip t WHERE t.trip_id = a.trip_id);
