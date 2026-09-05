-- V2 -- action drafts and the approval trail.
--
-- An action draft is what Pulse proposes a human should do about an insight.
-- Nothing leaves the building without a row in approval_log, so this pair is
-- the audit story: what was proposed, who decided, when, and on what facts.

CREATE TABLE action_draft (
    id              BIGSERIAL       PRIMARY KEY,
    tenant_id       VARCHAR(64)     NOT NULL,
    action_id       VARCHAR(64)     NOT NULL,
    insight_id      VARCHAR(64)     NOT NULL,

    action_type     VARCHAR(32)     NOT NULL,
    title           VARCHAR(512)    NOT NULL,
    body            TEXT            NOT NULL,
    rationale       TEXT            NOT NULL,

    -- Who it goes to: {"to": [...], "cc": [...], "channel": "email"}. Shape
    -- differs per action_type, so JSONB rather than five nullable columns.
    recipient       JSONB           NOT NULL DEFAULT '{}'::jsonb,
    -- The grounding. Every number the draft quotes, with the insight field it
    -- came from -- this is what makes a draft auditable rather than generated.
    facts_cited     JSONB           NOT NULL DEFAULT '[]'::jsonb,
    -- Rendered preview the approver actually sees before saying yes.
    preview         JSONB           NOT NULL DEFAULT '{}'::jsonb,
    -- Type-specific knobs (ticket project, severity, due date, ...).
    params          JSONB           NOT NULL DEFAULT '{}'::jsonb,

    status          VARCHAR(16)     NOT NULL DEFAULT 'draft',

    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),

    CONSTRAINT uq_action_draft_tenant_action_id UNIQUE (tenant_id, action_id),
    CONSTRAINT uq_action_draft_tenant_id UNIQUE (tenant_id, id),
    CONSTRAINT fk_action_draft_insight
        FOREIGN KEY (tenant_id, insight_id)
        REFERENCES insight (tenant_id, insight_id) ON DELETE CASCADE,
    CONSTRAINT ck_action_draft_status
        CHECK (status IN ('draft', 'approved', 'rejected', 'sent', 'failed'))
);

CREATE INDEX ix_action_draft_tenant_created ON action_draft (tenant_id, created_at DESC);
CREATE INDEX ix_action_draft_tenant_insight ON action_draft (tenant_id, insight_id);
CREATE INDEX ix_action_draft_tenant_status  ON action_draft (tenant_id, status);


CREATE TABLE approval_log (
    id                  BIGSERIAL       PRIMARY KEY,
    tenant_id           VARCHAR(64)     NOT NULL,
    action_draft_id     BIGINT          NOT NULL,

    decision            VARCHAR(16)     NOT NULL,
    actor               VARCHAR(256)    NOT NULL,
    note                TEXT,
    -- When the human decided, which is not when we got round to writing the row.
    decided_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),

    created_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),

    CONSTRAINT fk_approval_log_action_draft
        FOREIGN KEY (tenant_id, action_draft_id)
        REFERENCES action_draft (tenant_id, id) ON DELETE CASCADE,
    CONSTRAINT ck_approval_log_decision
        CHECK (decision IN ('approved', 'rejected', 'sent', 'failed'))
);

CREATE INDEX ix_approval_log_tenant_created ON approval_log (tenant_id, created_at DESC);
CREATE INDEX ix_approval_log_tenant_action  ON approval_log (tenant_id, action_draft_id);
