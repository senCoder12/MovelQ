package com.moveinsync.pulse.report;

import java.util.List;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.NotEmpty;

/** Body of POST /api/reports/leadership/dispatch. `recipientIds` must be
 * non-empty -- ReportDispatchService rejects an empty list rather than
 * silently recording a dispatch to nobody. `subject` is optional: the send
 * drawer's Step 2 shows the rendered subject as editable text, and if the
 * operator actually changed it this carries that edit through to what is
 * stored and sent -- otherwise the subject a dispatch used would silently
 * differ from the one the operator saw and approved, which is exactly the
 * kind of drift this whole design exists to prevent. `body_html`/`body_text`
 * are never overridable the same way: only the subject is editable in the
 * UI, so only the subject can differ from the render. */
public record DispatchApiRequest(
        String period,
        @NotEmpty @JsonProperty("recipient_ids") List<String> recipientIds,
        String subject,
        String note) {
}
