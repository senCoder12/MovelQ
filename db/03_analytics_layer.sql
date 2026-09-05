-- =============================================================
-- 03_analytics_layer.sql
-- Layer 3: what the AI agent is allowed to see.
--
-- One view per grain, dimensions already joined in. The agent
-- gets SELECT on this schema only. Because each view is a single
-- grain, the agent physically cannot write the trips x legs x
-- bills join that triples every cost and distance total -- the
-- most common way an LLM silently produces wrong numbers here.
-- =============================================================

CREATE SCHEMA IF NOT EXISTS analytics;

-- -------------------------------------------------------------
-- Trip grain: one row per trip
-- -------------------------------------------------------------
CREATE OR REPLACE VIEW analytics.v_trip AS
SELECT  f.trip_id,
        f.trip_date,
        d.year_month,
        d.day_name,
        d.is_weekend,
        bu.business_unit_name  AS business_unit,
        o.office_name          AS office,
        v.vendor_name          AS vendor,
        s.shift_code           AS shift,
        s.shift_band,
        veh.registration       AS cab_registration,
        veh.capacity           AS cab_capacity,
        veh.fuel_type          AS cab_fuel_type,
        f.product_type,
        f.trip_direction,
        f.trip_nodal,
        f.route_source,
        f.delay_reason,
        f.actual_escort,
        f.is_driver_nc,
        f.is_cab_nc,
        f.planned_km,
        f.traveled_km,
        f.traveled_km - f.planned_km          AS km_variance,
        f.planned_start_ts,
        f.actual_start_ts,
        f.planned_duration_min,
        f.actual_duration_min,
        f.delay_minutes,
        (f.delay_minutes > 0)                 AS is_delayed,
        (f.delay_minutes <= 15)               AS is_on_time,     -- SLA: 15 min. Change in ONE place.
        f.planned_employee_cnt,
        f.actual_employee_cnt,
        f.riders_actual,
        f.noshow_cnt,
        ROUND(f.riders_actual::numeric / NULLIF(veh.capacity,0), 3) AS capacity_utilisation,
        f.dq_flags,
        (cardinality(f.dq_flags) > 0)         AS has_quality_issue
FROM core.fact_trip f
LEFT JOIN core.dim_date          d   ON d.date_key = f.trip_date
LEFT JOIN core.dim_business_unit bu  ON bu.business_unit_key = f.business_unit_key
LEFT JOIN core.dim_office        o   ON o.office_key  = f.office_key
LEFT JOIN core.dim_vendor        v   ON v.vendor_key  = f.vendor_key
LEFT JOIN core.dim_shift         s   ON s.shift_key   = f.shift_key
LEFT JOIN core.dim_vehicle       veh ON veh.vehicle_key = f.actual_vehicle_key;

-- -------------------------------------------------------------
-- Leg grain: one row per employee per trip
-- -------------------------------------------------------------
CREATE OR REPLACE VIEW analytics.v_leg AS
SELECT  l.leg_key,
        l.trip_id,
        l.trip_is_orphan,
        l.stwid,
        e.gender,
        e.emp_role,
        l.trip_date,
        d.year_month,
        bu.business_unit_name AS business_unit,
        o.office_name         AS office,
        s.shift_code          AS shift,
        s.shift_band,
        l.product_type,
        l.signintype,
        l.boarding_status,
        l.not_boarding_reason,
        l.is_no_show,
        l.planned_pickup_ts,
        l.actual_pickup_ts,
        l.pickup_delay_min,
        (l.pickup_delay_min > 15) AS is_late_pickup,
        l.planned_km,
        l.traveled_km,
        l.dq_flags
FROM core.fact_trip_leg l
LEFT JOIN core.dim_employee      e  ON e.stwid = l.stwid
LEFT JOIN core.dim_date          d  ON d.date_key = l.trip_date
LEFT JOIN core.dim_business_unit bu ON bu.business_unit_key = l.business_unit_key
LEFT JOIN core.dim_office        o  ON o.office_key = l.office_key
LEFT JOIN core.dim_shift         s  ON s.shift_key  = l.shift_key;

-- -------------------------------------------------------------
-- Alert grain: one row per event
-- -------------------------------------------------------------
CREATE OR REPLACE VIEW analytics.v_alert AS
SELECT  a.event_id,
        a.trip_id,
        a.trip_is_orphan,
        a.stwid,
        a.alert_scope,
        a.alert_date,
        d.year_month,
        bu.business_unit_name AS business_unit,
        a.event_type,
        a.severity,            -- NULL unless a human triaged it
        a.severity_raw,
        a.was_triaged,
        a.resolution_path,
        a.start_ts,
        a.acknowledge_ts,
        a.ack_latency_min,
        a.state_text,
        a.source
FROM core.fact_alert a
LEFT JOIN core.dim_date          d  ON d.date_key = a.alert_date
LEFT JOIN core.dim_business_unit bu ON bu.business_unit_key = a.business_unit_key;

-- -------------------------------------------------------------
-- Feedback grain: one row per rating submission
-- -------------------------------------------------------------
CREATE OR REPLACE VIEW analytics.v_feedback AS
SELECT  f.feedback_key,
        f.trip_id,
        f.stwid,
        f.trip_date,
        d.year_month,
        bu.business_unit_name AS business_unit,
        f.trip_type,
        f.route_score,
        f.driver_score,
        f.cab_score,
        f.safety_score,
        f.marshal_score,
        f.response_lag_min
FROM core.fact_trip_feedback f
LEFT JOIN core.dim_date          d  ON d.date_key = f.trip_date
LEFT JOIN core.dim_business_unit bu ON bu.business_unit_key = f.business_unit_key;

-- -------------------------------------------------------------
-- Billing grain: one row per billed line item
-- -------------------------------------------------------------
CREATE OR REPLACE VIEW analytics.v_billing AS
SELECT  b.bill_line_key,
        b.trip_id,
        b.cycle_start,
        b.cycle_end,
        bu.business_unit_name AS business_unit,
        o.office_name         AS office,
        v.vendor_name         AS vendor,
        c.contract_code,
        c.slab_name,
        b.billed_km,
        b.trip_cost,
        b.cost_per_km,
        b.has_zero_km
FROM core.fact_trip_billing b
LEFT JOIN core.dim_business_unit bu ON bu.business_unit_key = b.business_unit_key
LEFT JOIN core.dim_office        o  ON o.office_key   = b.office_key
LEFT JOIN core.dim_vendor        v  ON v.vendor_key   = b.vendor_key
LEFT JOIN core.dim_contract      c  ON c.contract_key = b.contract_key;

-- =============================================================
-- Daily rollups. These make "how does this month compare to last"
-- instant, which is the shape of most agent questions.
-- Refresh after each load:  REFRESH MATERIALIZED VIEW ...
-- =============================================================

DROP MATERIALIZED VIEW IF EXISTS analytics.mv_daily_trip_metrics;
CREATE MATERIALIZED VIEW analytics.mv_daily_trip_metrics AS
SELECT  trip_date,
        year_month,
        business_unit,
        office,
        vendor,
        shift_band,
        trip_direction,
        COUNT(*)                                        AS trips,
        COUNT(*) FILTER (WHERE is_delayed)              AS delayed_trips,
        ROUND(AVG(delay_minutes), 2)                    AS avg_delay_min,
        ROUND(100.0 * COUNT(*) FILTER (WHERE is_on_time) / COUNT(*), 2) AS on_time_pct,
        COUNT(*) FILTER (WHERE delay_reason = 'TRAFFIC')  AS delay_traffic,
        COUNT(*) FILTER (WHERE delay_reason = 'DRIVER')   AS delay_driver,
        COUNT(*) FILTER (WHERE delay_reason = 'EMPLOYEE') AS delay_employee,
        SUM(traveled_km)                                AS total_km,
        SUM(noshow_cnt)                                 AS noshows,
        ROUND(AVG(capacity_utilisation), 3)             AS avg_capacity_utilisation
FROM analytics.v_trip
GROUP BY 1,2,3,4,5,6,7;

CREATE UNIQUE INDEX ux_mv_daily_trip
    ON analytics.mv_daily_trip_metrics
       (trip_date, business_unit, office, vendor, shift_band, trip_direction);

DROP MATERIALIZED VIEW IF EXISTS analytics.mv_daily_alert_metrics;
CREATE MATERIALIZED VIEW analytics.mv_daily_alert_metrics AS
SELECT  alert_date,
        business_unit,
        event_type,
        alert_scope,
        COUNT(*)                                          AS alerts,
        COUNT(*) FILTER (WHERE severity = 'Sev-1')        AS sev1,
        COUNT(*) FILTER (WHERE severity = 'Sev-2')        AS sev2,
        COUNT(*) FILTER (WHERE was_triaged)               AS triaged,
        -- MEDIAN, not average. The latency distribution is bimodal
        -- (a fast human cohort and a ~24h auto-close cohort), so a
        -- mean describes no alert that actually happened.
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ack_latency_min)
            FILTER (WHERE was_triaged)                    AS median_triaged_latency_min
FROM analytics.v_alert
GROUP BY 1,2,3,4;

CREATE UNIQUE INDEX ux_mv_daily_alert
    ON analytics.mv_daily_alert_metrics (alert_date, business_unit, event_type, alert_scope);

-- =============================================================
-- The agent's database role.
-- Run as the Neon owner. Replace the password.
-- =============================================================
-- CREATE ROLE ai_agent LOGIN PASSWORD 'change-me';
-- GRANT USAGE ON SCHEMA analytics TO ai_agent;
-- GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO ai_agent;
-- ALTER DEFAULT PRIVILEGES IN SCHEMA analytics
--     GRANT SELECT ON TABLES TO ai_agent;
--
-- Deliberately NOT granted: any access to staging or core, and
-- any INSERT/UPDATE/DELETE/DDL anywhere. A prompt injection that
-- tells the agent to drop a table then fails at the permission
-- layer, not at the prompt layer.
--
-- ALTER ROLE ai_agent SET statement_timeout = '10s';
-- ALTER ROLE ai_agent SET default_transaction_read_only = on;
-- =============================================================
