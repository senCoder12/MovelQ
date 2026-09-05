-- V8 -- one row per scan.
--
-- The record that the agent ran without anyone prompting it. Before this the only
-- evidence a refresh happened was a log line and a SyncResult that was returned and
-- dropped; there was no status, no timing and no way to ask "when did this last work".
--
-- Every counter here is populated. An empty tokens_in makes the cost slide impossible to
-- write after the fact, and llm_ms kept separate from duration_ms is what lets us say what
-- fraction of a scan is model time rather than warehouse time.
--
-- llm_calls / tokens_in / tokens_out / llm_ms are read back out of token_usage filtered by
-- run_id at the end of the run, never incremented in memory. Two counters for the same
-- fact eventually disagree, and the ledger is the one with the rows.

CREATE TABLE scan_run (
    run_id              UUID            PRIMARY KEY,
    tenant_id           VARCHAR(64)     NOT NULL,

    trigger             VARCHAR(16)     NOT NULL,

    started_at          TIMESTAMPTZ     NOT NULL,
    finished_at         TIMESTAMPTZ,
    duration_ms         INTEGER,

    -- The window actually scanned, derived from the warehouse's own max trip_date, not
    -- from the wall clock. The ride data is July 2026; a job that trusted the system clock
    -- would scan an empty window and write a cheerful zero-signal SUCCESS.
    window_start        DATE,
    window_end          DATE,

    trips_scanned       INTEGER         NOT NULL DEFAULT 0,
    signals_detected    INTEGER         NOT NULL DEFAULT 0,
    signals_surfaced    INTEGER         NOT NULL DEFAULT 0,
    insights_persisted  INTEGER         NOT NULL DEFAULT 0,
    actions_drafted     INTEGER         NOT NULL DEFAULT 0,

    llm_calls           INTEGER         NOT NULL DEFAULT 0,
    tokens_in           BIGINT          NOT NULL DEFAULT 0,
    tokens_out          BIGINT          NOT NULL DEFAULT 0,
    llm_ms              BIGINT          NOT NULL DEFAULT 0,

    status              VARCHAR(16)     NOT NULL,
    -- ["narrate_failed", "draft_failed", ...] -- which non-signal stage degraded, so a
    -- PARTIAL says what was partial about it.
    degraded_reasons    JSONB           NOT NULL DEFAULT '[]'::jsonb,
    error_summary       TEXT,

    created_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),

    CONSTRAINT ck_scan_run_trigger CHECK (trigger IN ('SCHEDULED', 'MANUAL')),
    CONSTRAINT ck_scan_run_status  CHECK (status IN ('RUNNING', 'SUCCESS', 'PARTIAL', 'FAILED'))
);

-- GET /api/jobs/status: the last ten runs for one tenant.
CREATE INDEX ix_scan_run_tenant_started ON scan_run (tenant_id, started_at DESC);

COMMENT ON COLUMN scan_run.status IS
    'RUNNING while in flight; SUCCESS every stage completed; PARTIAL insights persisted but '
    'a non-signal stage degraded (see degraded_reasons); FAILED no insights persisted. '
    'A narrate failure is never FAILED -- signal generation is LLM-free, so if the prose '
    'falls back to a template the insight still stands.';
COMMENT ON COLUMN scan_run.llm_ms IS
    'Sum of token_usage.duration_ms for this run. Separate from duration_ms so the share of '
    'a scan spent waiting on a model is answerable.';
