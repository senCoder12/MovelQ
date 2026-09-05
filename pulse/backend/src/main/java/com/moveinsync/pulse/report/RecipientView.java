package com.moveinsync.pulse.report;

import com.fasterxml.jackson.annotation.JsonProperty;

/** One row of GET /api/reports/leadership/recipients. */
public record RecipientView(
        @JsonProperty("recipient_id") String recipientId,
        String name,
        String email,
        String role,
        @JsonProperty("is_default") boolean isDefault) {

    public static RecipientView of(ReportRecipient recipient) {
        return new RecipientView(recipient.recipientId(), recipient.name(), recipient.email(), recipient.role(),
                recipient.isDefault());
    }
}
