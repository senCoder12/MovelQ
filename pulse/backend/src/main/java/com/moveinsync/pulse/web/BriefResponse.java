package com.moveinsync.pulse.web;

import java.time.Instant;
import java.util.List;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.moveinsync.pulse.agent.dto.InsightPacket;

/** Matches contracts/openapi.yaml components.schemas.BriefResponse. */
public record BriefResponse(
        String persona,
        @JsonProperty("generated_at") Instant generatedAt,
        List<InsightPacket> insights) {
}
