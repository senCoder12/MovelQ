package com.moveinsync.pulse.action;

import java.time.Instant;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

/** One human decision on one ActionDraft. This is the system log the design
 * calls for: nothing sends autonomously, and this row is the only durable
 * effect an approval has. `editedSubject`/`editedBody` hold the human's edit
 * when there was one -- the ActionDraft row is never overwritten, so this is
 * the only place the diff between what the agent proposed and what was
 * actually approved is recorded. */
@Entity
@Table(name = "approval_log")
public class ApprovalLog {

    @Id
    @Column(name = "log_id", nullable = false, updatable = false, length = 64)
    private String logId;

    @Column(name = "tenant_id", nullable = false, updatable = false, length = 64)
    private String tenantId;

    @Column(name = "action_id", nullable = false, updatable = false, length = 64)
    private String actionId;

    @Column(name = "decision", nullable = false, updatable = false, length = 32)
    private String decision;

    @Column(name = "decided_by", nullable = false, updatable = false, length = 128)
    private String decidedBy;

    @Column(name = "decided_at", nullable = false, updatable = false)
    private Instant decidedAt;

    @Column(name = "edited_subject", updatable = false, length = 500)
    private String editedSubject;

    @Column(name = "edited_body", updatable = false, columnDefinition = "text")
    private String editedBody;

    @Column(name = "note", updatable = false, length = 2000)
    private String note;

    protected ApprovalLog() {
        // JPA
    }

    public ApprovalLog(String logId, String tenantId, String actionId, String decision, String decidedBy,
            Instant decidedAt, String editedSubject, String editedBody, String note) {
        this.logId = logId;
        this.tenantId = tenantId;
        this.actionId = actionId;
        this.decision = decision;
        this.decidedBy = decidedBy;
        this.decidedAt = decidedAt;
        this.editedSubject = editedSubject;
        this.editedBody = editedBody;
        this.note = note;
    }

    public String logId() {
        return logId;
    }

    public String tenantId() {
        return tenantId;
    }

    public String actionId() {
        return actionId;
    }

    public String decision() {
        return decision;
    }

    public String decidedBy() {
        return decidedBy;
    }

    public Instant decidedAt() {
        return decidedAt;
    }

    public String editedSubject() {
        return editedSubject;
    }

    public String editedBody() {
        return editedBody;
    }

    public String note() {
        return note;
    }
}
