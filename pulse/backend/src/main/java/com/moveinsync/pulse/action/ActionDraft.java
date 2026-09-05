package com.moveinsync.pulse.action;

import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import com.moveinsync.pulse.insight.Insight;

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
import jakarta.persistence.PreUpdate;
import jakarta.persistence.Table;

import org.hibernate.annotations.Filter;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

/** What Pulse proposes a human should do about an insight. Never sent without a matching
 * {@link ApprovalLog} row -- the draft is a proposal, not an action. */
@Entity
@Table(name = "action_draft")
@Filter(name = "tenantFilter", condition = "tenant_id = :tenantId")
public class ActionDraft {

    /** Every value {@code status} is allowed to take; mirrors ck_action_draft_status in V2. */
    public static final String STATUS_DRAFT = "draft";
    public static final String STATUS_APPROVED = "approved";
    public static final String STATUS_REJECTED = "rejected";
    public static final String STATUS_SENT = "sent";
    public static final String STATUS_FAILED = "failed";

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "tenant_id", nullable = false, updatable = false, insertable = false, length = 64)
    private String tenantId;

    @Column(name = "action_id", nullable = false, updatable = false, length = 64)
    private String actionId;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumns({
            @JoinColumn(name = "insight_id", referencedColumnName = "insight_id", nullable = false),
            @JoinColumn(name = "tenant_id", referencedColumnName = "tenant_id", nullable = false)
    })
    private Insight insight;

    @Column(name = "action_type", nullable = false, length = 32)
    private String actionType;

    @Column(nullable = false, length = 512)
    private String title;

    @Column(nullable = false, columnDefinition = "text")
    private String body;

    @Column(nullable = false, columnDefinition = "text")
    private String rationale;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "recipient", nullable = false, columnDefinition = "jsonb")
    private Map<String, Object> recipient = new LinkedHashMap<>();

    /** Every number the draft quotes, tied back to the insight field it came from. This is
     * what makes a draft auditable rather than merely generated. */
    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "facts_cited", nullable = false, columnDefinition = "jsonb")
    private List<FactCitation> factsCited = new ArrayList<>();

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "preview", nullable = false, columnDefinition = "jsonb")
    private Map<String, Object> preview = new LinkedHashMap<>();

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "params", nullable = false, columnDefinition = "jsonb")
    private Map<String, Object> params = new LinkedHashMap<>();

    @Column(nullable = false, length = 16)
    private String status = STATUS_DRAFT;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    protected ActionDraft() {
    }

    public ActionDraft(Insight insight, String actionId, String actionType, String title, String body, String rationale) {
        this.insight = insight;
        this.actionId = actionId;
        this.actionType = actionType;
        this.title = title;
        this.body = body;
        this.rationale = rationale;
    }

    /** One quoted number and where it came from. */
    public record FactCitation(String field, String label, Object value, String unit) {
    }

    @PrePersist
    void onInsert() {
        Instant now = Instant.now();
        createdAt = createdAt == null ? now : createdAt;
        updatedAt = now;
        // The association owns the tenant_id column, so the mirror field would otherwise
        // stay null on a freshly persisted instance until it is reloaded in a new session.
        syncTenantId();
    }

    @PreUpdate
    void onUpdate() {
        updatedAt = Instant.now();
        syncTenantId();
    }

    private void syncTenantId() {
        if (tenantId == null && insight != null) {
            tenantId = insight.getTenantId();
        }
    }

    public Long getId() {
        return id;
    }

    public String getTenantId() {
        return tenantId;
    }

    public String getActionId() {
        return actionId;
    }

    public Insight getInsight() {
        return insight;
    }

    public String getActionType() {
        return actionType;
    }

    public void setActionType(String actionType) {
        this.actionType = actionType;
    }

    public String getTitle() {
        return title;
    }

    public void setTitle(String title) {
        this.title = title;
    }

    public String getBody() {
        return body;
    }

    public void setBody(String body) {
        this.body = body;
    }

    public String getRationale() {
        return rationale;
    }

    public void setRationale(String rationale) {
        this.rationale = rationale;
    }

    public Map<String, Object> getRecipient() {
        return recipient;
    }

    public void setRecipient(Map<String, Object> recipient) {
        this.recipient = recipient == null ? new LinkedHashMap<>() : recipient;
    }

    public List<FactCitation> getFactsCited() {
        return factsCited;
    }

    public void setFactsCited(List<FactCitation> factsCited) {
        this.factsCited = factsCited == null ? new ArrayList<>() : factsCited;
    }

    public Map<String, Object> getPreview() {
        return preview;
    }

    public void setPreview(Map<String, Object> preview) {
        this.preview = preview == null ? new LinkedHashMap<>() : preview;
    }

    public Map<String, Object> getParams() {
        return params;
    }

    public void setParams(Map<String, Object> params) {
        this.params = params == null ? new LinkedHashMap<>() : params;
    }

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }
}
