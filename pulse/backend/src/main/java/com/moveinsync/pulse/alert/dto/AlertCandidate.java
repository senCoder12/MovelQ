package com.moveinsync.pulse.alert.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

/** Matches agent/app/detect/alert_router.py's evaluate() candidate shape --
 * a rule matched an insight; cooldown and suppression have not been applied
 * yet, that's AlertScanService's job on the Java side. */
public record AlertCandidate(
        @JsonProperty("rule_id") String ruleId,
        @JsonProperty("insight_id") String insightId,
        String persona,
        String urgency,
        String channel,
        @JsonProperty("entity_dim") String entityDim,
        @JsonProperty("entity_value") String entityValue,
        @JsonProperty("cooldown_hours") int cooldownHours) {
}
