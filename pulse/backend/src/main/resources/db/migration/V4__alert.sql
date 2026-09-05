-- Proactive alerting: who gets told, when, how loudly -- without anyone
-- opening the app. scan_run is the (minimal, on-demand, not scheduled)
-- job's own record of itself; alert/alert_delivery/alert_suppression are
-- the decision, the rendered notification, and the mute, respectively.
-- tenant_id leads every index here, same reasoning as V2/V3.

CREATE TABLE scan_run (
    scan_run_id VARCHAR(64) PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL,
    started_at TIMESTAMP NOT NULL,
    finished_at TIMESTAMP,
    status VARCHAR(16) NOT NULL,
    insight_count INT NOT NULL,
    alerts_fired INT NOT NULL,
    alerts_suppressed INT NOT NULL,
    alerts_repeated INT NOT NULL,
    error_summary VARCHAR(2000)
);

CREATE INDEX idx_scan_run_tenant_started_at ON scan_run (tenant_id, started_at DESC);

CREATE TABLE alert (
    alert_id VARCHAR(64) PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL,
    rule_id VARCHAR(64) NOT NULL,
    insight_id VARCHAR(64) NOT NULL,
    persona VARCHAR(16) NOT NULL,
    urgency VARCHAR(16) NOT NULL,
    channel VARCHAR(24) NOT NULL,
    entity_dim VARCHAR(64) NOT NULL,
    entity_value VARCHAR(200) NOT NULL,
    fired_at TIMESTAMP NOT NULL,
    scan_run_id VARCHAR(64) NOT NULL,
    status VARCHAR(16) NOT NULL,
    acknowledged_at TIMESTAMP,
    acknowledged_by VARCHAR(128),
    acknowledged_note VARCHAR(2000),
    repeat_of VARCHAR(64)
);

CREATE INDEX idx_alert_tenant_status_fired_at ON alert (tenant_id, status, fired_at DESC);
-- Cooldown / repeat lookups: the same (tenant, rule, entity) is queried on
-- every scan.
CREATE INDEX idx_alert_tenant_rule_entity ON alert (tenant_id, rule_id, entity_dim, entity_value);

CREATE TABLE alert_delivery (
    delivery_id VARCHAR(64) PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL,
    alert_id VARCHAR(64) NOT NULL,
    channel VARCHAR(24) NOT NULL,
    rendered_subject VARCHAR(500) NOT NULL,
    rendered_body CLOB NOT NULL,
    would_send_to CLOB NOT NULL,
    created_at TIMESTAMP NOT NULL,
    delivery_status VARCHAR(16) NOT NULL
);

CREATE INDEX idx_alert_delivery_tenant_alert ON alert_delivery (tenant_id, alert_id);

CREATE TABLE alert_suppression (
    suppression_id VARCHAR(64) PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL,
    rule_id VARCHAR(64) NOT NULL,
    entity_dim VARCHAR(64) NOT NULL,
    entity_value VARCHAR(200) NOT NULL,
    suppressed_until TIMESTAMP NOT NULL,
    reason VARCHAR(2000),
    muted_by VARCHAR(128) NOT NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX idx_alert_suppression_tenant_rule_entity ON alert_suppression (tenant_id, rule_id, entity_dim, entity_value);
