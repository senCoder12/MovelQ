-- Report recipients and the immutable dispatch record. There is no user
-- table (and none is planned) -- report_recipient is a seeded stand-in,
-- read-only from the API. tenant_id leads both tables, matching the
-- convention in V2 for the same reason: every query here is tenant-scoped
-- first.
--
-- recipients_json on report_dispatch is a JSON array of the recipient
-- snapshot at send time (id/name/email/role), stored as text -- H2 has no
-- JSONB type, unlike the Postgres target in db/02_core_model.sql.

CREATE TABLE report_recipient (
    recipient_id VARCHAR(64) PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL,
    name VARCHAR(200) NOT NULL,
    email VARCHAR(320) NOT NULL,
    role VARCHAR(32) NOT NULL,
    is_default BOOLEAN NOT NULL
);

CREATE INDEX idx_report_recipient_tenant ON report_recipient (tenant_id);

CREATE TABLE report_dispatch (
    dispatch_id VARCHAR(64) PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL,
    report_id VARCHAR(64) NOT NULL,
    period VARCHAR(16) NOT NULL,
    recipients_json CLOB NOT NULL,
    subject VARCHAR(500) NOT NULL,
    body_html CLOB NOT NULL,
    body_text CLOB NOT NULL,
    transport VARCHAR(16) NOT NULL,
    status VARCHAR(16) NOT NULL,
    dispatched_at TIMESTAMP NOT NULL,
    dispatched_by VARCHAR(128) NOT NULL,
    provider_message_id VARCHAR(320),
    error_summary VARCHAR(2000),
    content_hash VARCHAR(64) NOT NULL
);

CREATE INDEX idx_report_dispatch_tenant_dispatched_at ON report_dispatch (tenant_id, dispatched_at DESC);

-- Four recipients per tenant, one per role. Emails on example.com so that
-- flipping pulse.dispatch.transport to smtp without also widening
-- pulse.smtp.allowlist-domains cannot reach a real inbox even by accident.
-- transport_head and leadership are pre-checked defaults in the send
-- drawer -- finance and vendor_manager are the ones you opt into, since not
-- every leadership-pack send needs billing or vendor-contact detail.
INSERT INTO report_recipient (recipient_id, tenant_id, name, email, role, is_default) VALUES
    ('rcpt_catalyst_transport_head', 'catalyst', 'Transport Head', 'transport.head@catalyst.example.com', 'transport_head', TRUE),
    ('rcpt_catalyst_finance', 'catalyst', 'Finance Desk', 'finance@catalyst.example.com', 'finance', FALSE),
    ('rcpt_catalyst_vendor_manager', 'catalyst', 'Vendor Manager', 'vendor.manager@catalyst.example.com', 'vendor_manager', FALSE),
    ('rcpt_catalyst_leadership', 'catalyst', 'Leadership Team', 'leadership@catalyst.example.com', 'leadership', TRUE),

    ('rcpt_orbit_transport_head', 'orbit', 'Transport Head', 'transport.head@orbit.example.com', 'transport_head', TRUE),
    ('rcpt_orbit_finance', 'orbit', 'Finance Desk', 'finance@orbit.example.com', 'finance', FALSE),
    ('rcpt_orbit_vendor_manager', 'orbit', 'Vendor Manager', 'vendor.manager@orbit.example.com', 'vendor_manager', FALSE),
    ('rcpt_orbit_leadership', 'orbit', 'Leadership Team', 'leadership@orbit.example.com', 'leadership', TRUE),

    ('rcpt_pinnacle_transport_head', 'pinnacle', 'Transport Head', 'transport.head@pinnacle.example.com', 'transport_head', TRUE),
    ('rcpt_pinnacle_finance', 'pinnacle', 'Finance Desk', 'finance@pinnacle.example.com', 'finance', FALSE),
    ('rcpt_pinnacle_vendor_manager', 'pinnacle', 'Vendor Manager', 'vendor.manager@pinnacle.example.com', 'vendor_manager', FALSE),
    ('rcpt_pinnacle_leadership', 'pinnacle', 'Leadership Team', 'leadership@pinnacle.example.com', 'leadership', TRUE),

    ('rcpt_vanta_transport_head', 'vanta', 'Transport Head', 'transport.head@vanta.example.com', 'transport_head', TRUE),
    ('rcpt_vanta_finance', 'vanta', 'Finance Desk', 'finance@vanta.example.com', 'finance', FALSE),
    ('rcpt_vanta_vendor_manager', 'vanta', 'Vendor Manager', 'vendor.manager@vanta.example.com', 'vendor_manager', FALSE),
    ('rcpt_vanta_leadership', 'vanta', 'Leadership Team', 'leadership@vanta.example.com', 'leadership', TRUE);
