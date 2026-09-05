-- =============================================================
-- 09_alert_stream_trigger.sql
-- Layer 1 -> Layer 2, event-driven instead of batch.
--
-- Two triggers replace the manual re-run of 04_transform_alerts.sql:
--
--   staging.alerts_data  --AFTER INSERT, per row-->  core.fact_alert
--   core.fact_alert       --AFTER INSERT, per row-->  pg_notify('important_alert', ...)
--
-- Postgres cannot call an LLM, push to a browser, or refresh a
-- materialized view from inside a trigger (REFRESH ... CONCURRENTLY
-- is on the list of statements that cannot run inside a transaction
-- block, and a trigger body always is one). So this file only takes
-- the pipeline as far as NOTIFY. Everything after that -- calling
-- the LLM, writing the dashboard alert, REFRESH MATERIALIZED VIEW,
-- re-running the situation/readiness queries -- has to be done by a
-- process that is LISTENing, i.e. the FastAPI backend. See the note
-- at the bottom of this file before wiring that up.
-- =============================================================

-- -------------------------------------------------------------
-- 1. Importance rule, centralized in one function so it isn't
--    copy-pasted into every trigger/query that needs it. Matches
--    the "Escalation Ladder" in architecture.md: heuristics decide
--    whether an alert is even worth spending an LLM call on.
--    Sev-1/Sev-2 are the human-triaged severities (see fact_alert's
--    severity_raw CHECK in 02_core_model.sql). The panic event types
--    are treated as important regardless of triage state, since an
--    un-acknowledged panic alert is exactly the case you can't wait
--    for a human to see first.
-- -------------------------------------------------------------
CREATE OR REPLACE FUNCTION core.fn_is_important_alert(
    p_severity_raw text,
    p_event_type   text
) RETURNS boolean
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT p_severity_raw IN ('Sev-1', 'Sev-2')
        OR p_event_type IN ('PANIC_DEVICE', 'PANIC_FIXED_DEVICE');
$$;

-- -------------------------------------------------------------
-- 2. staging.alerts_data -> core.fact_alert, one row at a time.
--    Same logic as 04_transform_alerts.sql, just scoped to NEW
--    instead of the whole table, and wrapped in an exception
--    handler: per 01_staging.sql's own rule ("nothing here is
--    allowed to reject a row"), one malformed live alert must not
--    roll back the INSERT into staging or take the feed down.
-- -------------------------------------------------------------
CREATE OR REPLACE FUNCTION core.fn_ingest_alert_row()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_start_ts   timestamptz;
    v_ack_ts     timestamptz;
    v_trip_id    bigint;
    v_stwid      bigint;
    v_bu_key     smallint;
    v_scope      text;
    v_resolution text;
BEGIN
    v_start_ts := TO_TIMESTAMP(NEW.start_time,       'FMMonth DD, YYYY, HH12:MI AM');
    v_ack_ts   := TO_TIMESTAMP(NEW.acknowledge_time, 'FMMonth DD, YYYY, HH12:MI AM');
    v_trip_id  := REPLACE(NEW.trip_id, ',', '')::bigint;
    v_stwid    := NULLIF(REPLACE(NEW.stwid, ',', '')::bigint, 0);

    IF NEW.business_unit IS NOT NULL THEN
        INSERT INTO core.dim_business_unit (business_unit_name)
        VALUES (NEW.business_unit)
        ON CONFLICT (business_unit_name) DO NOTHING;
    END IF;

    SELECT business_unit_key INTO v_bu_key
    FROM core.dim_business_unit
    WHERE business_unit_name = NEW.business_unit;

    IF v_stwid IS NOT NULL AND v_stwid > 0 THEN
        INSERT INTO core.dim_employee (stwid)
        VALUES (v_stwid)
        ON CONFLICT (stwid) DO NOTHING;
    END IF;

    v_scope := CASE
        WHEN NEW.event_type IN (
            'DEVICE_NOT_REACHABLE', 'VEHICLE_STOPPAGE', 'OVER_SPEEDING',
            'PANIC_DEVICE', 'PANIC_FIXED_DEVICE')
        THEN 'VEHICLE' ELSE 'EMPLOYEE'
    END;

    v_resolution := CASE
        WHEN v_ack_ts IS NULL                                        THEN 'unresolved'
        WHEN NEW.severity LIKE 'Sev-%'                                THEN 'triaged'
        WHEN EXTRACT(EPOCH FROM (v_ack_ts - v_start_ts)) / 60 > 720   THEN 'auto_overnight'
        ELSE 'auto_fast'
    END;

    INSERT INTO core.fact_alert (
        event_id, trip_id, stwid, business_unit_key, alert_date,
        event_type, alert_scope, severity_raw, resolution_path,
        start_ts, acknowledge_ts, state_text, source
    )
    VALUES (
        NEW.event_id::uuid, v_trip_id, v_stwid, v_bu_key, v_start_ts::date,
        NEW.event_type, v_scope, NEW.severity, v_resolution,
        v_start_ts, v_ack_ts, NULLIF(NEW.state_text, 'NA'), NULLIF(NEW.source, 'NA')
    )
    ON CONFLICT (event_id) DO NOTHING;   -- idempotent: replaying/re-inserting is a no-op

    RETURN NEW;

EXCEPTION WHEN OTHERS THEN
    RAISE WARNING 'fn_ingest_alert_row: skipped event_id=% (%)', NEW.event_id, SQLERRM;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_ingest_alert_row ON staging.alerts_data;
CREATE TRIGGER trg_ingest_alert_row
    AFTER INSERT ON staging.alerts_data
    FOR EACH ROW
    EXECUTE FUNCTION core.fn_ingest_alert_row();

-- -------------------------------------------------------------
-- 3. core.fact_alert -> pg_notify, only for alerts that pass the
--    importance rule. Payload is deliberately small (ids + the
--    fields needed to decide what to do next) -- NOTIFY payloads
--    are capped at 8000 bytes, and the listener can always pull
--    the rest from analytics.v_alert by event_id.
-- -------------------------------------------------------------
CREATE OR REPLACE FUNCTION core.fn_notify_important_alert()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_payload jsonb;
BEGIN
    IF core.fn_is_important_alert(NEW.severity_raw, NEW.event_type) THEN
        v_payload := jsonb_build_object(
            'event_id',          NEW.event_id,
            'trip_id',           NEW.trip_id,
            'trip_is_orphan',    NEW.trip_is_orphan,
            'stwid',             NEW.stwid,
            'business_unit_key', NEW.business_unit_key,
            'alert_date',        NEW.alert_date,
            'event_type',        NEW.event_type,
            'alert_scope',       NEW.alert_scope,
            'severity',          NEW.severity_raw,
            'state_text',        NEW.state_text,
            'start_ts',          NEW.start_ts
        );
        PERFORM pg_notify('important_alert', v_payload::text);
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_notify_important_alert ON core.fact_alert;
CREATE TRIGGER trg_notify_important_alert
    AFTER INSERT ON core.fact_alert
    FOR EACH ROW
    EXECUTE FUNCTION core.fn_notify_important_alert();

-- =============================================================
-- One thing this depends on: 01_staging.sql no longer drops any
-- table (CREATE TABLE IF NOT EXISTS everywhere) specifically so
-- trg_ingest_alert_row survives every re-run of that file. If that
-- rule is ever relaxed for staging.alerts_data, this trigger goes
-- with it.
--
-- Neon's pooled connection string (the one behind PgBouncer,
-- transaction-mode pooling -- likely what NEON_DATABASE_URL points
-- at in backend/app/config.py) does not deliver NOTIFYs: a LISTEN
-- issued on one pooled connection can be silently torn down when the
-- pooler recycles it to another client. The process that runs
-- `LISTEN important_alert;` must hold Neon's *direct* (unpooled)
-- connection string on its own dedicated, long-lived connection --
-- separate from the asyncpg pool used for normal request handling.
-- See app/infrastructure/alert_listener.py and NEON_DIRECT_DATABASE_URL.
-- =============================================================
