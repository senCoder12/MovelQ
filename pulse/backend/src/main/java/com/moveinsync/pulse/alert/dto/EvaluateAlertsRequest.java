package com.moveinsync.pulse.alert.dto;

import java.util.List;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.moveinsync.pulse.agent.dto.InsightPacket;

/** Body posted to the agent's POST /internal/evaluate-alerts. Every
 * (entity_dim, entity_id) pair in `knownEntities` is one Java has already
 * seen fire some alert before -- the agent keeps no history of its own, so
 * it cannot answer "is this entity new" without being told. */
public record EvaluateAlertsRequest(
        List<InsightPacket> insights,
        @JsonProperty("known_entities") List<List<String>> knownEntities) {
}
