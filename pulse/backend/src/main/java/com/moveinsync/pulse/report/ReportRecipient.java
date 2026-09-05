package com.moveinsync.pulse.report;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

/** A seeded stand-in for a real user table, which this app deliberately does
 * not have: `role` is a plain string ("transport_head", "finance",
 * "vendor_manager", "leadership") rather than a Java enum so the seed data
 * in V3__report_recipient.sql is the only place new roles are ever defined.
 * Rows are read-only from the API's point of view -- nothing here ever
 * creates, edits or deletes a recipient at runtime. */
@Entity
@Table(name = "report_recipient")
public class ReportRecipient {

    @Id
    @Column(name = "recipient_id", nullable = false, updatable = false, length = 64)
    private String recipientId;

    @Column(name = "tenant_id", nullable = false, updatable = false, length = 64)
    private String tenantId;

    @Column(name = "name", nullable = false, updatable = false, length = 200)
    private String name;

    @Column(name = "email", nullable = false, updatable = false, length = 320)
    private String email;

    @Column(name = "role", nullable = false, updatable = false, length = 32)
    private String role;

    @Column(name = "is_default", nullable = false, updatable = false)
    private boolean isDefault;

    protected ReportRecipient() {
        // JPA
    }

    public ReportRecipient(String recipientId, String tenantId, String name, String email, String role,
            boolean isDefault) {
        this.recipientId = recipientId;
        this.tenantId = tenantId;
        this.name = name;
        this.email = email;
        this.role = role;
        this.isDefault = isDefault;
    }

    public String recipientId() {
        return recipientId;
    }

    public String tenantId() {
        return tenantId;
    }

    public String name() {
        return name;
    }

    public String email() {
        return email;
    }

    public String role() {
        return role;
    }

    public boolean isDefault() {
        return isDefault;
    }
}
