package com.moveinsync.pulse.report;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.moveinsync.pulse.report.dispatch.DispatchRecipient;

/** Mirrors report.dispatch.DispatchRecipient for the API/JSON-column layer --
 * kept as a separate type rather than reusing DispatchRecipient directly so
 * the transport-facing record and the wire/storage shape can drift
 * independently if either ever needs to. */
public record DispatchRecipientView(
        @JsonProperty("recipient_id") String recipientId, String name, String email, String role) {

    public static DispatchRecipientView of(ReportRecipient recipient) {
        return new DispatchRecipientView(recipient.recipientId(), recipient.name(), recipient.email(), recipient.role());
    }

    public DispatchRecipient toTransportRecipient() {
        return new DispatchRecipient(recipientId, name, email, role);
    }
}
