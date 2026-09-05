package com.moveinsync.pulse.action;

import java.time.Instant;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

/** One drafted action: recipient, subject/body and facts_cited/preview are
 * stored as raw JSON text (recipient_json / facts_cited_json / preview_json)
 * -- ActionDraftService is the only place that (de)serializes them, via the
 * shared ObjectMapper, into the typed dto records the API returns. The row
 * itself is never edited after creation except for `status`: an approval
 * with an edited body is stored on ApprovalLog, never written back here --
 * see the design note on that entity. */
@Entity
@Table(name = "action_draft")
public class ActionDraft {

    @Id
    @Column(name = "action_id", nullable = false, updatable = false, length = 64)
    private String actionId;

    @Column(name = "tenant_id", nullable = false, updatable = false, length = 64)
    private String tenantId;

    @Column(name = "insight_id", nullable = false, updatable = false, length = 64)
    private String insightId;

    @Column(name = "type", nullable = false, updatable = false, length = 64)
    private String type;

    @Column(name = "title", nullable = false, updatable = false, length = 500)
    private String title;

    @Column(name = "recipient_json", nullable = false, updatable = false, columnDefinition = "text")
    private String recipientJson;

    @Column(name = "channel", nullable = false, updatable = false, length = 32)
    private String channel;

    @Column(name = "subject", nullable = false, updatable = false, length = 500)
    private String subject;

    @Column(name = "body", nullable = false, updatable = false, columnDefinition = "text")
    private String body;

    @Column(name = "facts_cited_json", nullable = false, updatable = false, columnDefinition = "text")
    private String factsCitedJson;

    @Column(name = "preview_json", nullable = false, updatable = false, columnDefinition = "text")
    private String previewJson;

    @Column(name = "rationale", updatable = false, columnDefinition = "text")
    private String rationale;

    @Column(name = "confidence", nullable = false, updatable = false, length = 16)
    private String confidence;

    @Enumerated(EnumType.STRING)
    @Column(name = "status", nullable = false, length = 32)
    private ActionStatus status;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    protected ActionDraft() {
        // JPA
    }

    public ActionDraft(String actionId, String tenantId, String insightId, String type, String title,
            String recipientJson, String channel, String subject, String body, String factsCitedJson,
            String previewJson, String rationale, String confidence, ActionStatus status, Instant createdAt) {
        this.actionId = actionId;
        this.tenantId = tenantId;
        this.insightId = insightId;
        this.type = type;
        this.title = title;
        this.recipientJson = recipientJson;
        this.channel = channel;
        this.subject = subject;
        this.body = body;
        this.factsCitedJson = factsCitedJson;
        this.previewJson = previewJson;
        this.rationale = rationale;
        this.confidence = confidence;
        this.status = status;
        this.createdAt = createdAt;
    }

    public String actionId() {
        return actionId;
    }

    public String tenantId() {
        return tenantId;
    }

    public String insightId() {
        return insightId;
    }

    public String type() {
        return type;
    }

    public String title() {
        return title;
    }

    public String recipientJson() {
        return recipientJson;
    }

    public String channel() {
        return channel;
    }

    public String subject() {
        return subject;
    }

    public String body() {
        return body;
    }

    public String factsCitedJson() {
        return factsCitedJson;
    }

    public String previewJson() {
        return previewJson;
    }

    public String rationale() {
        return rationale;
    }

    public String confidence() {
        return confidence;
    }

    public ActionStatus status() {
        return status;
    }

    public void setStatus(ActionStatus status) {
        this.status = status;
    }

    public Instant createdAt() {
        return createdAt;
    }
}
