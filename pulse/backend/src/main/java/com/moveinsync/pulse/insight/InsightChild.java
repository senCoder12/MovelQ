package com.moveinsync.pulse.insight;

import java.time.Instant;

import jakarta.persistence.Column;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.JoinColumns;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.MappedSuperclass;
import jakarta.persistence.PrePersist;

/**
 * Shared mapping for insight's child rows.
 *
 * <p>The association joins on <em>both</em> {@code insight_id} and {@code tenant_id}, matching
 * the composite foreign key in V1. That is the point: a child row cannot be persisted against
 * an insight belonging to another tenant, because there is no such parent to join to. The
 * {@code tenantId} field is a read-only mirror of the column the association writes.
 */
@MappedSuperclass
public abstract class InsightChild {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumns({
            @JoinColumn(name = "insight_id", referencedColumnName = "insight_id", nullable = false),
            @JoinColumn(name = "tenant_id", referencedColumnName = "tenant_id", nullable = false)
    })
    private Insight insight;

    @Column(name = "tenant_id", insertable = false, updatable = false, length = 64)
    private String tenantId;

    @Column(name = "ordinal", nullable = false)
    private int ordinal;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @PrePersist
    void onInsert() {
        if (createdAt == null) {
            createdAt = Instant.now();
        }
        // The association writes tenant_id; without this the mirror field stays null on a
        // freshly persisted child until it is reloaded in a new session.
        if (tenantId == null && insight != null) {
            tenantId = insight.getTenantId();
        }
    }

    public Long getId() {
        return id;
    }

    public Insight getInsight() {
        return insight;
    }

    void setInsight(Insight insight) {
        this.insight = insight;
    }

    public String getTenantId() {
        return tenantId;
    }

    public int getOrdinal() {
        return ordinal;
    }

    void setOrdinal(int ordinal) {
        this.ordinal = ordinal;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }
}
