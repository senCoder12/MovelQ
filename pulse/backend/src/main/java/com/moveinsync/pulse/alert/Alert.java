package com.moveinsync.pulse.alert;

import java.time.Instant;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

/** One fired rule against one insight, at one point in time. `repeatOf` is
 * set only on the single, once-only re-raise of an unacknowledged
 * immediate alert (see AlertScanService's repeat pass) -- it is never set
 * on an ordinary fresh fire, and nothing here ever repeats a repeat. */
@Entity
@Table(name = "alert")
public class Alert {

    @Id
    @Column(name = "alert_id", nullable = false, updatable = false, length = 64)
    private String alertId;

    @Column(name = "tenant_id", nullable = false, updatable = false, length = 64)
    private String tenantId;

    @Column(name = "rule_id", nullable = false, updatable = false, length = 64)
    private String ruleId;

    @Column(name = "insight_id", nullable = false, updatable = false, length = 64)
    private String insightId;

    @Column(name = "persona", nullable = false, updatable = false, length = 16)
    private String persona;

    @Column(name = "urgency", nullable = false, updatable = false, length = 16)
    private String urgency;

    @Column(name = "channel", nullable = false, updatable = false, length = 24)
    private String channel;

    @Column(name = "entity_dim", nullable = false, updatable = false, length = 64)
    private String entityDim;

    @Column(name = "entity_value", nullable = false, updatable = false, length = 200)
    private String entityValue;

    @Column(name = "fired_at", nullable = false, updatable = false)
    private Instant firedAt;

    @Column(name = "scan_run_id", nullable = false, updatable = false, length = 64)
    private String scanRunId;

    @Enumerated(EnumType.STRING)
    @Column(name = "status", nullable = false, length = 16)
    private AlertStatus status;

    @Column(name = "acknowledged_at")
    private Instant acknowledgedAt;

    @Column(name = "acknowledged_by", length = 128)
    private String acknowledgedBy;

    @Column(name = "acknowledged_note", length = 2000)
    private String acknowledgedNote;

    @Column(name = "repeat_of", updatable = false, length = 64)
    private String repeatOf;

    protected Alert() {
        // JPA
    }

    public Alert(String alertId, String tenantId, String ruleId, String insightId, String persona, String urgency,
            String channel, String entityDim, String entityValue, Instant firedAt, String scanRunId,
            AlertStatus status, String repeatOf) {
        this.alertId = alertId;
        this.tenantId = tenantId;
        this.ruleId = ruleId;
        this.insightId = insightId;
        this.persona = persona;
        this.urgency = urgency;
        this.channel = channel;
        this.entityDim = entityDim;
        this.entityValue = entityValue;
        this.firedAt = firedAt;
        this.scanRunId = scanRunId;
        this.status = status;
        this.repeatOf = repeatOf;
    }

    public void acknowledge(Instant when, String by, String note) {
        this.status = AlertStatus.ACKNOWLEDGED;
        this.acknowledgedAt = when;
        this.acknowledgedBy = by;
        this.acknowledgedNote = note;
    }

    public void mute() {
        this.status = AlertStatus.MUTED;
    }

    public String alertId() {
        return alertId;
    }

    public String tenantId() {
        return tenantId;
    }

    public String ruleId() {
        return ruleId;
    }

    public String insightId() {
        return insightId;
    }

    public String persona() {
        return persona;
    }

    public String urgency() {
        return urgency;
    }

    public String channel() {
        return channel;
    }

    public String entityDim() {
        return entityDim;
    }

    public String entityValue() {
        return entityValue;
    }

    public Instant firedAt() {
        return firedAt;
    }

    public String scanRunId() {
        return scanRunId;
    }

    public AlertStatus status() {
        return status;
    }

    public Instant acknowledgedAt() {
        return acknowledgedAt;
    }

    public String acknowledgedBy() {
        return acknowledgedBy;
    }

    public String acknowledgedNote() {
        return acknowledgedNote;
    }

    public String repeatOf() {
        return repeatOf;
    }
}
