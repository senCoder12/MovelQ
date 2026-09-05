-- V7 -- the token ledger.
--
-- One row per model call, written by the Python agent directly (agent/app/llm/ledger.py),
-- not routed through the backend. The ledger sits on the latency path of every model call;
-- adding a Java hop would put a round trip to us-east-2 in front of a round trip to Gemini.
-- The backend only ever reads this table -- see ScanService, which aggregates a run's
-- llm_calls/tokens/llm_ms back out of it rather than counting in memory.
--
-- Platform data, so Postgres rather than DuckDB: the warehouse is ride data the agent
-- rebuilds from raw files, and a ledger that disappears on the next ingest is not a ledger.
--
-- A failed call still gets a row: tokens 0, error set. A provider timeout costs latency
-- even when it returns no tokens, and a ledger that only records successes reports the
-- cheerful half of the bill.
--
-- Numbering: V5 and V6 were never issued in this tree. Flyway tolerates gaps in the
-- version sequence; the three tables this release adds are numbered V7-V9 as specified.

CREATE TABLE token_usage (
    usage_id        BIGSERIAL       PRIMARY KEY,
    tenant_id       VARCHAR(64)     NOT NULL,

    -- Set when the call was made inside a scan (the agent reads X-Scan-Run-Id off the
    -- request). Null for an ad-hoc call -- a leadership pack assembled from the UI, say.
    -- No foreign key to scan_run on purpose: the ledger row is written mid-run, before
    -- scan_run's row exists, and the ledger must never block on the run's bookkeeping.
    scan_run_id     UUID,
    insight_id      VARCHAR(64),

    call_type       VARCHAR(32)     NOT NULL,
    model           VARCHAR(128)    NOT NULL,

    tokens_in       INTEGER         NOT NULL DEFAULT 0,
    tokens_out      INTEGER         NOT NULL DEFAULT 0,
    -- Provider-side prompt cache. 0 when the provider reports nothing, which is not the
    -- same claim as "nothing was cached" -- it is "the provider did not say".
    cached_tokens   INTEGER         NOT NULL DEFAULT 0,

    -- Wall clock measured around the call, including a failed one.
    duration_ms     INTEGER         NOT NULL DEFAULT 0,
    -- OUR cache, not the provider's: true means the response came from the agent's own
    -- response cache and no request left the process. Such a row has tokens 0 and a
    -- duration measured in microseconds, and it is what the cache hit rate counts.
    cache_hit       BOOLEAN         NOT NULL DEFAULT FALSE,

    -- Null on success. On failure, the exception class and message, truncated.
    error           TEXT,

    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),

    CONSTRAINT ck_token_usage_call_type CHECK (
        call_type IN ('narrate', 'draft_action', 'leadership_narrative', 'route_intent', 'other')),
    CONSTRAINT ck_token_usage_tokens CHECK (
        tokens_in >= 0 AND tokens_out >= 0 AND cached_tokens >= 0 AND duration_ms >= 0)
);

-- The cost query: one tenant, one period, newest first.
CREATE INDEX ix_token_usage_tenant_created ON token_usage (tenant_id, created_at DESC);
-- The scan aggregate: every call made inside one run.
CREATE INDEX ix_token_usage_scan_run       ON token_usage (scan_run_id);

COMMENT ON TABLE token_usage IS
    'One row per model call, written by the Python agent. A degraded-mode scan writes none, '
    'which is how "no LLM calls" is measured rather than merely asserted.';
COMMENT ON COLUMN token_usage.cache_hit IS
    'The agent''s own response cache, not the provider''s prompt cache (see cached_tokens).';
