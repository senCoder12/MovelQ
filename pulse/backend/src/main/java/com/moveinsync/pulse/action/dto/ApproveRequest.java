package com.moveinsync.pulse.action.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

/** Body of POST /api/actions/{id}/approve. Both fields are optional --
 * plain approval sends neither. When `editedSubject` or `editedBody` is
 * present the draft's status becomes EDITED_APPROVED and the edit is stored
 * on the ApprovalLog row; the original ActionDraft is never overwritten,
 * so the diff between what the agent proposed and what the human sent
 * stays visible in the audit trail. */
public record ApproveRequest(
        String note,
        @JsonProperty("edited_subject") String editedSubject,
        @JsonProperty("edited_body") String editedBody) {

    public static ApproveRequest empty() {
        return new ApproveRequest(null, null, null);
    }
}
