package com.moveinsync.pulse.alert;

import java.time.Instant;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

/** A mute: no (tenant, rule_id, entity) match fires again until
 * suppressed_until. Rows are append-only, same audit philosophy as
 * ApprovalLog -- muting twice just adds a second row; whichever row's
 * suppressed_until is furthest in the future is what actually holds. */
@Entity
@Table(name = "alert_suppression")
public class AlertSuppression {

    @Id
    @Column(name = "suppression_id", nullable = false, updatable = false, length = 64)
    private String suppressionId;

    @Column(name = "tenant_id", nullable = false, updatable = false, length = 64)
    private String tenantId;

    @Column(name = "rule_id", nullable = false, updatable = false, length = 64)
    private String ruleId;

    @Column(name = "entity_dim", nullable = false, updatable = false, length = 64)
    private String entityDim;

    @Column(name = "entity_value", nullable = false, updatable = false, length = 200)
    private String entityValue;

    @Column(name = "suppressed_until", nullable = false, updatable = false)
    private Instant suppressedUntil;

    @Column(name = "reason", updatable = false, length = 2000)
    private String reason;

    @Column(name = "muted_by", nullable = false, updatable = false, length = 128)
    private String mutedBy;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    protected AlertSuppression() {
        // JPA
    }

    public AlertSuppression(String suppressionId, String tenantId, String ruleId, String entityDim,
            String entityValue, Instant suppressedUntil, String reason, String mutedBy, Instant createdAt) {
        this.suppressionId = suppressionId;
        this.tenantId = tenantId;
        this.ruleId = ruleId;
        this.entityDim = entityDim;
        this.entityValue = entityValue;
        this.suppressedUntil = suppressedUntil;
        this.reason = reason;
        this.mutedBy = mutedBy;
        this.createdAt = createdAt;
    }

    public String suppressionId() {
        return suppressionId;
    }

    public String tenantId() {
        return tenantId;
    }

    public String ruleId() {
        return ruleId;
    }

    public String entityDim() {
        return entityDim;
    }

    public String entityValue() {
        return entityValue;
    }

    public Instant suppressedUntil() {
        return suppressedUntil;
    }

    public String reason() {
        return reason;
    }

    public String mutedBy() {
        return mutedBy;
    }

    public Instant createdAt() {
        return createdAt;
    }
}
