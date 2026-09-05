package com.moveinsync.pulse.alert.dto;

import java.time.Instant;
import java.util.List;

import com.fasterxml.jackson.annotation.JsonProperty;

/** GET /api/alerts/{id}/delivery -- the rendered notification exactly as it
 * would have been sent, which is the whole audit artifact for an alert. */
public record AlertDeliveryView(
        @JsonProperty("delivery_id") String deliveryId,
        @JsonProperty("alert_id") String alertId,
        String channel,
        @JsonProperty("rendered_subject") String renderedSubject,
        @JsonProperty("rendered_body") String renderedBody,
        @JsonProperty("would_send_to") List<PersonaRecipient> wouldSendTo,
        @JsonProperty("created_at") Instant createdAt,
        @JsonProperty("delivery_status") String deliveryStatus) {
}
