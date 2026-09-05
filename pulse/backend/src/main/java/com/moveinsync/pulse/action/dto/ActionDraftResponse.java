package com.moveinsync.pulse.action.dto;

import java.time.Instant;
import java.util.List;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.moveinsync.pulse.action.ActionStatus;

/** What GET/POST /api/(insights/{id}/actions|actions) return: the drafted
 * action plus, once decided, the ApprovalLog that decided it. `decision` is
 * the field the actions-audit table reads to show an edit alongside the
 * original draft without ever mutating that draft. */
@JsonInclude(JsonInclude.Include.NON_NULL)
public record ActionDraftResponse(
        @JsonProperty("action_id") String actionId,
        @JsonProperty("insight_id") String insightId,
        String type,
        String title,
        Recipient recipient,
        String channel,
        String subject,
        String body,
        @JsonProperty("facts_cited") List<FactCited> factsCited,
        Preview preview,
        String rationale,
        String confidence,
        ActionStatus status,
        @JsonProperty("created_at") Instant createdAt,
        ApprovalDecisionView decision) {
}
