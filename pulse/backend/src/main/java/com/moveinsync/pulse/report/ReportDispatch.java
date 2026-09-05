package com.moveinsync.pulse.report;

import java.time.Instant;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

/** One immutable send record. Every rendered field (subject/body_html/
 * body_text) and the recipient list (recipients_json) are a snapshot at
 * dispatch time -- ReportDispatchService never re-renders from a stored
 * dispatch, and nothing here is ever updated after insert (not even
 * `status`: a FAILED row stays FAILED, a retry is a new dispatch, since
 * there is no retry path today anyway). `recipientsJson` is a JSON array of
 * DispatchRecipient, stored as text -- H2 has no JSONB type, unlike the
 * Postgres target in db/02_core_model.sql. */
@Entity
@Table(name = "report_dispatch")
public class ReportDispatch {

    @Id
    @Column(name = "dispatch_id", nullable = false, updatable = false, length = 64)
    private String dispatchId;

    @Column(name = "tenant_id", nullable = false, updatable = false, length = 64)
    private String tenantId;

    @Column(name = "report_id", nullable = false, updatable = false, length = 64)
    private String reportId;

    @Column(name = "period", nullable = false, updatable = false, length = 16)
    private String period;

    @Column(name = "recipients_json", nullable = false, updatable = false, columnDefinition = "text")
    private String recipientsJson;

    @Column(name = "subject", nullable = false, updatable = false, length = 500)
    private String subject;

    @Column(name = "body_html", nullable = false, updatable = false, columnDefinition = "text")
    private String bodyHtml;

    @Column(name = "body_text", nullable = false, updatable = false, columnDefinition = "text")
    private String bodyText;

    @Column(name = "transport", nullable = false, updatable = false, length = 16)
    private String transport;

    @Column(name = "status", nullable = false, updatable = false, length = 16)
    private String status;

    @Column(name = "dispatched_at", nullable = false, updatable = false)
    private Instant dispatchedAt;

    @Column(name = "dispatched_by", nullable = false, updatable = false, length = 128)
    private String dispatchedBy;

    @Column(name = "provider_message_id", updatable = false, length = 320)
    private String providerMessageId;

    @Column(name = "error_summary", updatable = false, length = 2000)
    private String errorSummary;

    @Column(name = "content_hash", nullable = false, updatable = false, length = 64)
    private String contentHash;

    protected ReportDispatch() {
        // JPA
    }

    public ReportDispatch(String dispatchId, String tenantId, String reportId, String period, String recipientsJson,
            String subject, String bodyHtml, String bodyText, String transport, String status, Instant dispatchedAt,
            String dispatchedBy, String providerMessageId, String errorSummary, String contentHash) {
        this.dispatchId = dispatchId;
        this.tenantId = tenantId;
        this.reportId = reportId;
        this.period = period;
        this.recipientsJson = recipientsJson;
        this.subject = subject;
        this.bodyHtml = bodyHtml;
        this.bodyText = bodyText;
        this.transport = transport;
        this.status = status;
        this.dispatchedAt = dispatchedAt;
        this.dispatchedBy = dispatchedBy;
        this.providerMessageId = providerMessageId;
        this.errorSummary = errorSummary;
        this.contentHash = contentHash;
    }

    public String dispatchId() {
        return dispatchId;
    }

    public String tenantId() {
        return tenantId;
    }

    public String reportId() {
        return reportId;
    }

    public String period() {
        return period;
    }

    public String recipientsJson() {
        return recipientsJson;
    }

    public String subject() {
        return subject;
    }

    public String bodyHtml() {
        return bodyHtml;
    }

    public String bodyText() {
        return bodyText;
    }

    public String transport() {
        return transport;
    }

    public String status() {
        return status;
    }

    public Instant dispatchedAt() {
        return dispatchedAt;
    }

    public String dispatchedBy() {
        return dispatchedBy;
    }

    public String providerMessageId() {
        return providerMessageId;
    }

    public String errorSummary() {
        return errorSummary;
    }

    public String contentHash() {
        return contentHash;
    }
}
