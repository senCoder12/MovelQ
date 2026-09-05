package com.moveinsync.pulse.action;

import java.time.Instant;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.JoinColumns;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.PrePersist;
import jakarta.persistence.Table;

import org.hibernate.annotations.Filter;

/** Who decided what about an action draft, and when they decided it. Append-only. */
@Entity
@Table(name = "approval_log")
@Filter(name = "tenantFilter", condition = "tenant_id = :tenantId")
public class ApprovalLog {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "tenant_id", nullable = false, updatable = false, insertable = false, length = 64)
    private String tenantId;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumns({
            @JoinColumn(name = "action_draft_id", referencedColumnName = "id", nullable = false),
            @JoinColumn(name = "tenant_id", referencedColumnName = "tenant_id", nullable = false)
    })
    private ActionDraft actionDraft;

    @Column(nullable = false, length = 16)
    private String decision;

    @Column(nullable = false, length = 256)
    private String actor;

    @Column(columnDefinition = "text")
    private String note;

    /** When the human decided, not when we got round to writing the row. */
    @Column(name = "decided_at", nullable = false)
    private Instant decidedAt;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    protected ApprovalLog() {
    }

    public ApprovalLog(ActionDraft actionDraft, String decision, String actor, String note, Instant decidedAt) {
        this.actionDraft = actionDraft;
        this.decision = decision;
        this.actor = actor;
        this.note = note;
        this.decidedAt = decidedAt == null ? Instant.now() : decidedAt;
    }

    @PrePersist
    void onInsert() {
        Instant now = Instant.now();
        createdAt = createdAt == null ? now : createdAt;
        if (decidedAt == null) {
            decidedAt = now;
        }
        // See ActionDraft.syncTenantId: the association writes the column, this keeps the
        // in-memory mirror honest before the entity is reloaded.
        if (tenantId == null && actionDraft != null) {
            tenantId = actionDraft.getTenantId();
        }
    }

    public Long getId() {
        return id;
    }

    public String getTenantId() {
        return tenantId;
    }

    public ActionDraft getActionDraft() {
        return actionDraft;
    }

    public String getDecision() {
        return decision;
    }

    public String getActor() {
        return actor;
    }

    public String getNote() {
        return note;
    }

    public Instant getDecidedAt() {
        return decidedAt;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }
}
