package com.moveinsync.pulse.report;

import java.time.Instant;
import java.util.List;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;

/** One persisted report_dispatch row, as the API and the history table see
 * it -- the same shape whether it just came back from POST .../dispatch or
 * from GET /api/reports/dispatches. Carries body_html/body_text in full so
 * the history page's expandable row can show "the exact rendered HTML that
 * was stored" without a second request per row. */
@JsonInclude(JsonInclude.Include.NON_NULL)
public record DispatchView(
        @JsonProperty("dispatch_id") String dispatchId,
        @JsonProperty("report_id") String reportId,
        String period,
        List<DispatchRecipientView> recipients,
        String subject,
        @JsonProperty("body_html") String bodyHtml,
        @JsonProperty("body_text") String bodyText,
        String transport,
        String status,
        @JsonProperty("dispatched_at") Instant dispatchedAt,
        @JsonProperty("dispatched_by") String dispatchedBy,
        @JsonProperty("provider_message_id") String providerMessageId,
        @JsonProperty("error_summary") String errorSummary,
        @JsonProperty("content_hash") String contentHash) {
}
