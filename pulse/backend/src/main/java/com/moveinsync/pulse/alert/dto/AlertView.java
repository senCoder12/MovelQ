package com.moveinsync.pulse.alert.dto;

import java.time.Instant;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.moveinsync.pulse.alert.Alert;
import com.moveinsync.pulse.alert.AlertStatus;

/** One row of GET /api/alerts, and what an insight card's "alerted HH:mm"
 * chip is built from. `repeat_of` non-null is the "re-raised, unacknowledged
 * 24h" chip -- the frontend derives that from status still being NEW on a
 * row that has one, rather than a separate boolean the server would have to
 * keep in sync. */
@JsonInclude(JsonInclude.Include.NON_NULL)
public record AlertView(
        @JsonProperty("alert_id") String alertId,
        @JsonProperty("rule_id") String ruleId,
        @JsonProperty("insight_id") String insightId,
        String persona,
        String urgency,
        String channel,
        @JsonProperty("entity_dim") String entityDim,
        @JsonProperty("entity_value") String entityValue,
        @JsonProperty("fired_at") Instant firedAt,
        @JsonProperty("scan_run_id") String scanRunId,
        AlertStatus status,
        @JsonProperty("acknowledged_at") Instant acknowledgedAt,
        @JsonProperty("acknowledged_by") String acknowledgedBy,
        @JsonProperty("acknowledged_note") String acknowledgedNote,
        @JsonProperty("repeat_of") String repeatOf) {

    public static AlertView of(Alert alert) {
        return new AlertView(alert.alertId(), alert.ruleId(), alert.insightId(), alert.persona(), alert.urgency(),
                alert.channel(), alert.entityDim(), alert.entityValue(), alert.firedAt(), alert.scanRunId(),
                alert.status(), alert.acknowledgedAt(), alert.acknowledgedBy(), alert.acknowledgedNote(),
                alert.repeatOf());
    }
}
