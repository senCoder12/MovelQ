-- V9 -- the pre-assembled brief.
--
-- GET /api/brief reads exactly one row of this table and returns payload verbatim. No
-- joins, no folding of a cartesian product, no per-request assembly.
--
-- Reason: Neon is us-east-2 and the demo runs from India, where one round trip costs
-- 150-250ms. The previous brief path was already down to a single wide query, but it still
-- rebuilt every packet on the request thread and needed the agent alive to refill a cold
-- cache. One indexed primary-key read of one JSONB row renders instantly and keeps
-- rendering with the agent switched off -- correct architecture, and demo insurance.
--
-- Persona filtering happens at write time, not read time. The scan decides once which
-- insights belong in each persona's brief; the read does not filter, because a filter on
-- the read path is a filter that runs on every page load.

CREATE TABLE brief_snapshot (
    tenant_id       VARCHAR(64)     NOT NULL,
    persona         VARCHAR(16)     NOT NULL,

    generated_at    TIMESTAMPTZ     NOT NULL DEFAULT now(),
    -- The run that wrote this snapshot. The brief's header block is read from it, so the
    -- UI status line shows what the scan actually did.
    scan_run_id     UUID,

    -- The whole brief: header, insights with references / attributions / controls /
    -- narrative / data quality, and the action drafts already on file for them.
    payload         JSONB           NOT NULL,
    -- SHA-256 over the payload with generated_at and the run id excluded, so a re-run that
    -- found the same thing is detectable as unchanged rather than merely re-timestamped.
    payload_hash    CHAR(64)        NOT NULL,

    PRIMARY KEY (tenant_id, persona),

    CONSTRAINT ck_brief_snapshot_persona CHECK (persona IN ('ops', 'strategic', 'shift'))
);

COMMENT ON TABLE brief_snapshot IS
    'One row per tenant per persona, upserted by the scan. GET /api/brief reads one row.';
COMMENT ON COLUMN brief_snapshot.payload_hash IS
    'Excludes generated_at and scan_run_id: it answers "did this run find anything new", '
    'not "did this run happen".';
