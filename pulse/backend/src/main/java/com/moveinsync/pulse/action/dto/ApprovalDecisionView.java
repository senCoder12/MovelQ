package com.moveinsync.pulse.action.dto;

import java.time.Instant;

import com.fasterxml.jackson.annotation.JsonProperty;

/** The latest ApprovalLog row for an action, as seen by the API -- present
 * once a human has approved or rejected, null on a still-DRAFTED action.
 * Carrying the edit here (rather than only on ActionDraft) is what makes
 * the diff between what the agent proposed and what the human sent visible
 * in the audit table, per the design note on ApprovalLog. */
public record ApprovalDecisionView(
        String decision,
        @JsonProperty("decided_by") String decidedBy,
        @JsonProperty("decided_at") Instant decidedAt,
        @JsonProperty("edited_subject") String editedSubject,
        @JsonProperty("edited_body") String editedBody,
        String note) {
}
