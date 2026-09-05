package com.moveinsync.pulse.report;

import java.util.List;

import com.fasterxml.jackson.annotation.JsonProperty;

/** Body of POST /api/reports/leadership/preview. Renders but never
 * persists -- unlike DispatchApiRequest, there is no `note` here, since a
 * preview never reaches an ApprovalLog-equivalent record. */
public record PreviewRequest(String period, @JsonProperty("recipient_ids") List<String> recipientIds) {
}
