package com.moveinsync.pulse.report;

import com.fasterxml.jackson.annotation.JsonProperty;

public record PreviewResponse(
        String subject,
        @JsonProperty("body_html") String bodyHtml,
        @JsonProperty("body_text") String bodyText) {
}
