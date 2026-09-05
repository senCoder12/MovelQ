-- V1 -- insight and its child tables.
--
-- Shape follows contracts/insight.schema.json: one insight row plus four
-- child collections (references, attribution, controls, trace).
--
-- Tenancy rules applied to every table here:
--   * tenant_id is NOT NULL, no default, no "global" sentinel
--   * every index leads with tenant_id, so a tenant-scoped scan is the
--     cheap path and a cross-tenant scan is the expensive one
--   * child rows carry their own tenant_id and the foreign key is composite
--     (tenant_id, insight_id), so a child physically cannot point at another
--     tenant's insight. The Hibernate tenantFilter is the second line of
--     defence, not the only one.
--
-- Times are TIMESTAMPTZ throughout. Neon runs in us-east-2, the demo runs from
-- India, and the agent stamps UTC -- a naive TIMESTAMP would silently pick up
-- whichever offset the writer happened to have.

CREATE TABLE insight (
    id                          BIGSERIAL       PRIMARY KEY,
    tenant_id                   VARCHAR(64)     NOT NULL,
    insight_id                  VARCHAR(64)     NOT NULL,

    severity                    INTEGER         NOT NULL,

    metric_id                   VARCHAR(128)    NOT NULL,
    metric_name                 VARCHAR(256)    NOT NULL,
    metric_value                DOUBLE PRECISION NOT NULL,
    metric_unit                 VARCHAR(32)     NOT NULL,
    metric_n                    INTEGER         NOT NULL,
    metric_window               VARCHAR(64)     NOT NULL,

    entity_dim                  VARCHAR(64)     NOT NULL,
    entity_ref                  VARCHAR(128)    NOT NULL,
    entity_name                 VARCHAR(256)    NOT NULL,

    impact_affected_trips       INTEGER,
    impact_late_minutes_total   DOUBLE PRECISION,
    impact_cost_inr_month       DOUBLE PRECISION,

    data_quality_excluded_pct   DOUBLE PRECISION NOT NULL DEFAULT 0,
    data_quality_confidence     VARCHAR(16)     NOT NULL,

    narrative_headline          TEXT            NOT NULL,
    narrative_body              TEXT            NOT NULL,
    -- List[recommended_action]; free-shaped and only ever read whole.
    recommended_actions         JSONB           NOT NULL DEFAULT '[]'::jsonb,
    -- List[coincident_event]; same.
    coincident_events           JSONB           NOT NULL DEFAULT '[]'::jsonb,

    created_at                  TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at                  TIMESTAMPTZ     NOT NULL DEFAULT now(),

    CONSTRAINT uq_insight_tenant_insight_id UNIQUE (tenant_id, insight_id),
    CONSTRAINT ck_insight_severity CHECK (severity BETWEEN 0 AND 100)
);

-- The feed query: everything for one tenant, newest first.
CREATE INDEX ix_insight_tenant_created  ON insight (tenant_id, created_at DESC);
-- The brief query: everything for one tenant, worst first.
CREATE INDEX ix_insight_tenant_severity ON insight (tenant_id, severity DESC);
CREATE INDEX ix_insight_tenant_metric   ON insight (tenant_id, metric_id);


CREATE TABLE insight_reference (
    id              BIGSERIAL       PRIMARY KEY,
    tenant_id       VARCHAR(64)     NOT NULL,
    insight_id      VARCHAR(64)     NOT NULL,

    ordinal         INTEGER         NOT NULL DEFAULT 0,
    ref_type        VARCHAR(32)     NOT NULL,
    label           VARCHAR(512)    NOT NULL,
    -- insight.schema.json types reference.value as number|string. Keeping both
    -- columns avoids coercing "electric" into a numeric or 38.2 into text.
    value_num       DOUBLE PRECISION,
    value_text      VARCHAR(512),
    unit            VARCHAR(32),

    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),

    CONSTRAINT fk_insight_reference_insight
        FOREIGN KEY (tenant_id, insight_id)
        REFERENCES insight (tenant_id, insight_id) ON DELETE CASCADE,
    CONSTRAINT ck_insight_reference_value CHECK (value_num IS NOT NULL OR value_text IS NOT NULL)
);

CREATE INDEX ix_insight_reference_tenant_insight ON insight_reference (tenant_id, insight_id);
CREATE INDEX ix_insight_reference_tenant_created ON insight_reference (tenant_id, created_at DESC);


CREATE TABLE insight_attribution (
    id                  BIGSERIAL       PRIMARY KEY,
    tenant_id           VARCHAR(64)     NOT NULL,
    insight_id          VARCHAR(64)     NOT NULL,

    ordinal             INTEGER         NOT NULL DEFAULT 0,
    dim                 VARCHAR(64)     NOT NULL,
    value               VARCHAR(256)    NOT NULL,
    contribution_pct    DOUBLE PRECISION NOT NULL,
    n                   INTEGER         NOT NULL,

    created_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),

    CONSTRAINT fk_insight_attribution_insight
        FOREIGN KEY (tenant_id, insight_id)
        REFERENCES insight (tenant_id, insight_id) ON DELETE CASCADE
);

CREATE INDEX ix_insight_attribution_tenant_insight ON insight_attribution (tenant_id, insight_id);
CREATE INDEX ix_insight_attribution_tenant_created ON insight_attribution (tenant_id, created_at DESC);


CREATE TABLE insight_control (
    id              BIGSERIAL       PRIMARY KEY,
    tenant_id       VARCHAR(64)     NOT NULL,
    insight_id      VARCHAR(64)     NOT NULL,

    ordinal         INTEGER         NOT NULL DEFAULT 0,
    control         VARCHAR(128)    NOT NULL,
    gap_pp          DOUBLE PRECISION NOT NULL,
    survives        BOOLEAN         NOT NULL,

    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),

    CONSTRAINT fk_insight_control_insight
        FOREIGN KEY (tenant_id, insight_id)
        REFERENCES insight (tenant_id, insight_id) ON DELETE CASCADE
);

CREATE INDEX ix_insight_control_tenant_insight ON insight_control (tenant_id, insight_id);
CREATE INDEX ix_insight_control_tenant_created ON insight_control (tenant_id, created_at DESC);


CREATE TABLE insight_trace (
    id                  BIGSERIAL       PRIMARY KEY,
    tenant_id           VARCHAR(64)     NOT NULL,
    insight_id          VARCHAR(64)     NOT NULL,

    ordinal             INTEGER         NOT NULL DEFAULT 0,
    query_id            VARCHAR(128)    NOT NULL,
    -- Arbitrary query parameters; JSONB so a trace can be queried by param
    -- without a migration every time the agent adds a knob.
    params              JSONB           NOT NULL DEFAULT '{}'::jsonb,
    numerator           INTEGER         NOT NULL,
    denominator         INTEGER         NOT NULL,
    exclusions          JSONB           NOT NULL DEFAULT '[]'::jsonb,
    validation_status   VARCHAR(16)     NOT NULL,
    validation_notes    TEXT,

    created_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),

    CONSTRAINT fk_insight_trace_insight
        FOREIGN KEY (tenant_id, insight_id)
        REFERENCES insight (tenant_id, insight_id) ON DELETE CASCADE
);

CREATE INDEX ix_insight_trace_tenant_insight ON insight_trace (tenant_id, insight_id);
CREATE INDEX ix_insight_trace_tenant_created ON insight_trace (tenant_id, created_at DESC);
