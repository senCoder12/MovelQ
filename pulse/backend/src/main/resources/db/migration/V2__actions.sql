-- Action drafting and approval: the agent only ever writes DRAFTED rows via
-- Java; every other status transition is a human decision logged in
-- approval_log. tenant_id leads both tables and both indexes -- every query
-- this app ever runs is scoped to a tenant first.

CREATE TABLE action_draft (
    action_id VARCHAR(64) PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL,
    insight_id VARCHAR(64) NOT NULL,
    type VARCHAR(64) NOT NULL,
    title VARCHAR(500) NOT NULL,
    recipient_json TEXT NOT NULL,
    channel VARCHAR(32) NOT NULL,
    subject VARCHAR(500) NOT NULL,
    body TEXT NOT NULL,
    facts_cited_json TEXT NOT NULL,
    preview_json TEXT NOT NULL,
    rationale TEXT,
    confidence VARCHAR(16) NOT NULL,
    status VARCHAR(32) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_action_draft_tenant_insight ON action_draft (tenant_id, insight_id);
CREATE INDEX idx_action_draft_tenant_status ON action_draft (tenant_id, status);

CREATE TABLE approval_log (
    log_id VARCHAR(64) PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL,
    action_id VARCHAR(64) NOT NULL,
    decision VARCHAR(32) NOT NULL,
    decided_by VARCHAR(128) NOT NULL,
    decided_at TIMESTAMPTZ NOT NULL,
    edited_subject VARCHAR(500),
    edited_body TEXT,
    note VARCHAR(2000)
);

CREATE INDEX idx_approval_log_tenant_action ON approval_log (tenant_id, action_id);
