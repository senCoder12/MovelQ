package com.moveinsync.pulse.agent.dto;

import java.util.List;

import com.fasterxml.jackson.annotation.JsonProperty;

/** Matches contracts/insight.schema.json $defs.narrative. */
public record Narrative(
        String headline,
        String body,
        @JsonProperty("recommended_actions") List<RecommendedAction> recommendedActions) {
}
